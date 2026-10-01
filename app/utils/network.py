"""
Fund-flow network analysis over TRANSACTIONS.

Every transfer row (ACCOUNT_ID → COUNTERPARTY_ACCOUNT) becomes a directed
edge. Connected components ("rings") show when separately raised alerts are
in fact one scheme — the link an analyst working alert-by-alert misses.
"""

from __future__ import annotations

import pandas as pd

from utils.ui import risk_color


def flow_edges(txns: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transfers into SRC → DST edges."""
    cols = ["SRC", "DST", "AMOUNT_INR", "TXN_COUNT", "FIRST_TS", "LAST_TS", "TRANSACTION_IDS"]
    if txns.empty:
        return pd.DataFrame(columns=cols)
    transfers = txns[txns["COUNTERPARTY_ACCOUNT"].notna()]
    transfers = transfers[transfers["COUNTERPARTY_ACCOUNT"].astype(str).str.len() > 0]
    if transfers.empty:
        return pd.DataFrame(columns=cols)
    grouped = transfers.groupby(["ACCOUNT_ID", "COUNTERPARTY_ACCOUNT"]).agg(
        AMOUNT_INR=("AMOUNT_INR", "sum"),
        TXN_COUNT=("TRANSACTION_ID", "count"),
        FIRST_TS=("TRANSACTION_DATE", "min"),
        LAST_TS=("TRANSACTION_DATE", "max"),
        TRANSACTION_IDS=("TRANSACTION_ID", list),
    ).reset_index()
    grouped = grouped.rename(columns={"ACCOUNT_ID": "SRC", "COUNTERPARTY_ACCOUNT": "DST"})
    return grouped[cols].sort_values("AMOUNT_INR", ascending=False).reset_index(drop=True)


def components(edges: pd.DataFrame) -> list[set[str]]:
    """Weakly connected components, largest first."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, e in edges.iterrows():
        a, b = find(str(e["SRC"])), find(str(e["DST"]))
        if a != b:
            parent[a] = b
    groups: dict[str, set[str]] = {}
    for node in list(parent):
        groups.setdefault(find(node), set()).add(node)
    return sorted(groups.values(), key=lambda g: (-len(g), sorted(g)[0]))


def neighborhood(edges: pd.DataFrame, seeds: set[str], hops: int = 2) -> pd.DataFrame:
    """Edges within `hops` of any seed account (direction ignored)."""
    if edges.empty or not seeds:
        return edges.iloc[0:0]
    frontier, seen = set(seeds), set(seeds)
    for _ in range(hops):
        touching = edges[edges["SRC"].isin(frontier) | edges["DST"].isin(frontier)]
        nxt = (set(touching["SRC"]) | set(touching["DST"])) - seen
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    return edges[edges["SRC"].isin(seen) & edges["DST"].isin(seen)].reset_index(drop=True)


def ring_summary(edges: pd.DataFrame, alerts: pd.DataFrame) -> pd.DataFrame:
    """One row per connected ring with the alerts that sit inside it."""
    rows = []
    active = alerts if alerts.empty else alerts[~alerts["ALERT_STATUS"].isin(["CLOSED_FALSE_POSITIVE"])]
    for i, ring in enumerate(components(edges), start=1):
        ring_edges = edges[edges["SRC"].isin(ring) & edges["DST"].isin(ring)]
        ring_alerts = active[active["ACCOUNT_ID"].isin(ring)] if not active.empty else active
        rows.append({
            "RING": f"R{i}",
            "ACCOUNTS": len(ring),
            "TRANSFERS": int(ring_edges["TXN_COUNT"].sum()),
            "FLOW_INR": float(ring_edges["AMOUNT_INR"].sum()),
            "ALERTS": len(ring_alerts),
            "ALERT_IDS": ", ".join(sorted(ring_alerts["ALERT_ID"])) if len(ring_alerts) else "",
            "MEMBERS": ", ".join(sorted(ring)),
        })
    return pd.DataFrame(rows, columns=["RING", "ACCOUNTS", "TRANSFERS", "FLOW_INR", "ALERTS", "ALERT_IDS", "MEMBERS"])


def _compact_inr(value: float) -> str:
    if value >= 1e7:
        return f"₹{value / 1e7:.2f} Cr"
    if value >= 1e5:
        return f"₹{value / 1e5:.1f} L"
    return f"₹{value:,.0f}"


def _dot_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def build_dot(edges: pd.DataFrame, accounts: pd.DataFrame, alerts: pd.DataFrame,
              focus: set[str] | None = None, flagged_txns: set[str] | None = None,
              rankdir: str = "LR") -> str:
    """Graphviz DOT for the given edges, styled by account risk and alert involvement."""
    focus = focus or set()
    flagged_txns = flagged_txns or set()
    nodes = sorted(set(edges["SRC"]) | set(edges["DST"]) | focus) if not edges.empty else sorted(focus)
    info = accounts.set_index("ACCOUNT_ID") if not accounts.empty else pd.DataFrame()
    alerted = set(alerts["ACCOUNT_ID"]) if not alerts.empty else set()

    lines = [
        "digraph G {",
        f'  graph [rankdir={rankdir}, bgcolor="transparent", pad="0.3", nodesep="0.35", ranksep="0.7", '
        'fontname="Helvetica", splines=true];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, penwidth=1.2, margin="0.16,0.08"];',
        '  edge [fontname="Helvetica", fontsize=9, arrowsize=0.7];',
    ]
    for acc in nodes:
        if acc in info.index:
            row = info.loc[acc]
            score = float(row.get("RISK_SCORE", 0) or 0)
            name = str(row.get("FULL_NAME", "") or "")
            status = str(row.get("STATUS", "") or "")
        else:
            score, name, status = 0.0, "External account", ""
        fill = risk_color(score)
        font = "#FFFFFF" if score >= 0.85 or 0.5 <= score < 0.70 else "#0B2E22"
        border = "#E5C778" if acc in alerted else "#0B4F3A"
        width = 3.2 if acc in focus else (2.4 if acc in alerted else 1.2)
        style = "rounded,filled,dashed" if status == "FROZEN" else "rounded,filled"
        short_name = name if len(name) <= 24 else name[:23] + "…"
        tag = "  ⚑ ALERT" if acc in alerted else ""
        frozen = "  · FROZEN" if status == "FROZEN" else ""
        label = f"{acc}{tag}\\n{_dot_escape(short_name)}\\nrisk {score:.2f}{frozen}"
        lines.append(
            f'  "{_dot_escape(acc)}" [label="{label}", fillcolor="{fill}", fontcolor="{font}", '
            f'color="{border}", penwidth={width}, style="{style}"];'
        )
    max_amt = float(edges["AMOUNT_INR"].max()) if not edges.empty else 1.0
    for _, e in edges.iterrows():
        hot = bool(flagged_txns.intersection(e["TRANSACTION_IDS"]))
        color = "#BA1A1A" if hot else "#0E6B4E"
        width = 1.0 + 3.0 * (float(e["AMOUNT_INR"]) / max_amt) ** 0.5
        count = int(e["TXN_COUNT"])
        label = _compact_inr(float(e["AMOUNT_INR"])) + (f" ×{count}" if count > 1 else "")
        lines.append(
            f'  "{_dot_escape(e["SRC"])}" -> "{_dot_escape(e["DST"])}" '
            f'[label="{label}", color="{color}", fontcolor="{color}", penwidth={width:.2f}];'
        )
    lines.append("}")
    return "\n".join(lines)
