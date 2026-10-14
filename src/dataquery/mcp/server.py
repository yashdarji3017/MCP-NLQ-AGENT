"""Dedicated MCP (Model Context Protocol) Server for Database and Schema Tools.

Runs with streamable-http transport for remote / web client integrations,
registering all database query, schema exploration, and validation tools
via the unified MCPToolRegistry.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any
from dotenv import load_dotenv
from starlette.responses import PlainTextResponse

load_dotenv()

from dataquery.config import get_settings
from dataquery.database.connection import test_db_connection
from dataquery.database.schema_definitions import introspect_database_schema
from dataquery.mcp.tools import MCPToolRegistry

logger = logging.getLogger(__name__)

try:
    from fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        HAS_MCP = True
    except ImportError:
        HAS_MCP = False
        FastMCP = Any


def create_mcp_server() -> FastMCP | None:
    """Create and configure the FastMCP database tool server with lifespan and tools."""
    if not HAS_MCP:
        logger.warning("FastMCP package is not installed. Server requires 'fastmcp' or 'mcp>=1.1.2'.")
        return None

    settings = get_settings()

    mcp_server_name = os.getenv("MCP_SERVER_NAME", settings.MCP_SERVER_NAME)

    @asynccontextmanager
    async def lifespan(app: FastMCP):
        """Warm up database connectivity and dynamically introspect schema on startup."""
        logger.info("[MCP] Lifespan startup: checking database connectivity...")
        is_connected = test_db_connection()
        if is_connected:
            logger.info("[MCP] Database connectivity confirmed. Introspecting schema...")
            try:
                tables = introspect_database_schema(force_refresh=True)
                logger.info(f"[MCP] Successfully introspected {len(tables)} tables.")
            except Exception as exc:
                logger.warning(f"[MCP] Schema introspection warning: {exc}")
        else:
            logger.info("[MCP] Operating in offline/decoupled mode (database connection check skipped or pending).")

        yield
        logger.info("[MCP] Lifespan shutdown.")

    mcp = FastMCP(
        name=mcp_server_name,
        instructions=(
            "You have access to a PostgreSQL database exploration and query execution engine.\n\n"
            "Tools available:\n"
            "- `search_schema`: Find relevant tables and columns for a business question.\n"
            "- `get_database_schema`: Retrieve safe column definitions, data types, and foreign keys.\n"
            "- `validate_sql`: Validate SQL query for syntax, read-only guarantees, and safety.\n"
            "- `execute_sql`: Execute safe read-only SQL queries with timeout and capped row limits.\n"
            "- `get_table_sample`: Sample rows from authorized tables to inspect actual values.\n"
            "- `explain_sql`: Get query execution plan without executing.\n\n"
            "Sensitive columns (passwords, tokens, secrets) are strictly masked and never returned."
        ),
        lifespan=lifespan,
    )

    MCPToolRegistry(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    return mcp


mcp = create_mcp_server()


def run() -> None:
    """Start the MCP server with streamable-http as default transport.

    Set MCP_TRANSPORT=streamable-http (default) for web/server deployments.
    Set MCP_TRANSPORT=stdio for local terminal/editor clients.
    """
    settings = get_settings()

    mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("MCP_PORT", str(settings.API_PORT + 1 if hasattr(settings, "API_PORT") else 8001)))
    mcp_path = os.getenv("MCP_PATH", "/mcp")
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")

    if mcp is None:
        logger.error("FastMCP is not available. Please verify 'fastmcp' or 'mcp' is installed.")
        sys.exit(1)

    if transport == "streamable-http":
        logger.info(f"[MCP] Starting Database MCP server on streamable-http -> http://{mcp_host}:{mcp_port}{mcp_path}")
        try:
            mcp.run(
                transport="streamable-http",
                host=mcp_host,
                port=mcp_port,
                path=mcp_path,
            )
        except TypeError:
            try:
                mcp.run(transport="streamable-http", host=mcp_host, port=mcp_port)
            except TypeError:
                mcp.run(transport="sse", host=mcp_host, port=mcp_port)
    else:
        logger.info("[MCP] Starting Database MCP server in stdio transport mode...")
        mcp.run(transport="stdio")


main = run

if __name__ == "__main__":
    run()
