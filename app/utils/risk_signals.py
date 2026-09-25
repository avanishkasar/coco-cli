"""
Risk Signals — pure-Python fraud pattern detection helpers.

These mirror the SQL rules encoded in AML_ALERTS.TRIGGER_RULE and the
features in ML_RISK_FEATURES, so the same typology logic used to generate
synthetic alerts can also be explained in the UI or re-run ad hoc over a
transaction DataFrame (e.g. in the Investigation Chat page or a notebook)
without round-tripping through Snowflake.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class Signal:
    typology: str
    severity: str
    description: str
    transaction_ids: list[str]
    total_amount_inr: float


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
                        f"₹{group['AMOUNT_INR'].min():,} and ₹{group['AMOUNT_INR'].max():,} "
                        f"on {account_id} within {STRUCTURING_WINDOW.days} days."
                    ),
                    transaction_ids=list(group["TRANSACTION_ID"]),
                    total_amount_inr=float(group["AMOUNT_INR"].sum()),
                )
            )
    return signals


def detect_velocity(txns: pd.DataFrame) -> list[Signal]:
    """Many outgoing transfers from one account in a very short window."""
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
                                f"₹{out_txn['AMOUNT_INR']:,} sent {account_id} → {counterparty}, "
                                f"₹{ret_txn['AMOUNT_INR']:,} returned within "
                                f"{(ret_txn['TRANSACTION_DATE'] - out_txn['TRANSACTION_DATE']).days} days."
                            ),
                            transaction_ids=[out_txn["TRANSACTION_ID"], ret_txn["TRANSACTION_ID"]],
                            total_amount_inr=float(out_txn["AMOUNT_INR"] + ret_txn["AMOUNT_INR"]),
                        )
                    )
    return signals


def detect_cash_intensive(txns: pd.DataFrame) -> list[Signal]:
    """Account whose recent activity is disproportionately cash-based."""
    signals = []
    for account_id, group in txns.groupby("ACCOUNT_ID"):
        if len(group) < 5:
            continue
        cash_ratio = group["IS_CASH"].mean()
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
                )
            )
    return signals


def run_all_detectors(txns: pd.DataFrame) -> list[Signal]:
    """Run every rule-based detector over a transactions DataFrame."""
    if txns.empty:
        return []
    txns = txns.copy()
    txns["TRANSACTION_DATE"] = pd.to_datetime(txns["TRANSACTION_DATE"])
    return [
        *detect_structuring(txns),
        *detect_velocity(txns),
        *detect_round_trip(txns),
        *detect_cash_intensive(txns),
    ]
