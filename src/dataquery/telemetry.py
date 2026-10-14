"""Logfire telemetry configuration for PydanticAI Agent.

Configured exclusively for the Agent to capture:
- Agent run hierarchy and execution spans
- Input & output system prompts
- Input & output token counts
- LLM model metadata and generated SQL
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_telemetry_lock = threading.Lock()
_telemetry_initialized = False


def setup_telemetry() -> None:
    """Initialize Logfire telemetry exclusively for PydanticAI Agent.

    Configures Logfire to capture token counts, prompts, model calls,
    and agent tool executions without tracing API or MCP servers.
    """
    global _telemetry_initialized

    if _telemetry_initialized:
        return

    with _telemetry_lock:
        if _telemetry_initialized:
            return

        try:
            import logfire
            from pydantic_ai import Agent

            logfire.configure(send_to_logfire="if-token-present")

            Agent.instrument_all()

            logger.info("Logfire agent telemetry initialized successfully.")
        except ImportError as e:
            logger.info(f"Logfire/PydanticAI not available for tracing: {e}")
        except Exception as exc:
            logger.warning(f"Logfire telemetry initialization skipped: {exc}")

        _telemetry_initialized = True


setup_logfire = setup_telemetry
