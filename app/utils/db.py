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
_CFG_KEY = "_sr_connection_cfg"


def env(name: str, default: str | None = None) -> str | None:
    """Environment value with template placeholders treated as unset."""
    value = os.getenv(name, default)
    if value is None or value.strip().lower() in _PLACEHOLDERS:
        return default
    return value.strip()


def demo_forced() -> bool:
    return (os.getenv("SENTINEL_DEMO_MODE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _connection_config(use_pat: bool = False) -> tuple[dict | None, str | None]:
    account = env("SNOWFLAKE_ACCOUNT")
    user = env("SNOWFLAKE_USER")
    password = env("SNOWFLAKE_PASSWORD")
    pat = env("SENTINEL_REG_PAT")

    # Preferred: password. Fallback: the same programmatic access token that
    # authenticates Cortex Analyst, passed to Snowpark as a PAT.
    use_pat = use_pat or (not password and bool(pat))
    missing = [
        name
        for name, value in (
            ("SNOWFLAKE_ACCOUNT", account),
            ("SNOWFLAKE_USER", user),
            ("SNOWFLAKE_PASSWORD or SENTINEL_REG_PAT", pat if use_pat else password),
        )
        if not value
    ]
    if missing:
        return None, f"Missing credentials: {', '.join(missing)}."

    cfg = {
        "account": account,
        "user": user,
        "role": env("SNOWFLAKE_ROLE", "SENTINEL_REG_ROLE"),
        "warehouse": env("SNOWFLAKE_WAREHOUSE", "SENTINEL_REG_WH"),
        "database": env("SNOWFLAKE_DATABASE", "SENTINEL_REG"),
        "schema": env("SNOWFLAKE_SCHEMA", "DATA"),
    }
    if use_pat:
        cfg.update({"authenticator": "PROGRAMMATIC_ACCESS_TOKEN", "token": pat})
    else:
        cfg["password"] = password
    return cfg, None


@st.cache_resource(show_spinner=False)
def _session_for(**cfg):
    from snowflake.snowpark import Session

    return Session.builder.configs({**cfg, "login_timeout": 20}).create()


def _short(exc: Exception, limit: int = 220) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _try_connect(cfg: dict) -> dict:
    try:
        _session_for(**cfg)
        st.session_state[_CFG_KEY] = cfg
        return {"live": True, "reason": None}
    except Exception as exc:  # noqa: BLE001 — any connector failure means "not live"
        return {"live": False, "reason": f"Snowflake connection failed: {_short(exc)}"}


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
        status = _try_connect(cfg)
        if not status["live"] and "password" in cfg and env("SENTINEL_REG_PAT"):
            pat_cfg, _ = _connection_config(use_pat=True)
            retry = _try_connect(pat_cfg) if pat_cfg else status
            status = retry if retry["live"] else status

    st.session_state[_STATUS_KEY] = status
    return status


def is_live() -> bool:
    return connection_status()["live"]


def reset_connection() -> None:
    st.session_state.pop(_STATUS_KEY, None)
    st.session_state.pop(_CFG_KEY, None)
    _session_for.clear()


def get_snowflake_session():
    """Open Snowpark session, or RuntimeError explaining why there isn't one."""
    status = connection_status()
    if not status["live"]:
        raise RuntimeError(status["reason"])
    cfg = st.session_state.get(_CFG_KEY)
    if not cfg:
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
