"""MCP Client for connecting to and executing tools on the streamable-http MCP server."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dataquery.config import get_settings

logger = logging.getLogger(__name__)

try:
    from fastmcp import Client as FastMCPClient
    HAS_FASTMCP_CLIENT = True
except ImportError:
    FastMCPClient = None
    HAS_FASTMCP_CLIENT = False


class MCPClient:
    """Client for calling tools on the FastMCP streamable-http server."""

    def __init__(self, server_url: str | None = None):
        settings = get_settings()
        mcp_host = os.getenv("MCP_HOST", "localhost")
        mcp_port = os.getenv("MCP_PORT", "8001")
        mcp_path = os.getenv("MCP_PATH", "/mcp")

        if server_url:
            self.server_url = server_url.rstrip("/")
        elif os.getenv("MCP_SERVER_URL"):
            self.server_url = os.getenv("MCP_SERVER_URL").rstrip("/")
        elif getattr(settings, "MCP_SERVER_URL", None):
            self.server_url = settings.MCP_SERVER_URL.rstrip("/")
        else:
            self.server_url = f"http://{mcp_host}:{mcp_port}{mcp_path}".rstrip("/")

        self.timeout = float(os.getenv("MCP_TIMEOUT_SECONDS", "30.0"))

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke an MCP tool over the streamable-http transport.

        Uses native FastMCP Client for full session initialization and protocol compliance.
        If the remote server is unreachable, falls back gracefully to in-process tool dispatch.
        """
        args = arguments or {}

        if HAS_FASTMCP_CLIENT:
            try:
                logger.info(f"[MCPClient] Calling tool '{name}' on MCP server at {self.server_url}...")
                async with FastMCPClient(self.server_url) as client:
                    call_res = await client.call_tool(name, args)

                    raw_val = getattr(call_res, "data", None)
                    if raw_val is None and hasattr(call_res, "content") and call_res.content:
                        text_chunks = [c.text for c in call_res.content if hasattr(c, "text")]
                        raw_val = "".join(text_chunks)
                    if raw_val is None:
                        raw_val = getattr(call_res, "structured_content", {})

                    if isinstance(raw_val, str):
                        try:
                            return json.loads(raw_val)
                        except Exception:
                            return {"result": raw_val}
                    elif isinstance(raw_val, (dict, list)):
                        return raw_val
                    return {"result": raw_val}
            except Exception as exc:
                logger.warning(
                    f"[MCPClient] Remote MCP server at {self.server_url} error ({exc}). "
                    f"Falling back to in-process tool dispatch for '{name}'."
                )
                return await self._dispatch_local(name, args)

        return await self._dispatch_local(name, args)

    def call_tool_sync(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Synchronous version of call_tool for sync contexts."""
        args = arguments or {}
        if HAS_FASTMCP_CLIENT:
            try:
                import anyio
                return anyio.from_thread.run(self.call_tool, name, args)
            except Exception:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    res = loop.run_until_complete(self.call_tool(name, args))
                    loop.close()
                    return res
                except Exception:
                    pass
        return self._dispatch_local_sync(name, args)

    async def _dispatch_local(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Direct in-process fallback dispatch for high availability."""
        return self._dispatch_local_sync(name, arguments)

    def _dispatch_local_sync(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Direct in-process fallback dispatch."""
        from dataquery.mcp.tools import (
            execute_sql_impl,
            explain_sql_impl,
            get_database_schema_impl,
            get_table_sample_impl,
            search_schema_impl,
            validate_sql_impl,
        )

        if name == "search_schema":
            return search_schema_impl(
                question=arguments.get("question", ""),
                top_k=arguments.get("top_k", 4),
            )
        elif name == "get_database_schema":
            return get_database_schema_impl(
                table_names=arguments.get("table_names"),
            )
        elif name == "validate_sql":
            return validate_sql_impl(
                sql=arguments.get("sql", ""),
            )
        elif name == "execute_sql":
            return execute_sql_impl(
                sql=arguments.get("sql", ""),
            )
        elif name == "get_table_sample":
            return get_table_sample_impl(
                table_name=arguments.get("table_name", ""),
                limit=arguments.get("limit", 5),
            )
        elif name == "explain_sql":
            return explain_sql_impl(
                sql=arguments.get("sql", ""),
            )
        else:
            raise ValueError(f"Unknown MCP tool: {name}")


_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Return shared MCPClient instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
