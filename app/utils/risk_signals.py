"""
Risk Signals — pure-Python fraud pattern detection helpers.

These mirror the SQL rules encoded in AML_ALERTS.TRIGGER_RULE and the
features in ML_RISK_FEATURES, so the same typology logic used to generate
synthetic alerts can also be explained in the UI or re-run ad hoc over a
transaction DataFrame (the Alert Triage "Detection Engine" tab does exactly
that) without round-tripping through Snowflake.

Transaction convention: a row with a COUNTERPARTY_ACCOUNT is a transfer
from ACCOUNT_ID to COUNTERPARTY_ACCOUNT; a row without one is a cash
movement on ACCOUNT_ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

STRUCTURING_THRESHOLD_INR = 50_000
STRUCTURING_MIN_COUNT = 3
STRUCTURING_WINDOW = timedelta(days=3)

VELOCITY_MIN_COUNT = 5
VELOCITY_WINDOW = timedelta(hours=2)

ROUND_TRIP_WINDOW = timedelta(days=8)
ROUND_TRIP_MIN_RETURN_RATIO = 0.80

CASH_INTENSIVE_RATIO = 0.70

FAN_OUT_MIN_INFLOW_INR = 5_000_000
FAN_OUT_MIN_RECIPIENTS = 3
FAN_OUT_WINDOW = timedelta(hours=24)
FAN_OUT_MIN_PASS_THROUGH = 0.80

RULE_CATALOGUE = [
    {
        "TYPOLOGY": "STRUCTURING",
        "SEVERITY": "HIGH",
        "LOGIC": f"≥{STRUCTURING_MIN_COUNT} cash deposits of 90–100% of ₹{STRUCTURING_THRESHOLD_INR:,} "
                 f"on one account within {STRUCTURING_WINDOW.days} days",
    },
    {
        "TYPOLOGY": "VELOCITY",
        "SEVERITY": "HIGH",
        "LOGIC": f"≥{VELOCITY_MIN_COUNT} transactions on one account within "
                 f"{int(VELOCITY_WINDOW.total_seconds() // 3600)} hours",
    },
    {
        "TYPOLOGY": "ROUND_TRIP",
        "SEVERITY": "CRITICAL",
        "LOGIC": f"Transfer A→B returned B→A at ≥{ROUND_TRIP_MIN_RETURN_RATIO:.0%} of the amount "
                 f"within {ROUND_TRIP_WINDOW.days} days",
    },
    {
        "TYPOLOGY": "CASH_INTENSIVE",
        "SEVERITY": "MEDIUM",
        "LOGIC": f"≥{CASH_INTENSIVE_RATIO:.0%} of an account's transactions (min. 5) are cash",
    },
    {
        "TYPOLOGY": "FAN_OUT",
        "SEVERITY": "CRITICAL",
        "LOGIC": f"Inbound transfer ≥₹{FAN_OUT_MIN_INFLOW_INR:,} pushed on to ≥{FAN_OUT_MIN_RECIPIENTS} "
                 f"accounts (≥{FAN_OUT_MIN_PASS_THROUGH:.0%} pass-through) within "
                 f"{int(FAN_OUT_WINDOW.total_seconds() // 3600)} hours",
    },
]


@dataclass
class Signal:
    typology: str
    severity: str
    description: str
    transaction_ids: list[str]
    total_amount_inr: float
    account_id: str = field(default="")


def _inr(value) -> str:
    return f"₹{float(value):,.0f}"


def detect_structuring(txns: pd.DataFrame) -> list[Signal]:
    """Multiple cash deposits just below the CTR threshold in a short window."""
    signals = []
    cash = txns[
        (txns["IS_CASH"])
        & (txns["AMOUNT_INR"] < STRUCTURING_THRESHOLD_INR)
        & (txns["AMOUNT_INR"] >= STRUCTURING_THRESHOLD_INR * 0.9)
    ].sort_values("TRANSACTION_DATE")

    for account_id, group in cash.groupby("ACCOUNT_ID"):
        dates = group["TRANSACTION_DATE"]
        if len(group) >= STRUCTURING_MIN_COUNT and (
            dates.max() - dates.min() <= STRUCTURING_WINDOW
        ):
            signals.append(
                Signal(
                    typology="STRUCTURING",
                    severity="HIGH",
                    description=(
                        f"{len(group)} cash deposits between "
                        f"{_inr(group['AMOUNT_INR'].min())} and {_inr(group['AMOUNT_INR'].max())} "
                        f"on {account_id} within {STRUCTURING_WINDOW.days} days."
                    ),
                    transaction_ids=list(group["TRANSACTION_ID"]),
                    total_amount_inr=float(group["AMOUNT_INR"].sum()),
                    account_id=str(account_id),
                )
            )
    return signals


def detect_velocity(txns: pd.DataFrame) -> list[Signal]:
    """Many transactions from one account in a very short window."""
    signals = []
    outgoing = txns.sort_values("TRANSACTION_DATE")
    for account_id, group in outgoing.groupby("ACCOUNT_ID"):
        dates = group["TRANSACTION_DATE"]
        if len(group) >= VELOCITY_MIN_COUNT and (
            dates.max() - dates.min() <= VELOCITY_WINDOW
        ):
            signals.append(
                Signal(
                    typology="VELOCITY",
                    severity="HIGH",
                    description=(
                        f"{len(group)} outgoing transfers from {account_id} within "
                        f"{int(VELOCITY_WINDOW.total_seconds() // 60)} minutes."
                    ),
                    transaction_ids=list(group["TRANSACTION_ID"]),
                    total_amount_inr=float(group["AMOUNT_INR"].sum()),
                    account_id=str(account_id),
                )
            )
    return signals


def detect_round_trip(txns: pd.DataFrame) -> list[Signal]:
    """Funds sent out and returned in near-full amount within a short window."""
    signals = []
    txns = txns.sort_values("TRANSACTION_DATE")
    for account_id, group in txns.groupby("ACCOUNT_ID"):
        outbound = group[group["COUNTERPARTY_ACCOUNT"].notna()]
        for _, out_txn in outbound.iterrows():
            counterparty = out_txn["COUNTERPARTY_ACCOUNT"]
            window_end = out_txn["TRANSACTION_DATE"] + ROUND_TRIP_WINDOW
            returns = txns[
                (txns["ACCOUNT_ID"] == counterparty)
                & (txns["COUNTERPARTY_ACCOUNT"] == account_id)
                & (txns["TRANSACTION_DATE"] > out_txn["TRANSACTION_DATE"])
                & (txns["TRANSACTION_DATE"] <= window_end)
            ]
            for _, ret_txn in returns.iterrows():
                if ret_txn["AMOUNT_INR"] >= out_txn["AMOUNT_INR"] * ROUND_TRIP_MIN_RETURN_RATIO:
                    signals.append(
                        Signal(
                            typology="ROUND_TRIP",
                            severity="CRITICAL",
                            description=(
                                f"{_inr(out_txn['AMOUNT_INR'])} sent {account_id} → {counterparty}, "
                                f"{_inr(ret_txn['AMOUNT_INR'])} returned within "
                                f"{(ret_txn['TRANSACTION_DATE'] - out_txn['TRANSACTION_DATE']).days} days."
                            ),
                            transaction_ids=[out_txn["TRANSACTION_ID"], ret_txn["TRANSACTION_ID"]],
                            total_amount_inr=float(out_txn["AMOUNT_INR"] + ret_txn["AMOUNT_INR"]),
                            account_id=str(account_id),
                        )
                    )
    return signals


def detect_cash_intensive(txns: pd.DataFrame) -> list[Signal]:
    """Account whose recent activity is disproportionately cash-based."""
    signals = []
    for account_id, group in txns.groupby("ACCOUNT_ID"):
        if len(group) < 5:
            continue
        cash_ratio = group["IS_CASH"].astype(bool).mean()
        if cash_ratio >= CASH_INTENSIVE_RATIO:
            signals.append(
                Signal(
                    typology="CASH_INTENSIVE",
                    severity="MEDIUM",
                    description=(
                        f"{cash_ratio:.0%} of {account_id}'s last {len(group)} transactions "
                        "were cash-based."
                    ),
                    transaction_ids=list(group["TRANSACTION_ID"]),
                    total_amount_inr=float(group["AMOUNT_INR"].sum()),
                    account_id=str(account_id),
                )
            )
    return signals


def detect_fan_out(txns: pd.DataFrame) -> list[Signal]:
    """Large inbound transfer pushed on to several recipients almost immediately (layering)."""
    signals = []
    transfers = txns[txns["COUNTERPARTY_ACCOUNT"].notna()]
    inbound = transfers[transfers["AMOUNT_INR"] >= FAN_OUT_MIN_INFLOW_INR]
    for _, in_txn in inbound.iterrows():
        hub = in_txn["COUNTERPARTY_ACCOUNT"]
        start = in_txn["TRANSACTION_DATE"]
        outs = transfers[
            (transfers["ACCOUNT_ID"] == hub)
            & (transfers["COUNTERPARTY_ACCOUNT"] != in_txn["ACCOUNT_ID"])
            & (transfers["TRANSACTION_DATE"] > start)
            & (transfers["TRANSACTION_DATE"] <= start + FAN_OUT_WINDOW)
        ].sort_values("TRANSACTION_DATE")
        recipients = outs["COUNTERPARTY_ACCOUNT"].nunique()
        passed_on = float(outs["AMOUNT_INR"].sum())
        if recipients >= FAN_OUT_MIN_RECIPIENTS and passed_on >= in_txn["AMOUNT_INR"] * FAN_OUT_MIN_PASS_THROUGH:
            hours = (outs["TRANSACTION_DATE"].max() - start).total_seconds() / 3600
            signals.append(
                Signal(
                    typology="FAN_OUT",
                    severity="CRITICAL",
                    description=(
                        f"{hub} received {_inr(in_txn['AMOUNT_INR'])} from {in_txn['ACCOUNT_ID']} and passed "
                        f"{passed_on / float(in_txn['AMOUNT_INR']):.0%} of it to {recipients} accounts "
                        f"within {hours:.1f} hours."
                    ),
                    transaction_ids=[in_txn["TRANSACTION_ID"], *outs["TRANSACTION_ID"]],
                    total_amount_inr=float(in_txn["AMOUNT_INR"]) + passed_on,
                    account_id=str(hub),
                )
            )
    return signals


def run_all_detectors(txns: pd.DataFrame) -> list[Signal]:
    """Run every rule-based detector over a transactions DataFrame."""
    if txns.empty:
        return []
    txns = txns.copy()
    txns["TRANSACTION_DATE"] = pd.to_datetime(txns["TRANSACTION_DATE"])
    txns["IS_CASH"] = txns["IS_CASH"].astype(bool)
    return [
        *detect_structuring(txns),
        *detect_velocity(txns),
        *detect_round_trip(txns),
        *detect_cash_intensive(txns),
        *detect_fan_out(txns),
    ]


def signals_frame(signals: list[Signal]) -> pd.DataFrame:
    """Signals as a DataFrame (one row per signal) for display."""
    return pd.DataFrame([
        {
            "TYPOLOGY": s.typology,
            "SEVERITY": s.severity,
            "ACCOUNT_ID": s.account_id,
            "DESCRIPTION": s.description,
            "TXN_COUNT": len(s.transaction_ids),
            "AMOUNT_INR": s.total_amount_inr,
            "TRANSACTION_IDS": s.transaction_ids,
        }
        for s in signals
    ], columns=["TYPOLOGY", "SEVERITY", "ACCOUNT_ID", "DESCRIPTION", "TXN_COUNT", "AMOUNT_INR", "TRANSACTION_IDS"])
