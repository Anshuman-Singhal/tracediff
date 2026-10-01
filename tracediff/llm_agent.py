"""Optional OpenAI-compatible agent adapter.

This is the bridge from the offline demo to real usage: any LLM agent that can
call tools can be plugged into the harness. It activates only when
OPENAI_API_KEY is set, and the demo never needs it.

It uses only the standard library (urllib) so the project stays
zero-dependency.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from .agent import AgentResult, Step
from .tools import ToolRegistry

TOOL_SCHEMAS = {
    "search_kb": {
        "description": "Search the support knowledge base for an article.",
        "parameters": {"query": "string"},
    },
    "lookup_order": {
        "description": "Look up an order by ID.",
        "parameters": {"order_id": "string"},
    },
    "check_refund_policy": {
        "description": "Check whether an order is eligible for a refund.",
        "parameters": {"order_id": "string"},
    },
    "issue_refund": {
        "description": "Issue a refund for an order. Only call for eligible orders.",
        "parameters": {"order_id": "string", "amount": "number"},
    },
    "escalate": {
        "description": "Escalate the conversation to a human support agent.",
        "parameters": {"reason": "string"},
    },
    "get_account_status": {
        "description": "Get the status of a customer account.",
        "parameters": {"user_id": "string"},
    },
}

SYSTEM_PROMPT = (
    "You are a careful customer-support agent. Always verify the refund policy "
    "with check_refund_policy before issuing any refund, never refund ineligible "
    "orders, and escalate to a human when you are uncertain. Keep answers concise."
)


class OpenAIAgent:
    """ReAct loop around an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        max_steps: int = 8,
    ) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it to use the OpenAI agent, "
                "or use the built-in 'v1' / 'v2' demo agents instead."
            )
        self.key = key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_steps = max_steps

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def _tools_payload(self) -> list[dict[str, Any]]:
        payload = []
        for tool_name, spec in TOOL_SCHEMAS.items():
            payload.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": spec["description"],
                        "parameters": {
                            "type": "object",
                            "properties": {
                                k: {"type": v}
                                for k, v in spec["parameters"].items()
                            },
                            "required": list(spec["parameters"]),
                        },
                    },
                }
            )
        return payload

    def _chat(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps(
            {"model": self.model, "messages": messages, "tools": self._tools_payload()}
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())

    def run(self, task: dict[str, Any], tools: ToolRegistry) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["message"]},
        ]
        steps: list[Step] = []
        tokens_in = 0
        tokens_out = 0
        final_answer = ""

        for _ in range(self.max_steps):
            started = time.perf_counter()
            reply = self._chat(messages)
            latency_ms = (time.perf_counter() - started) * 1000.0
            choice = reply["choices"][0]["message"]
            usage = reply.get("usage", {})
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
            messages.append(choice)

            tool_calls = choice.get("tool_calls") or []
            thought = choice.get("content") or "(no textual reasoning returned)"
            if not tool_calls:
                final_answer = choice.get("content") or ""
                steps.append(
                    Step(thought=thought, tool=None, args={}, observation="", latency_ms=0.0)
                )
                break
            for call in tool_calls:
                name = call["function"]["name"]
                args = json.loads(call["function"].get("arguments") or "{}")
                observation = tools.call(name, args)
                steps.append(
                    Step(
                        thought=thought,
                        tool=name,
                        args=args,
                        observation=observation,
                        latency_ms=latency_ms / max(len(tool_calls), 1),
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": observation,
                    }
                )
        else:
            final_answer = "I have reached my step limit, so I am escalating this to a human."

        return AgentResult(
            task_id=task["id"],
            final_answer=final_answer,
            steps=steps,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
