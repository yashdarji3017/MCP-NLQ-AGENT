"""PydanticAI agent definition, Gemini integration, and end-to-end NLQ pipeline coordinator."""

import json
import logging
import time
from typing import Any
from dataquery.agent.dependencies import AgentDeps
from dataquery.agent.models import ExplanationResult, SQLGenerationResult
from dataquery.agent.prompts import EXPLANATION_SYSTEM_PROMPT, SQL_GENERATOR_SYSTEM_PROMPT
from dataquery.config import get_settings
from dataquery.mcp.client import MCPClient, get_mcp_client
from dataquery.schemas.database import DatabaseSchema, SchemaSearchResult
from dataquery.schemas.results import ChartRecommendation, NLQResponse, QueryResult
from dataquery.schemas.sql import ValidationResult
from dataquery.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

setup_telemetry()

try:
    from pydantic_ai import Agent, RunContext
    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False
    Agent = None
    RunContext = None


def get_agent_model_string() -> str:
    """Format model identifier for PydanticAI Google provider."""
    settings = get_settings()
    model_id = settings.GEMINI_MODEL.strip()
    if not model_id.startswith("google:") and not model_id.startswith("google-vertex:"):
        return f"google:{model_id}"
    return model_id


def _get_agent_output_kwarg(model_cls: Any) -> dict[str, Any]:
    """Support both modern PydanticAI (output_type) and legacy (result_type)."""
    try:
        import inspect
        if HAS_PYDANTIC_AI and Agent is not None:
            sig = inspect.signature(Agent.__init__)
            if "output_type" in sig.parameters:
                return {"output_type": model_cls}
    except Exception:
        pass
    return {"result_type": model_cls}


def create_sql_agent(mcp_url: str | None = None) -> Any:
    """Create PydanticAI agent configured for PostgreSQL SQL generation via MCP server URL."""
    if not HAS_PYDANTIC_AI:
        return None

    model_name = get_agent_model_string()
    agent = Agent(
        model_name,
        deps_type=AgentDeps,
        system_prompt=SQL_GENERATOR_SYSTEM_PROMPT,
        **_get_agent_output_kwarg(SQLGenerationResult),
    )

    client = MCPClient(server_url=mcp_url)

    @agent.tool
    async def search_database_schema(ctx: RunContext[AgentDeps], query: str) -> dict[str, Any]:
        """Find relevant tables and columns matching a question or concept via MCP server URL."""
        return await client.call_tool("search_schema", {"question": query})

    @agent.tool
    async def get_table_schema(ctx: RunContext[AgentDeps], table_names: list[str]) -> dict[str, Any]:
        """Retrieve safe column schemas and foreign keys for specific tables via MCP server URL."""
        return await client.call_tool("get_database_schema", {"table_names": table_names})

    @agent.tool
    async def inspect_table_sample(ctx: RunContext[AgentDeps], table_name: str, limit: int = 3) -> dict[str, Any]:
        """Inspect a small sample of safe data to see realistic column values via MCP server URL."""
        return await client.call_tool("get_table_sample", {"table_name": table_name, "limit": limit})

    @agent.tool
    async def pre_validate_sql(ctx: RunContext[AgentDeps], sql: str) -> dict[str, Any]:
        """Check if an SQL query passes AST and safety policies before finalizing via MCP server URL."""
        return await client.call_tool("validate_sql", {"sql": sql})

    return agent


def create_explanation_agent() -> Any:
    """Create PydanticAI agent for business result explanations and chart recommendations."""
    if not HAS_PYDANTIC_AI:
        return None

    model_name = get_agent_model_string()
    return Agent(
        model_name,
        deps_type=AgentDeps,
        system_prompt=EXPLANATION_SYSTEM_PROMPT,
        **_get_agent_output_kwarg(ExplanationResult),
    )


