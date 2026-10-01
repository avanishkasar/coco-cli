"""
Alert Triage Page (Risk Dashboard) — SentinelReg
Human-in-the-loop alert queue, re-runnable detection engine, ML model
comparison and transaction monitoring.
"""

import altair as alt
import pandas as pd
import streamlit as st

from utils import data, nav, ui
from utils.risk_signals import RULE_CATALOGUE, run_all_detectors, signals_frame

SEVERITY_COLORS = data.SEVERITY_COLORS
SEVERITY_OPTIONS = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _reason_codes(row: dict) -> list[tuple[str, str, str]]:
    """(label, detail, tone) reason codes from ML feature thresholds."""
    out = []
    if (row.get("JUST_BELOW_THRESHOLD_COUNT") or 0) >= 3:
        out.append(("Structuring proxy", f"{int(row['JUST_BELOW_THRESHOLD_COUNT'])} txns just below ₹50k", "critical"))
    if (row.get("VELOCITY_SCORE") or 0) >= 0.7:
        out.append(("High velocity", f"score {row['VELOCITY_SCORE']:.2f}", "high"))
    if (row.get("CASH_TXN_RATIO_30D") or 0) >= 0.7:
        out.append(("Cash intensive", f"{row['CASH_TXN_RATIO_30D']:.0%} cash", "high"))
    if row.get("ROUND_TRIP_DETECTED"):
        out.append(("Round trip", "funds returned", "critical"))
    if (row.get("GEOGRAPHIC_ANOMALY_SCORE") or 0) >= 0.5:
        out.append(("Geographic anomaly", f"score {row['GEOGRAPHIC_ANOMALY_SCORE']:.2f}", "high"))
    return out


def _queue_tab(alerts: pd.DataFrame, as_of: pd.Timestamp):
    if alerts.empty:
        st.info("No alerts in AML_ALERTS.")
        return

    f1, f2, f3 = st.columns([1.6, 1.4, 1.6])
    with f1:
        sev = st.segmented_control("Severity", SEVERITY_OPTIONS, default="All", key="triage_sev")
    with f2:
        scope = st.segmented_control("Status", ["Active", "Closed", "All"], default="Active", key="triage_scope")
    with f3:
        search = st.text_input("Search", placeholder="Alert, customer, account or typology…", key="alert_search")

    df = alerts.copy()
    if scope == "Active":
        df = df[df["ALERT_STATUS"].isin(data.ACTIVE_STATUSES)]
    elif scope == "Closed":
        df = df[df["ALERT_STATUS"].isin(data.CLOSED_STATUSES)]
    if sev and sev != "All":
        df = df[df["ALERT_SEVERITY"] == sev]
    if search:
        hay = df[["ALERT_ID", "CUSTOMER", "ACCOUNT_ID", "ALERT_TYPE", "CUSTOMER_ID"]].astype(str).agg(" ".join, axis=1)
        df = df[hay.str.lower().str.contains(search.lower(), regex=False)]

    clocks = [data.filing_clock(a, reference=as_of) for a in df.to_dict("records")]
    view = pd.DataFrame({
        "Alert": df["ALERT_ID"],
        "Severity": df["ALERT_SEVERITY"],
        "Typology": df["ALERT_TYPE"],
        "Customer": df["CUSTOMER"],
        "Account": df["ACCOUNT_ID"],
        "Amount (₹)": df["TOTAL_AMOUNT_INR"],
        "Status": df["ALERT_STATUS"].str.replace("_", " ").str.title(),
        "Analyst": df["ANALYST_ASSIGNED"].fillna("— unassigned"),
        "STR clock (days)": [c["days_left"] if c["state"] != "FILED" else None for c in clocks],
        "Detected": df["ALERT_DATE"],
    })
    st.caption(f"Showing {len(view)} of {len(alerts)} alerts · filing clock measured against data as of {as_of:%d %b %Y %H:%M}; "
               "negative = overdue")
    st.dataframe(
        view.style.map(lambda v: f"color:{SEVERITY_COLORS.get(v, '#16241E')};font-weight:700", subset=["Severity"]),
        hide_index=True, width="stretch",
        column_config={
            "Amount (₹)": st.column_config.NumberColumn(format="%,.0f"),
            "Detected": st.column_config.DatetimeColumn(format="DD MMM YYYY, HH:mm"),
            "STR clock (days)": st.column_config.NumberColumn(help="Days left in the 7-day STR window (RBI-KYC-003)"),
        },
    )
    if df.empty:
        return

    ids = list(df["ALERT_ID"])
    preset = st.session_state.pop("triage_alert_id", None)
    if preset in ids:
        st.session_state["triage_case"] = preset
    if st.session_state.get("triage_case") not in ids:
        st.session_state["triage_case"] = ids[0]
    labels = {r["ALERT_ID"]: f"{r['ALERT_ID']} — {r['ALERT_TYPE']} · {r['ALERT_SEVERITY']} · {r['CUSTOMER']}"
              for r in df.to_dict("records")}
    case_id = st.selectbox("Open case", ids, format_func=lambda x: labels[x], key="triage_case")
    a = data.alert(case_id)
    if not a:
        return
    _case_panel(a, as_of)


