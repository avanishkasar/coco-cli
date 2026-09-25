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

import os
from typing import Generator

import requests
from dotenv import load_dotenv
from snowflake.snowpark import Session

load_dotenv()

PAT    = os.getenv("SENTINEL_REG_PAT")
HOST   = os.getenv("SENTINEL_REG_HOST")
DB     = os.getenv("SNOWFLAKE_DATABASE", "SENTINEL_REG")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "DATA")

ANALYST_URL = f"https://{HOST}/api/v2/cortex/analyst/message"
SEMANTIC_MODEL_FILE = f"@{DB.lower()}.{SCHEMA.lower()}.models/aml_risk_model.yaml"


def _get_session() -> Session:
    return Session.builder.configs(
        {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE", "SENTINEL_REG_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "SENTINEL_REG_WH"),
            "database": DB,
            "schema": SCHEMA,
        }
    ).create()


def build_message(role: str, text: str) -> dict:
    return {"role": role, "content": [{"type": "text", "text": text}]}


def stream_agent_response(
    conversation_history: list[dict],
) -> Generator[dict, None, None]:
    """
    Yields structured event dicts:
        { "type": str, "data": any }
    Types: text | sql | table | error | done
    """
    payload = {
        "messages": conversation_history,
        "semantic_model_file": SEMANTIC_MODEL_FILE,
    }

    try:
        resp = requests.post(
            ANALYST_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {PAT}",
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
            session = _get_session()
            df = session.sql(sql_statement).to_pandas()
            yield {"type": "table", "data": df}
        except Exception as exc:
            yield {"type": "error", "data": f"Query execution failed: {exc}"}

    yield {"type": "done", "data": None}
