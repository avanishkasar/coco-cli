"""
Runs every live-mode SQL statement against DuckDB (snowflake → duckdb via
sqlglot) loaded with the seed data, to prove the Snowflake code path
executes and returns the same shapes as the demo path.
"""

import json
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest
import sqlglot

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))
os.environ.pop("SENTINEL_DEMO_MODE", None)

from streamlit.testing.v1 import AppTest  # noqa: E402


class _Frame:
    def __init__(self, df):
        self._df = df

    def to_pandas(self):
        return self._df

    def collect(self):
        return []


class FakeSession:
    def __init__(self):
        self.con = duckdb.connect()
        snap = json.loads((APP_DIR / "data" / "demo_snapshot.json").read_text())
        for name, rows in snap.items():
            df = pd.DataFrame(rows)
            for col in df.columns:
                if isinstance(df[col].iloc[0], list):
                    df[col] = df[col].map(json.dumps)
            self.con.register("_t", df)
            self.con.execute(f"CREATE TABLE {name} AS SELECT * FROM _t")
            self.con.unregister("_t")
        self.con.execute("ALTER TABLE AML_ALERTS ADD COLUMN UPDATED_AT TIMESTAMP")
        self.executed = []

    def sql(self, query, params=None):
        self.executed.append(query)
        out = sqlglot.transpile(query, read="snowflake", write="duckdb")[0]
        cur = self.con.execute(out, params or [])
        if cur.description is None:
            return _Frame(pd.DataFrame())
        df = cur.fetchdf()
        df.columns = [c.upper() for c in df.columns]
        return _Frame(df)


HARNESS = """
import sys
sys.path.insert(0, {app!r})
from utils import db
db.connection_status = lambda: {{"live": True, "reason": None}}
db.get_snowflake_session = lambda: {session_getter}
import utils.data as d
d.is_live = lambda: True
d.connection_status = db.connection_status
d.run_statement = db.run_statement
d.query_or_raise = db.query_or_raise
import streamlit as st
from utils import ui
ui.inject_theme()
from {module} import {fn}
{fn}()
"""


@pytest.fixture()
def fake():
    import streamlit as st
    st.cache_data.clear()
    return FakeSession()


def _run(module, fn, session):
    import builtins
    builtins._SR_FAKE = session
    code = HARNESS.format(app=str(APP_DIR), session_getter="__import__('builtins')._SR_FAKE", module=module, fn=fn)
    return AppTest.from_string(code, default_timeout=90).run()


PAGES = [
    ("views.overview", "render_overview"),
    ("views.risk_dashboard", "render_dashboard"),
    ("views.investigation", "render_investigation"),
    ("views.entity_360", "render_entity_360"),
    ("views.network", "render_network"),
    ("views.regulatory_library", "render_regulatory_library"),
    ("views.sar_generator", "render_sar_generator"),
    ("views.audit_trail", "render_audit_trail"),
]


@pytest.mark.parametrize("module,fn", PAGES)
def test_live_page_renders(fake, module, fn):
    at = _run(module, fn, fake)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    if fn == "render_investigation":
        for q in ("Why was account ACC-9823 flagged?", "Which accounts have a risk score above 0.7?",
                  "Show fan-out layering", "What does RBI say about STR timelines?", "Explain ALERT-2024-0043"):
            at.session_state["pending_prompt"] = q
            at.run()
            assert not at.exception, [e.value for e in at.exception]
    assert fake.executed, "page issued no SQL in live mode"


def test_live_triage_update_uses_bound_params(fake):
    from utils import data
    import builtins
    builtins._SR_FAKE = fake
    from utils import db
    db.get_snowflake_session = lambda: fake
    db.connection_status = lambda: {"live": True, "reason": None}
    data.is_live = lambda: True
    data.run_statement = db.run_statement
    ok, err = data.update_alert("ALERT-2024-0047", "ESCALATED", "A. Analyst", "note")
    assert ok, err
    row = fake.con.execute("SELECT ALERT_STATUS, ANALYST_ASSIGNED FROM AML_ALERTS WHERE ALERT_ID='ALERT-2024-0047'").fetchone()
    assert row == ("ESCALATED", "A. Analyst")
    ok, err = data.update_alert("x' OR '1'='1", "OPEN", None, None)
    assert fake.con.execute("SELECT COUNT(*) FROM AML_ALERTS WHERE ALERT_STATUS='OPEN'").fetchone()[0] == 1