def _case_panel(a: dict, as_of: pd.Timestamp):
    clock = data.filing_clock(a, reference=as_of)
    cust = data.customer(a["CUSTOMER_ID"]) or {}
    txns = data.transactions()
    ev = txns[txns["TRANSACTION_ID"].isin(a["TRANSACTION_IDS"])] if not txns.empty else txns

    with st.container(border=True):
        flags = ""
        if cust.get("PEP_FLAG"):
            flags += ui.badge("PEP", "gold")
        if cust.get("SANCTIONS_FLAG"):
            flags += ui.badge("Sanctions match", "critical")
        ui.render(
            f'<div class="sr-card-head"><div><div class="sr-card-title" style="font-size:1.1rem">'
            f'{ui.esc(a["ALERT_ID"])} · {ui.esc(a["ALERT_TYPE"])}</div>'
            f'<div class="sr-card-meta">{ui.esc(cust.get("FULL_NAME", a.get("CUSTOMER")))} · {ui.esc(a["ACCOUNT_ID"])} · '
            f'KYC {ui.esc(cust.get("KYC_TIER", "—"))} · detected {pd.Timestamp(a["ALERT_DATE"]):%d %b %Y %H:%M}</div></div>'
            f'<div>{ui.severity_badge(a["ALERT_SEVERITY"])} {ui.status_badge(a["ALERT_STATUS"])} '
            f'{ui.clock_badge(clock)} {flags}</div></div>'
        )
        c1, c2 = st.columns([1.35, 1], gap="large")
        with c1:
            st.markdown(f"**Trigger rule** — {a.get('TRIGGER_RULE') or '—'}")
            st.markdown(f"**Amount** — {data.format_inr(a['TOTAL_AMOUNT_INR'])} "
                        f"({data.format_inr(a['TOTAL_AMOUNT_INR'], compact=True)}) across {len(ev)} transaction(s)")
            st.dataframe(
                ev[["TRANSACTION_ID", "TRANSACTION_DATE", "AMOUNT_INR", "TRANSACTION_TYPE", "COUNTERPARTY_ACCOUNT", "NARRATION"]],
                hide_index=True, width="stretch",
                column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                               "TRANSACTION_DATE": st.column_config.DatetimeColumn("When", format="DD MMM, HH:mm")},
            )
        with c2:
            st.markdown("**Analyst decision**")
            with st.form(f"triage_form_{a['ALERT_ID']}", border=False):
                statuses = list(data.TRIAGE_STATUSES)
                current = a["ALERT_STATUS"] if a["ALERT_STATUS"] in statuses else statuses[0]
                status = st.selectbox("Disposition", statuses, index=statuses.index(current),
                                      format_func=lambda s: s.replace("_", " ").title())
                analyst = st.text_input("Assigned analyst", value=a.get("ANALYST_ASSIGNED") or data.current_analyst())
                note = st.text_area("Add case note", placeholder="What did you verify? Why this disposition?", height=90)
                saved = st.form_submit_button("Save decision", icon=":material/gavel:", width="stretch", type="primary")
            if saved:
                notes = a.get("INVESTIGATION_NOTES") or ""
                if note.strip():
                    stamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    notes = (notes + "\n" if notes else "") + f"[{stamp} · {analyst.strip()}] {note.strip()}"
                ok, err = data.update_alert(a["ALERT_ID"], status, analyst.strip(), notes)
                if ok:
                    data.log_event(
                        "TRIAGE_DECISION", a["ALERT_ID"],
                        f"Status {a['ALERT_STATUS']} → {status}; analyst {analyst.strip()}"
                        + (f"; note: {note.strip()}" if note.strip() else ""),
                    )
                    st.toast(f"{a['ALERT_ID']} saved as {status.replace('_', ' ').title()}", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.error(f"Could not save: {err}")
            if a.get("INVESTIGATION_NOTES"):
                with st.expander("Case notes", expanded=False):
                    st.text(a["INVESTIGATION_NOTES"])

        b1, b2, b3 = st.columns(3)
        if b1.button("Ask the copilot", icon=":material/forum:", width="stretch", key=f"ask_{a['ALERT_ID']}"):
            nav.goto("copilot", pending_prompt=f"Explain alert {a['ALERT_ID']} and summarise the evidence.")
        if b2.button("Entity 360", icon=":material/person_search:", width="stretch", key=f"e360_{a['ALERT_ID']}"):
            nav.goto("entity", entity_focus=a["CUSTOMER_ID"])
        if b3.button("Draft SAR", icon=":material/description:", width="stretch", type="primary", key=f"sar_{a['ALERT_ID']}"):
            nav.goto("sar", sar_alert_id=a["ALERT_ID"])


def _detection_tab(alerts: pd.DataFrame):
    ui.section("Detection engine", "The typology rules in utils/risk_signals.py re-run live over TRANSACTIONS, "
                                   "then reconciled against the alert queue", "radar")
    txns = data.transactions()
    sigs = signals_frame(run_all_detectors(txns))
    alert_txns = {a["ALERT_ID"]: set(a["TRANSACTION_IDS"]) for a in alerts.to_dict("records")} if not alerts.empty else {}

    def coverage(ids):
        hits = [aid for aid, t in alert_txns.items() if t.intersection(ids)]
        return ", ".join(hits) if hits else "NEW — no alert covers this"

    if not sigs.empty:
        sigs["COVERED_BY"] = sigs["TRANSACTION_IDS"].map(coverage)
    uncovered = int((sigs["COVERED_BY"].str.startswith("NEW")).sum()) if not sigs.empty else 0
    ui.kpi_cards([
        {"label": "Rules", "value": len(RULE_CATALOGUE), "sub": "Typologies monitored", "icon": "rule"},
        {"label": "Signals fired", "value": len(sigs), "sub": f"over {len(txns)} transactions", "icon": "sensors"},
        {"label": "Covered by alerts", "value": len(sigs) - uncovered, "sub": "Reconciled with AML_ALERTS", "icon": "link"},
        {"label": "Uncovered", "value": uncovered, "sub": "Candidates for new alerts", "icon": "new_releases",
         "tone": "high" if uncovered else ""},
    ])
    if sigs.empty:
        st.info("No detector fired on the current transactions.")
    else:
        st.dataframe(
            sigs.drop(columns=["TRANSACTION_IDS"]),
            hide_index=True, width="stretch",
            column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                           "DESCRIPTION": st.column_config.TextColumn(width="large")},
        )
    with st.expander("Rule catalogue", icon=":material/menu_book:"):
        st.dataframe(pd.DataFrame(RULE_CATALOGUE), hide_index=True, width="stretch")


