"""Query execution, execution traces, and NLQ response schemas."""

from typing import Any
from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    """Structured result returned by safe SQL execution."""

    columns: list[str] = Field(default_factory=list, description="Column names returned by the query")
    rows: list[list[Any]] = Field(default_factory=list, description="Row values as JSON-serializable list")
    row_count: int = Field(default=0, description="Number of returned rows")
    truncated: bool = Field(default=False, description="True if query results reached MAX_QUERY_ROWS cap")
    query_duration_ms: float = Field(default=0.0, description="Database execution time in milliseconds")


class TraceStep(BaseModel):
    """Single step in the end-to-end NLQ pipeline."""

    step_name: str = Field(..., description="Name of the pipeline step")
    duration_ms: float = Field(default=0.0, description="Step duration in milliseconds")
    status: str = Field(default="SUCCESS", description="Step status: SUCCESS, FAILED, SKIPPED, WARNING")
    details: dict[str, Any] = Field(default_factory=dict, description="Step metadata (never includes secrets)")


class ExecutionTrace(BaseModel):
    """Full observability trace of the NLQ request."""

    steps: list[TraceStep] = Field(default_factory=list, description="Chronological trace steps")
    total_duration_ms: float = Field(default=0.0, description="Total pipeline execution time in ms")


class ChartRecommendation(BaseModel):
    """Visualization metadata for Streamlit UI."""

    chart_type: str = Field(default="none", description="Recommended chart: bar, line, scatter, pie, table, none")
    x_column: str | None = Field(default=None, description="Suggested column for X axis")
    y_column: str | None = Field(default=None, description="Suggested column for Y axis")
    title: str = Field(default="", description="Title for visualization")


class NLQResponse(BaseModel):
    """Complete portfolio-grade response model for natural language questions."""

    question: str = Field(..., description="Original user natural language question")
    sql: str = Field(default="", description="Generated and validated PostgreSQL query")
    answer: str = Field(..., description="Natural language explanation and business insights")
    columns: list[str] = Field(default_factory=list, description="Columns present in query result")
    rows: list[list[Any]] = Field(default_factory=list, description="Row values")
    row_count: int = Field(default=0, description="Number of rows returned")
    truncated: bool = Field(default=False, description="Whether row limit was capped")
    tables_used: list[str] = Field(default_factory=list, description="Database tables referenced")
    columns_used: list[str] = Field(default_factory=list, description="Database columns referenced")
    warnings: list[str] = Field(default_factory=list, description="Safety or domain warnings")
    execution_trace: ExecutionTrace = Field(
        default_factory=ExecutionTrace, description="Observability trace of pipeline"
    )
    chart: ChartRecommendation | None = Field(
        default=None, description="Recommended visualization configuration"
    )
    is_ambiguous: bool = Field(
        default=False, description="True if query is ambiguous and needs clarification"
    )
    clarification_options: list[str] = Field(
        default_factory=list, description="Suggested options to resolve ambiguity"
    )
    is_unsupported: bool = Field(
        default=False, description="True if question cannot be answered from database"
    )
    unsupported_reason: str | None = Field(
        default=None, description="Explanation of missing data"
    )
