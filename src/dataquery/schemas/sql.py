"""SQL validation and sanitization schemas."""

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of SQL programmatic validation."""

    valid: bool = Field(..., description="Whether the SQL passed all security and syntax checks")
    statement_type: str = Field(default="UNKNOWN", description="Parsed SQL statement type (e.g. SELECT)")
    tables: list[str] = Field(default_factory=list, description="List of tables referenced in query")
    columns: list[str] = Field(default_factory=list, description="List of columns referenced in query")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking safety warnings or notes")
    error_message: str | None = Field(default=None, description="Detailed error message if validation failed")
    suggested_fix: str | None = Field(
        default=None, description="Actionable suggestion to fix validation failure"
    )


class SanitizedSQL(BaseModel):
    """Sanitized and limit-injected SQL statement."""

    raw_sql: str = Field(..., description="Original SQL string")
    sanitized_sql: str = Field(..., description="Cleaned and safety-checked SQL")
    limit_injected: bool = Field(default=False, description="Whether LIMIT clause was appended or clamped")
    effective_limit: int | None = Field(default=None, description="Applied LIMIT value")
