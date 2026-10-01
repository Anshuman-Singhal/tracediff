"""Demo agents driven by explicit, inspectable policies.

These agents are deterministic stand-ins, not LLMs: each one runs a real
ReAct-style loop (decide, call tool, read observation, repeat) against the
tool registry, but the "brain" is a plain decision function so the whole
harness can run offline with zero dependencies.

The thoughts are templated and labeled as simulated reasoning. The point of
the demo is the harness (execution, evaluation, diffing), not the agents.

Two versions ship:
  v1: careful support agent. Checks the refund policy before issuing refunds,
      looks up the knowledge base first, escalates uncertain cases.
  v2: a "prompt optimization" gone wrong. Skips verification, skips KB
      lookups, and writes verbose answers. The differ should catch its
      regressions.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Any

from .agent import AgentResult, Step
from .tools import ORDERS, ToolRegistry, refund_eligible


@dataclass
class Decision:
    thought: str  # simulated reasoning, templated by the policy
    tool: str | None
    args: dict[str, Any]
    final_answer: str | None  # set when the agent is done with the task


@dataclass(frozen=True)
class Policy:
    name: str
    verify_before_refund: bool = True
    lookup_kb_first: bool = True
    escalate_when_uncertain: bool = True
    verbose: bool = False
    max_steps: int = 8


POLICIES: dict[str, Policy] = {
    "v1": Policy(name="support-agent v1"),
    "v2": Policy(
        name="support-agent v2",
        verify_before_refund=False,
        lookup_kb_first=False,
        verbose=True,
    ),
}


def classify_intent(message: str) -> str:
    m = message.lower()
    if any(k in m for k in ("refund", "money back", "charged")):
        return "refund"
    if "cancel" in m:
        return "cancel"
    if any(k in m for k in ("how do i", "how to", "reset")):
        return "howto"
    if any(k in m for k in ("bug", "broken", "not working", "error")):
        return "bug"
    if "account" in m:
        return "account"
    return "unknown"


def simulated_latency(tool: str, step_index: int) -> float:
    """Deterministic fake latency so runs are reproducible."""
    return 120.0 + (zlib.crc32(f"{tool}:{step_index}".encode()) % 380)


class PolicyAgent:
    """Runs the ReAct loop using a fixed decision policy."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    @property
    def name(self) -> str:
        return self.policy.name

    def run(self, task: dict[str, Any], tools: ToolRegistry) -> AgentResult:
        intent = classify_intent(task["message"])
        state: dict[str, Any] = {}
        steps: list[Step] = []
        tokens_in = 0
        tokens_out = 0
        final_answer = ""

        decide = {
            "refund": self._decide_refund,
            "cancel": self._decide_cancel,
            "howto": self._decide_howto,
            "bug": self._decide_bug,
            "account": self._decide_account,
            "unknown": self._decide_unknown,
        }[intent]

        while sum(1 for s in steps if s.tool) < self.policy.max_steps:
            d = decide(task, steps, state)
            tokens_in += len(d.thought) // 4 + 8
            if d.final_answer is not None:
                final_answer = d.final_answer
                tokens_out += len(final_answer) // 4
                steps.append(
                    Step(
                        thought=d.thought,
                        tool=None,
                        args={},
                        observation="",
                        latency_ms=0.0,
                    )
                )
                break
            assert d.tool is not None
            observation = tools.call(d.tool, d.args)
            latency = simulated_latency(d.tool, len(steps))
            tokens_out += len(d.thought) // 4
            tokens_in += len(observation) // 4
            steps.append(
                Step(
                    thought=d.thought,
                    tool=d.tool,
                    args=dict(d.args),
                    observation=observation,
                    latency_ms=latency,
                )
            )
        else:
            final_answer = (
                "I have reached my step limit, so I am escalating this to a "
                "human who will follow up with you."
            )

        return AgentResult(
            task_id=task["id"],
            final_answer=final_answer,
            steps=steps,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    # -- intent handlers -------------------------------------------------

    def _decide_refund(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        p = self.policy
        oid = task.get("order_id", "")
        tool_steps = [s for s in steps if s.tool]

        if any(s.tool == "issue_refund" for s in tool_steps):
            amount = ORDERS.get(oid, {}).get("amount", 0.0)
            return Decision(
                thought="Refund issued. Wrapping up with a confirmation.",
                tool=None,
                args={},
                final_answer=self._refund_confirmation(oid, amount),
            )
        if any(s.tool == "escalate" for s in tool_steps):
            reason = state.get("policy_reason", "our refund policy")
            return Decision(
                thought="Already escalated. Wrapping up.",
                tool=None,
                args={},
                final_answer=self._ineligible_answer(oid, reason),
            )
        if p.lookup_kb_first and "kb" not in state:
            state["kb"] = True
            return Decision(
                thought="Customer is asking for a refund. I will check the refund policy article first.",
                tool="search_kb",
                args={"query": "refund policy"},
                final_answer=None,
            )
        if "order" not in state:
            state["order"] = True
            return Decision(
                thought="I need the order details before I can act on this refund request.",
                tool="lookup_order",
                args={"order_id": oid},
                final_answer=None,
            )
        if p.verify_before_refund and "policy" not in state:
            state["policy"] = True
            return Decision(
                thought="I must verify refund eligibility against the policy before issuing anything.",
                tool="check_refund_policy",
                args={"order_id": oid},
                final_answer=None,
            )
        if p.verify_before_refund:
            policy_step = next(
                s for s in tool_steps if s.tool == "check_refund_policy"
            )
            eligible = "ELIGIBLE." in policy_step.observation and "NOT ELIGIBLE" not in policy_step.observation
            _, reason = refund_eligible(oid)
            state["policy_reason"] = reason
            if eligible:
                amount = ORDERS[oid]["amount"]
                return Decision(
                    thought="The order is eligible. Issuing the refund now.",
                    tool="issue_refund",
                    args={"order_id": oid, "amount": amount},
                    final_answer=None,
                )
            if p.escalate_when_uncertain:
                return Decision(
                    thought="The order is not eligible under the policy. Escalating to a human rather than guessing.",
                    tool="escalate",
                    args={"reason": f"Refund requested for {oid}; not eligible: {reason}"},
                    final_answer=None,
                )
            return Decision(
                thought="The order is not eligible, so I cannot issue a refund.",
                tool=None,
                args={},
                final_answer=self._ineligible_answer(oid, reason),
            )
        amount = ORDERS.get(oid, {}).get("amount", 0.0)
        return Decision(
            thought="Issuing the refund for the customer.",
            tool="issue_refund",
            args={"order_id": oid, "amount": amount},
            final_answer=None,
        )

    def _decide_cancel(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        p = self.policy
        if p.lookup_kb_first and "kb" not in state:
            state["kb"] = True
            return Decision(
                thought="The customer wants to cancel. I will pull up the cancellation article.",
                tool="search_kb",
                args={"query": "cancel subscription"},
                final_answer=None,
            )
        return Decision(
            thought="Answering with the cancellation steps.",
            tool=None,
            args={},
            final_answer=self._cancel_answer(),
        )

    def _decide_howto(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        p = self.policy
        if p.lookup_kb_first and "kb" not in state:
            state["kb"] = True
            query = (
                "reset password"
                if "password" in task["message"].lower()
                else "general help"
            )
            return Decision(
                thought="This is a how-to question. I will search the knowledge base for the right article.",
                tool="search_kb",
                args={"query": query},
                final_answer=None,
            )
        if p.verbose and "kb2" not in state:
            state["kb2"] = True
            return Decision(
                thought="Let me also check the troubleshooting article to be thorough.",
                tool="search_kb",
                args={"query": "troubleshooting"},
                final_answer=None,
            )
        return Decision(
            thought="I found the relevant article. Answering the customer now.",
            tool=None,
            args={},
            final_answer=self._howto_answer(),
        )

    def _decide_bug(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        p = self.policy
        if p.lookup_kb_first and "kb" not in state:
            state["kb"] = True
            return Decision(
                thought="The customer reports a bug. I will check the troubleshooting guide, then escalate to engineering.",
                tool="search_kb",
                args={"query": "troubleshooting"},
                final_answer=None,
            )
        if "esc" not in state:
            state["esc"] = True
            return Decision(
                thought="This needs engineering. Escalating with the details the customer provided.",
                tool="escalate",
                args={"reason": "Dashboard export error reported by customer"},
                final_answer=None,
            )
        return Decision(
            thought="Escalated to engineering. Confirming with the customer.",
            tool=None,
            args={},
            final_answer=(
                "I have escalated this to our engineering team and opened a "
                "ticket with the error details you shared. They will investigate "
                "and follow up with you directly."
            ),
        )

    def _decide_account(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        if "acct" not in state:
            state["acct"] = True
            return Decision(
                thought="Account question. I will look up the account status.",
                tool="get_account_status",
                args={"user_id": task.get("user_id", "")},
                final_answer=None,
            )
        status = next(
            (s.observation for s in steps if s.tool == "get_account_status"),
            "unavailable",
        )
        return Decision(
            thought="Answering with the account status.",
            tool=None,
            args={},
            final_answer=f"Here is what I see on your account: {status}",
        )

    def _decide_unknown(
        self, task: dict[str, Any], steps: list[Step], state: dict[str, Any]
    ) -> Decision:
        if "esc" not in state:
            state["esc"] = True
            return Decision(
                thought="I do not recognize this request type. Escalating to a human.",
                tool="escalate",
                args={"reason": f"Unrecognized request: {task['message'][:80]}"},
                final_answer=None,
            )
        return Decision(
            thought="Escalated. Confirming with the customer.",
            tool=None,
            args={},
            final_answer=(
                "I want to make sure you get the right help, so I have escalated "
                "this to our support team. Someone will follow up shortly."
            ),
        )

    # -- answer templates ------------------------------------------------

    def _refund_confirmation(self, order_id: str, amount: float) -> str:
        if self.policy.verbose:
            return (
                f"All set! I have gone ahead and issued a refund of ${amount:.2f} "
                f"for order {order_id} on your behalf. It should show up on your "
                "original payment method within 5 to 10 business days, though it "
                "can occasionally take a touch longer depending on your bank. "
                "Thanks so much for being a customer, and please do not hesitate "
                "to reach out if there is anything else I can help with at all."
            )
        return (
            f"Done. I have issued a refund of ${amount:.2f} for order {order_id}. "
            "It should appear within 5 to 10 business days."
        )

    def _ineligible_answer(self, order_id: str, reason: str) -> str:
        return (
            f"I checked order {order_id} against our refund policy: it is not "
            f"eligible ({reason}). I have escalated your request to our support "
            "team, and someone will follow up within one business day."
        )

    def _cancel_answer(self) -> str:
        base = (
            "I can help with that. To cancel your subscription: go to Settings, "
            "then Billing, then Cancel plan. The cancellation takes effect at "
            "the end of your current billing period."
        )
        if self.policy.verbose:
            base += (
                " I completely understand wanting to make a change, and I want to "
                "reassure you that there are no hidden fees or complicated steps "
                "involved here whatsoever. If you change your mind later, you are "
                "always welcome to come back and reactivate whenever you like."
            )
        return base

    def _howto_answer(self) -> str:
        if self.policy.verbose:
            return (
                "Thanks so much for reaching out, and I completely understand how "
                "frustrating it can be when you cannot get into your account, so "
                "let me walk you through exactly how to reset your password step "
                "by step. First, head over to the login page and look for the "
                "small 'Forgot password' link right underneath the sign-in button, "
                "then go ahead and click it. We will send a reset link to the "
                "email address on your account within a couple of minutes, though "
                "I would recommend checking your spam folder just in case it "
                "lands there. Once you get the email, click the link and choose "
                "a new password, keeping in mind that these links expire after "
                "60 minutes for your security. If the link has already expired "
                "or you do not see the email after a few minutes, just let me "
                "know and I will happily resend it or look into your account "
                "directly. I hope that gets you back in quickly, and please do "
                "not hesitate to reply if anything else comes up at all."
            )
        return (
            "To reset your password: click 'Forgot password' on the login page, "
            "then follow the link in the email we send you. Links expire after "
            "60 minutes, so use it promptly."
        )
