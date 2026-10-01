"""Mock customer-support tool registry for the demo suite.

These tools stand in for real helpdesk APIs. The runner creates a fresh
registry for every task, so side effects (refunds, escalations) never leak
between tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

KB = {
    "refund policy": (
        "Refund policy: orders are eligible for a refund within 30 days of "
        "purchase when the total is under $500. Orders over $500 need manager "
        "approval. Digital downloads (e-books, templates) are non-refundable."
    ),
    "cancel subscription": (
        "To cancel: go to Settings > Billing > Cancel plan. Cancellation takes "
        "effect at the end of the current billing period. Annual plans cancelled "
        "within 30 days qualify for a prorated refund."
    ),
    "reset password": (
        "To reset a password: click 'Forgot password' on the login page, then "
        "follow the email link. Links expire after 60 minutes."
    ),
    "troubleshooting": (
        "For dashboard errors: clear cache, retry, and capture the error code. "
        "If the error persists, escalate to engineering with the code and timestamp."
    ),
}

ORDERS = {
    "ORD-1001": {
        "user_id": "u-42",
        "amount": 129.00,
        "days_ago": 12,
        "item": "Pro plan (annual)",
        "digital": False,
    },
    "ORD-1002": {
        "user_id": "u-77",
        "amount": 899.00,
        "days_ago": 40,
        "item": "Enterprise add-on",
        "digital": False,
    },
    "ORD-1003": {
        "user_id": "u-42",
        "amount": 49.00,
        "days_ago": 5,
        "item": "E-book: Growth Playbook",
        "digital": True,
    },
}

ACCOUNT_STATUS = {
    "u-42": "Active Pro plan, renews 2027-01-15, billing current.",
    "u-77": "Active Enterprise trial, ends 2026-10-05, card on file.",
}


def refund_eligible(order_id: str) -> tuple[bool, str]:
    """Return (eligible, reason) for a refund request on an order."""
    order = ORDERS.get(order_id)
    if order is None:
        return False, f"Order {order_id} was not found."
    if order["digital"]:
        return False, f"Order {order_id} is a digital download and is non-refundable."
    if order["days_ago"] > 30:
        return (
            False,
            f"Order {order_id} is {order['days_ago']} days old, past the 30-day window.",
        )
    if order["amount"] > 500:
        return (
            False,
            f"Order {order_id} totals ${order['amount']:.2f} and needs manager approval.",
        )
    return True, f"Order {order_id} is eligible for a refund of ${order['amount']:.2f}."


@dataclass
class ToolRegistry:
    """Dispatches tool calls and records every invocation."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    refunds: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[dict[str, Any]] = field(default_factory=list)

    def call(self, name: str, args: dict[str, Any]) -> str:
        handler = self._handlers().get(name)
        if handler is None:
            observation = f"Error: unknown tool '{name}'."
        else:
            try:
                observation = handler(**args)
            except TypeError as exc:
                observation = f"Error calling {name}: {exc}"
        self.calls.append({"tool": name, "args": dict(args), "observation": observation})
        return observation

    def _handlers(self) -> dict[str, Callable[..., str]]:
        return {
            "search_kb": self.search_kb,
            "lookup_order": self.lookup_order,
            "check_refund_policy": self.check_refund_policy,
            "issue_refund": self.issue_refund,
            "escalate": self.escalate,
            "get_account_status": self.get_account_status,
        }

    # -- tools -----------------------------------------------------------

    def search_kb(self, query: str) -> str:
        q = query.lower()
        if "refund" in q:
            return KB["refund policy"]
        if "cancel" in q:
            return KB["cancel subscription"]
        if "password" in q or "reset" in q or "login" in q:
            return KB["reset password"]
        if "troubleshoot" in q or "bug" in q or "error" in q:
            return KB["troubleshooting"]
        return "No knowledge-base article matched that query."

    def lookup_order(self, order_id: str) -> str:
        order = ORDERS.get(order_id)
        if order is None:
            return f"Order {order_id} was not found."
        return (
            f"Order {order_id}: {order['item']}, ${order['amount']:.2f}, "
            f"placed {order['days_ago']} days ago, customer {order['user_id']}."
        )

    def check_refund_policy(self, order_id: str) -> str:
        eligible, reason = refund_eligible(order_id)
        verdict = "ELIGIBLE" if eligible else "NOT ELIGIBLE"
        return f"Policy check for {order_id}: {verdict}. {reason}"

    def issue_refund(self, order_id: str, amount: float) -> str:
        order = ORDERS.get(order_id)
        if order is None:
            return f"Error: order {order_id} was not found, refund not issued."
        if amount > order["amount"]:
            return (
                f"Error: ${amount:.2f} exceeds the order total of "
                f"${order['amount']:.2f}, refund not issued."
            )
        self.refunds.append({"order_id": order_id, "amount": amount})
        return f"Refund of ${amount:.2f} issued for order {order_id}."

    def escalate(self, reason: str) -> str:
        self.escalations.append({"reason": reason})
        return f"Escalated to human support: {reason}"

    def get_account_status(self, user_id: str) -> str:
        return ACCOUNT_STATUS.get(user_id, f"No account found for {user_id}.")
