"""Centralized SQL security policy for DataQuery AI.

Enforces table allowlists, sensitive column denylists, statement restrictions,
and forbidden function registries.
"""

from typing import Final

BLOCKED_TABLES: Final[set[str]] = {
    "refresh_tokens",
    "password_reset_tokens",
}

ALLOWED_TABLES: Final[set[str]] = {
    "users",
    "user_activities",
    "apps",
    "app_keywords",
    "keywords",
    "ranking_history",
    "app_invitations",
    "app_audit_history",
    "payment_transactions",
    "shopify_categories",
    "category_snapshots",
    "category_apps",
    "slack_integrations",
}

SENSITIVE_COLUMNS: Final[dict[str, set[str]]] = {
    "users": {
        "hashed_password",
    },
    "password_reset_tokens": {
        "token",
        "code",
    },
    "refresh_tokens": {
        "token_hash",
        "family_id",
        "ip_address",
    },
    "payment_transactions": {
        "razorpay_signature",
    },
    "slack_integrations": {
        "webhook_url",
        "bot_token",
    },
}

GLOBAL_SENSITIVE_COLUMN_PATTERNS: Final[set[str]] = {
    "password",
    "passwd",
    "secret",
    "token",
    "signature",
    "webhook_url",
    "bot_token",
}

DISALLOWED_STATEMENTS: Final[set[str]] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "CALL",
    "DO",
    "VACUUM",
    "ANALYZE",
    "EXECUTE",
    "PREPARE",
    "LOCK",
    "COMMENT",
    "REINDEX",
    "SECURITY",
}

DISALLOWED_FUNCTIONS: Final[set[str]] = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_write_file",
    "pg_write_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "dblink",
    "dblink_exec",
    "query_to_xml",
    "query_to_json",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "current_setting",
    "set_config",
}


def is_table_allowed(table_name: str) -> bool:
    """Check if table is allowed for querying.

    Enforces that table is not blocked, not a PostgreSQL system table,
    and exists either in the dynamic database schema or fallback allowed tables.
    """
    normalized = table_name.lower().strip()
    if normalized in BLOCKED_TABLES or normalized.startswith(("pg_", "sql_", "alembic_")):
        return False

    try:
        from dataquery.database.schema_definitions import get_safe_table_dict
        safe_tables = get_safe_table_dict()
        if normalized in safe_tables:
            return True
    except Exception:
        pass

    return normalized in ALLOWED_TABLES


def is_column_sensitive(table_name: str | None, column_name: str) -> bool:
    """Check if column is classified as sensitive."""
    col_norm = column_name.lower().strip()

    if table_name:
        tbl_norm = table_name.lower().strip()
        if tbl_norm in SENSITIVE_COLUMNS and col_norm in SENSITIVE_COLUMNS[tbl_norm]:
            return True

    for pattern in GLOBAL_SENSITIVE_COLUMN_PATTERNS:
        if pattern in col_norm:
            return True

    return False
