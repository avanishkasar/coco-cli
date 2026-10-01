"""
Entity 360 Page — SentinelReg
One customer, everything about them: KYC profile, accounts, risk drivers,
transactions, alerts, fund-flow neighbourhood and applicable regulations.
"""

import altair as alt
import pandas as pd
import streamlit as st

from utils import data, nav, network, ui
from utils.risk_signals import run_all_detectors

KYC_REFRESH_YEARS = {"HIGH": 2, "PROHIBITED": 2, "MEDIUM": 8, "LOW": 10}  # RBI-KYC-001


def render_entity_360():
    mode = data.mode()
    customers = data.customers()
    accounts = data.accounts()
    alerts = data.alerts()
    txns = data.transactions()
    as_of = data.as_of()

    ui.page_header(
        title="Entity 360",
        subtitle="KYC profile, accounts, risk drivers, money movement and alerts for one customer — on one screen.",
        eyebrow="Customer intelligence", eyebrow_icon="person_search", mode=mode,
    )
    if customers.empty:
        st.info("No customers found.")
        return

    max_risk = accounts.groupby("CUSTOMER_ID")["RISK_SCORE"].max() if not accounts.empty else pd.Series(dtype=float)
    ordered = customers.assign(_R=customers["CUSTOMER_ID"].map(max_risk).fillna(0)).sort_values("_R", ascending=False)
    ids = list(ordered["CUSTOMER_ID"])
    focus = st.session_state.pop("entity_focus", None)
    if focus in ids:
        st.session_state["entity_customer"] = focus
    if st.session_state.get("entity_customer") not in ids:
        st.session_state["entity_customer"] = ids[0]
    names = dict(zip(ordered["CUSTOMER_ID"], ordered["FULL_NAME"]))
    cid = st.selectbox("Customer", ids, key="entity_customer",
                       format_func=lambda c: f"{names[c]}  ·  {c}  ·  max risk {max_risk.get(c, 0):.2f}")

    c = data.customer(cid) or {}
    accs = accounts[accounts["CUSTOMER_ID"] == cid]
    acc_ids = set(accs["ACCOUNT_ID"])
    c_alerts = alerts[alerts["CUSTOMER_ID"] == cid] if not alerts.empty else alerts
    active = c_alerts[c_alerts["ALERT_STATUS"].isin(data.ACTIVE_STATUSES)] if not c_alerts.empty else c_alerts
    c_txns = txns[txns["ACCOUNT_ID"].isin(acc_ids) | txns["COUNTERPARTY_ACCOUNT"].isin(acc_ids)] if not txns.empty else txns
    ml = data.ml_features()
    c_ml = ml[ml["ACCOUNT_ID"].isin(acc_ids)] if not ml.empty else ml
    top_risk = float(accs["RISK_SCORE"].max()) if not accs.empty else 0.0
    top_ml = float(c_ml["COMPUTED_RISK_SCORE"].max()) if not c_ml.empty else None

    # ── Profile card ──────────────────────────────────────────
    tier = str(c.get("KYC_TIER", "—")).upper()
    tier_tone = {"HIGH": "critical", "PROHIBITED": "critical", "MEDIUM": "high", "LOW": "ok"}.get(tier, "neutral")
    badges = ui.badge(f"KYC {tier}", tier_tone) + ui.badge(str(c.get("ENTITY_TYPE", "—")), "neutral", dot=False)
    if c.get("PEP_FLAG"):
        badges += ui.badge("PEP", "gold")
    if c.get("SANCTIONS_FLAG"):
        badges += ui.badge("Sanctions match", "critical")
    if (accs["STATUS"] == "FROZEN").any():
        badges += ui.badge("Frozen account", "dark", dot=False)

    refresh_txt, refresh_tone = "—", "neutral"
    last_kyc = pd.to_datetime(c.get("LAST_KYC_REFRESH"), errors="coerce")
    years = KYC_REFRESH_YEARS.get(tier)
    if pd.notna(last_kyc) and years:
        due = last_kyc + pd.DateOffset(years=years)
        overdue = due < as_of
        refresh_txt = f"{'Overdue since' if overdue else 'Due'} {due:%d %b %Y} ({years}-yearly for {tier} risk, RBI-KYC-001)"
        refresh_tone = "critical" if overdue else "ok"

    with st.container(border=True):
        ui.render(
            f'<div class="sr-profile"><div class="sr-avatar">{ui.esc(ui.initials(c.get("FULL_NAME")))}</div>'
            f'<div style="flex:1"><div class="sr-profile-name">{ui.esc(c.get("FULL_NAME"))}</div>'
            f'<div class="sr-card-meta">{ui.esc(cid)} · {ui.esc(c.get("OCCUPATION", "—"))} · {ui.esc(c.get("COUNTRY_OF_ORIGIN", "—"))} · '
            f'RM {ui.esc(c.get("RELATIONSHIP_MANAGER", "—"))} · customer since {ui.esc(data.clean(c.get("ACCOUNT_OPEN_DATE"))[:10])}</div>'
            f'<div class="sr-profile-meta">{badges}</div></div>'
            f'<div style="min-width:180px"><div class="sr-kpi-label">Max account risk</div>'
            f'<div class="sr-kpi-value" style="font-size:1.7rem">{top_risk:.2f}</div>{ui.gauge(top_risk)}</div></div>'
        )
        meta = f"KYC refresh: {ui.badge(refresh_txt, refresh_tone, dot=False)}"
        if c.get("NOTES"):
            meta += f' &nbsp; <span class="sr-muted" style="font-size:.82rem">Note on file: {ui.esc(c["NOTES"])}</span>'
        ui.render(f'<div style="margin-top:.7rem">{meta}</div>')

    ui.kpi_cards([
        {"label": "Accounts", "value": len(accs), "sub": ", ".join(sorted(acc_ids)) or "—", "icon": "account_balance_wallet"},
        {"label": "Balance", "value": data.format_inr(accs["CURRENT_BALANCE_INR"].sum(), compact=True),
         "sub": "Across all accounts", "icon": "savings"},
        {"label": "ML risk score", "value": f"{top_ml:.2f}" if top_ml is not None else "—",
         "sub": "Snowpark ML (max)", "icon": "model_training", "tone": "critical" if (top_ml or 0) >= 0.85 else ""},
        {"label": "Active alerts", "value": len(active), "sub": data.format_inr(active["TOTAL_AMOUNT_INR"].sum(), compact=True)
         if not active.empty else "None", "icon": "notifications_active", "tone": "critical" if len(active) else ""},
        {"label": "Transactions", "value": len(c_txns), "sub": "Sent, received or cash", "icon": "swap_horiz"},
    ])

    # ── Risk drivers ──────────────────────────────────────────
    sigs = [s for s in run_all_detectors(txns) if s.account_id in acc_ids] if not txns.empty else []
    drivers = []
    if c.get("SANCTIONS_FLAG"):
        drivers.append(("Sanctions match", "screening hit", "critical"))
    if c.get("PEP_FLAG"):
        drivers.append(("Politically exposed", "EDD required", "high"))
    if tier in {"HIGH", "PROHIBITED"}:
        drivers.append((f"KYC tier {tier}", "customer risk rating", "high"))
    for s in sigs:
        drivers.append((s.typology.replace("_", " ").title(), f"{s.account_id}: rule fired", s.severity.lower()))
    for r in c_ml.to_dict("records"):
        if (r.get("GEOGRAPHIC_ANOMALY_SCORE") or 0) >= 0.5:
            drivers.append(("Geographic anomaly", f"{r['ACCOUNT_ID']} score {r['GEOGRAPHIC_ANOMALY_SCORE']:.2f}", "high"))
    tone_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "medium"}
    chips = "".join(
        f'<span class="sr-reason {tone_map.get(t, "medium")}">{ui.esc(a)} <small>{ui.esc(b)}</small></span>'
        for a, b, t in drivers
    ) or '<span class="sr-reason medium">No risk drivers detected</span>'
    ui.section("Risk drivers", "Screening flags, KYC rating, detection-engine hits and ML features", "psychology")
    ui.render(f'<div class="sr-reasons" style="margin-bottom:1rem">{chips}</div>')

    t1, t2, t3, t4, t5 = st.tabs([":material/account_balance_wallet: Accounts", ":material/swap_horiz: Transactions",
                                  ":material/notifications_active: Alerts", ":material/hub: Fund flow",
                                  ":material/menu_book: Regulations"])
    with t1:
        st.dataframe(
            accs[["ACCOUNT_ID", "ACCOUNT_TYPE", "STATUS", "IFSC_CODE", "OPENING_DATE", "CURRENT_BALANCE_INR",
                  "AVERAGE_MONTHLY_CREDIT", "RISK_SCORE"]],
            hide_index=True, width="stretch",
            column_config={"CURRENT_BALANCE_INR": st.column_config.NumberColumn("Balance (₹)", format="%,.0f"),
                           "AVERAGE_MONTHLY_CREDIT": st.column_config.NumberColumn("Avg monthly credit (₹)", format="%,.0f"),
                           "RISK_SCORE": st.column_config.ProgressColumn("Risk", min_value=0, max_value=1, format="%.2f")},
        )
    with t2:
        if c_txns.empty:
            st.caption("No transactions.")
        else:
            view = c_txns.copy()
            view["DIRECTION"] = view.apply(
                lambda r: "Cash" if r["IS_CASH"] else ("Out" if r["ACCOUNT_ID"] in acc_ids else "In"), axis=1)
            chart = alt.Chart(view).mark_bar(cornerRadiusEnd=3, width=10).encode(
                x=alt.X("TRANSACTION_DATE:T", title=None),
                y=alt.Y("AMOUNT_INR:Q", title="₹", scale=alt.Scale(type="symlog")),
                color=alt.Color("DIRECTION:N", title=None, scale=alt.Scale(domain=["In", "Out", "Cash"],
                                                                         range=["#0E6B4E", "#BA1A1A", "#C8A24A"])),
                tooltip=["TRANSACTION_ID", "DIRECTION", alt.Tooltip("AMOUNT_INR:Q", format=",.0f"), "NARRATION"],
            )
            st.altair_chart(ui.style_chart(chart.properties(height=220)), width="stretch")
            st.dataframe(
                view[["TRANSACTION_ID", "TRANSACTION_DATE", "DIRECTION", "ACCOUNT_ID", "COUNTERPARTY_ACCOUNT",
                      "AMOUNT_INR", "TRANSACTION_TYPE", "CHANNEL", "NARRATION"]],
                hide_index=True, width="stretch",
                column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                               "TRANSACTION_DATE": st.column_config.DatetimeColumn("When", format="DD MMM YYYY, HH:mm")},
            )
    with t3:
        if c_alerts.empty:
            ui.callout("No alerts", "This customer has never been alerted.", tone="green", callout_icon="task_alt")
        for a in c_alerts.to_dict("records"):
            ui.render(
                f'<div class="sr-card"><div class="sr-card-head"><div class="sr-card-title">{ui.esc(a["ALERT_ID"])} · '
                f'{ui.esc(a["ALERT_TYPE"])} · {ui.esc(data.format_inr(a["TOTAL_AMOUNT_INR"], compact=True))}</div>'
                f'<div>{ui.severity_badge(a["ALERT_SEVERITY"])} {ui.status_badge(a["ALERT_STATUS"])}</div></div>'
                f'<div class="sr-card-meta">{ui.esc(a.get("TRIGGER_RULE"))}</div>'
                f'<div class="sr-card-meta">{ui.esc(a.get("INVESTIGATION_NOTES") or "No notes yet.")}</div></div>'
            )
        if not active.empty:
            b1, b2 = st.columns(2)
            first = active.iloc[0]["ALERT_ID"]
            if b1.button("Triage top alert", icon=":material/gavel:", width="stretch"):
                nav.goto("triage", triage_alert_id=first)
            if b2.button("Draft SAR", icon=":material/description:", width="stretch", type="primary"):
                nav.goto("sar", sar_alert_id=first)
    with t4:
        edges = network.flow_edges(txns)
        hood = network.neighborhood(edges, acc_ids, hops=2)
        if hood.empty:
            st.caption("No transfers involving this customer's accounts.")
        else:
            flagged = {t for ids_ in alerts["TRANSACTION_IDS"] for t in ids_} if not alerts.empty else set()
            st.caption("Two hops out from this customer's accounts (thick gold border = this customer; red edges = alerted transfers).")
            st.graphviz_chart(network.build_dot(hood, accounts, alerts, focus=acc_ids, flagged_txns=flagged), width="stretch")
    with t5:
        ids_ = []
        for a in c_alerts.to_dict("records"):
            ids_ += data.TYPOLOGY_CITATIONS.get(a["ALERT_TYPE"], [])
        if c.get("PEP_FLAG") or tier in {"HIGH", "PROHIBITED"}:
            ids_.append("RBI-KYC-004")
        ids_ += ["RBI-KYC-001", "RBI-KYC-003"]
        for r in data.chunks_by_id(ids_).to_dict("records"):
            ui.render(
                f'<div class="sr-clause"><div class="sr-clause-head">{ui.badge(r["CHUNK_ID"], "dark", dot=False)}'
                f'<span class="sr-clause-title">{ui.esc(r["DOC_TYPE"])} {ui.esc(r["SECTION_NUMBER"])} — {ui.esc(r["SECTION_TITLE"])}</span></div>'
                f'<div class="sr-clause-doc">{ui.esc(r["DOC_NAME"])} · {ui.esc(r["JURISDICTION"])}</div>'
                f'<div class="sr-clause-text">{ui.esc(r["CHUNK_TEXT"])}</div></div>'
            )
