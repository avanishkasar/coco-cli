"""
SAR narrative drafting.

* draft_with_cortex — SNOWFLAKE.CORTEX.COMPLETE, grounded on the alert facts
  and the regulatory clauses retrieved for this case.
* draft_from_template — deterministic fallback built only from database
  fields, used in demo mode or whenever Cortex is unavailable.

Either way the result passes through enforce_citations(), which strips any
bracketed citation that is not a CHUNK_ID we supplied. That is the
"never fabricate a citation" rule from AGENTS.md, enforced in code.
"""

from __future__ import annotations

import os
import re

import pandas as pd

from utils.data import cortex_complete, format_inr

DEFAULT_MODEL = "mistral-large2"
_CITATION_RE = re.compile(r"\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\]")

_TYPOLOGY_SENTENCES = {
    "STRUCTURING": (
        "RBI-KYC-005",
        "The pattern of repeated cash deposits kept just below a reporting threshold is consistent with "
        "the structuring indicators described in the RBI KYC Master Direction",
    ),
    "VELOCITY": (
        "RBI-KYC-006",
        "The burst of transfers in a short window is the kind of velocity anomaly the RBI requires "
        "transaction monitoring systems to flag",
    ),
    "ROUND_TRIP": (
        "FINCEN-002",
        "Funds leaving and returning in near-identical amounts within days, with no evident business "
        "purpose, match recognised layering techniques",
    ),
    "SHELL_FANOUT": (
        "FINCEN-002",
        "The rapid onward movement of a large inbound transfer to newly opened shell-profile accounts "
        "matches recognised layering techniques involving shell company transactions",
    ),
    "FAN_OUT": (
        "FINCEN-002",
        "The rapid onward movement of a large inbound transfer to several accounts matches recognised "
        "layering techniques",
    ),
    "CASH_INTENSIVE": (
        "BASEL-AML-002",
        "Cash usage of this scale is inconsistent with the customer's declared business profile, an "
        "unusual pattern Basel guidance expects monitoring to detect",
    ),
}


def model_name() -> str:
    return (os.getenv("SENTINEL_REG_LLM_MODEL") or DEFAULT_MODEL).strip()


def enforce_citations(text: str, allowed_ids: set[str]) -> tuple[str, list[str]]:
    """Remove bracketed citations that are not in allowed_ids. Returns (clean_text, removed_ids)."""
    removed: list[str] = []

    def _check(match: re.Match) -> str:
        cid = match.group(1)
        if cid in allowed_ids:
            return match.group(0)
        removed.append(cid)
        return ""

    cleaned = _CITATION_RE.sub(_check, text or "")
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip(), removed


def _facts(alert: dict, customer: dict, txns: pd.DataFrame) -> dict:
    dates = pd.to_datetime(txns["TRANSACTION_DATE"], errors="coerce") if not txns.empty else pd.Series(dtype="datetime64[ns]")
    alert_date = pd.to_datetime(alert.get("ALERT_DATE"), errors="coerce")
    return {
        "alert_id": alert.get("ALERT_ID"),
        "alert_type": alert.get("ALERT_TYPE"),
        "severity": alert.get("ALERT_SEVERITY"),
        "alert_date": alert_date.strftime("%d %b %Y") if pd.notna(alert_date) else "an unrecorded date",
        "trigger_rule": alert.get("TRIGGER_RULE"),
        "account_id": alert.get("ACCOUNT_ID"),
        "total_amount": format_inr(alert.get("TOTAL_AMOUNT_INR")),
        "analyst_notes": alert.get("INVESTIGATION_NOTES") or "",
        "customer_name": customer.get("FULL_NAME") or "the customer",
        "customer_id": customer.get("CUSTOMER_ID"),
        "entity_type": str(customer.get("ENTITY_TYPE") or "").lower() or "customer",
        "kyc_tier": customer.get("KYC_TIER") or "unrated",
        "country": customer.get("COUNTRY_OF_ORIGIN") or "unknown",
        "occupation": customer.get("OCCUPATION") or "not recorded",
        "pep": bool(customer.get("PEP_FLAG")),
        "sanctions": bool(customer.get("SANCTIONS_FLAG")),
        "txn_count": int(len(txns)),
        "txn_total": format_inr(txns["AMOUNT_INR"].sum()) if not txns.empty else format_inr(0),
        "first_txn": dates.min().strftime("%d %b %Y") if len(dates.dropna()) else None,
        "last_txn": dates.max().strftime("%d %b %Y") if len(dates.dropna()) else None,
    }


