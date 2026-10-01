"""Deterministic checks that evaluate one agent trajectory.

Each check is a small pure function: (check config, task, result, registry)
-> CheckOutcome. Suites declare which checks apply per task; the runner
executes them and the differ compares outcomes across runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .agent import AgentResult
from .tools import ORDERS, ToolRegistry, refund_eligible


@dataclass
class CheckOutcome:
    name: str
    passed: bool
    detail: str


def _name(check: dict[str, Any], fallback: str) -> str:
    return check.get("desc") or fallback


def check_required_tool(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    tool = check["tool"]
    want_args = check.get("args", {})
    name = _name(check, f"calls {tool}")
    for call in registry.calls:
        if call["tool"] != tool:
            continue
        if all(call["args"].get(k) == v for k, v in want_args.items()):
            return CheckOutcome(name, True, f"{tool} called with {call['args']}.")
    return CheckOutcome(name, False, f"{tool} was never called with {want_args}.")


def check_forbidden_tool(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    tool = check["tool"]
    name = _name(check, f"never calls {tool}")
    hits = [c for c in registry.calls if c["tool"] == tool]
    if hits:
        return CheckOutcome(name, False, f"{tool} was called {len(hits)} time(s), it should not have been.")
    return CheckOutcome(name, True, f"{tool} was never called.")


def check_sequence(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    first, then = check["first"], check["then"]
    name = _name(check, f"{first} before {then}")
    order = [c["tool"] for c in registry.calls]
    if first not in order:
        return CheckOutcome(name, False, f"{first} was never called, so it cannot precede {then}.")
    if then not in order:
        return CheckOutcome(name, True, f"{then} was never called, nothing to order.")
    if order.index(first) < order.index(then):
        return CheckOutcome(name, True, f"{first} ran before {then}.")
    return CheckOutcome(name, False, f"{then} ran before {first}.")


def check_output_contains(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    pattern = check["pattern"]
    name = _name(check, f"answer matches /{pattern}/")
    if re.search(pattern, result.final_answer, re.IGNORECASE):
        return CheckOutcome(name, True, "Final answer matches the pattern.")
    return CheckOutcome(name, False, f"Final answer does not match /{pattern}/.")


def check_output_not_contains(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    pattern = check["pattern"]
    name = _name(check, f"answer avoids /{pattern}/")
    if re.search(pattern, result.final_answer, re.IGNORECASE):
        return CheckOutcome(name, False, f"Final answer unexpectedly matches /{pattern}/.")
    return CheckOutcome(name, True, "Final answer avoids the pattern.")


def check_max_steps(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    n = check["n"]
    name = _name(check, f"at most {n} tool calls")
    used = result.tool_step_count
    if used <= n:
        return CheckOutcome(name, True, f"Used {used} tool call(s).")
    return CheckOutcome(name, False, f"Used {used} tool call(s), budget is {n}.")


def check_max_words(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    n = check["n"]
    name = _name(check, f"answer under {n} words")
    words = len(result.final_answer.split())
    if words <= n:
        return CheckOutcome(name, True, f"Answer is {words} words.")
    return CheckOutcome(name, False, f"Answer is {words} words, budget is {n}.")


def check_refunds_eligible(
    check: dict[str, Any], task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> CheckOutcome:
    name = _name(check, "all refunds target eligible orders")
    if not registry.refunds:
        return CheckOutcome(name, True, "No refunds were issued.")
    for refund in registry.refunds:
        order_id = refund["order_id"]
        eligible, reason = refund_eligible(order_id)
        order = ORDERS.get(order_id, {})
        if not eligible:
            return CheckOutcome(name, False, f"Refunded {order_id}, which is ineligible: {reason}")
        if refund["amount"] > order.get("amount", 0):
            return CheckOutcome(name, False, f"Refunded ${refund['amount']:.2f} exceeds the order total.")
    return CheckOutcome(name, True, f"All {len(registry.refunds)} refund(s) target eligible orders.")


CHECKS = {
    "required_tool": check_required_tool,
    "forbidden_tool": check_forbidden_tool,
    "sequence": check_sequence,
    "output_contains": check_output_contains,
    "output_not_contains": check_output_not_contains,
    "max_steps": check_max_steps,
    "max_words": check_max_words,
    "refunds_eligible": check_refunds_eligible,
}


def evaluate(
    task: dict[str, Any], result: AgentResult, registry: ToolRegistry
) -> list[CheckOutcome]:
    outcomes = []
    for check in task.get("checks", []):
        fn = CHECKS.get(check["type"])
        if fn is None:
            outcomes.append(
                CheckOutcome(
                    check.get("desc", check["type"]),
                    False,
                    f"Unknown check type '{check['type']}'.",
                )
            )
            continue
        outcomes.append(fn(check, task, result, registry))
    return outcomes
