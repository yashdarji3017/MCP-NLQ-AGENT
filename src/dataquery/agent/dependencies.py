"""Agent context and dependency models for tracing and tool coordination."""

from dataclasses import dataclass, field
import time
from typing import Any
from dataquery.database.metadata import SchemaManager, get_schema_manager
from dataquery.schemas.results import ExecutionTrace, TraceStep


@dataclass
class AgentDeps:
    """Execution dependencies passed into PydanticAI agent run context."""

    schema_manager: SchemaManager = field(default_factory=get_schema_manager)
    trace_steps: list[TraceStep] = field(default_factory=list)
    start_time: float = field(default_factory=time.perf_counter)

    def record_step(
        self,
        step_name: str,
        duration_ms: float,
        status: str = "SUCCESS",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an observability step in the execution trace."""
        safe_details = details or {}
        cleaned_details = {
            k: v
            for k, v in safe_details.items()
            if not any(s in k.lower() for s in ["password", "token", "secret", "key", "signature"])
        }
        self.trace_steps.append(
            TraceStep(
                step_name=step_name,
                duration_ms=round(duration_ms, 2),
                status=status,
                details=cleaned_details,
            )
        )

    def get_execution_trace(self) -> ExecutionTrace:
        """Calculate total execution time and return full trace."""
        total_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        return ExecutionTrace(steps=self.trace_steps, total_duration_ms=total_ms)
