"""Agent interface and trajectory records.

Any agent that implements the ``Agent`` protocol can be evaluated: a
deterministic policy (like the shipped demo agents), a scripted baseline, or a
real LLM-backed agent (see ``llm_agent.py`` for an optional adapter).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Step:
    """One recorded step of an agent trajectory."""

    thought: str
    tool: str | None  # None for the final-answer step
    args: dict[str, Any]
    observation: str
    latency_ms: float


@dataclass
class AgentResult:
    """Everything the harness needs to evaluate one task attempt."""

    task_id: str
    final_answer: str
    steps: list[Step] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def tools_called(self) -> list[str]:
        return [s.tool for s in self.steps if s.tool]

    @property
    def tool_step_count(self) -> int:
        return len(self.tools_called)

    @property
    def latency_ms(self) -> float:
        return sum(s.latency_ms for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


class Agent(Protocol):
    """Minimal interface every evaluated agent must satisfy."""

    name: str

    def run(self, task: dict[str, Any], tools: Any) -> AgentResult:
        """Execute one task against the given tool registry."""
        ...
