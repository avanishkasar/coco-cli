"""
Network Intelligence Page — SentinelReg
Fund-flow graph over all transfers; connected rings show when separate
alerts are one laundering scheme.
"""

import streamlit as st

from utils import data, nav, network, ui


def render_network():
    mode = data.mode()
    alerts = data.alerts()
    accounts = data.accounts()
    txns = data.transactions()
    edges = network.flow_edges(txns)
    active = alerts[alerts["ALERT_STATUS"].isin(data.ACTIVE_STATUSES)] if not alerts.empty else alerts
    rings = network.ring_summary(edges, alerts)

    ui.page_header(
        title="Network Intelligence",
        subtitle="Every transfer is an edge. Connected rings expose layering schemes that alert-by-alert review misses.",
        eyebrow="Fund-flow analysis", eyebrow_icon="hub", mode=mode,
    )
    if edges.empty:
        st.info("No transfers between accounts in TRANSACTIONS.")
        return

    nodes = set(edges["SRC"]) | set(edges["DST"])
    ui.kpi_cards([
        {"label": "Accounts in network", "value": len(nodes), "sub": "Sent or received a transfer", "icon": "hub"},
        {"label": "Transfer links", "value": len(edges), "sub": f"{int(edges['TXN_COUNT'].sum())} transfers", "icon": "share"},
        {"label": "Rings", "value": len(rings), "sub": "Connected components", "icon": "bubble_chart"},
        {"label": "Largest ring", "value": int(rings.iloc[0]["ACCOUNTS"]) if not rings.empty else 0,
         "sub": f"{int(rings.iloc[0]['ALERTS'])} alerts inside" if not rings.empty else "", "icon": "crisis_alert",
         "tone": "critical"},
        {"label": "Flow mapped", "value": data.format_inr(edges["AMOUNT_INR"].sum(), compact=True), "sub": "All transfers",
         "icon": "payments", "tone": "gold"},
    ])

    if not rings.empty and rings.iloc[0]["ALERTS"] >= 2:
        top = rings.iloc[0]
        ui.callout(
            f"Ring {top['RING']}: {int(top['ALERTS'])} alerts, one scheme",
            f"{int(top['ACCOUNTS'])} accounts ({top['MEMBERS']}) are linked by {int(top['TRANSFERS'])} transfers worth "
            f"{data.format_inr(top['FLOW_INR'], compact=True)}. Alerts {top['ALERT_IDS']} should be investigated together.",
            tone="red", callout_icon="hub",
        )

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.4, 1.2, 1])
        ring_opts = ["All rings"] + list(rings["RING"])
        ring = c1.selectbox("Ring", ring_opts, format_func=lambda r: r if r == "All rings" else
                            f"{r} — {int(rings.set_index('RING').loc[r, 'ACCOUNTS'])} accounts")
        min_amt = c2.select_slider("Hide transfers below", options=[0, 10_000, 100_000, 1_000_000, 5_000_000],
                                   value=0, format_func=lambda v: data.format_inr(v, compact=True) if v else "show all")
        layout = c3.segmented_control("Layout", ["Left → right", "Top → bottom"], default="Left → right")
        view = edges[edges["AMOUNT_INR"] >= min_amt]
        if ring != "All rings":
            members = set(rings.set_index("RING").loc[ring, "MEMBERS"].split(", "))
            view = view[view["SRC"].isin(members) & view["DST"].isin(members)]
        flagged = {t for ids in active["TRANSACTION_IDS"] for t in ids} if not active.empty else set()
        if view.empty:
            st.caption("No transfers match these filters.")
        else:
            st.graphviz_chart(
                network.build_dot(view, accounts, active, flagged_txns=flagged,
                                  rankdir="TB" if layout == "Top → bottom" else "LR"),
                width="stretch",
            )
        ui.render(
            '<div class="sr-card-meta">Node colour = rule-based risk (red ≥0.85, gold ≥0.70, green ≥0.50) · '
            'gold border + ⚑ = account with an alert · dashed = frozen · red edge = transfer cited in an active alert · '
            'edge width ∝ amount</div>'
        )

    left, right = st.columns([1.1, 1], gap="medium")
    with left, st.container(border=True):
        ui.section("Rings", "Weakly connected components, largest first", "bubble_chart")
        st.dataframe(rings, hide_index=True, width="stretch",
                     column_config={"FLOW_INR": st.column_config.NumberColumn("Flow (₹)", format="%,.0f")})
    with right, st.container(border=True):
        ui.section("Heaviest links", "Aggregated by sender → receiver", "trending_up")
        st.dataframe(
            edges[["SRC", "DST", "AMOUNT_INR", "TXN_COUNT", "FIRST_TS"]].head(15),
            hide_index=True, width="stretch",
            column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                           "FIRST_TS": st.column_config.DatetimeColumn("First", format="DD MMM YYYY")},
        )
        nav.link("entity", "Open Entity 360", icon=":material/person_search:")
