"""
Overview Page — SentinelReg
Command-center landing page: KPIs, priority queue with filing clocks,
exposure mix, the fund-flow network insight, and how the copilot works.
"""

import altair as alt
import pandas as pd
import streamlit as st

from utils import data, network, nav, ui

FLOW_STEPS = [
    ("01", "database", "Ingest", "Transactions, accounts, KYC profiles and RBI / FATF / Basel / FinCEN text "
                                 "live in Snowflake tables.", "Snowflake"),
    ("02", "radar", "Detect", "Five typology rules and a Snowpark ML classifier score every account and "
                              "raise alerts.", "Fraud signal triage"),
    ("03", "forum", "Investigate", "Ask in plain English — Cortex Analyst writes and runs the SQL; Entity 360 "
                                   "and the network map add context.", "Natural-language Q&A"),
    ("04", "description", "Report", "SAR narrative drafted by Cortex AI; every citation is traced to a "
                                    "regulatory clause in the corpus.", "Audit-ready reports"),
    ("05", "verified_user", "Audit", "Every triage decision and filing is written to a hash-chained, "
                                     "tamper-evident log.", "Evidence trail"),
]


def _priority_rows(active: pd.DataFrame, as_of: pd.Timestamp) -> list[dict]:
    rows = []
    for a in active.to_dict("records"):
        clock = data.filing_clock(a, reference=as_of)
        rows.append({**a, "_clock": clock, "_days": clock["days_left"] if clock["days_left"] is not None else 999})
    rows.sort(key=lambda r: (data.SEVERITY_ORDER.get(r["ALERT_SEVERITY"], 9), r["_days"]))
    return rows


