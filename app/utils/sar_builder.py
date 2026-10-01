"""
SAR Builder — formats investigation data into a structured
Suspicious Activity Report (SAR / STR) document.

Regulatory citations come only from the `citations` rows passed in, which
are read from REGULATORY_DOCS_CHUNKS — nothing in Section 5 is hard-coded.
"""

import re
from datetime import datetime
from typing import Any

import pandas as pd


# ── Helpers ───────────────────────────────────────────────────

def _risk_label(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


def _format_inr(amount: Any) -> str:
    try:
        return f"₹{float(amount):,.0f}"
    except (TypeError, ValueError):
        return str(amount)


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    try:
        return bool(value) and not pd.isna(value)
    except (TypeError, ValueError):
        return bool(value)


def _pep_text(flag: Any) -> str:
    return "Yes — Enhanced Due Diligence required" if _flag(flag) else "No"


def _sanctions_text(flag: Any) -> str:
    return "YES — SANCTIONS MATCH" if _flag(flag) else "No"


def _cell(value: Any) -> str:
    """Markdown-table-safe cell text."""
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass
    text = str(value).replace("|", "/").replace("\n", " ").strip()
    return text or "—"


def _date(value: Any, with_time: bool = False) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return _cell(value)
    return ts.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def citation_label(c: dict) -> str:
    return f"{c.get('DOC_TYPE', '')} {c.get('SECTION_NUMBER', '')} — {c.get('SECTION_TITLE', '')}".strip()


# ── Markdown SAR ──────────────────────────────────────────────

def build_sar_markdown(data: dict) -> str:
    alert = data.get("alert", {}) or {}
    customer = data.get("customer", {}) or {}
    txns = data.get("transactions", []) or []
    citations = data.get("citations", []) or []
    clock = data.get("filing_clock") or {}
    regulator = data.get("regulator", "FIU-IND (RBI)")
    generated = data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    txn_table_rows = "\n".join(
        f"| {_cell(t.get('TRANSACTION_ID'))} | {_date(t.get('TRANSACTION_DATE'), True)} "
        f"| {_format_inr(t.get('AMOUNT_INR'))} | {_cell(t.get('TRANSACTION_TYPE'))} "
        f"| {_cell(t.get('CHANNEL'))} | {_cell(t.get('COUNTERPARTY_ACCOUNT'))} | {_cell(t.get('NARRATION'))} |"
        for t in txns[:25]
    )

    if citations:
        basis = "\n\n".join(
            f"**[{c.get('CHUNK_ID')}] {citation_label(c)}**  \n"
            f"*{c.get('DOC_NAME', '')} · {c.get('JURISDICTION', '')} · effective {c.get('EFFECTIVE_DATE', '')}*\n\n"
            f"> {str(c.get('CHUNK_TEXT', '')).strip()}"
            for c in citations
        )
    else:
        basis = "*No regulatory clauses attached — add citations from the Regulatory Library before filing.*"

    report = clock.get("report", "STR")
    due = clock.get("due")
    due_text = _date(due) if due is not None else "—"
    clock_cite = f" [{clock['chunk_id']}]" if clock.get("chunk_id") else ""
    tipping = next(
        (
            f"> **Tipping-off prohibited** [{c.get('CHUNK_ID')}]: \"Banks shall not tip off customers about an STR filing.\""
            for c in citations
            if "shall not tip off customers about an STR filing" in str(c.get("CHUNK_TEXT", ""))
        ),
        "",
    )
    edd_cite = " [RBI-KYC-004]" if any(c.get("CHUNK_ID") == "RBI-KYC-004" for c in citations) else ""
    pep_row = (
        f"| Apply Enhanced Due Diligence and senior-management approval{edd_cite} | Required (PEP / high risk) |\n"
        if _flag(customer.get("PEP_FLAG")) or str(customer.get("KYC_TIER", "")).upper() in {"HIGH", "PROHIBITED"}
        else ""
    )

    return f"""# SUSPICIOUS ACTIVITY REPORT ({report})

---

**SAR Reference:** `{data.get('sar_ref', '—')}`
**Filing Date:** {data.get('filing_date', datetime.today().strftime('%Y-%m-%d'))}
**Status:** DRAFT — Pending submission to {regulator}
**Filing deadline:** {due_text} ({clock.get('days', '—')}-day window from alert date{clock_cite})

---

## Section 1: Reporting Entity Information

| Field | Value |
|---|---|
| Reporting Institution | {_cell(data.get('institution'))} |
| Branch / Unit | {_cell(data.get('branch'))} |
| Reporting Officer | {_cell(data.get('reporting_officer'))} |
| Recipient Regulator | {_cell(regulator)} |
| Report Generated | {generated} |

---

## Section 2: Subject Information

| Field | Value |
|---|---|
| Customer ID | {_cell(customer.get('CUSTOMER_ID'))} |
| Full Name / Entity | {_cell(customer.get('FULL_NAME'))} |
| Entity Type | {_cell(customer.get('ENTITY_TYPE'))} |
| Country of Origin | {_cell(customer.get('COUNTRY_OF_ORIGIN'))} |
| KYC Risk Tier | **{_cell(customer.get('KYC_TIER'))}** |
| Politically Exposed Person (PEP) | {_pep_text(customer.get('PEP_FLAG', False))} |
| Sanctions Flag | {_sanctions_text(customer.get('SANCTIONS_FLAG', False))} |
| Occupation | {_cell(customer.get('OCCUPATION'))} |
| Last KYC Refresh | {_cell(customer.get('LAST_KYC_REFRESH'))} |
| Account Open Date | {_cell(customer.get('ACCOUNT_OPEN_DATE'))} |

---

## Section 3: Suspicious Activity Description

| Field | Value |
|---|---|
| Alert ID | `{_cell(alert.get('ALERT_ID'))}` |
| Account | {_cell(alert.get('ACCOUNT_ID'))} |
| Alert Type / Typology | **{_cell(alert.get('ALERT_TYPE'))}** |
| Severity | **{_cell(alert.get('ALERT_SEVERITY'))}** |
| Detection Date | {_date(alert.get('ALERT_DATE'), True)} |
| Total Amount Involved | **{_format_inr(alert.get('TOTAL_AMOUNT_INR', 0))}** |
| Trigger Rule | {_cell(alert.get('TRIGGER_RULE'))} |

### Narrative

{data.get('investigation_notes') or '*No narrative provided. Draft one in the SAR Generator or add findings from the Investigation Copilot.*'}

*Narrative source: {data.get('narrative_source', 'Analyst')}*

---

## Section 4: Transaction Evidence

| Transaction ID | Date & Time | Amount | Type | Channel | Counterparty | Narration |
|---|---|---|---|---|---|---|
{txn_table_rows if txn_table_rows else '| — | No transactions retrieved | — | — | — | — | — |'}

---

## Section 5: Regulatory Basis

Quoted verbatim from `REGULATORY_DOCS_CHUNKS` — each bracketed ID is a row in that table.

{basis}

{tipping}

---

## Section 6: Recommended Action

| Action | Priority |
|---|---|
| File {report} with {regulator} by {due_text}{clock_cite} | Mandatory |
| Do not inform the subject of this filing | Mandatory |
{pep_row}| Escalate to Senior Compliance Officer / MLRO | Recommended |
| Review account restrictions pending investigation | Recommended |
| Retain alert, evidence and disposition records | Mandatory |

---

*Generated by SentinelReg — AML Risk Intelligence Copilot.*
*Reference: {data.get('sar_ref', '—')} | Generated: {generated} | Prepared by: {_cell(data.get('reporting_officer'))}*
"""


# ── Plain text SAR (for submission systems) ───────────────────

def build_sar_text(data: dict) -> str:
    """Returns a plain text version suitable for submission portals."""
    md = build_sar_markdown(data)
    text = re.sub(r"^\|[-|\s]+\|$", "", md, flags=re.MULTILINE)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*#`]", "", text)
    text = re.sub(r"^\|\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s?\|$", "", text, flags=re.MULTILINE)
    text = text.replace(" | ", "  :  ")
    text = re.sub(r"^>\s?", "    ", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
