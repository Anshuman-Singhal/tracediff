"""Diffs two runs: baseline vs candidate.

A task is a regression when any check newly fails, an improvement when checks
newly pass and none newly fail, and unchanged otherwise. Trajectory changes
(added/removed tools, step deltas) and cost/latency deltas are reported even
when check outcomes are unchanged, because silent behavior shifts matter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskDiff:
    task_id: str
    title: str
    status: str  # regression | improvement | unchanged | new | missing
    newly_failed: list[str] = field(default_factory=list)
    newly_passed: list[str] = field(default_factory=list)
    score_before: float = 1.0
    score_now: float = 1.0
    step_delta: int = 0
    added_tools: list[str] = field(default_factory=list)
    removed_tools: list[str] = field(default_factory=list)
    token_delta: int = 0
    latency_delta_ms: float = 0.0


@dataclass
class DiffReport:
    baseline_agent: str
    candidate_agent: str
    suite: str
    tasks: list[TaskDiff] = field(default_factory=list)

    @property
    def regressions(self) -> list[TaskDiff]:
        return [t for t in self.tasks if t.status == "regression"]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)

    @property
    def summary(self) -> dict[str, int]:
        counts = {"regression": 0, "improvement": 0, "unchanged": 0, "new": 0, "missing": 0}
        for t in self.tasks:
            counts[t.status] += 1
        return counts


def _failed_names(task_result: dict[str, Any]) -> set[str]:
    return {c["name"] for c in task_result["checks"] if not c["passed"]}


def _unique_tools(task_result: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for tool in task_result["tools_called"]:
        if tool not in seen:
            seen.append(tool)
    return seen


def diff_runs(baseline: dict[str, Any], candidate: dict[str, Any]) -> DiffReport:
    report = DiffReport(
        baseline_agent=baseline.get("agent", "?"),
        candidate_agent=candidate.get("agent", "?"),
        suite=baseline.get("suite", "?"),
    )
    base_tasks = baseline.get("tasks", {})
    cand_tasks = candidate.get("tasks", {})

    for task_id, b in base_tasks.items():
        c = cand_tasks.get(task_id)
        if c is None:
            report.tasks.append(
                TaskDiff(task_id=task_id, title=b.get("title", ""), status="missing")
            )
            continue
        failed_before = _failed_names(b)
        failed_now = _failed_names(c)
        newly_failed = sorted(failed_now - failed_before)
        newly_passed = sorted(failed_before - failed_now)
        if newly_failed:
            status = "regression"
        elif newly_passed:
            status = "improvement"
        else:
            status = "unchanged"

        tools_before = _unique_tools(b)
        tools_now = _unique_tools(c)
        tokens_before = b.get("tokens_in", 0) + b.get("tokens_out", 0)
        tokens_now = c.get("tokens_in", 0) + c.get("tokens_out", 0)

        report.tasks.append(
            TaskDiff(
                task_id=task_id,
                title=b.get("title", ""),
                status=status,
                newly_failed=newly_failed,
                newly_passed=newly_passed,
                score_before=round(b.get("score", 1.0), 3),
                score_now=round(c.get("score", 1.0), 3),
                step_delta=len(c["tools_called"]) - len(b["tools_called"]),
                added_tools=[t for t in tools_now if t not in tools_before],
                removed_tools=[t for t in tools_before if t not in tools_now],
                token_delta=tokens_now - tokens_before,
                latency_delta_ms=round(c.get("latency_ms", 0) - b.get("latency_ms", 0), 1),
            )
        )

    for task_id, c in cand_tasks.items():
        if task_id not in base_tasks:
            report.tasks.append(
                TaskDiff(task_id=task_id, title=c.get("title", ""), status="new")
            )

    return report