def render_overview():
    mode = data.mode()
    as_of = data.as_of()
    alerts = data.alerts()
    active = alerts[alerts["ALERT_STATUS"].isin(data.ACTIVE_STATUSES)] if not alerts.empty else alerts
    k = data.kpis()
    clocks = [data.filing_clock(a, reference=as_of) for a in active.to_dict("records")]
    overdue = sum(1 for c in clocks if c["state"] == "OVERDUE")
    due_soon = sum(1 for c in clocks if c["state"] == "DUE_SOON")

    ui.page_header(
        title="Compliance Command Center",
        subtitle="Fraud signal triage, plain-English investigation and audit-ready SAR filing — "
                 "one copilot running on Snowflake.",
        eyebrow="Risk · Fraud · Regulatory Intelligence",
        eyebrow_icon="shield_with_heart",
        chips=[("event", f"Data as of {as_of:%d %b %Y, %H:%M}"), ("badge", data.current_analyst())],
        mode=mode,
    )
    if mode == "DEMO":
        ui.demo_notice(data.mode_reason())

    ui.kpi_cards([
        {"label": "Open alerts", "value": k["open_alerts"], "sub": f"{k['unassigned']} unassigned",
         "icon": "notifications_active"},
        {"label": "Critical", "value": k["critical"], "sub": "Immediate escalation", "icon": "crisis_alert",
         "tone": "critical", "pulse": k["critical"] > 0},
        {"label": "Exposure under review", "value": data.format_inr(k["exposure_inr"], compact=True),
         "sub": "Sum of active alert amounts", "icon": "account_balance", "tone": "gold"},
        {"label": "High-risk accounts", "value": k["high_risk_accounts"], "sub": "Rule score above 0.70",
         "icon": "warning", "tone": "high"},
        {"label": "Filings overdue", "value": overdue, "sub": f"{due_soon} due within 2 days",
         "icon": "timer", "tone": "critical" if overdue else ""},
        {"label": "SARs filed", "value": k["sar_filed"], "sub": f"{k['sar_pending']} escalated, awaiting filing",
         "icon": "task_alt"},
    ])

    left, right = st.columns([1.4, 1], gap="medium")
    with left, st.container(border=True):
        ui.section("Priority queue", "Active alerts ranked by severity, then by time left on the filing clock "
                                     "(7 days from alert, RBI-KYC-003)", "priority_high")
        rows = _priority_rows(active, as_of)
        if not rows:
            ui.callout("Queue clear", "No active alerts — every case has a disposition.", tone="green",
                       callout_icon="task_alt")
        for i, a in enumerate(rows[:6]):
            sev = ui.SEVERITY_CLASS.get(a["ALERT_SEVERITY"], "low")
            item, action = st.columns([5, 1.3], vertical_alignment="center")
            with item:
                ui.render(
                    f'<div class="sr-queue-item" style="animation-delay:{i * 0.05:.2f}s">'
                    f'<div class="sr-queue-sev {sev}"></div>'
                    f'<div style="min-width:0"><div class="sr-queue-title">{ui.esc(a["ALERT_ID"])}</div>'
                    f'<div class="sr-queue-sub">{ui.esc(a["ALERT_TYPE"])} · {ui.esc(a.get("CUSTOMER") or a["CUSTOMER_ID"])}</div>'
                    f'<div class="sr-queue-sub">{ui.esc(a["ACCOUNT_ID"])} · {ui.esc(a.get("ANALYST_ASSIGNED") or "Unassigned")}</div></div>'
                    f'<div class="sr-queue-right"><div class="sr-queue-amt">'
                    f'{ui.esc(data.format_inr(a["TOTAL_AMOUNT_INR"], compact=True))}</div>'
                    f'<div style="margin-top:4px">{ui.severity_badge(a["ALERT_SEVERITY"])} {ui.clock_badge(a["_clock"])}</div>'
                    f'</div></div>'
                )
            with action:
                if st.button(" ", key=f"ov_open_{a['ALERT_ID']}", icon=":material/arrow_forward:", width="stretch"):
                    nav.goto("triage", triage_alert_id=a["ALERT_ID"])

    with right:
        with st.container(border=True):
            ui.section("Severity mix", "Active alerts", "donut_large")
            if active.empty:
                st.caption("No active alerts.")
            else:
                sev = active.groupby("ALERT_SEVERITY").size().reset_index(name="ALERTS")
                base = alt.Chart(sev).encode(
                    theta=alt.Theta("ALERTS:Q", stack=True),
                    color=alt.Color("ALERT_SEVERITY:N", title=None, legend=alt.Legend(orient="bottom", columns=2, labelFontSize=11, symbolSize=70),
                                    scale=alt.Scale(domain=list(data.SEVERITY_COLORS),
                                                    range=list(data.SEVERITY_COLORS.values()))),
                    tooltip=[alt.Tooltip("ALERT_SEVERITY:N", title="Severity"), alt.Tooltip("ALERTS:Q", title="Alerts")],
                )
                donut = base.mark_arc(innerRadius=50, outerRadius=80, cornerRadius=4, padAngle=0.02)
                total = alt.Chart(pd.DataFrame({"t": [f"{len(active)}"]})).mark_text(
                    font="Playfair Display", fontSize=30, fontWeight=600, color="#0B2E22").encode(text="t:N")
                st.altair_chart(
                    ui.style_chart((donut + total).properties(height=210, padding={"top": 14, "bottom": 6, "left": 6, "right": 6})),
                    width="stretch",
                )

        with st.container(border=True):
            ui.section("Exposure by typology", "Active alert amounts", "stacked_bar_chart")
            if not active.empty:
                ex = active.groupby("ALERT_TYPE", as_index=False)["TOTAL_AMOUNT_INR"].sum()
                ex["CRORE"] = ex["TOTAL_AMOUNT_INR"] / 1e7
                bars = alt.Chart(ex).mark_bar(cornerRadiusEnd=6, height=18, color="#0E6B4E").encode(
                    x=alt.X("CRORE:Q", title="₹ crore"),
                    y=alt.Y("ALERT_TYPE:N", sort="-x", title=None),
                    tooltip=[alt.Tooltip("ALERT_TYPE:N", title="Typology"),
                             alt.Tooltip("CRORE:Q", title="₹ crore", format=",.2f")],
                )
                st.altair_chart(ui.style_chart(bars.properties(height=180)), width="stretch")

    # ── Network insight ───────────────────────────────────────
    txns = data.transactions()
    edges = network.flow_edges(txns)
    rings = network.ring_summary(edges, active)
    with st.container(border=True):
        ui.section("Network intelligence", "Alerts raised one at a time can belong to one scheme. "
                                           "Connected transfers reveal it.", "hub")
        if rings.empty or rings.iloc[0]["ALERTS"] < 2:
            st.caption("No multi-alert fund-flow rings in the current data.")
        else:
            top = rings.iloc[0]
            ring_members = set(top["MEMBERS"].split(", "))
            ui.callout(
                f"{int(top['ALERTS'])} of {len(active)} active alerts sit in one connected fund-flow network",
                f"Ring {top['RING']} links {int(top['ACCOUNTS'])} accounts through {int(top['TRANSFERS'])} transfers "
                f"worth {data.format_inr(top['FLOW_INR'], compact=True)}. Alerts: {top['ALERT_IDS']}. "
                "Treat them as one case: a single SAR with the full network is stronger evidence than separate filings.",
                tone="red", callout_icon="hub",
            )
            g_col, t_col = st.columns([2.2, 1], gap="medium")
            with g_col:
                ring_edges = edges[edges["SRC"].isin(ring_members) & edges["DST"].isin(ring_members)]
                flagged = {t for ids in active["TRANSACTION_IDS"] for t in ids}
                st.graphviz_chart(network.build_dot(ring_edges, data.accounts(), active, flagged_txns=flagged),
                                  width="stretch")
            with t_col:
                st.dataframe(
                    rings[["RING", "ACCOUNTS", "ALERTS", "FLOW_INR"]],
                    hide_index=True, width="stretch",
                    column_config={"FLOW_INR": st.column_config.NumberColumn("Flow (₹)", format="%,.0f")},
                )
                nav.link("network", "Open network map", icon=":material/hub:")

    # ── How it works ──────────────────────────────────────────
    ui.section("How SentinelReg answers the problem statement",
               "Transactions + account records + AML/Basel texts in → triaged fraud signals, cited answers and "
               "audit-ready reports out", "route")
    steps = "".join(
        f'<div class="sr-flow-step" style="animation-delay:{i * 0.07:.2f}s"><div class="sr-flow-num">{num}</div>'
        f'<div class="sr-flow-title">{ui.icon(ic)}{ui.esc(title)}</div>'
        f'<div class="sr-flow-body">{ui.esc(body)}</div><div class="sr-flow-tag">{ui.esc(tag)}</div></div>'
        for i, (num, ic, title, body, tag) in enumerate(FLOW_STEPS)
    )
    ui.render(f'<div class="sr-flow">{steps}</div>')

    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        nav.link("triage", "Triage alerts", icon=":material/notifications_active:")
    with c2:
        nav.link("copilot", "Ask the copilot", icon=":material/forum:")
    with c3:
        nav.link("sar", "Draft a SAR", icon=":material/description:")
    with c4:
        nav.link("regulatory", "Search regulations", icon=":material/menu_book:")
