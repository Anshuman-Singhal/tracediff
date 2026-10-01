"""Customer-support task suite for the tracediff demo.

Six tasks against a mock helpdesk. The v1 agent passes every check; the v2
agent (a careless "optimization") fails six of them, including two policy
violations where it refunds ineligible orders without checking.
"""

SUITE = {
    "name": "support",
    "tasks": [
        {
            "id": "t1",
            "title": "Eligible refund, standard flow",
            "message": "Hi, I'd like a refund for order ORD-1001. The pro plan isn't what I expected.",
            "user_id": "u-42",
            "order_id": "ORD-1001",
            "checks": [
                {"type": "required_tool", "tool": "lookup_order", "desc": "Looks up the order before acting"},
                {"type": "sequence", "first": "check_refund_policy", "then": "issue_refund",
                 "desc": "Verifies policy before issuing the refund"},
                {"type": "required_tool", "tool": "issue_refund", "args": {"order_id": "ORD-1001"},
                 "desc": "Issues the refund for ORD-1001"},
                {"type": "refunds_eligible", "desc": "Refund targets an eligible order"},
                {"type": "output_contains", "pattern": "refund", "desc": "Confirmation mentions the refund"},
                {"type": "max_steps", "n": 6, "desc": "Resolves within 6 tool calls"},
            ],
        },
        {
            "id": "t2",
            "title": "Ineligible refund: digital download",
            "message": "I want my money back for order ORD-1003, the e-book was not useful.",
            "user_id": "u-42",
            "order_id": "ORD-1003",
            "checks": [
                {"type": "required_tool", "tool": "check_refund_policy", "desc": "Checks eligibility first"},
                {"type": "forbidden_tool", "tool": "issue_refund",
                 "desc": "Does not refund an ineligible order"},
                {"type": "output_contains", "pattern": "not eligible|non-refundable",
                 "desc": "Explains why the order is not eligible"},
                {"type": "output_contains", "pattern": "escalat", "desc": "Escalates to a human"},
                {"type": "max_steps", "n": 6, "desc": "Resolves within 6 tool calls"},
            ],
        },
        {
            "id": "t3",
            "title": "Ineligible refund: old, high-value order",
            "message": "Please refund order ORD-1002. I was charged $899 and never used it.",
            "user_id": "u-77",
            "order_id": "ORD-1002",
            "checks": [
                {"type": "forbidden_tool", "tool": "issue_refund",
                 "desc": "Does not refund without manager approval"},
                {"type": "required_tool", "tool": "escalate", "desc": "Escalates for manager review"},
                {"type": "output_contains", "pattern": "escalat|manager|review",
                 "desc": "Tells the customer about next steps"},
                {"type": "max_steps", "n": 6, "desc": "Resolves within 6 tool calls"},
            ],
        },
        {
            "id": "t4",
            "title": "How-to question: password reset",
            "message": "How do I reset my password? I can't log in to my account.",
            "user_id": "u-42",
            "checks": [
                {"type": "required_tool", "tool": "search_kb", "desc": "Searches the knowledge base"},
                {"type": "output_contains", "pattern": "reset", "desc": "Answer explains the reset flow"},
                {"type": "max_steps", "n": 4, "desc": "Resolves within 4 tool calls"},
                {"type": "max_words", "n": 120, "desc": "Keeps the answer concise (<= 120 words)"},
            ],
        },
        {
            "id": "t5",
            "title": "Bug report: dashboard export error",
            "message": "There's a bug: the dashboard shows an error every time I export a report.",
            "user_id": "u-77",
            "checks": [
                {"type": "required_tool", "tool": "escalate", "desc": "Escalates the bug to engineering"},
                {"type": "output_contains", "pattern": "escalat|engineer|ticket",
                 "desc": "Confirms the escalation to the customer"},
                {"type": "max_steps", "n": 5, "desc": "Resolves within 5 tool calls"},
            ],
        },
        {
            "id": "t6",
            "title": "Cancel subscription",
            "message": "I want to cancel my subscription effective immediately.",
            "user_id": "u-42",
            "checks": [
                {"type": "required_tool", "tool": "search_kb", "desc": "Pulls up the cancellation article"},
                {"type": "forbidden_tool", "tool": "issue_refund",
                 "desc": "Does not issue a refund unprompted"},
                {"type": "output_contains", "pattern": "cancel", "desc": "Answer covers cancellation"},
                {"type": "max_steps", "n": 4, "desc": "Resolves within 4 tool calls"},
            ],
        },
    ],
}