def draft_from_template(alert: dict, customer: dict, txns: pd.DataFrame, citations: pd.DataFrame,
                        regulator: str, report: str) -> str:
    f = _facts(alert, customer, txns)
    cited = set(citations["CHUNK_ID"]) if not citations.empty else set()

    flags = []
    if f["pep"]:
        flags.append("a politically exposed person (PEP)-linked relationship")
    if f["sanctions"]:
        flags.append("a sanctions-list match")
    profile = f"{f['entity_type']} customer {f['customer_name']} ({f['customer_id']}), KYC risk tier {f['kyc_tier']}, " \
              f"country of origin {f['country']}, recorded occupation {f['occupation']}"
    if flags:
        profile += ", flagged as " + " and ".join(flags)

    parts = [
        f"On {f['alert_date']}, SentinelReg transaction monitoring raised alert {f['alert_id']} "
        f"({f['alert_type']}, severity {f['severity']}) on account {f['account_id']}, held by {profile}.",
        f"The alert was triggered by: {f['trigger_rule']}.",
    ]
    if f["txn_count"]:
        window = f" between {f['first_txn']} and {f['last_txn']}" if f["first_txn"] else ""
        parts.append(
            f"The evidence set comprises {f['txn_count']} transaction(s) totalling {f['txn_total']}{window}; "
            f"the alert records a total of {f['total_amount']} involved."
        )
    if f["analyst_notes"]:
        parts.append(f"Analyst findings: {f['analyst_notes'].strip().rstrip('.')}.")

    typ = str(f["alert_type"] or "").upper()
    if typ in _TYPOLOGY_SENTENCES:
        cid, sentence = _TYPOLOGY_SENTENCES[typ]
        parts.append(f"{sentence} [{cid}]." if cid in cited else f"{sentence}.")
    if f["pep"] and "RBI-KYC-004" in cited:
        parts.append("PEP-linked customers are to be treated as high risk and subject to Enhanced Due Diligence [RBI-KYC-004].")

    filing_cite = next((c for c in ("RBI-KYC-003", "FINCEN-001") if c in cited and
                        ((c == "RBI-KYC-003") == ("FIU-IND" in regulator))), None)
    closing = (
        f"On this basis there are reasonable grounds to suspect that the funds may be linked to money laundering, "
        f"and this {report} is filed with {regulator}"
    )
    parts.append(f"{closing} [{filing_cite}]." if filing_cite else f"{closing}.")
    if "FATF-R-002" in cited:
        parts.append("Prompt reporting of such suspicion to the financial intelligence unit is required [FATF-R-002].")
    return " ".join(parts)


def _prompt(alert: dict, customer: dict, txns: pd.DataFrame, citations: pd.DataFrame,
            regulator: str, report: str) -> str:
    f = _facts(alert, customer, txns)
    txn_lines = "\n".join(
        f"- {r['TRANSACTION_ID']} | {pd.to_datetime(r['TRANSACTION_DATE']).strftime('%Y-%m-%d %H:%M')} | "
        f"{format_inr(r['AMOUNT_INR'])} | {r.get('TRANSACTION_TYPE', '')} | counterparty {r.get('COUNTERPARTY_ACCOUNT') or 'none'} | "
        f"{r.get('NARRATION', '')}"
        for _, r in txns.head(20).iterrows()
    ) or "- none"
    clause_lines = "\n".join(
        f"[{r['CHUNK_ID']}] {r['DOC_TYPE']} {r['SECTION_NUMBER']} ({r['SECTION_TITLE']}): {r['CHUNK_TEXT']}"
        for _, r in citations.iterrows()
    ) or "(none)"
    return f"""You are a senior AML compliance officer drafting the narrative section of a {report} for {regulator}.

FACTS (use only these — do not invent names, amounts, dates or events):
- Alert: {f['alert_id']} | typology {f['alert_type']} | severity {f['severity']} | raised {f['alert_date']}
- Trigger rule: {f['trigger_rule']}
- Account: {f['account_id']} | total amount on alert: {f['total_amount']}
- Customer: {f['customer_name']} ({f['customer_id']}) | {f['entity_type']} | KYC tier {f['kyc_tier']} | country {f['country']} | occupation {f['occupation']} | PEP: {'yes' if f['pep'] else 'no'} | sanctions match: {'yes' if f['sanctions'] else 'no'}
- Analyst notes: {f['analyst_notes'] or 'none'}
- Transactions:
{txn_lines}

REGULATORY CLAUSES (the only sources you may cite):
{clause_lines}

INSTRUCTIONS:
- Write 150 to 230 words in formal, third-person, past-tense prose. No headings, no bullet points.
- Cover: who, what, when, how much, why it is suspicious, and the reporting basis.
- Cite clauses only by their bracketed ID exactly as shown, e.g. [RBI-KYC-003]. Never cite anything else.
- Do not speculate beyond the facts. Do not address the customer.

NARRATIVE:"""


def draft_with_cortex(alert: dict, customer: dict, txns: pd.DataFrame, citations: pd.DataFrame,
                      regulator: str, report: str) -> tuple[str | None, str | None]:
    text, error = cortex_complete(_prompt(alert, customer, txns, citations, regulator, report), model_name())
    if error or not text:
        return None, error or "Empty response from Cortex COMPLETE."
    return text.strip().strip('"').strip(), None


def draft_narrative(alert: dict, customer: dict, txns: pd.DataFrame, citations: pd.DataFrame,
                    regulator: str, report: str, use_llm: bool) -> dict:
    """Returns {text, source, removed_citations, llm_error}."""
    allowed = set(citations["CHUNK_ID"]) if not citations.empty else set()
    llm_error = None
    if use_llm:
        text, llm_error = draft_with_cortex(alert, customer, txns, citations, regulator, report)
        if text:
            clean, removed = enforce_citations(text, allowed)
            return {"text": clean, "source": f"Snowflake Cortex COMPLETE ({model_name()})",
                    "removed_citations": removed, "llm_error": None}
    text = draft_from_template(alert, customer, txns, citations, regulator, report)
    clean, removed = enforce_citations(text, allowed)
    return {"text": clean, "source": "Deterministic template (database fields only)",
            "removed_citations": removed, "llm_error": llm_error}
