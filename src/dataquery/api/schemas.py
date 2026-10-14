"""API request and response schemas for FastAPI gateway."""

from typing import Any
from pydantic import BaseModel, Field
from dataquery.schemas.results import NLQResponse, QueryResult
from dataquery.schemas.sql import ValidationResult


class QueryRequest(BaseModel):
    """User natural language query request."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language business question to ask the database.",
        examples=["Which apps have the highest average ranking over the last 30 days?"],
    )
    mcp_url: str | None = Field(
        default=None,
        description="Optional custom MCP server streamable-http URL (e.g. http://localhost:8001/mcp).",
    )


class ValidateSQLRequest(BaseModel):
    """SQL validation request."""

    sql: str = Field(
        ...,
        min_length=5,
        max_length=10000,
        description="PostgreSQL SELECT query to validate for read-only safety.",
    )


class ExecuteSQLRequest(BaseModel):
    """Direct SQL execution request (internal/admin)."""

    sql: str = Field(
        ...,
        min_length=5,
        max_length=10000,
        description="Validated read-only SQL query to execute.",
    )


class HealthResponse(BaseModel):
    """API health status and environment configuration metadata."""

    status: str = Field(default="ok")
    database_connected: bool = Field(default=False)
    mcp_tools_available: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
