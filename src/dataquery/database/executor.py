"""Safe SQL execution engine with read-only guarantees, timeout, and row limit capping."""

import datetime
from decimal import Decimal
import logging
import time
from typing import Any
from sqlalchemy import text
from dataquery.config import get_settings
from dataquery.database.connection import get_db_connection
from dataquery.database.schema_definitions import get_safe_table_dict
from dataquery.schemas.results import QueryResult
from dataquery.sql.policy import is_table_allowed
from dataquery.sql.validator import validate_sql_statement

logger = logging.getLogger(__name__)


def serialize_value(val: Any) -> Any:
    """Convert database values (datetime, Decimal, UUID) to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val) if val % 1 else int(val)
    if isinstance(val, bytes):
        return "<binary data>"
    return val


def execute_safe_query(sql: str) -> QueryResult:
    """Execute a validated read-only SQL query against PostgreSQL.

    Safety controls enforced:
    1. Re-validates SQL through AST security layer.
    2. Read-only transaction enforcement.
    3. Query timeout limit.
    4. Row limit capping (max MAX_QUERY_ROWS).
    5. Type serialization.
    """
    settings = get_settings()

    val_result = validate_sql_statement(sql)
    if not val_result.valid:
        raise ValueError(f"SQL validation failed: {val_result.error_message}")

    start_time = time.perf_counter()

    try:
        with get_db_connection() as conn:
            timeout_ms = settings.QUERY_TIMEOUT_SECONDS * 1000
            conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms};"))

            cursor_result = conn.execute(text(sql))
            columns = list(cursor_result.keys()) if cursor_result.returns_rows else []

            max_rows = settings.MAX_QUERY_ROWS
            fetched_rows = cursor_result.fetchmany(max_rows + 1) if cursor_result.returns_rows else []

            truncated = len(fetched_rows) > max_rows
            final_rows = fetched_rows[:max_rows]

            serialized_rows = [
                [serialize_value(val) for val in row]
                for row in final_rows
            ]

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return QueryResult(
                columns=columns,
                rows=serialized_rows,
                row_count=len(serialized_rows),
                truncated=truncated,
                query_duration_ms=duration_ms,
            )

    except Exception as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        err_msg = str(e)
        logger.error(f"SQL execution error ({duration_ms}ms): {err_msg}")
        raise RuntimeError(f"Database query error: {err_msg}") from e


def get_table_sample(table_name: str, limit: int = 5) -> QueryResult:
    """Fetch a small safe sample of rows from an allowed table."""
    settings = get_settings()
    norm_name = table_name.lower().strip()

    if not is_table_allowed(norm_name):
        raise ValueError(f"Table '{table_name}' is not allowed for sampling.")

    safe_tables = get_safe_table_dict()
    table_meta = safe_tables.get(norm_name)
    if not table_meta:
        raise ValueError(f"Table '{table_name}' does not exist in safe schema.")

    safe_col_names = [f'"{col.name}"' for col in table_meta.columns if not col.is_sensitive]
    if not safe_col_names:
        raise ValueError(f"Table '{table_name}' has no accessible columns.")

    effective_limit = min(max(1, limit), settings.MAX_SAMPLE_ROWS)
    query_str = f'SELECT {", ".join(safe_col_names)} FROM "{norm_name}" LIMIT {effective_limit};'

    return execute_safe_query(query_str)


def explain_safe_query(sql: str) -> dict[str, Any]:
    """Execute EXPLAIN (read-only plan, no ANALYZE) for a validated query."""
    settings = get_settings()
    if not settings.ENABLE_EXPLAIN:
        raise ValueError("EXPLAIN functionality is disabled by configuration.")

    val_result = validate_sql_statement(sql)
    if not val_result.valid:
        raise ValueError(f"SQL validation failed: {val_result.error_message}")

    explain_sql = f"EXPLAIN (FORMAT JSON) {sql.rstrip(';')};"

    with get_db_connection() as conn:
        res = conn.execute(text(explain_sql)).scalar()
        return {"query_plan": res}
