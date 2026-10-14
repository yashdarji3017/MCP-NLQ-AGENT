"""SQL sanitizer: cleans input SQL, enforces single-statement bounds, and clamps LIMIT clauses."""

import re
from dataquery.config import get_settings
from dataquery.schemas.sql import SanitizedSQL


class SQLSanitizationError(ValueError):
    """Raised when SQL fails basic sanitization checks."""

    pass


def clean_sql_string(raw_sql: str) -> str:
    """Remove markdown formatting, code block markers, and extra whitespace."""
    sql = raw_sql.strip()

    if sql.startswith("```"):
        lines = sql.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    sql = sql.rstrip(";").strip()
    return sql


def check_for_multi_statement(sql: str) -> None:
    """Detect and reject multiple statements chained with semicolons."""
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for i, char in enumerate(sql):
        if char == "\\" and not escaped:
            escaped = True
            continue

        if char == "'" and not in_double_quote and not escaped:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote and not escaped:
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote:
            rest = sql[i + 1 :].strip()
            if rest:
                raise SQLSanitizationError(
                    "Multiple SQL statements detected. Only a single SELECT statement is allowed."
                )

        escaped = False


def check_dangerous_comments(sql: str) -> None:
    """Reject suspicious comments designed to hide payloads or bypass checks."""
    suspicious_patterns = [
        r"--.*(?:drop|delete|insert|update|alter|truncate|copy|grant)",
        r"/\*.*(?:drop|delete|insert|update|alter|truncate|copy|grant).*\*/",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
            raise SQLSanitizationError(
                "Suspicious SQL comment detected. Comments containing administrative keywords are rejected."
            )


def sanitize_and_clamp_limit(raw_sql: str, max_limit: int | None = None) -> SanitizedSQL:
    """Clean the SQL string, verify length, and ensure a safe LIMIT is enforced."""
    settings = get_settings()
    effective_max_limit = max_limit or settings.MAX_QUERY_ROWS

    if not raw_sql or not raw_sql.strip():
        raise SQLSanitizationError("SQL string is empty.")

    if len(raw_sql) > settings.MAX_SQL_LENGTH:
        raise SQLSanitizationError(
            f"SQL statement length ({len(raw_sql)}) exceeds maximum allowed ({settings.MAX_SQL_LENGTH})."
        )

    sql = clean_sql_string(raw_sql)
    check_for_multi_statement(sql)
    check_dangerous_comments(sql)

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    limit_injected = False
    effective_limit = effective_max_limit

    if limit_match:
        found_limit = int(limit_match.group(1))
        if found_limit > effective_max_limit:
            sql = re.sub(
                r"\bLIMIT\s+\d+\b",
                f"LIMIT {effective_max_limit}",
                sql,
                flags=re.IGNORECASE,
            )
            limit_injected = True
            effective_limit = effective_max_limit
        else:
            effective_limit = found_limit
    else:
        sql = f"{sql}\nLIMIT {effective_max_limit}"
        limit_injected = True
        effective_limit = effective_max_limit

    return SanitizedSQL(
        raw_sql=raw_sql,
        sanitized_sql=sql,
        limit_injected=limit_injected,
        effective_limit=effective_limit,
    )
