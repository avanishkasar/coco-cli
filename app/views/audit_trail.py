"""
Audit Trail Page — SentinelReg
Hash-chained log of every analyst decision, copilot query and SAR action,
with chain verification and export for examiners.
"""

import streamlit as st

from utils import data, ui

ACTION_TONE = {"SAR_FILED": "ok", "SAR_GENERATED": "gold", "TRIAGE_DECISION": "high", "COPILOT_QUERY": "neutral"}


def render_audit_trail():
    mode = data.mode()
    log = data.audit_log()
    intact, broken_at = data.verify_audit_chain(log)
    ui.page_header(
        title="Audit Trail",
        subtitle="Who reviewed what, when, and what they concluded — each entry hash-chained to the one before it, "
                 "so any edit breaks the chain.",
        eyebrow="Evidence & accountability", eyebrow_icon="verified_user",
        chips=[("storage", f"Stored in {data.audit_backend()}")], mode=mode,
    )

    ui.kpi_cards([
        {"label": "Events logged", "value": len(log), "sub": "All actions", "icon": "history"},
        {"label": "Analysts", "value": int(log["ANALYST"].nunique()) if not log.empty else 0, "sub": "Distinct actors",
         "icon": "group"},
        {"label": "Triage decisions", "value": int((log["ACTION"] == "TRIAGE_DECISION").sum()), "sub": "Dispositions saved",
         "icon": "gavel"},
        {"label": "SARs filed", "value": int((log["ACTION"] == "SAR_FILED").sum()),
         "sub": f"{int((log['ACTION'] == 'SAR_GENERATED').sum())} generated", "icon": "task_alt"},
        {"label": "Chain integrity", "value": "Verified" if intact else f"Broken at #{broken_at}",
         "sub": "SHA-256 hash chain", "icon": "link" if intact else "link_off", "tone": "" if intact else "critical"},
    ])

    if log.empty:
        ui.callout("No events yet",
                   "Triage an alert, ask the copilot or generate a SAR — each action is appended here with its hash.",
                   callout_icon="history")
    elif intact:
        ui.callout("Chain verified", f"All {len(log)} entries recompute to their stored SHA-256 hashes and link to "
                   "their predecessor. No entry has been altered or removed.", tone="green", callout_icon="verified")
    else:
        ui.callout("Chain broken", f"Entry #{broken_at} does not match its hash — the log was modified after it was "
                   "written.", tone="red", callout_icon="link_off")

    left, right = st.columns([1.25, 1], gap="medium")
    with left, st.container(border=True):
        ui.section("Timeline", "Most recent first", "timeline")
        actions = sorted(log["ACTION"].unique()) if not log.empty else []
        chosen = st.multiselect("Action", actions, default=actions, key="audit_actions", label_visibility="collapsed")
        view = log[log["ACTION"].isin(chosen)] if not log.empty else log
        items = "".join(
            f'<div class="sr-tl-item"><div class="sr-tl-head">{ui.badge(r["ACTION"].replace("_", " "), ACTION_TONE.get(r["ACTION"], "neutral"), dot=False)}'
            f'<b>{ui.esc(r["ENTITY_ID"])}</b><span class="sr-tl-time">#{int(r["EVENT_SEQ"])} · '
            f'{r["EVENT_TS"]:%d %b %Y %H:%M:%S} UTC · {ui.esc(r["ANALYST"])}</span></div>'
            f'<div class="sr-tl-detail">{ui.esc(r["DETAIL"])}</div>'
            f'<div class="sr-tl-hash">hash {ui.esc(r["ENTRY_HASH"][:20])}… ← prev {ui.esc(r["PREV_HASH"][:12])}…</div></div>'
            for r in view.sort_values("EVENT_SEQ", ascending=False).head(60).to_dict("records")
        )
        if items:
            ui.render(f'<div class="sr-timeline">{items}</div>')
        else:
            st.caption("Nothing to show.")

    with right:
        with st.container(border=True):
            ui.section("Alert dispositions", "Current status of every alert in AML_ALERTS", "fact_check")
            alerts = data.alerts()
            if not alerts.empty:
                st.dataframe(
                    alerts[["ALERT_ID", "ALERT_TYPE", "ALERT_STATUS", "ANALYST_ASSIGNED", "SAR_REFERENCE"]],
                    hide_index=True, width="stretch",
                )
        with st.container(border=True):
            ui.section("Export", "For examiners and internal audit", "download")
            st.download_button(
                "Download audit log (CSV)", log.to_csv(index=False).encode("utf-8"),
                file_name="sentinelreg_audit_log.csv", mime="text/csv", icon=":material/download:",
                width="stretch", disabled=log.empty,
            )
            st.caption("Verify independently: hash = SHA-256 of "
                       "`seq|event_id|timestamp|analyst|action|entity|detail|prev_hash`, starting from 64 zeros.")
