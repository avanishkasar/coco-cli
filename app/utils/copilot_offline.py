"""
Offline copilot — a deterministic question router used when Cortex Analyst
is unreachable (demo mode, or no PAT configured).

It never generates free text from a model: every answer is assembled from
rows returned by utils.data (so it works over the demo snapshot and over
live Snowflake alike) and every regulatory quote is a verbatim
REGULATORY_DOCS_CHUNKS row.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

from utils import data
from utils.risk_signals import detect_fan_out, detect_round_trip, run_all_detectors

ACC_RE = re.compile(r"\bACC-\d{3,6}\b", re.IGNORECASE)
ALERT_RE = re.compile(r"\bALERT-\d{4}-\d{3,6}\b", re.IGNORECASE)
CUST_RE = re.compile(r"\bCUST-\d{3,6}\b", re.IGNORECASE)

_STRONG_REG_CUES = (
    "what does", "say about", "says about", "definition", "define", "regulat", "guideline", "requirement",
    "obligation", "timeline", "deadline", "according to", " law", "rbi", "fatf", "basel", "fincen", "pmla",
    "how long", "how many days", "tipping", "tip off", "retention", "retain",
)
_WEAK_REG_CUES = ("what is", "what are", "explain", "meaning")
_TYPOLOGY_WORDS = {
    "STRUCTURING": ("structur", "smurf"),
    "VELOCITY": ("velocity",),
    "ROUND_TRIP": ("round-trip", "round trip", "roundtrip"),
    "CASH_INTENSIVE": ("cash-intensive", "cash intensive"),
    "SHELL_FANOUT": ("fan-out", "fanout", "fan out", "shell"),
}
EXAMPLES = [
    "Why was account ACC-9823 flagged for AML?",
    "Which accounts have a risk score above 0.7?",
    "List all open CRITICAL alerts with their total amounts",
    "How many cash deposits were made just below ₹50,000 this month?",
    "What does RBI say about suspicious transaction reporting timelines?",
    "Summarise the round-trip transfer pattern on account ACC-0009",
    "Show fan-out / layering activity",
    "Which customers are PEPs or sanctions matches?",
]


def _result(intent: str, text: str, df: pd.DataFrame | None = None, citations: pd.DataFrame | None = None) -> dict:
    return {"intent": intent, "text": text.strip(), "df": df, "citations": citations}


def _typology_in(q: str) -> str | None:
    for typ, words in _TYPOLOGY_WORDS.items():
        if any(w in q for w in words):
            return typ
    return None


def _alert_line(a: dict) -> str:
    analyst = a.get("ANALYST_ASSIGNED") or "unassigned"
    return (
        f"- **{a['ALERT_ID']}** · {a['ALERT_TYPE']} · {a['ALERT_SEVERITY']} · {str(a['ALERT_STATUS']).replace('_', ' ').title()} · "
        f"{data.format_inr(a['TOTAL_AMOUNT_INR'], compact=True)} · {analyst}  \n"
        f"  Trigger: {a.get('TRIGGER_RULE') or '—'}"
    )


def _txn_view(txns: pd.DataFrame) -> pd.DataFrame:
    cols = ["TRANSACTION_ID", "TRANSACTION_DATE", "ACCOUNT_ID", "COUNTERPARTY_ACCOUNT", "AMOUNT_INR",
            "TRANSACTION_TYPE", "CHANNEL", "IS_CASH", "NARRATION"]
    return txns[[c for c in cols if c in txns.columns]].reset_index(drop=True)


# ── Intents ───────────────────────────────────────────────────

def _alert_intent(alert_id: str) -> dict:
    a = data.alert(alert_id)
    if not a:
        return _result("alert", f"No alert with ID **{alert_id}** was found.")
    txns = data.transactions()
    ev = txns[txns["TRANSACTION_ID"].isin(a["TRANSACTION_IDS"])] if not txns.empty else txns
    cust = data.customer(a["CUSTOMER_ID"]) or {}
    clock = data.filing_clock(a)
    text = (
        f"**{a['ALERT_ID']}** is a **{a['ALERT_SEVERITY']} {a['ALERT_TYPE']}** alert on **{a['ACCOUNT_ID']}** "
        f"({cust.get('FULL_NAME', a.get('CUSTOMER', '—'))}), raised {pd.Timestamp(a['ALERT_DATE']):%d %b %Y %H:%M}, "
        f"status **{str(a['ALERT_STATUS']).replace('_', ' ').title()}**, amount **{data.format_inr(a['TOTAL_AMOUNT_INR'])}**.\n\n"
        f"**Trigger rule:** {a.get('TRIGGER_RULE') or '—'}\n\n"
        f"**Analyst notes:** {a.get('INVESTIGATION_NOTES') or '_none yet_'}"
    )
    if clock.get("due") is not None:
        text += (
            f"\n\n**Filing clock:** {clock['report']} due {clock['due']:%d %b %Y} "
            f"({clock['days']}-day window from the alert date, {clock['chunk_id']})."
        )
    cites = data.citations_for_alert(a, pep=bool(cust.get("PEP_FLAG")))
    return _result("alert", text, _txn_view(ev), cites)


def _entity_intent(account_ids: list[str], customer_ids: list[str], q: str) -> dict:
    acc = data.accounts()
    if customer_ids and not acc.empty:
        account_ids = account_ids + list(acc[acc["CUSTOMER_ID"].isin(customer_ids)]["ACCOUNT_ID"])
    account_ids = list(dict.fromkeys(account_ids))
    known = acc[acc["ACCOUNT_ID"].isin(account_ids)] if not acc.empty else acc
    if known.empty:
        return _result("entity", f"No account matching {', '.join(account_ids) or ', '.join(customer_ids)} was found.")

    alerts = data.alerts()
    ml = data.ml_features()
    txns = data.transactions()
    typ = _typology_in(q)
    blocks = []
    for _, row in known.iterrows():
        aid = row["ACCOUNT_ID"]
        ml_row = ml[ml["ACCOUNT_ID"] == aid] if not ml.empty else ml
        ml_txt = f" · ML score **{float(ml_row.iloc[0]['COMPUTED_RISK_SCORE']):.2f}**" if not ml_row.empty else ""
        flags = []
        if row.get("PEP_FLAG"):
            flags.append("PEP")
        if row.get("SANCTIONS_FLAG"):
            flags.append("SANCTIONS MATCH")
        if row.get("STATUS") == "FROZEN":
            flags.append("FROZEN")
        head = (
            f"### {aid} — {row.get('FULL_NAME', '—')}\n"
            f"{row.get('ENTITY_TYPE', '—')} · KYC **{row.get('KYC_TIER', '—')}** · {row.get('COUNTRY_OF_ORIGIN', '—')} · "
            f"rule-based risk **{float(row['RISK_SCORE']):.2f}**{ml_txt}"
            + (f" · ⚠ {', '.join(flags)}" if flags else "")
        )
        acc_alerts = alerts[alerts["ACCOUNT_ID"] == aid] if not alerts.empty else alerts
        if typ and not acc_alerts.empty and (acc_alerts["ALERT_TYPE"] == typ).any():
            acc_alerts = acc_alerts[acc_alerts["ALERT_TYPE"] == typ]
        if acc_alerts.empty:
            alert_txt = "No alerts on this account."
        else:
            alert_txt = f"**{len(acc_alerts)} alert(s):**\n" + "\n".join(
                _alert_line(a) + (f"  \n  Notes: {a['INVESTIGATION_NOTES']}" if a.get("INVESTIGATION_NOTES") else "")
                for a in acc_alerts.to_dict("records")
            )
        involved = txns[(txns["ACCOUNT_ID"] == aid) | (txns["COUNTERPARTY_ACCOUNT"] == aid)] if not txns.empty else txns
        sigs = [s for s in run_all_detectors(txns) if s.account_id == aid or aid in s.description] if not txns.empty else []
        sig_txt = (
            "**Detection engine (re-run now):**\n" + "\n".join(f"- {s.typology} ({s.severity}): {s.description}" for s in sigs)
            if sigs else "**Detection engine (re-run now):** no rule fired on this account's transactions."
        )
        blocks.append(f"{head}\n\n{alert_txt}\n\n{sig_txt}\n\n_{len(involved)} transaction(s) involve this account._")
    involved_all = txns[txns["ACCOUNT_ID"].isin(known["ACCOUNT_ID"]) | txns["COUNTERPARTY_ACCOUNT"].isin(known["ACCOUNT_ID"])] \
        if not txns.empty else txns
    return _result("entity", "\n\n".join(blocks), _txn_view(involved_all))


def _regulatory_intent(q: str) -> dict | None:
    doc_types = [d for d in ("RBI", "FATF", "BASEL", "FINCEN") if d.lower() in q]
    hits = data.search_regulations(q, doc_types=doc_types or None, limit=3)
    if hits.empty and doc_types:
        hits = data.search_regulations(q, limit=3)
    if hits.empty:
        return None
    terms = data._terms(q)
    top = hits.iloc[0]
    sentences = re.split(r"(?<=[.;])\s+", str(top["CHUNK_TEXT"]))
    scored = sorted(
        ((sum(1 for t in terms if t in s.lower()), i, s) for i, s in enumerate(sentences)),
        key=lambda x: (-x[0], x[1]),
    )
    key_sentence = scored[0][2] if scored and scored[0][0] > 0 else sentences[0]
    text = (
        f"**Answer (verbatim):** {key_sentence} **[{top['CHUNK_ID']}]**\n\n"
        f"Most relevant clauses from `REGULATORY_DOCS_CHUNKS`:\n\n"
        + "\n\n".join(
            f"**[{r['CHUNK_ID']}] {r['DOC_TYPE']} {r['SECTION_NUMBER']} — {r['SECTION_TITLE']}** "
            f"_({r['JURISDICTION']} · {r['DOC_NAME']})_\n> {r['CHUNK_TEXT']}"
            for _, r in hits.iterrows()
        )
    )
    return _result("regulatory", text, None, hits)


def _risk_score_intent(q: str) -> dict:
    m = re.search(r"(?:above|over|greater than|more than|>|exceeding)\s*(0?\.\d+|\d+(?:\.\d+)?)", q)
    threshold = float(m.group(1)) if m else 0.7
    if threshold > 1:
        threshold = threshold / 100
    acc = data.accounts()
    ml = data.ml_features()
    hits = acc[acc["RISK_SCORE"] > threshold].sort_values("RISK_SCORE", ascending=False)
    if not ml.empty:
        hits = hits.merge(ml[["ACCOUNT_ID", "COMPUTED_RISK_SCORE"]], on="ACCOUNT_ID", how="left")
    view = hits[[c for c in ["ACCOUNT_ID", "FULL_NAME", "KYC_TIER", "STATUS", "RISK_SCORE", "COMPUTED_RISK_SCORE",
                             "PEP_FLAG", "SANCTIONS_FLAG"] if c in hits.columns]]
    lines = "\n".join(
        f"- **{r['ACCOUNT_ID']}** {r['FULL_NAME']} — rule {r['RISK_SCORE']:.2f}"
        + (f", ML {r['COMPUTED_RISK_SCORE']:.2f}" if pd.notna(r.get("COMPUTED_RISK_SCORE")) else "")
        for _, r in hits.head(10).iterrows()
    )
    text = f"**{len(hits)} account(s)** have a rule-based risk score above **{threshold:.2f}**:\n\n{lines or '_none_'}"
    return _result("risk_score", text, view.reset_index(drop=True))


def _window(q: str, as_of: pd.Timestamp) -> tuple[pd.Timestamp | None, str]:
    m = re.search(r"last\s+(\d+)\s+days?", q)
    if m:
        days = int(m.group(1))
        return as_of - timedelta(days=days), f"in the {days} days to {as_of:%d %b %Y}"
    if "this month" in q:
        start = as_of.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, f"in {as_of:%B %Y}"
    if "this week" in q or "last 7" in q:
        return as_of - timedelta(days=7), f"in the 7 days to {as_of:%d %b %Y}"
    return None, "in the dataset"


def _structuring_intent(q: str) -> dict:
    txns = data.transactions()
    as_of = data.as_of()
    start, label = _window(q, as_of)
    cash = txns[txns["IS_CASH"] & (txns["AMOUNT_INR"] < 50_000) & (txns["AMOUNT_INR"] >= 45_000)]
    if start is not None:
        cash = cash[cash["TRANSACTION_DATE"] >= start]
    by_acc = cash.groupby("ACCOUNT_ID").size().sort_values(ascending=False)
    spread = ", ".join(f"{a} ({n})" for a, n in by_acc.items())
    text = (
        f"**{len(cash)} cash deposit(s)** between ₹45,000 and ₹49,999 (within 10% below the ₹50,000 rule threshold) "
        f"{label}, totalling **{data.format_inr(cash['AMOUNT_INR'].sum())}**"
        + (f", across: {spread}." if spread else ".")
        + "\n\n_Data as of " + f"{as_of:%d %b %Y %H:%M}" + "; windows are measured from that point._"
    )
    return _result("structuring", text, _txn_view(cash))


def _alert_list_intent(q: str) -> dict:
    df = data.alerts()
    sev = [s for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if s.lower() in q]
    if sev:
        df = df[df["ALERT_SEVERITY"].isin(sev)]
    if "closed" in q:
        df = df[df["ALERT_STATUS"].isin(data.CLOSED_STATUSES)]
    elif "escalat" in q:
        df = df[df["ALERT_STATUS"] == "ESCALATED"]
    elif "open" in q or "active" in q or "pending" in q:
        df = df[df["ALERT_STATUS"].isin(data.ACTIVE_STATUSES)]
    if "unassigned" in q:
        df = df[df["ANALYST_ASSIGNED"].isna()]
    typ = _typology_in(q)
    if typ:
        df = df[df["ALERT_TYPE"] == typ]
    text = (
        f"**{len(df)} alert(s)** match, total **{data.format_inr(df['TOTAL_AMOUNT_INR'].sum())}** "
        f"({data.format_inr(df['TOTAL_AMOUNT_INR'].sum(), compact=True)}):\n\n"
        + ("\n".join(_alert_line(a) for a in df.to_dict("records")) or "_none_")
    )
    view = df[["ALERT_ID", "ACCOUNT_ID", "CUSTOMER", "ALERT_TYPE", "ALERT_SEVERITY", "ALERT_STATUS",
               "TOTAL_AMOUNT_INR", "ANALYST_ASSIGNED", "ALERT_DATE"]]
    return _result("alerts", text, view.reset_index(drop=True))


def _round_trip_intent() -> dict:
    txns = data.transactions()
    sigs = detect_round_trip(txns) if not txns.empty else []
    ids = {i for s in sigs for i in s.transaction_ids}
    text = (
        f"The detection engine found **{len(sigs)} round-trip pattern(s)** (funds returned at ≥80% within 8 days):\n\n"
        + ("\n".join(f"- {s.description}" for s in sigs) or "_none_")
    )
    return _result("round_trip", text, _txn_view(txns[txns["TRANSACTION_ID"].isin(ids)]))


def _fan_out_intent() -> dict:
    txns = data.transactions()
    sigs = detect_fan_out(txns) if not txns.empty else []
    ids = {i for s in sigs for i in s.transaction_ids}
    text = (
        f"The detection engine found **{len(sigs)} fan-out / layering pattern(s)** "
        f"(≥₹50L inbound passed to ≥3 accounts within 24h):\n\n"
        + ("\n".join(f"- {s.description}" for s in sigs) or "_none_")
    )
    return _result("fan_out", text, _txn_view(txns[txns["TRANSACTION_ID"].isin(ids)]))


def _pep_intent() -> dict:
    cust = data.customers()
    hits = cust[cust["PEP_FLAG"] | cust["SANCTIONS_FLAG"]]
    lines = "\n".join(
        f"- **{r['CUSTOMER_ID']}** {r['FULL_NAME']} ({r['COUNTRY_OF_ORIGIN']}) — "
        + ", ".join(x for x, f in (("PEP", r["PEP_FLAG"]), ("sanctions match", r["SANCTIONS_FLAG"])) if f)
        + f" · KYC {r['KYC_TIER']}"
        for _, r in hits.iterrows()
    )
    view = hits[["CUSTOMER_ID", "FULL_NAME", "ENTITY_TYPE", "KYC_TIER", "COUNTRY_OF_ORIGIN", "PEP_FLAG", "SANCTIONS_FLAG", "NOTES"]]
    return _result("pep", f"**{len(hits)} customer(s)** carry a PEP or sanctions flag:\n\n{lines or '_none_'}", view.reset_index(drop=True))


def _cash_intent(q: str) -> dict:
    txns = data.transactions()
    m = re.search(r"(?:above|over|more than|>)\s*₹?\s*([\d,]+)", q)
    floor = float(m.group(1).replace(",", "")) if m else 40_000
    cash = txns[txns["IS_CASH"] & (txns["AMOUNT_INR"] >= floor)]
    text = (
        f"**{len(cash)} cash transaction(s)** of {data.format_inr(floor)} or more, totalling "
        f"**{data.format_inr(cash['AMOUNT_INR'].sum())}**."
    )
    return _result("cash", text, _txn_view(cash))


def _help() -> dict:
    text = (
        "I answer from the data and the regulatory corpus without a language model in this mode. Try:\n\n"
        + "\n".join(f"- {e}" for e in EXAMPLES)
    )
    return _result("help", text)


def answer(question: str) -> dict:
    q = (question or "").strip()
    ql = f" {q.lower()} "
    if not q:
        return _help()

    alert_ids = [m.upper() for m in ALERT_RE.findall(q)]
    account_ids = [m.upper() for m in ACC_RE.findall(q)]
    customer_ids = [m.upper() for m in CUST_RE.findall(q)]

    if alert_ids:
        return _alert_intent(alert_ids[0])
    if account_ids or customer_ids:
        return _entity_intent(account_ids, customer_ids, ql)
    if any(c in ql for c in _STRONG_REG_CUES):
        reg = _regulatory_intent(ql)
        if reg:
            return reg
    if "risk score" in ql or "high risk" in ql or "high-risk" in ql or "riskiest" in ql:
        return _risk_score_intent(ql)
    if "alert" in ql:
        return _alert_list_intent(ql)
    if "structur" in ql or "just below" in ql or "below ₹50" in ql or "below 50" in ql or "threshold" in ql:
        return _structuring_intent(ql)
    if _typology_in(ql) == "ROUND_TRIP":
        return _round_trip_intent()
    if _typology_in(ql) == "SHELL_FANOUT" or "layering" in ql:
        return _fan_out_intent()
    if "pep" in ql or "politically" in ql or "sanction" in ql:
        return _pep_intent()
    if "cash" in ql:
        return _cash_intent(ql)
    if any(c in ql for c in _WEAK_REG_CUES):
        reg = _regulatory_intent(ql)
        if reg:
            return reg
    return _help()
