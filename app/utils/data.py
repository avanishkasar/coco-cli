"""
Domain data access for every page.

Each reader returns the same column layout whether it comes from Snowflake
(LIVE) or from the bundled snapshot (DEMO), so pages never branch on mode.
Live reads are cached for two minutes; every write clears that cache.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from utils import demo_store
from utils.db import connection_status, is_live, query_or_raise, run_statement

SEVERITY_ORDER = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
SEVERITY_COLORS = {"CRITICAL": "#BA1A1A", "HIGH": "#A9790A", "MEDIUM": "#147C5B", "LOW": "#6B7280"}
ACTIVE_STATUSES = ("OPEN", "UNDER_REVIEW", "ESCALATED")
CLOSED_STATUSES = ("CLOSED_FALSE_POSITIVE", "CLOSED_SAR_FILED")
TRIAGE_STATUSES = ("OPEN", "UNDER_REVIEW", "ESCALATED", "CLOSED_FALSE_POSITIVE")

# Filing windows quoted from REGULATORY_DOCS_CHUNKS (RBI-KYC-003 / FINCEN-001).
FILING_RULES = {
    "FIU-IND (RBI)": {"days": 7, "chunk_id": "RBI-KYC-003", "report": "STR"},
    "FinCEN (US)": {"days": 30, "chunk_id": "FINCEN-001", "report": "SAR"},
}

# Which clauses of the regulatory corpus apply to each alert typology.
TYPOLOGY_CITATIONS = {
    "STRUCTURING": ["RBI-KYC-005", "RBI-KYC-002", "RBI-KYC-006"],
    "VELOCITY": ["RBI-KYC-006", "BASEL-AML-002"],
    "ROUND_TRIP": ["FINCEN-002", "BASEL-AML-002"],
    "CASH_INTENSIVE": ["BASEL-AML-001", "BASEL-AML-002", "RBI-KYC-002"],
    "SHELL_FANOUT": ["FINCEN-002", "BASEL-AML-002"],
    "FAN_OUT": ["FINCEN-002", "BASEL-AML-002"],
    "UNUSUAL_GEOGRAPHY": ["BASEL-AML-001", "BASEL-AML-002"],
}
REPORTING_CITATIONS = ["RBI-KYC-003", "FATF-R-002"]
PEP_CITATION = "RBI-KYC-004"

_LIVE_TXN_LIMIT = 20000


# ── Generic helpers ──────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _cached_query(sql: str, params: tuple | None) -> pd.DataFrame:
    return query_or_raise(sql, list(params) if params else None)


def _read(sql: str, params: tuple | None = None) -> pd.DataFrame:
    try:
        return _cached_query(sql, params)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Snowflake query failed: {' '.join(str(exc).split())[:400]}")
        return pd.DataFrame()


def _write(sql: str, params: list | None = None) -> tuple[bool, str | None]:
    ok, error = run_statement(sql, params)
    _cached_query.clear()
    return ok, error


def mode() -> str:
    return "LIVE" if is_live() else "DEMO"


def mode_reason() -> str | None:
    return connection_status()["reason"]


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [v.strip() for v in value.strip("[]").split(",") if v.strip()]
    if hasattr(value, "tolist"):
        return list(value.tolist())
    return []


def clean(value, default: str = "—") -> str:
    """Display-safe string for a possibly-null value."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def format_inr(amount, compact: bool = False) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "—"
    if compact:
        if abs(value) >= 1e7:
            return f"₹{value / 1e7:,.2f} Cr"
        if abs(value) >= 1e5:
            return f"₹{value / 1e5:,.2f} L"
    return f"₹{value:,.0f}"


# ── Readers ──────────────────────────────────────────────────

def customers() -> pd.DataFrame:
    df = _read("SELECT * FROM CUSTOMERS") if is_live() else demo_store.table("CUSTOMERS")
    if df.empty:
        return df
    for col in ("PEP_FLAG", "SANCTIONS_FLAG"):
        df[col] = df[col].map(_as_bool)
    return df.sort_values("CUSTOMER_ID").reset_index(drop=True)


