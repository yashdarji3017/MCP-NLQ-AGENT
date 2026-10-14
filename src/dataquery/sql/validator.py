"""SQL validation engine: AST parsing, statement type verification, and security enforcement."""

import logging
from typing import Any
from dataquery.config import get_settings
from dataquery.schemas.sql import ValidationResult
from dataquery.sql.policy import (
    BLOCKED_TABLES,
    DISALLOWED_FUNCTIONS,
    DISALLOWED_STATEMENTS,
    is_column_sensitive,
    is_table_allowed,
)
from dataquery.sql.sanitizer import (
    SQLSanitizationError,
    clean_sql_string,
    sanitize_and_clamp_limit,
)

logger = logging.getLogger(__name__)

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False
    sqlglot = None
    exp = None


def validate_sql_statement(sql: str) -> ValidationResult:
    """Perform comprehensive AST and rule-based validation of SQL.

    Enforces:
    1. Single statement only
    2. Read-only SELECT operation
    3. Table allowlist check (no blocked or arbitrary tables)
    4. Sensitive column denylist check (no passwords, tokens, signatures)
    5. Disallowed function check (no sleep, file I/O, server management)
    6. Limit clamp
    """
    settings = get_settings()
    warnings: list[str] = []

    try:
        sanitized = sanitize_and_clamp_limit(sql, max_limit=settings.MAX_QUERY_ROWS)
        clean_sql = sanitized.sanitized_sql
    except SQLSanitizationError as e:
        return ValidationResult(
            valid=False,
            statement_type="INVALID",
            error_message=str(e),
            suggested_fix="Ensure query is a single read-only SELECT statement without dangerous comments.",
        )

    upper_tokens = clean_sql.upper().split()
    if not upper_tokens:
        return ValidationResult(
            valid=False,
            statement_type="EMPTY",
            error_message="Query is empty.",
        )

    first_keyword = upper_tokens[0]
    for disallowed in DISALLOWED_STATEMENTS:
        if disallowed in upper_tokens:
            return ValidationResult(
                valid=False,
                statement_type=first_keyword,
                error_message=f"Disallowed SQL statement detected: {disallowed}. Only SELECT queries are permitted.",
                suggested_fix="Rewrite the query as a safe, read-only SELECT query.",
            )

    if HAS_SQLGLOT:
        try:
            parsed = sqlglot.parse_one(clean_sql, read="postgres")
        except Exception as e:
            return ValidationResult(
                valid=False,
                statement_type="PARSE_ERROR",
                error_message=f"PostgreSQL syntax parsing failed: {e}",
                suggested_fix="Check SQL syntax for PostgreSQL compatibility.",
            )

        if isinstance(parsed, exp.Select):
            statement_type = "SELECT"
        elif isinstance(parsed, exp.Explain):
            statement_type = "EXPLAIN"
            if not settings.ENABLE_EXPLAIN:
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    error_message="EXPLAIN statements are disabled by configuration.",
                )
            if "analyze" in clean_sql.lower():
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    error_message="EXPLAIN ANALYZE executes queries and is strictly forbidden.",
                    suggested_fix="Use regular EXPLAIN without ANALYZE.",
                )
        else:
            return ValidationResult(
                valid=False,
                statement_type=type(parsed).__name__,
                error_message=f"Only SELECT queries are allowed. Received: {type(parsed).__name__}",
                suggested_fix="Provide a SELECT query.",
            )

        tables: set[str] = set()
        for tbl in parsed.find_all(exp.Table):
            tbl_name = tbl.name.lower().strip()
            if tbl_name:
                tables.add(tbl_name)

        for tbl_name in tables:
            if tbl_name in BLOCKED_TABLES:
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=list(tables),
                    error_message=f"Table '{tbl_name}' contains sensitive authentication data and is blocked.",
                    suggested_fix="Query authorized analytics tables instead.",
                )
            if not is_table_allowed(tbl_name):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=list(tables),
                    error_message=f"Table '{tbl_name}' is not in the allowed database schema.",
                    suggested_fix="Use search_schema or get_database_schema to find allowed tables.",
                )

        columns: set[str] = set()
        for col in parsed.find_all(exp.Column):
            col_name = col.name.lower().strip()
            tbl_ref = col.table.lower().strip() if col.table else None
            columns.add(f"{tbl_ref}.{col_name}" if tbl_ref else col_name)

            if is_column_sensitive(tbl_ref, col_name):
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    tables=list(tables),
                    columns=list(columns),
                    error_message=f"Access to sensitive column '{col_name}' is strictly prohibited.",
                    suggested_fix="Remove the sensitive column from the SELECT clause and query filters.",
                )

        for func in parsed.find_all(exp.Func, exp.Anonymous):
            func_name = (
                func.name.lower().strip()
                if hasattr(func, "name")
                else getattr(func, "this", "").lower().strip()
            )
            if func_name in DISALLOWED_FUNCTIONS:
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    error_message=f"Execution of dangerous function '{func_name}' is prohibited.",
                    suggested_fix="Remove the disallowed administrative function.",
                )

        if any(isinstance(select_col, exp.Star) for select_col in parsed.find_all(exp.Star)):
            warnings.append("Query uses SELECT *. Prefer specifying explicit columns for better safety and performance.")

        return ValidationResult(
            valid=True,
            statement_type=statement_type,
            tables=sorted(list(tables)),
            columns=sorted(list(columns)),
            warnings=warnings,
        )

    else:
        statement_type = "SELECT" if first_keyword == "SELECT" else first_keyword
        if statement_type != "SELECT":
            return ValidationResult(
                valid=False,
                statement_type=statement_type,
                error_message="Only SELECT statements are permitted.",
            )

        for tbl in BLOCKED_TABLES:
            if tbl in clean_sql.lower():
                return ValidationResult(
                    valid=False,
                    statement_type=statement_type,
                    error_message=f"Table '{tbl}' is blocked from queries.",
                )

        return ValidationResult(
            valid=True,
            statement_type=statement_type,
            warnings=["Validated using standard regex rules (sqlglot recommended for full AST verification)."],
        )
