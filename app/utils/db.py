"""
Snowflake connection layer shared by every page.

The app runs in one of two modes:

* LIVE — a Snowpark session to the SENTINEL_REG database could be opened.
  Every read and write goes to Snowflake.
* DEMO — no usable credentials (or SENTINEL_DEMO_MODE=1). Pages read from
  app/data/demo_snapshot.json instead, which is generated from the exact
  seed data in setup/03 and setup/04, so the demo shows the same records a
  freshly provisioned Snowflake account would.

Connection failures are remembered per browser session so a bad password
doesn't cost a login timeout on every query; "Retry connection" in the
sidebar clears that memory.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

import pandas as pd
import streamlit as st

_PLACEHOLDERS = {
    "",
    "n/a",
    "na",
    "none",
    "your_password",
    "your_username",
    "your_account_identifier",
    "your_personal_access_token",
    "your_account.snowflakecomputing.com",
}
_STATUS_KEY = "_sr_connection_status"


def env(name: str, default: str | None = None) -> str | None:
    """Environment value with template placeholders treated as unset."""
    value = os.getenv(name, default)
    if value is None or value.strip().lower() in _PLACEHOLDERS:
        return default
    return value.strip()


def demo_forced() -> bool:
    return (os.getenv("SENTINEL_DEMO_MODE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _connection_config() -> tuple[dict | None, str | None]:
    account = env("SNOWFLAKE_ACCOUNT")
    user = env("SNOWFLAKE_USER")
    # A programmatic access token is accepted in place of a password by the
    # Snowflake drivers, so the PAT already used for Cortex Analyst doubles
    # as the Snowpark credential when no password is configured.
    password = env("SNOWFLAKE_PASSWORD") or env("SENTINEL_REG_PAT")

    missing = [
        name
        for name, value in (
            ("SNOWFLAKE_ACCOUNT", account),
            ("SNOWFLAKE_USER", user),
            ("SNOWFLAKE_PASSWORD or SENTINEL_REG_PAT", password),
        )
        if not value
    ]
    if missing:
        return None, f"Missing credentials: {', '.join(missing)}."

    return {
        "account": account,
        "user": user,
        "password": password,
        "role": env("SNOWFLAKE_ROLE", "SENTINEL_REG_ROLE"),
        "warehouse": env("SNOWFLAKE_WAREHOUSE", "SENTINEL_REG_WH"),
        "database": env("SNOWFLAKE_DATABASE", "SENTINEL_REG"),
        "schema": env("SNOWFLAKE_SCHEMA", "DATA"),
    }, None


@st.cache_resource(show_spinner=False)
def _session_for(account, user, password, role, warehouse, database, schema):
    from snowflake.snowpark import Session

    return Session.builder.configs({
        "account": account,
        "user": user,
        "password": password,
        "role": role,
        "warehouse": warehouse,
        "database": database,
        "schema": schema,
        "login_timeout": 20,
    }).create()


def _short(exc: Exception, limit: int = 220) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def connection_status() -> dict:
    """{'live': bool, 'reason': str | None} — cached for the browser session."""
    if demo_forced():
        return {"live": False, "reason": "Demo mode is switched on (SENTINEL_DEMO_MODE)."}

    cached = st.session_state.get(_STATUS_KEY)
    if cached is not None:
        return cached

    cfg, error = _connection_config()
    if error:
        status = {"live": False, "reason": error}
    else:
        try:
            _session_for(**cfg)
            status = {"live": True, "reason": None}
        except Exception as exc:  # noqa: BLE001 — any connector failure means "not live"
            status = {"live": False, "reason": f"Snowflake connection failed: {_short(exc)}"}

    st.session_state[_STATUS_KEY] = status
    return status


def is_live() -> bool:
    return connection_status()["live"]


def reset_connection() -> None:
    st.session_state.pop(_STATUS_KEY, None)
    _session_for.clear()


def get_snowflake_session():
    """Open Snowpark session, or RuntimeError explaining why there isn't one."""
    status = connection_status()
    if not status["live"]:
        raise RuntimeError(status["reason"])
    cfg, error = _connection_config()
    if error:
        raise RuntimeError(error)
    return _session_for(**cfg)


def _is_expired(exc: Exception) -> bool:
    text = str(exc).lower()
    return "390114" in text or "token has expired" in text or "session no longer exists" in text


def query_or_raise(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame; raises on any failure."""
    for attempt in (1, 2):
        try:
            return get_snowflake_session().sql(sql, params=list(params) if params else None).to_pandas()
        except Exception as exc:
            if attempt == 1 and _is_expired(exc):
                _session_for.clear()
                continue
            raise
    return pd.DataFrame()


def run_query(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    """Run a SELECT; on failure show the error and return an empty frame."""
    if not is_live():
        return pd.DataFrame()
    try:
        return query_or_raise(sql, params)
    except Exception as exc:
        st.error(f"Query error: {_short(exc, 400)}")
        return pd.DataFrame()


def run_statement(sql: str, params: Sequence[Any] | None = None) -> tuple[bool, str | None]:
    """Run DML/DDL. Returns (ok, error_message)."""
    if not is_live():
        return False, connection_status()["reason"]
    for attempt in (1, 2):
        try:
            get_snowflake_session().sql(sql, params=list(params) if params else None).collect()
            return True, None
        except Exception as exc:
            if attempt == 1 and _is_expired(exc):
                _session_for.clear()
                continue
            return False, _short(exc, 400)
    return False, "Unknown error"