def accounts() -> pd.DataFrame:
    """Accounts joined to their customer's KYC profile."""
    acc = _read("SELECT * FROM ACCOUNTS") if is_live() else demo_store.table("ACCOUNTS")
    if acc.empty:
        return acc
    cust = customers()
    keep = ["CUSTOMER_ID", "FULL_NAME", "ENTITY_TYPE", "KYC_TIER", "COUNTRY_OF_ORIGIN", "PEP_FLAG", "SANCTIONS_FLAG"]
    if not cust.empty:
        acc = acc.merge(cust[keep], on="CUSTOMER_ID", how="left")
    acc["RISK_SCORE"] = pd.to_numeric(acc["RISK_SCORE"], errors="coerce").fillna(0.0)
    return acc.sort_values("ACCOUNT_ID").reset_index(drop=True)


def transactions() -> pd.DataFrame:
    if is_live():
        df = _read(f"SELECT * FROM TRANSACTIONS ORDER BY TRANSACTION_DATE DESC LIMIT {_LIVE_TXN_LIMIT}")
    else:
        df = demo_store.table("TRANSACTIONS")
    if df.empty:
        return df
    df["TRANSACTION_DATE"] = pd.to_datetime(df["TRANSACTION_DATE"], errors="coerce")
    df["AMOUNT_INR"] = pd.to_numeric(df["AMOUNT_INR"], errors="coerce").fillna(0)
    df["IS_CASH"] = df["IS_CASH"].map(_as_bool)
    return df.sort_values("TRANSACTION_DATE", ascending=False).reset_index(drop=True)


def alerts() -> pd.DataFrame:
    """All alerts (any status), with customer name, sorted by severity then recency."""
    if is_live():
        df = _read(
            "SELECT a.*, c.FULL_NAME AS CUSTOMER FROM AML_ALERTS a "
            "LEFT JOIN CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID"
        )
    else:
        df = demo_store.table("AML_ALERTS")
        cust = demo_store.table("CUSTOMERS")[["CUSTOMER_ID", "FULL_NAME"]].rename(columns={"FULL_NAME": "CUSTOMER"})
        df = df.merge(cust, on="CUSTOMER_ID", how="left")
    if df.empty:
        return df
    df["ALERT_DATE"] = pd.to_datetime(df["ALERT_DATE"], errors="coerce")
    df["TOTAL_AMOUNT_INR"] = pd.to_numeric(df["TOTAL_AMOUNT_INR"], errors="coerce").fillna(0)
    df["SAR_FILED"] = df["SAR_FILED"].map(_as_bool)
    df["TRANSACTION_IDS"] = df["TRANSACTION_IDS"].map(_as_list)
    for col in ("ANALYST_ASSIGNED", "INVESTIGATION_NOTES", "SAR_REFERENCE"):
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    df["_SEV"] = df["ALERT_SEVERITY"].map(SEVERITY_ORDER).fillna(9)
    df = df.sort_values(["_SEV", "ALERT_DATE"], ascending=[True, False]).drop(columns="_SEV")
    return df.reset_index(drop=True)


def active_alerts() -> pd.DataFrame:
    df = alerts()
    return df if df.empty else df[df["ALERT_STATUS"].isin(ACTIVE_STATUSES)].reset_index(drop=True)


def alert(alert_id: str) -> dict | None:
    df = alerts()
    if df.empty:
        return None
    match = df[df["ALERT_ID"] == alert_id]
    return None if match.empty else match.iloc[0].to_dict()


def customer(customer_id: str) -> dict | None:
    df = customers()
    if df.empty:
        return None
    match = df[df["CUSTOMER_ID"] == customer_id]
    return None if match.empty else match.iloc[0].to_dict()


