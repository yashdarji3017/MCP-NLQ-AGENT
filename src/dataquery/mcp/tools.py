"""Unified MCP Tool Registry for Database and Schema Operations.

Consolidates all MCP tool definitions and implementations into a single registry,
following FastMCP standard patterns with strict parameter validation and safety guarantees.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any
from pydantic import Field

try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = Any

from dataquery.database.executor import execute_safe_query, explain_safe_query, get_table_sample
from dataquery.database.metadata import get_schema_manager
from dataquery.mcp.security import assert_safe_sample_limit, assert_safe_table_name
from dataquery.sql.validator import validate_sql_statement

logger = logging.getLogger(__name__)


def search_schema_impl(question: str, top_k: int = 4) -> dict[str, Any]:
    """Find relevant PostgreSQL tables and columns based on a natural-language business question."""
    mgr = get_schema_manager()
    result = mgr.search_schema(question, top_k=top_k)
    return result.model_dump()


def get_database_schema_impl(table_names: list[str] | None = None) -> dict[str, Any]:
    """Retrieve structured schema information for specified tables or all allowed tables."""
    mgr = get_schema_manager()
    schema = mgr.get_database_schema(table_names)
    return schema.model_dump()


def validate_sql_impl(sql: str) -> dict[str, Any]:
    """Validate a generated SQL query for syntax, read-only safety, table allowlists, and column sensitivity."""
    result = validate_sql_statement(sql)
    return result.model_dump()


def execute_sql_impl(sql: str) -> dict[str, Any]:
    """Execute a safe, validated read-only SQL query against the PostgreSQL database."""
    result = execute_safe_query(sql)
    return result.model_dump()


def get_table_sample_impl(table_name: str, limit: int = 5) -> dict[str, Any]:
    """Retrieve a small safe sample of rows from an authorized database table."""
    safe_table = assert_safe_table_name(table_name)
    safe_limit = assert_safe_sample_limit(limit, max_limit=20)
    result = get_table_sample(safe_table, limit=safe_limit)
    return result.model_dump()


def explain_sql_impl(sql: str) -> dict[str, Any]:
    """Provide a safe PostgreSQL query execution plan (EXPLAIN FORMAT JSON) without executing."""
    return explain_safe_query(sql)


class MCPToolRegistry:
    """Registry for MCP database tools and prompts.

    Registers all schema discovery, query validation, and safe execution tools
    onto a FastMCP server instance.
    """

    def __init__(self, mcp: FastMCP):
        self.mcp = mcp
        self.register_tools()

    def register_tools(self) -> None:
        """Register all database query and schema exploration tools."""

        @self.mcp.tool(
            name="search_schema",
            description=(
                "Search and discover PostgreSQL database tables and columns relevant to the user's question. "
                "Returns targeted schema subsets, business domain notes, and relevant column names to prevent context bloat."
            ),
        )
        async def search_schema(
            question: Annotated[
                str,
                Field(
                    description=(
                        "Natural-language question or business concept to look up in the database schema. "
                        "Examples: 'Which apps have top rankings?', 'Show monthly subscription revenue', "
                        "'User login frequency'"
                    ),
                    min_length=1,
                    max_length=1000,
                ),
            ],
            top_k: Annotated[
                int,
                Field(
                    default=4,
                    description="Maximum number of relevant tables to return (range: 1-10).",
                    ge=1,
                    le=10,
                ),
            ] = 4,
        ) -> str:
            """Find relevant PostgreSQL tables and columns matching a question or concept."""
            logger.info(f"[MCP:search_schema] question='{question}' | top_k={top_k}")
            try:
                res = search_schema_impl(question=question, top_k=top_k)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:search_schema] Failed: {exc}")
                return json.dumps({"error": str(exc), "question": question}, ensure_ascii=False)

        @self.mcp.tool(
            name="get_database_schema",
            description=(
                "Retrieve safe, structured schema definitions for specified tables or all allowed tables. "
                "Excludes sensitive columns (passwords, secret tokens, signatures, webhooks). "
                "Dynamically reflects tables, column types, primary keys, and foreign key relationships."
            ),
        )
        async def get_database_schema(
            table_names: Annotated[
                list[str] | None,
                Field(
                    default=None,
                    description=(
                        "Optional list of table names to inspect (e.g. ['apps', 'ranking_history']). "
                        "If omitted or null, returns all accessible tables."
                    ),
                ),
            ] = None,
        ) -> str:
            """Retrieve structured schema information for specified or all allowed tables."""
            logger.info(f"[MCP:get_database_schema] table_names={table_names}")
            try:
                res = get_database_schema_impl(table_names=table_names)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:get_database_schema] Failed: {exc}")
                return json.dumps({"error": str(exc), "table_names": table_names}, ensure_ascii=False)

        @self.mcp.tool(
            name="validate_sql",
            description=(
                "Validate an SQL query for syntax, read-only safety, table allowlists, and column sensitivity. "
                "Strictly rejects write statements (INSERT, UPDATE, DELETE, DROP, ALTER), "
                "multi-statements, unauthorized tables, and forbidden PostgreSQL functions."
            ),
        )
        async def validate_sql(
            sql: Annotated[
                str,
                Field(
                    description="PostgreSQL query string to validate for safety and syntax.",
                    min_length=1,
                    max_length=10000,
                ),
            ],
        ) -> str:
            """Validate SQL statement before execution."""
            logger.info(f"[MCP:validate_sql] sql='{sql[:100]}...'")
            try:
                res = validate_sql_impl(sql=sql)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:validate_sql] Failed: {exc}")
                return json.dumps({"error": str(exc), "valid": False}, ensure_ascii=False)

        @self.mcp.tool(
            name="execute_sql",
            description=(
                "Execute a validated read-only SQL SELECT query against PostgreSQL with strict row limits and timeout. "
                "Returns columns, serialized row data, row count, execution time, and truncation indicator."
            ),
        )
        async def execute_sql(
            sql: Annotated[
                str,
                Field(
                    description="Validated safe PostgreSQL SELECT query to execute.",
                    min_length=1,
                    max_length=10000,
                ),
            ],
        ) -> str:
            """Execute safe read-only SQL query against the database."""
            logger.info(f"[MCP:execute_sql] sql='{sql[:100]}...'")
            try:
                res = execute_sql_impl(sql=sql)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:execute_sql] Failed: {exc}")
                return json.dumps({"error": str(exc), "sql": sql}, ensure_ascii=False)

        @self.mcp.tool(
            name="get_table_sample",
            description=(
                "Retrieve a small safe sample of rows from an authorized database table. "
                "Never exposes sensitive columns or secrets. Useful for inspecting realistic column values."
            ),
        )
        async def get_table_sample(
            table_name: Annotated[
                str,
                Field(
                    description="Authorized database table name to sample (e.g. 'apps', 'users').",
                    min_length=1,
                    max_length=255,
                ),
            ],
            limit: Annotated[
                int,
                Field(
                    default=5,
                    description="Number of sample rows to retrieve (range: 1-20).",
                    ge=1,
                    le=20,
                ),
            ] = 5,
        ) -> str:
            """Fetch safe data sample from an authorized table."""
            logger.info(f"[MCP:get_table_sample] table='{table_name}' | limit={limit}")
            try:
                res = get_table_sample_impl(table_name=table_name, limit=limit)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:get_table_sample] Failed: {exc}")
                return json.dumps({"error": str(exc), "table_name": table_name}, ensure_ascii=False)

        @self.mcp.tool(
            name="explain_sql",
            description=(
                "Provide a safe PostgreSQL query execution plan (EXPLAIN FORMAT JSON) without executing the query. "
                "Helps evaluate query complexity, index usage, and performance."
            ),
        )
        async def explain_sql(
            sql: Annotated[
                str,
                Field(
                    description="Validated SELECT query to inspect execution plan for.",
                    min_length=1,
                    max_length=10000,
                ),
            ],
        ) -> str:
            """Generate query execution plan without execution."""
            logger.info(f"[MCP:explain_sql] sql='{sql[:100]}...'")
            try:
                res = explain_sql_impl(sql=sql)
                return json.dumps(res, ensure_ascii=False)
            except Exception as exc:
                logger.error(f"[MCP:explain_sql] Failed: {exc}")
                return json.dumps({"error": str(exc), "sql": sql}, ensure_ascii=False)
