"""
End-to-end smoke tests: every page renders in demo mode without exceptions,
and the core flows (triage → SAR → audit chain) work.

Run from the repo root:  SENTINEL_DEMO_MODE=1 pytest tests/
"""

import os
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))
os.environ["SENTINEL_DEMO_MODE"] = "1"

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = {
    "overview": ("views.overview", "render_overview"),
    "triage": ("views.risk_dashboard", "render_dashboard"),
    "copilot": ("views.investigation", "render_investigation"),
    "entity": ("views.entity_360", "render_entity_360"),
    "network": ("views.network", "render_network"),
    "regulatory": ("views.regulatory_library", "render_regulatory_library"),
    "sar": ("views.sar_generator", "render_sar_generator"),
    "audit": ("views.audit_trail", "render_audit_trail"),
}

HARNESS = """
import sys
sys.path.insert(0, {app!r})
from utils import ui
ui.inject_theme()
from {module} import {fn}
{fn}()
"""


def page_app(page: str) -> AppTest:
    module, fn = PAGES[page]
    at = AppTest.from_string(HARNESS.format(app=str(APP_DIR), module=module, fn=fn), default_timeout=90)
    return at.run()


def test_main_entrypoint_renders_overview():
    at = AppTest.from_file(str(APP_DIR / "main.py"), default_timeout=90).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Compliance Command Center" in m.value for m in at.markdown)


@pytest.mark.parametrize("page", list(PAGES))
def test_page_renders(page):
    at = page_app(page)
    assert not at.exception, [e.value for e in at.exception]


def _btn(at, label_part):
    return next(b for b in at.button if label_part in b.label)


def test_copilot_offline_answers():
    from utils import copilot_offline
    from utils.copilot_offline import answer

    cases = {
        "Why was account ACC-9823 flagged for AML?": "entity",
        "Which accounts have a risk score above 0.7?": "risk_score",
        "List all open CRITICAL alerts with their total amounts": "alerts",
        "What does RBI say about suspicious transaction reporting timelines?": "regulatory",
        "Summarise the round-trip transfer pattern on account ACC-0009": "entity",
        "How many cash deposits were made just below ₹50,000 this month?": "structuring",
        "Show all structuring transactions in the last 30 days": "structuring",
        "What is the regulatory definition of structuring under RBI guidelines?": "regulatory",
        "Show fan-out / layering activity": "fan_out",
        "Which customers are PEPs or sanctions matches?": "pep",
        "Explain ALERT-2024-0043": "alert",
    }
    at = AppTest.from_string("import sys\nsys.path.insert(0, %r)\nimport streamlit as st\n"
                             "from utils.copilot_offline import answer\n"
                             "for q in st.session_state.get('qs', []):\n    r = answer(q)\n"
                             "    st.write(q + '||' + r['intent'] + '||' + r['text'][:60])\n" % str(APP_DIR))
    at.session_state["qs"] = list(cases)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    got = {m.value.split("||")[0]: m.value.split("||")[1] for m in at.markdown if "||" in m.value}
    for q, intent in cases.items():
        assert got[q] == intent, (q, got[q])
    reg = answer("What does RBI say about suspicious transaction reporting timelines?")
    assert "within 7 days" in reg["text"] and "RBI-KYC-003" in reg["text"]


def test_copilot_chat_flow():
    at = page_app("copilot")
    _btn(at, "ACC-9823").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.session_state["chat_history"]) == 2
    assert at.session_state["chat_history"][1]["role"] == "analyst"


def test_triage_decision_writes_audit_entry():
    at = page_app("triage")
    at.session_state["triage_case"] = "ALERT-2024-0047"
    at.run()
    form_btn = next(b for b in at.button if "Save decision" in b.label)
    sel = next(s for s in at.selectbox if s.label == "Disposition")
    sel.set_value("CLOSED_FALSE_POSITIVE")
    at.text_area[0].set_value("Verified with branch: payroll sweep.")
    form_btn.click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    log = at.session_state["_sr_audit_log"]
    assert log and log[-1]["ACTION"] == "TRIAGE_DECISION" and log[-1]["ENTITY_ID"] == "ALERT-2024-0047"
    alerts = at.session_state["_sr_demo_tables"]["AML_ALERTS"]
    row = alerts[alerts["ALERT_ID"] == "ALERT-2024-0047"].iloc[0]
    assert row["ALERT_STATUS"] == "CLOSED_FALSE_POSITIVE" and "payroll sweep" in row["INVESTIGATION_NOTES"]


def test_sar_generate_and_file():
    at = page_app("sar")
    next(b for b in at.button if "Draft narrative" in b.label).click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    next(b for b in at.button if "Generate audit-ready SAR" in b.label).click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    doc = at.session_state["sar_doc"]
    assert doc["pdf"][:5] == b"%PDF-" and len(doc["zip"]) > 1000
    assert "PMLA" not in doc["md"]
    assert "[RBI-KYC-003]" in doc["md"]
    at.checkbox[0].check()
    at.run()
    next(b for b in at.button if "Confirm SAR filed" in b.label).click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    alerts = at.session_state["_sr_demo_tables"]["AML_ALERTS"]
    assert alerts["SAR_FILED"].sum() == 1
    actions = [e["ACTION"] for e in at.session_state["_sr_audit_log"]]
    assert actions[-2:] == ["SAR_GENERATED", "SAR_FILED"]


def test_audit_chain_detects_tampering():
    from utils import data
    log = at_log = None
    at = AppTest.from_string(
        "import sys\nsys.path.insert(0, %r)\nimport streamlit as st\nfrom utils import data\n"
        "data.log_event('A','X','one'); data.log_event('B','Y','two'); data.log_event('C','Z','three')\n"
        "ok1, _ = data.verify_audit_chain(data.audit_log())\n"
        "st.session_state['_sr_audit_log'][1]['DETAIL'] = 'edited'\n"
        "ok2, at_seq = data.verify_audit_chain(data.audit_log())\n"
        "st.write(f'{ok1}|{ok2}|{at_seq}')\n" % str(APP_DIR)
    ).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.markdown[0].value == "True|False|2"


def test_narrative_strips_fabricated_citations():
    from utils.narrative import enforce_citations
    text, removed = enforce_citations("Filed under [RBI-KYC-003] and [PMLA-2002-12] per [FATF-R-002].",
                                      {"RBI-KYC-003", "FATF-R-002"})
    assert removed == ["PMLA-2002-12"] and "PMLA" not in text and "[RBI-KYC-003]" in text


def test_detectors_find_all_seeded_typologies():
    import json
    import pandas as pd
    from utils.risk_signals import run_all_detectors
    rows = json.loads((APP_DIR / "data" / "demo_snapshot.json").read_text())["TRANSACTIONS"]
    kinds = {s.typology for s in run_all_detectors(pd.DataFrame(rows))}
    assert {"STRUCTURING", "VELOCITY", "ROUND_TRIP", "CASH_INTENSIVE", "FAN_OUT"} <= kinds