def ml_features() -> pd.DataFrame:
    """Latest ML feature snapshot per account, joined to the rule-based score."""
    if is_live():
        df = _read(
            "SELECT * FROM ML_RISK_FEATURES "
            "QUALIFY ROW_NUMBER() OVER (PARTITION BY ACCOUNT_ID ORDER BY FEATURE_DATE DESC) = 1"
        )
    else:
        df = demo_store.table("ML_RISK_FEATURES")
        df["_D"] = pd.to_datetime(df["FEATURE_DATE"], errors="coerce")
        df = df.sort_values("_D").groupby("ACCOUNT_ID", as_index=False).tail(1).drop(columns="_D")
    if df.empty:
        return df
    acc = accounts()
    if not acc.empty:
        df = df.merge(acc[["ACCOUNT_ID", "FULL_NAME", "RISK_SCORE", "KYC_TIER"]], on="ACCOUNT_ID", how="left")
    df["ROUND_TRIP_DETECTED"] = df["ROUND_TRIP_DETECTED"].map(_as_bool)
    for col in ("COMPUTED_RISK_SCORE", "RISK_SCORE", "CASH_TXN_RATIO_30D", "VELOCITY_SCORE", "GEOGRAPHIC_ANOMALY_SCORE"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("COMPUTED_RISK_SCORE", ascending=False).reset_index(drop=True)


def regulatory_chunks() -> pd.DataFrame:
    if is_live():
        df = _read(
            "SELECT CHUNK_ID, DOC_NAME, DOC_TYPE, SECTION_NUMBER, SECTION_TITLE, CHUNK_TEXT, "
            "EFFECTIVE_DATE, JURISDICTION FROM REGULATORY_DOCS_CHUNKS"
        )
    else:
        df = demo_store.table("REGULATORY_DOCS_CHUNKS")
    if df.empty:
        return df
    df["EFFECTIVE_DATE"] = df["EFFECTIVE_DATE"].map(lambda v: clean(v)[:10])
    return df.sort_values(["DOC_TYPE", "CHUNK_ID"]).reset_index(drop=True)


def chunks_by_id(chunk_ids: list[str]) -> pd.DataFrame:
    """Rows of REGULATORY_DOCS_CHUNKS for the given IDs, in the given order. Missing IDs are dropped."""
    df = regulatory_chunks()
    if df.empty or not chunk_ids:
        return df.iloc[0:0]
    order = {cid: i for i, cid in enumerate(dict.fromkeys(chunk_ids))}
    out = df[df["CHUNK_ID"].isin(order)].copy()
    out["_O"] = out["CHUNK_ID"].map(order)
    return out.sort_values("_O").drop(columns="_O").reset_index(drop=True)


_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are", "what", "which",
    "does", "do", "say", "says", "about", "under", "with", "by", "be", "how", "when", "should",
    "shall", "rbi", "fatf", "basel", "fincen", "guidelines", "guideline", "regulatory", "regulation",
    "regulations", "me", "tell", "show", "explain", "requirement", "requirements", "rule", "rules",
    "definition", "define", "as", "at", "it", "this", "that", "from", "per", "any", "all",
}
_SYNONYMS = {
    "str": ["suspicious", "str"],
    "sar": ["suspicious", "sar"],
    "ctr": ["cash", "ctr"],
    "timeline": ["within", "days"],
    "timelines": ["within", "days"],
    "deadline": ["within", "days"],
    "deadlines": ["within", "days"],
    "pep": ["politically", "pep", "peps"],
    "kyc": ["due", "diligence", "kyc"],
    "cdd": ["due", "diligence"],
    "edd": ["enhanced", "due", "diligence"],
    "smurfing": ["structuring"],
    "layering": ["layering"],
    "fanout": ["layering", "shell"],
    "shell": ["shell", "layering"],
    "round": ["layering", "rapid"],
    "velocity": ["velocity", "rapid"],
    "monitoring": ["monitoring", "monitor"],
}


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    out: list[str] = []
    for w in words:
        if w in _STOPWORDS or len(w) < 2:
            continue
        out.extend(_SYNONYMS.get(w, [w]))
    return list(dict.fromkeys(out))