def _ml_tab():
    ui.section("ML risk model — rule-based vs. Snowpark ML score",
               "COMPUTED_RISK_SCORE comes from ml_pipeline/fraud_classifier.py; points above the dashed line are "
               "accounts the model rates riskier than the rules", "model_training")
    ml = data.ml_features()
    if ml.empty:
        st.info("No ML feature snapshots yet — run `python ml_pipeline/fraud_classifier.py --mode score`.")
        return
    ml = ml.copy()
    ml["GAP"] = ml["COMPUTED_RISK_SCORE"] - ml["RISK_SCORE"]
    agree = int((ml["GAP"].abs() <= 0.1).sum())
    ui.kpi_cards([
        {"label": "Scored accounts", "value": len(ml), "sub": "Latest feature snapshot", "icon": "model_training"},
        {"label": "Model ≈ rules", "value": agree, "sub": "within ±0.10", "icon": "balance"},
        {"label": "Model riskier", "value": int((ml["GAP"] > 0.1).sum()), "sub": "> 0.10 above rules",
         "icon": "trending_up", "tone": "high"},
        {"label": "Labelled fraud", "value": int(ml["IS_FRAUD_LABEL"].map(bool).sum()), "sub": "Training ground truth",
         "icon": "fact_check"},
    ])
    g, t = st.columns([1.1, 1.4], gap="medium")
    with g:
        diagonal = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(
            strokeDash=[4, 4], color="#A9A48C").encode(x="x", y="y")
        scatter = alt.Chart(ml).mark_circle(size=150, opacity=0.9, stroke="#FFFFFF", strokeWidth=1.5).encode(
            x=alt.X("RISK_SCORE:Q", title="Rule-based score", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("COMPUTED_RISK_SCORE:Q", title="ML score", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("COMPUTED_RISK_SCORE:Q", title="ML score",
                            scale=alt.Scale(range=["#8FB5A3", "#C8A24A", "#BA1A1A"], domain=[0, 0.6, 1])),
            tooltip=["ACCOUNT_ID", "FULL_NAME", alt.Tooltip("RISK_SCORE:Q", format=".2f"),
                     alt.Tooltip("COMPUTED_RISK_SCORE:Q", format=".2f")],
        )
        st.altair_chart(ui.style_chart((diagonal + scatter).properties(height=300)), width="stretch")
    with t:
        st.dataframe(
            ml[["ACCOUNT_ID", "FULL_NAME", "RISK_SCORE", "COMPUTED_RISK_SCORE", "CASH_TXN_RATIO_30D",
                "JUST_BELOW_THRESHOLD_COUNT", "VELOCITY_SCORE", "GEOGRAPHIC_ANOMALY_SCORE", "ROUND_TRIP_DETECTED"]],
            hide_index=True, width="stretch", height=300,
            column_config={
                "RISK_SCORE": st.column_config.ProgressColumn("Rule", min_value=0, max_value=1, format="%.2f"),
                "COMPUTED_RISK_SCORE": st.column_config.ProgressColumn("ML", min_value=0, max_value=1, format="%.2f"),
                "CASH_TXN_RATIO_30D": st.column_config.NumberColumn("Cash %", format="percent"),
            },
        )
    ui.section("Reason codes", "Which features push each high-scoring account up (feature thresholds)", "psychology")
    for r in ml[ml["COMPUTED_RISK_SCORE"] >= 0.5].to_dict("records"):
        codes = _reason_codes(r)
        chips = "".join(
            f'<span class="sr-reason {tone}">{ui.esc(lbl)} <small>{ui.esc(det)}</small></span>' for lbl, det, tone in codes
        ) or '<span class="sr-reason">No single feature dominant</span>'
        ui.render(
            f'<div class="sr-card"><div class="sr-card-head"><div class="sr-card-title">{ui.esc(r["ACCOUNT_ID"])} · '
            f'{ui.esc(r.get("FULL_NAME", ""))}</div>{ui.badge("ML " + format(r["COMPUTED_RISK_SCORE"], ".2f"), "dark", dot=False)}</div>'
            f'<div class="sr-reasons" style="margin-top:.5rem">{chips}</div></div>'
        )


def _monitor_tab(alerts: pd.DataFrame):
    txns = data.transactions()
    if txns.empty:
        st.info("No transactions.")
        return
    ui.section("Transaction timeline", "Every movement by amount (log scale). Red rules mark alert detections.", "timeline")
    tl = txns.copy()
    tl["KIND"] = tl["IS_CASH"].map({True: "Cash", False: "Transfer"})
    points = alt.Chart(tl).mark_circle(opacity=0.85, stroke="#FFFFFF", strokeWidth=1).encode(
        x=alt.X("TRANSACTION_DATE:T", title=None),
        y=alt.Y("AMOUNT_INR:Q", scale=alt.Scale(type="log"), title="Amount (₹, log)"),
        color=alt.Color("KIND:N", title=None, scale=alt.Scale(domain=["Cash", "Transfer"], range=["#C8A24A", "#0E6B4E"])),
        size=alt.Size("AMOUNT_INR:Q", legend=None, scale=alt.Scale(range=[40, 420])),
        tooltip=["TRANSACTION_ID", "ACCOUNT_ID", "COUNTERPARTY_ACCOUNT", alt.Tooltip("AMOUNT_INR:Q", format=",.0f"),
                 "TRANSACTION_TYPE", alt.Tooltip("TRANSACTION_DATE:T", format="%d %b %Y %H:%M")],
    )
    layers = points
    if not alerts.empty:
        rules = alt.Chart(alerts[["ALERT_ID", "ALERT_DATE", "ALERT_TYPE"]]).mark_rule(
            color="#BA1A1A", strokeDash=[3, 3], opacity=0.6).encode(x="ALERT_DATE:T", tooltip=["ALERT_ID", "ALERT_TYPE"])
        layers = rules + points
    st.altair_chart(ui.style_chart(layers.properties(height=300)), width="stretch")

    ui.section("Recent high-value cash transactions", "Cash movements of ₹40,000 or more", "payments")
    acc = data.accounts()[["ACCOUNT_ID", "FULL_NAME"]]
    cash = txns[txns["IS_CASH"] & (txns["AMOUNT_INR"] >= 40000)].merge(acc, on="ACCOUNT_ID", how="left").head(20)
    st.dataframe(
        cash[["TRANSACTION_ID", "ACCOUNT_ID", "FULL_NAME", "TRANSACTION_DATE", "TRANSACTION_TYPE", "AMOUNT_INR"]],
        hide_index=True, width="stretch",
        column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                       "TRANSACTION_DATE": st.column_config.DatetimeColumn("When", format="DD MMM YYYY, HH:mm")},
    )

    ui.section("High-risk accounts", "Rule-based score above 0.65", "warning")
    hr = data.accounts()
    hr = hr[hr["RISK_SCORE"] > 0.65].sort_values("RISK_SCORE", ascending=False)
    st.dataframe(
        hr[["ACCOUNT_ID", "FULL_NAME", "KYC_TIER", "STATUS", "PEP_FLAG", "SANCTIONS_FLAG", "RISK_SCORE"]],
        hide_index=True, width="stretch",
        column_config={"RISK_SCORE": st.column_config.ProgressColumn("Risk", min_value=0, max_value=1, format="%.2f")},
    )


def render_dashboard():
    mode = data.mode()
    as_of = data.as_of()
    alerts = data.alerts()
    k = data.kpis()
    ui.page_header(
        title="Alert Triage",
        subtitle="Review, assign and dispose of fraud signals — every decision is written back and audit-logged.",
        eyebrow="Fraud signal triage", eyebrow_icon="notifications_active",
        chips=[("event", f"Data as of {as_of:%d %b %Y}")], mode=mode,
    )

    @st.fragment(run_every="5m")
    def _kpi_row():
        kk = data.kpis()
        ui.kpi_cards([
            {"label": "Open alerts", "value": kk["open_alerts"], "sub": "Awaiting disposition", "icon": "notifications_active"},
            {"label": "Critical", "value": kk["critical"], "sub": "Immediate escalation", "icon": "crisis_alert",
             "tone": "critical", "pulse": kk["critical"] > 0},
            {"label": "Unassigned", "value": kk["unassigned"], "sub": "Need an owner", "icon": "person_off", "tone": "high"},
            {"label": "SAR pending", "value": kk["sar_pending"], "sub": "Escalated, not yet filed", "icon": "pending_actions"},
        ])

    _kpi_row()
    st.caption(f"KPIs refresh every 5 minutes · {k['transactions']} transactions · {k['accounts']} accounts monitored")

    t1, t2, t3, t4 = st.tabs([":material/inbox: Alert queue", ":material/radar: Detection engine",
                              ":material/model_training: ML risk model", ":material/monitoring: Transaction monitor"])
    with t1:
        _queue_tab(alerts, as_of)
    with t2:
        _detection_tab(alerts)
    with t3:
        _ml_tab()
    with t4:
        _monitor_tab(alerts)
