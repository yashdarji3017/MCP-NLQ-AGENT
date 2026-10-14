"""Structured output models for PydanticAI agent generation."""

from typing import Any
from pydantic import BaseModel, Field


class SQLGenerationResult(BaseModel):
    """Structured result produced by the Gemini SQL generation agent."""

    sql: str = Field(
        default="",
        description="PostgreSQL-compatible SELECT query. Empty if question is ambiguous or unsupported.",
    )
    tables_used: list[str] = Field(
        default_factory=list,
        description="Exact table names referenced in the query.",
    )
    columns_used: list[str] = Field(
        default_factory=list,
        description="Exact column names selected or filtered in the query.",
    )
    reasoning_summary: str = Field(
        ...,
        description="Brief step-by-step reasoning explaining how the SQL answers the question.",
    )
    is_clarification_needed: bool = Field(
        default=False,
        description="True if the user's question has multiple valid interpretations that change the SQL.",
    )
    clarification_options: list[str] = Field(
        default_factory=list,
        description="Suggested specific interpretations to present to the user if ambiguous.",
    )
    is_unsupported: bool = Field(
        default=False,
        description="True if the question asks for data not present in the database.",
    )
    unsupported_reason: str | None = Field(
        default=None,
        description="Clear explanation of what required data or entity is missing.",
    )


class ExplanationResult(BaseModel):
    """Structured natural language explanation of query results."""

    answer: str = Field(
        ...,
        description="Clear, professional executive answer to the user's question with domain context.",
    )
    key_takeaways: list[str] = Field(
        default_factory=list,
        description="Key bullets summarizing the data findings.",
    )
    recommended_chart: str = Field(
        default="none",
        description="Chart type best suited to display these results: 'bar', 'line', 'scatter', 'pie', or 'none'.",
    )
    chart_x_column: str | None = Field(
        default=None,
        description="Column name to place on X-axis or category dimension.",
    )
    chart_y_column: str | None = Field(
        default=None,
        description="Column name to place on Y-axis or numeric metric.",
    )
    chart_title: str | None = Field(
        default=None,
        description="Suggested descriptive title for the chart.",
    )