def search_regulations(query: str, doc_types: list[str] | None = None,
                       jurisdictions: list[str] | None = None, limit: int = 13) -> pd.DataFrame:
    """
    Keyword retrieval over REGULATORY_DOCS_CHUNKS (no LLM in the loop).
    Scores each chunk by matched query terms, weighting title hits higher.
    """
    df = regulatory_chunks()
    if df.empty:
        return df
    if doc_types:
        df = df[df["DOC_TYPE"].isin(doc_types)]
    if jurisdictions:
        df = df[df["JURISDICTION"].isin(jurisdictions)]
    query = (query or "").strip()
    if not query:
        out = df.copy()
        out["SCORE"] = 0.0
        return out.head(limit).reset_index(drop=True)

    terms = _terms(query)
    phrase = query.lower()
    scores = []
    for _, row in df.iterrows():
        body = str(row["CHUNK_TEXT"]).lower()
        title = str(row["SECTION_TITLE"]).lower()
        score = 0.0
        for t in terms:
            if re.search(rf"\b{re.escape(t)}", body):
                score += 1.0 + 0.25 * min(body.count(t), 4)
            if re.search(rf"\b{re.escape(t)}", title):
                score += 2.0
        if len(phrase) > 3 and phrase in body:
            score += 3.0
        scores.append(score)
    out = df.copy()
    out["SCORE"] = scores
    out = out[out["SCORE"] > 0].sort_values(["SCORE", "CHUNK_ID"], ascending=[False, True])
    return out.head(limit).reset_index(drop=True)


def citations_for_alert(alert_row: dict, regulator: str = "FIU-IND (RBI)", pep: bool = False) -> pd.DataFrame:
    """Corpus clauses that justify filing on this alert — every row exists in REGULATORY_DOCS_CHUNKS."""
    ids = list(TYPOLOGY_CITATIONS.get(str(alert_row.get("ALERT_TYPE", "")).upper(), []))
    if pep:
        ids.append(PEP_CITATION)
    rule = FILING_RULES.get(regulator)
    if rule:
        ids.append(rule["chunk_id"])
    ids.extend(REPORTING_CITATIONS)
    return chunks_by_id(ids)


# ── Derived metrics ──────────────────────────────────────────

def as_of() -> pd.Timestamp:
    """Latest event timestamp in the data — the reference point for ageing and SLA clocks."""
    stamps = []
    a = alerts()
    if not a.empty:
        stamps.append(a["ALERT_DATE"].max())
    t = transactions()
    if not t.empty:
        stamps.append(t["TRANSACTION_DATE"].max())
    stamps = [s for s in stamps if pd.notna(s)]
    return max(stamps) if stamps else pd.Timestamp(datetime.now())


def filing_clock(alert_row: dict, regulator: str = "FIU-IND (RBI)", reference: pd.Timestamp | None = None) -> dict:
    """
    Conservative filing deadline: the regulator's window counted from the alert date
    (the earliest moment suspicion could have formed).
    """
    rule = FILING_RULES.get(regulator, FILING_RULES["FIU-IND (RBI)"])
    start = pd.to_datetime(alert_row.get("ALERT_DATE"), errors="coerce")
    if pd.isna(start):
        return {"due": None, "days_left": None, "state": "UNKNOWN", **rule}
    due = start + timedelta(days=rule["days"])
    ref = reference if reference is not None else as_of()
    days_left = (due.normalize() - ref.normalize()).days
    if _as_bool(alert_row.get("SAR_FILED")):
        state = "FILED"
    elif days_left < 0:
        state = "OVERDUE"
    elif days_left <= 2:
        state = "DUE_SOON"
    else:
        state = "ON_TRACK"
    return {"due": due, "days_left": days_left, "state": state, **rule}


def kpis() -> dict:
    a = alerts()
    acc = accounts()
    active = a[a["ALERT_STATUS"].isin(ACTIVE_STATUSES)] if not a.empty else a
    return {
        "open_alerts": int(len(active)),
        "critical": int((active["ALERT_SEVERITY"] == "CRITICAL").sum()) if not active.empty else 0,
        "unassigned": int(active["ANALYST_ASSIGNED"].isna().sum()) if not active.empty else 0,
        "high_risk_accounts": int((acc["RISK_SCORE"] > 0.7).sum()) if not acc.empty else 0,
        "sar_pending": int(((a["ALERT_STATUS"] == "ESCALATED") & (~a["SAR_FILED"])).sum()) if not a.empty else 0,
        "sar_filed": int(a["SAR_FILED"].sum()) if not a.empty else 0,
        "exposure_inr": float(active["TOTAL_AMOUNT_INR"].sum()) if not active.empty else 0.0,
        "accounts": int(len(acc)),
        "customers": int(acc["CUSTOMER_ID"].nunique()) if not acc.empty else 0,
        "transactions": int(len(transactions())),
        "frozen_accounts": int((acc["STATUS"] == "FROZEN").sum()) if not acc.empty else 0,
        "pep_customers": int(customers()["PEP_FLAG"].sum()) if not customers().empty else 0,
    }


