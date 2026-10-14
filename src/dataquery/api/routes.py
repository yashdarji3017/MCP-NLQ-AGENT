"""FastAPI router implementing REST endpoints for NLQ, schema, validation, and execution."""

import datetime
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from dataquery.agent.agent import execute_nlq_pipeline
from dataquery.api.schemas import (
    ExecuteSQLRequest,
    HealthResponse,
    QueryRequest,
    ValidateSQLRequest,
)
from dataquery.config import get_settings
from dataquery.database.connection import test_db_connection
from dataquery.database.executor import execute_safe_query
from dataquery.database.metadata import get_schema_manager
from dataquery.schemas.database import DatabaseSchema
from dataquery.schemas.results import NLQResponse, QueryResult
from dataquery.schemas.sql import ValidationResult
from dataquery.sql.validator import validate_sql_statement

logger = logging.getLogger(__name__)

router = APIRouter()

RECENT_QUERIES: list[dict[str, Any]] = []
MAX_HISTORY_ENTRIES = 50


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Return health status, database connectivity, and configuration."""
    settings = get_settings()
    db_ok = test_db_connection()

    tools = [
        "get_database_schema",
        "search_schema",
        "validate_sql",
        "execute_sql",
        "get_table_sample",
        "explain_sql",
    ]

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database_connected=db_ok,
        mcp_tools_available=tools,
        configuration=settings.safe_dict(),
    )


@router.get("/schema", response_model=DatabaseSchema, tags=["Schema"])
async def get_schema(
    tables: list[str] | None = Query(default=None, description="Optional filter of table names")
) -> DatabaseSchema:
    """Return safe PostgreSQL schema definitions with sensitive columns excluded."""
    mgr = get_schema_manager()
    return mgr.get_database_schema(tables)


@router.post("/query", response_model=NLQResponse, tags=["NLQ"])
async def process_query(request: QueryRequest) -> NLQResponse:
    """Translate a natural language question into validated SQL, execute it safely, and explain findings."""
    try:
        response = await execute_nlq_pipeline(request.question, mcp_url=request.mcp_url)

        history_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "question": response.question,
            "sql": response.sql,
            "row_count": response.row_count,
            "is_ambiguous": response.is_ambiguous,
            "is_unsupported": response.is_unsupported,
            "tables_used": response.tables_used,
        }
        RECENT_QUERIES.insert(0, history_entry)
        if len(RECENT_QUERIES) > MAX_HISTORY_ENTRIES:
            RECENT_QUERIES.pop()

        return response
    except Exception as e:
        logger.error(f"Error processing NLQ query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while answering your question: {str(e)}",
        )


@router.post("/sql/validate", response_model=ValidationResult, tags=["SQL Safety"])
async def validate_sql(request: ValidateSQLRequest) -> ValidationResult:
    """Validate an SQL statement against AST and safety policies before execution."""
    return validate_sql_statement(request.sql)


@router.post("/sql/execute", response_model=QueryResult, tags=["SQL Safety"])
async def execute_sql(request: ExecuteSQLRequest) -> QueryResult:
    """Execute a validated, read-only SQL query with timeout and row limit capping."""
    val = validate_sql_statement(request.sql)
    if not val.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL Validation failed: {val.error_message}",
        )

    try:
        return execute_safe_query(request.sql)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(e)}",
        )


@router.get("/history", tags=["Observability"])
async def get_query_history() -> list[dict[str, Any]]:
    """Return in-memory query history for recent user requests."""
    return RECENT_QUERIES
