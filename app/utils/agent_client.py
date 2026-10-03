"""
Agent client — calls the Cortex Analyst REST API directly and executes
the SQL it generates via Snowpark.

Cortex Agents (the multi-tool orchestration object) is not available on
trial accounts ("Access denied for trial accounts"). Cortex Analyst
(text-to-SQL) is a lower-level primitive that is available, so this client
talks to it directly: it converts the user's question into SQL against
semantic_model/aml_risk_model.yaml, runs that SQL, and returns both the
explanation and the resulting rows.
"""

from typing import Generator

import requests
from dotenv import load_dotenv

from utils import db as _db
from utils.db import env, is_live

load_dotenv()


def _config() -> dict:
    """
    Reads connection config fresh on every call rather than caching it at
    module-import time. On Streamlit Cloud, secrets can be injected into
    the environment after this module is first imported (or updated later
    without a full cold restart); caching these as module-level constants
    meant a stale/empty PAT could get baked in for the life of the running
    process, causing every request to silently send "Bearer None".
    """
    db = env("SNOWFLAKE_DATABASE", "SENTINEL_REG")
    schema = env("SNOWFLAKE_SCHEMA", "DATA")
    host = env("SENTINEL_REG_HOST")
    if host:
        host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    return {
        "pat": env("SENTINEL_REG_PAT"),
        "host": host,
        "db": db,
        "schema": schema,
        "analyst_url": f"https://{host}/api/v2/cortex/analyst/message",
        "semantic_model_file": f"@{db.lower()}.{schema.lower()}.models/aml_risk_model.yaml",
    }


def analyst_available() -> bool:
    """Cortex Analyst needs a PAT + host to generate SQL and a live Snowpark session to run it."""
    cfg = _config()
    return bool(cfg["pat"] and cfg["host"]) and is_live()


def build_message(role: str, text: str, sql: str | None = None) -> dict:
    """
    One turn in Cortex Analyst's request format. The API only accepts the
    roles "user" and "analyst"; "assistant" is mapped for older callers.
    """
    role = "analyst" if role == "assistant" else role
    content = [{"type": "text", "text": text or ("Here is the result." if role == "analyst" else "")}]
    if role == "analyst" and sql:
        content.append({"type": "sql", "statement": sql})
    return {"role": role, "content": content}


def _normalise_roles(history: list[dict]) -> list[dict]:
    out = []
    for msg in history:
        msg = dict(msg)
        if msg.get("role") == "assistant":
            msg["role"] = "analyst"
        out.append(msg)
    return out


def stream_agent_response(
    conversation_history: list[dict],
) -> Generator[dict, None, None]:
    """
    Yields structured event dicts:
        { "type": str, "data": any }
    Types: text | sql | table | error | done
    """
    cfg = _config()

    if not cfg["pat"] or not cfg["host"]:
        yield {
            "type": "error",
            "data": (
                "SENTINEL_REG_PAT or SENTINEL_REG_HOST is not set in this environment. "
                "Check your .env (local) or app secrets (Streamlit Cloud: Settings → Secrets)."
            ),
        }
        yield {"type": "done", "data": None}
        return

    payload = {
        "messages": _normalise_roles(conversation_history),
        "semantic_model_file": cfg["semantic_model_file"],
    }

    try:
        resp = requests.post(
            cfg["analyst_url"],
            json=payload,
            headers={
                "Authorization": f"Bearer {cfg['pat']}",
                "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc)) if hasattr(exc, "response") and exc.response is not None else str(exc)
        yield {"type": "error", "data": f"{exc} — {detail[:500]}"}
        yield {"type": "done", "data": None}
        return

    body = resp.json()
    content = body.get("message", {}).get("content", [])

    sql_statement = None
    for item in content:
        item_type = item.get("type")
        if item_type == "text":
            yield {"type": "text", "data": item.get("text", "")}
        elif item_type == "sql":
            sql_statement = item.get("statement", "")
            yield {"type": "sql", "data": sql_statement}
        elif item_type == "suggestions":
            suggestions = item.get("suggestions", [])
            if suggestions:
                yield {
                    "type": "text",
                    "data": "\n\nDid you mean:\n" + "\n".join(f"- {s}" for s in suggestions),
                }

    if sql_statement:
        try:
            session = _db.get_snowflake_session()
            df = session.sql(sql_statement).to_pandas()
            yield {"type": "table", "data": df}
        except Exception as exc:
            yield {"type": "error", "data": f"Query execution failed: {exc}"}

    yield {"type": "done", "data": None}
