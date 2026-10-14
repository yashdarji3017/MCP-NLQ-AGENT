"""PydanticAI agent orchestrator package."""

from dataquery.agent.agent import create_explanation_agent, create_sql_agent, execute_nlq_pipeline
from dataquery.agent.dependencies import AgentDeps
from dataquery.agent.models import ExplanationResult, SQLGenerationResult
from dataquery.agent.prompts import EXPLANATION_SYSTEM_PROMPT, SQL_GENERATOR_SYSTEM_PROMPT

__all__ = [
    "create_sql_agent",
    "create_explanation_agent",
    "execute_nlq_pipeline",
    "AgentDeps",
    "SQLGenerationResult",
    "ExplanationResult",
    "SQL_GENERATOR_SYSTEM_PROMPT",
    "EXPLANATION_SYSTEM_PROMPT",
]
