"""
Agent client — wraps Snowflake Cortex Agent REST API
with streaming SSE support.
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Generator

import requests
import sseclient


# ── Config from environment ──────────────────────────────────
PAT    = os.getenv("SENTINEL_REG_PAT")
HOST   = os.getenv("SENTINEL_REG_HOST")
DB     = os.getenv("SENTINEL_REG_AGENT_DB",     "SNOWFLAKE_INTELLIGENCE")
SCHEMA = os.getenv("SENTINEL_REG_AGENT_SCHEMA",  "AGENTS")
AGENT  = os.getenv("SENTINEL_REG_AGENT_NAME",    "AML_RISK_AGENT")

AGENT_URL = f"https://{HOST}/api/v2/databases/{DB}/schemas/{SCHEMA}/agents/{AGENT}:run"


# ── Message types ────────────────────────────────────────────
@dataclass
class UserMessage:
    text: str

    def to_dict(self) -> dict:
        return {
            "role": "user",
            "content": [{"type": "text", "text": self.text}],
        }


@dataclass
class AgentResponse:
    role: str
    content: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# ── Core streaming call ──────────────────────────────────────
def stream_agent_response(
    conversation_history: list[dict],
) -> Generator[dict, None, None]:
    """
    Sends the conversation history to the Cortex Agent API and
    yields structured event dicts as they stream in.

    Event dict schema:
        { "type": str, "data": any }

    Types: text_delta | thinking | tool_use | tool_result |
           chart | table | status | error | done
    """
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": conversation_history,
    }

    try:
        resp = requests.post(
            url=AGENT_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {PAT}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            stream=True,
            verify=False,
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        yield {"type": "error", "data": str(exc)}
        return

    client = sseclient.SSEClient(resp)
    for event in client.events():
        if not event.data or event.data.strip() == "[DONE]":
            break
        try:
            raw = json.loads(event.data)
        except json.JSONDecodeError:
            continue

        match event.event:
            case "response.status":
                yield {"type": "status", "data": raw.get("message", "")}
            case "response.text.delta":
                yield {"type": "text_delta", "data": raw.get("text", "")}
            case "response.thinking.delta":
                yield {"type": "thinking", "data": raw.get("text", "")}
            case "response.tool_use":
                yield {"type": "tool_use", "data": raw}
            case "response.tool_result":
                yield {"type": "tool_result", "data": raw}
            case "response.chart":
                yield {"type": "chart", "data": raw}
            case "response.table":
                yield {"type": "table", "data": raw}
            case "response":
                yield {"type": "done", "data": raw}
            case "error":
                yield {"type": "error", "data": raw.get("message", "Unknown error")}

    yield {"type": "done", "data": None}


def build_message(role: str, text: str) -> dict:
    return {
        "role": role,
        "content": [{"type": "text", "text": text}],
    }