async def execute_nlq_pipeline(question: str, mcp_url: str | None = None) -> NLQResponse:
    """Execute end-to-end Natural Language to SQL generation, validation, execution, and explanation via MCP server URL."""
    settings = get_settings()
    deps = AgentDeps()
    warnings: list[str] = []

    mcp_client = MCPClient(server_url=mcp_url)

    t0 = time.perf_counter()
    raw_search = await mcp_client.call_tool("search_schema", {"question": question})
    schema_search = SchemaSearchResult.model_validate(raw_search)
    search_duration = (time.perf_counter() - t0) * 1000
    deps.record_step(
        "Schema Search (MCP)",
        search_duration,
        details={
            "selected_tables": schema_search.tables,
            "relevant_columns": schema_search.relevant_columns,
            "mcp_url": mcp_client.server_url,
        },
    )

    t0 = time.perf_counter()
    raw_schema = await mcp_client.call_tool("get_database_schema", {"table_names": schema_search.tables})
    targeted_schema = DatabaseSchema.model_validate(raw_schema)
    retrieval_duration = (time.perf_counter() - t0) * 1000
    deps.record_step(
        "Schema Retrieval (MCP)",
        retrieval_duration,
        details={"table_count": len(targeted_schema.tables), "mcp_url": mcp_client.server_url},
    )

    t0 = time.perf_counter()
    if not HAS_PYDANTIC_AI:
        raise RuntimeError("PydanticAI is required for LLM SQL generation. Please install pydantic-ai.")

    agent = create_sql_agent(mcp_url=mcp_url)
    if agent is None:
        raise RuntimeError("Failed to create SQL agent. Verify environment configuration.")

    prompt_context = f"""
USER QUESTION: {question}

GROUNDED RELEVANT SCHEMA:
{targeted_schema.model_dump_json(indent=2)}

DOMAIN GUIDANCE:
{json.dumps(schema_search.domain_guidance, indent=2)}

Generate safe PostgreSQL SQL answering the question.
"""
    try:
        import logfire
        has_logfire = True
    except ImportError:
        has_logfire = False

    try:
        if has_logfire:
            with logfire.span(f"Running Pydantic AI NLQ Agent for Query: {question}"):
                logfire.info(
                    f"NLQ Grounded Schema Input for Query: {question}",
                    tables=schema_search.tables,
                    relevant_columns=schema_search.relevant_columns,
                    table_count=len(targeted_schema.tables),
                )
                run_result = await agent.run(prompt_context, deps=deps)
                raw_output = getattr(run_result, "output", getattr(run_result, "data", None))
                if isinstance(raw_output, SQLGenerationResult):
                    sql_gen_result = raw_output
                elif isinstance(raw_output, dict):
                    sql_gen_result = SQLGenerationResult.model_validate(raw_output)
                else:
                    sql_gen_result = SQLGenerationResult(
                        sql=str(raw_output or ""),
                        tables_used=[],
                        columns_used=[],
                        reasoning_summary="Generated from prompt.",
                    )
                logfire.info(
                    f"NLQ SQL Generated for Query: {question}",
                    sql=sql_gen_result.sql,
                    tables_used=sql_gen_result.tables_used,
                    columns_used=sql_gen_result.columns_used,
                    reasoning=sql_gen_result.reasoning_summary,
                )
        else:
            run_result = await agent.run(prompt_context, deps=deps)
            raw_output = getattr(run_result, "output", getattr(run_result, "data", None))
            if isinstance(raw_output, SQLGenerationResult):
                sql_gen_result = raw_output
            elif isinstance(raw_output, dict):
                sql_gen_result = SQLGenerationResult.model_validate(raw_output)
            else:
                sql_gen_result = SQLGenerationResult(
                    sql=str(raw_output or ""),
                    tables_used=[],
                    columns_used=[],
                    reasoning_summary="Generated from prompt.",
                )
    except Exception as e:
        gen_duration = (time.perf_counter() - t0) * 1000
        deps.record_step(
            "SQL Generation",
            gen_duration,
            status="FAILED",
            details={"error": str(e)},
        )
        logger.error(f"SQL Generation agent run failed: {e}")
        return NLQResponse(
            question=question,
            sql="",
            answer=f"SQL Generation failed: {e}",
            warnings=[f"Agent error: {type(e).__name__}"],
            execution_trace=deps.get_execution_trace(),
        )

    gen_duration = (time.perf_counter() - t0) * 1000
    deps.record_step(
        "SQL Generation",
        gen_duration,
        details={
            "reasoning": sql_gen_result.reasoning_summary,
            "tables_used": sql_gen_result.tables_used,
        },
    )

    if sql_gen_result.is_clarification_needed:
        return NLQResponse(
            question=question,
            sql="",
            answer="Your question has multiple possible interpretations. Please select one of the following specific options to proceed:",
            is_ambiguous=True,
            clarification_options=sql_gen_result.clarification_options,
            execution_trace=deps.get_execution_trace(),
        )

    if sql_gen_result.is_unsupported:
        return NLQResponse(
            question=question,
            sql="",
            answer=f"I cannot answer that from the available database data: {sql_gen_result.unsupported_reason}",
            is_unsupported=True,
            unsupported_reason=sql_gen_result.unsupported_reason,
            execution_trace=deps.get_execution_trace(),
        )

    raw_sql = sql_gen_result.sql

    t0 = time.perf_counter()
    raw_val = await mcp_client.call_tool("validate_sql", {"sql": raw_sql})
    val_result = ValidationResult.model_validate(raw_val)
    val_duration = (time.perf_counter() - t0) * 1000

    if not val_result.valid:
        deps.record_step(
            "SQL Validation (MCP)",
            val_duration,
            status="FAILED",
            details={"error": val_result.error_message, "suggested_fix": val_result.suggested_fix},
        )
        return NLQResponse(
            question=question,
            sql=raw_sql,
            answer=f"The generated SQL failed security validation: {val_result.error_message}. Execution was blocked.",
            warnings=[f"Security violation: {val_result.error_message}"],
            execution_trace=deps.get_execution_trace(),
        )

    warnings.extend(val_result.warnings)
    deps.record_step(
        "SQL Validation (MCP)",
        val_duration,
        status="SUCCESS",
        details={
            "statement_type": val_result.statement_type,
            "tables": val_result.tables,
            "columns": val_result.columns,
        },
    )

    t0 = time.perf_counter()
    query_result: QueryResult
    try:
        raw_exec = await mcp_client.call_tool("execute_sql", {"sql": raw_sql})
        if "error" in raw_exec and not raw_exec.get("columns"):
            raise RuntimeError(raw_exec["error"])
        query_result = QueryResult.model_validate(raw_exec)
        exec_duration = (time.perf_counter() - t0) * 1000
        deps.record_step(
            "SQL Execution (MCP)",
            exec_duration,
            status="SUCCESS",
            details={
                "row_count": query_result.row_count,
                "truncated": query_result.truncated,
                "duration_ms": query_result.query_duration_ms,
            },
        )
    except Exception as e:
        exec_duration = (time.perf_counter() - t0) * 1000
        deps.record_step(
            "SQL Execution (MCP)",
            exec_duration,
            status="FAILED",
            details={"error": str(e)},
        )
        return NLQResponse(
            question=question,
            sql=raw_sql,
            answer=f"Database execution failed: {e}. Please ensure PostgreSQL is running and accessible via DATABASE_URL.",
            tables_used=val_result.tables,
            columns_used=val_result.columns,
            warnings=warnings,
            execution_trace=deps.get_execution_trace(),
        )

    t0 = time.perf_counter()
    answer_text: str
    chart_rec: ChartRecommendation | None = None

    if query_result.row_count == 0:
        answer_text = "The query executed successfully, but no matching records were found in the database for the given criteria."
    else:
        numeric_cols = [
            col for idx, col in enumerate(query_result.columns)
            if query_result.rows and isinstance(query_result.rows[0][idx], (int, float))
        ]
        text_cols = [
            col for idx, col in enumerate(query_result.columns)
            if query_result.rows and isinstance(query_result.rows[0][idx], str)
        ]

        if numeric_cols and text_cols:
            chart_rec = ChartRecommendation(
                chart_type="bar",
                x_column=text_cols[0],
                y_column=numeric_cols[0],
                title=f"{numeric_cols[0].replace('_', ' ').title()} by {text_cols[0].replace('_', ' ').title()}",
            )
        elif numeric_cols:
            chart_rec = ChartRecommendation(
                chart_type="line",
                x_column=query_result.columns[0],
                y_column=numeric_cols[0],
                title=f"{numeric_cols[0].replace('_', ' ').title()} Trend",
            )

        first_row_preview = dict(zip(query_result.columns, query_result.rows[0])) if query_result.rows else {}
        answer_text = (
            f"Retrieved {query_result.row_count} record(s). "
            f"{sql_gen_result.reasoning_summary} "
            f"Top result: {first_row_preview}."
        )

        if "rank" in question.lower():
            answer_text += " Note: A lower numerical rank indicates superior ranking performance (rank = 1 is top position)."

    explain_duration = (time.perf_counter() - t0) * 1000
    deps.record_step(
        "Result Explanation",
        explain_duration,
        details={"chart_recommended": chart_rec.chart_type if chart_rec else "none"},
    )

    return NLQResponse(
        question=question,
        sql=raw_sql,
        answer=answer_text,
        columns=query_result.columns,
        rows=query_result.rows,
        row_count=query_result.row_count,
        truncated=query_result.truncated,
        tables_used=val_result.tables,
        columns_used=val_result.columns,
        warnings=warnings,
        execution_trace=deps.get_execution_trace(),
        chart=chart_rec,
    )