# ── Writes (human-in-the-loop decisions) ─────────────────────

def update_alert(alert_id: str, status: str, analyst: str | None, notes: str | None) -> tuple[bool, str | None]:
    if is_live():
        return _write(
            "UPDATE AML_ALERTS SET ALERT_STATUS = ?, ANALYST_ASSIGNED = ?, INVESTIGATION_NOTES = ?, "
            "UPDATED_AT = CURRENT_TIMESTAMP() WHERE ALERT_ID = ?",
            [status, analyst or None, notes or None, alert_id],
        )
    ok = demo_store.update_alert(
        alert_id,
        ALERT_STATUS=status,
        ANALYST_ASSIGNED=analyst or None,
        INVESTIGATION_NOTES=notes or None,
        UPDATED_AT=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return ok, None if ok else f"Alert {alert_id} not found."


def mark_sar_filed(alert_id: str, sar_ref: str) -> tuple[bool, str | None]:
    if is_live():
        return _write(
            "UPDATE AML_ALERTS SET SAR_FILED = TRUE, SAR_REFERENCE = ?, ALERT_STATUS = 'CLOSED_SAR_FILED', "
            "UPDATED_AT = CURRENT_TIMESTAMP() WHERE ALERT_ID = ?",
            [sar_ref, alert_id],
        )
    ok = demo_store.update_alert(
        alert_id,
        SAR_FILED=True,
        SAR_REFERENCE=sar_ref,
        ALERT_STATUS="CLOSED_SAR_FILED",
        UPDATED_AT=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return ok, None if ok else f"Alert {alert_id} not found."


# ── Tamper-evident audit trail ───────────────────────────────

AUDIT_COLUMNS = ["EVENT_SEQ", "EVENT_ID", "EVENT_TS", "ANALYST", "ACTION", "ENTITY_ID", "DETAIL", "PREV_HASH", "ENTRY_HASH"]
GENESIS_HASH = "0" * 64
_AUDIT_SESSION_KEY = "_sr_audit_log"
_AUDIT_READY_KEY = "_sr_audit_table_ready"
AUDIT_DDL = """CREATE TABLE IF NOT EXISTS AML_AUDIT_LOG (
    EVENT_SEQ   INT            NOT NULL,
    EVENT_ID    VARCHAR(40)    NOT NULL,
    EVENT_TS    TIMESTAMP_NTZ  NOT NULL,
    ANALYST     VARCHAR(200),
    ACTION      VARCHAR(100),
    ENTITY_ID   VARCHAR(100),
    DETAIL      VARCHAR,
    PREV_HASH   VARCHAR(64),
    ENTRY_HASH  VARCHAR(64),
    PRIMARY KEY (EVENT_SEQ)
)"""


def current_analyst() -> str:
    return (st.session_state.get("analyst_name") or "Compliance Analyst").strip() or "Compliance Analyst"


def entry_hash(seq: int, event_id: str, ts: str, analyst: str, action: str, entity_id: str,
               detail: str, prev_hash: str) -> str:
    payload = "|".join([str(int(seq)), event_id, ts, analyst, action, entity_id, detail, prev_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit_in_snowflake() -> bool:
    """True when the audit log lives in Snowflake (table exists or could be created)."""
    if not is_live():
        return False
    ready = st.session_state.get(_AUDIT_READY_KEY)
    if ready is None:
        ok, _ = run_statement(AUDIT_DDL)
        ready = bool(ok)
        st.session_state[_AUDIT_READY_KEY] = ready
    return ready


def audit_backend() -> str:
    return "Snowflake table AML_AUDIT_LOG" if _audit_in_snowflake() else "this browser session"


def audit_log() -> pd.DataFrame:
    if _audit_in_snowflake():
        try:
            df = query_or_raise("SELECT * FROM AML_AUDIT_LOG ORDER BY EVENT_SEQ")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not read AML_AUDIT_LOG: {' '.join(str(exc).split())[:300]}")
            df = pd.DataFrame(columns=AUDIT_COLUMNS)
    else:
        df = pd.DataFrame(st.session_state.get(_AUDIT_SESSION_KEY, []), columns=AUDIT_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    df["EVENT_SEQ"] = pd.to_numeric(df["EVENT_SEQ"], errors="coerce").astype(int)
    df["EVENT_TS"] = pd.to_datetime(df["EVENT_TS"], errors="coerce")
    for col in ("ANALYST", "ACTION", "ENTITY_ID", "DETAIL", "PREV_HASH", "ENTRY_HASH", "EVENT_ID"):
        df[col] = df[col].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    return df.sort_values("EVENT_SEQ").reset_index(drop=True)


def log_event(action: str, entity_id: str, detail: str) -> tuple[bool, str | None]:
    """Append a hash-chained entry to the audit trail."""
    log = audit_log()
    seq = int(log["EVENT_SEQ"].max()) + 1 if not log.empty else 1
    prev = log.iloc[-1]["ENTRY_HASH"] if not log.empty else GENESIS_HASH
    event_id = uuid.uuid4().hex[:12].upper()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    analyst = current_analyst()
    detail = (detail or "").strip()[:4000]
    digest = entry_hash(seq, event_id, ts, analyst, action, entity_id, detail, prev)

    if _audit_in_snowflake():
        return run_statement(
            "INSERT INTO AML_AUDIT_LOG (EVENT_SEQ, EVENT_ID, EVENT_TS, ANALYST, ACTION, ENTITY_ID, DETAIL, "
            "PREV_HASH, ENTRY_HASH) SELECT ?, ?, TO_TIMESTAMP_NTZ(?), ?, ?, ?, ?, ?, ?",
            [seq, event_id, ts, analyst, action, entity_id, detail, prev, digest],
        )
    st.session_state.setdefault(_AUDIT_SESSION_KEY, []).append({
        "EVENT_SEQ": seq, "EVENT_ID": event_id, "EVENT_TS": ts, "ANALYST": analyst, "ACTION": action,
        "ENTITY_ID": entity_id, "DETAIL": detail, "PREV_HASH": prev, "ENTRY_HASH": digest,
    })
    return True, None


def verify_audit_chain(log: pd.DataFrame) -> tuple[bool, int | None]:
    """Recompute every hash. Returns (intact, first_broken_seq)."""
    prev = GENESIS_HASH
    for _, row in log.iterrows():
        ts = pd.Timestamp(row["EVENT_TS"]).strftime("%Y-%m-%d %H:%M:%S")
        expected = entry_hash(row["EVENT_SEQ"], row["EVENT_ID"], ts, row["ANALYST"], row["ACTION"],
                              row["ENTITY_ID"], row["DETAIL"], prev)
        if row["PREV_HASH"] != prev or row["ENTRY_HASH"] != expected:
            return False, int(row["EVENT_SEQ"])
        prev = row["ENTRY_HASH"]
    return True, None


# ── Cortex LLM (narrative drafting) ─────────────────────────

def cortex_complete(prompt: str, model: str) -> tuple[str | None, str | None]:
    """SNOWFLAKE.CORTEX.COMPLETE in live mode. Returns (text, error)."""
    if not is_live():
        return None, "Cortex COMPLETE needs a live Snowflake connection."
    try:
        df = query_or_raise("SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS RESPONSE", [model, prompt])
    except Exception as exc:  # noqa: BLE001
        return None, " ".join(str(exc).split())[:300]
    if df.empty:
        return None, "Cortex COMPLETE returned no rows."
    return str(df.iloc[0, 0]).strip(), None
