"""Tests for the deterministic check functions."""
import unittest

from tracediff.agent import AgentResult, Step
from tracediff.evaluators import evaluate
from tracediff.tools import ToolRegistry


def make_result(final_answer="done", tool_calls=()):
    registry = ToolRegistry()
    steps = []
    for tool, args in tool_calls:
        obs = registry.call(tool, dict(args))
        steps.append(Step(thought="t", tool=tool, args=dict(args), observation=obs, latency_ms=1.0))
    return AgentResult(task_id="t", final_answer=final_answer, steps=steps), registry


class TestChecks(unittest.TestCase):
    def test_required_tool_passes_with_matching_args(self):
        result, registry = make_result(tool_calls=[("lookup_order", {"order_id": "ORD-1001"})])
        task = {"checks": [{"type": "required_tool", "tool": "lookup_order",
                            "args": {"order_id": "ORD-1001"}, "desc": "lookup"}]}
        (outcome,) = evaluate(task, result, registry)
        self.assertTrue(outcome.passed)

    def test_required_tool_fails_when_missing(self):
        result, registry = make_result()
        task = {"checks": [{"type": "required_tool", "tool": "escalate", "desc": "esc"}]}
        (outcome,) = evaluate(task, result, registry)
        self.assertFalse(outcome.passed)

    def test_forbidden_tool(self):
        result, registry = make_result(tool_calls=[("issue_refund", {"order_id": "ORD-1003", "amount": 49.0})])
        task = {"checks": [{"type": "forbidden_tool", "tool": "issue_refund", "desc": "no refund"}]}
        (outcome,) = evaluate(task, result, registry)
        self.assertFalse(outcome.passed)

    def test_sequence_pass_and_fail(self):
        good, reg = make_result(tool_calls=[
            ("check_refund_policy", {"order_id": "ORD-1001"}),
            ("issue_refund", {"order_id": "ORD-1001", "amount": 129.0}),
        ])
        bad, reg2 = make_result(tool_calls=[
            ("issue_refund", {"order_id": "ORD-1001", "amount": 129.0}),
        ])
        task = {"checks": [{"type": "sequence", "first": "check_refund_policy",
                            "then": "issue_refund", "desc": "order"}]}
        self.assertTrue(evaluate(task, good, reg)[0].passed)
        self.assertFalse(evaluate(task, bad, reg2)[0].passed)

    def test_output_contains_case_insensitive(self):
        result, registry = make_result(final_answer="Your REFUND is on the way.")
        task = {"checks": [{"type": "output_contains", "pattern": "refund", "desc": "m"}]}
        self.assertTrue(evaluate(task, result, registry)[0].passed)

    def test_max_words(self):
        result, registry = make_result(final_answer="one two three four five")
        task = {"checks": [{"type": "max_words", "n": 4, "desc": "short"}]}
        self.assertFalse(evaluate(task, result, registry)[0].passed)

    def test_refunds_eligible_catches_ineligible(self):
        result, registry = make_result(tool_calls=[("issue_refund", {"order_id": "ORD-1003", "amount": 49.0})])
        task = {"checks": [{"type": "refunds_eligible", "desc": "eligible"}]}
        (outcome,) = evaluate(task, result, registry)
        self.assertFalse(outcome.passed)
        self.assertIn("ORD-1003", outcome.detail)

    def test_refunds_eligible_passes_when_nothing_issued(self):
        result, registry = make_result()
        task = {"checks": [{"type": "refunds_eligible", "desc": "eligible"}]}
        self.assertTrue(evaluate(task, result, registry)[0].passed)

    def test_unknown_check_type_fails_loudly(self):
        result, registry = make_result()
        task = {"checks": [{"type": "nope", "desc": "mystery"}]}
        (outcome,) = evaluate(task, result, registry)
        self.assertFalse(outcome.passed)
        self.assertIn("Unknown check type", outcome.detail)


if __name__ == "__main__":
    unittest.main()
