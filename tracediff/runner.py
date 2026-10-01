"""Executes a task suite against an agent and records a run."""
from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .agent import Agent
from .evaluators import evaluate
from .tools import ToolRegistry


def load_suite(name: str) -> dict[str, Any]:
    module = importlib.import_module(f"suites.{name}")
    return module.SUITE


def list_suites() -> list[str]:
    suites_dir = Path(__file__).resolve().parent.parent / "suites"
    return sorted(p.stem for p in suites_dir.glob("*.py") if p.stem != "__init__")


def run_suite(
    suite_name: str,
    agent: Agent,
    out_dir: str | Path,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    suite = load_suite(suite_name)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {}
    tasks = suite["tasks"]
    if task_ids:
        tasks = [t for t in tasks if t["id"] in task_ids]
    print(f"Running suite '{suite_name}' with agent '{agent.name}' ({len(tasks)} tasks)")

    for i, task in enumerate(tasks, 1):
        registry = ToolRegistry()  # fresh tools per task
        result = agent.run(task, registry)
        outcomes = evaluate(task, result, registry)
        passed = sum(1 for o in outcomes if o.passed)
        results[task["id"]] = {
            "title": task["title"],
            "message": task["message"],
            "final_answer": result.final_answer,
            "steps": [asdict(s) for s in result.steps],
            "tools_called": result.tools_called,
            "checks": [
                {"name": o.name, "passed": o.passed, "detail": o.detail}
                for o in outcomes
            ],
            "score": passed / len(outcomes) if outcomes else 1.0,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "latency_ms": round(result.latency_ms, 1),
        }
        mark = "PASS" if passed == len(outcomes) else f"{passed}/{len(outcomes)}"
        print(f"  [{i}/{len(tasks)}] {task['id']}: {mark}")

    run = {
        "agent": agent.name,
        "suite": suite_name,
        "tasks": results,
    }
    (out / "run.json").write_text(json.dumps(run, indent=2))
    print(f"Run saved to {out / 'run.json'}")
    return run


def load_run(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "run.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No run.json found in {run_dir}. Run 'tracediff run' first."
        )
    return json.loads(path.read_text())
