"""Security interceptors and input validation for MCP database tools."""

from dataquery.sql.policy import is_column_sensitive, is_table_allowed


class MCPToolSecurityError(PermissionError):
    """Raised when an MCP tool invocation attempts an unauthorized operation."""

    pass


def assert_safe_table_name(table_name: str) -> str:
    """Verify table name is permitted and sanitize."""
    normalized = table_name.lower().strip()
    if not is_table_allowed(normalized):
        raise MCPToolSecurityError(
            f"Table '{table_name}' is not allowed or does not exist in authorized schema."
        )
    return normalized


def assert_safe_sample_limit(limit: int, max_limit: int = 20) -> int:
    """Verify and bound sample query limits."""
    if limit < 1:
        return 1
    if limit > max_limit:
        return max_limit
    return limit
