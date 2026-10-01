"""
SAR Generator Page — SentinelReg
Builds audit-ready Suspicious Activity Reports (STR/SAR): evidence dossier,
Cortex-drafted narrative with enforced citations, PDF + evidence package,
and a write-back when the filing is confirmed.
"""

import hashlib
import io
import json
import zipfile
from datetime import datetime

import streamlit as st

from utils import data, nav, ui
from utils.narrative import draft_narrative, enforce_citations, model_name
from utils.sar_builder import build_sar_markdown, build_sar_text
from utils.sar_pdf import build_sar_pdf

REGULATORS = list(data.FILING_RULES)


def _steps(active: int):
    labels = [("Select alert", "Pick the case"), ("Evidence", "Dossier & citations"),
              ("Narrative", "Draft with Cortex AI"), ("Export & file", "PDF, package, confirm")]
    html = "".join(
        f'<div class="sr-step {"done" if i < active else "active" if i == active else ""}">'
        f'<span class="sr-step-num">{i + 1}</span><div><div class="sr-step-label">{ui.esc(a)}</div>'
        f'<div class="sr-step-sub">{ui.esc(b)}</div></div></div>'
        for i, (a, b) in enumerate(labels)
    )
    ui.render(f'<div class="sr-steps">{html}</div>')


def _evidence_package(sar_data: dict, md: str, txt: str, pdf: bytes, doc_hash: str) -> bytes:
    evidence = {
        "sar_reference": sar_data["sar_ref"],
        "generated_at": sar_data["generated_at"],
        "generated_by": sar_data["reporting_officer"],
        "regulator": sar_data["regulator"],
        "filing_clock": sar_data["filing_clock"],
        "narrative_source": sar_data["narrative_source"],
        "alert": sar_data["alert"],
        "customer": sar_data["customer"],
        "accounts": sar_data["accounts"],
        "transactions": sar_data["transactions"],
        "citations": sar_data["citations"],
        "text_sha256": doc_hash,
    }
    files = {
        f"{sar_data['sar_ref']}.pdf": pdf,
        f"{sar_data['sar_ref']}.md": md.encode("utf-8"),
        f"{sar_data['sar_ref']}.txt": txt.encode("utf-8"),
        "evidence.json": json.dumps(evidence, indent=2, default=str).encode("utf-8"),
    }
    manifest = {name: hashlib.sha256(blob).hexdigest() for name, blob in files.items()}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in files.items():
            zf.writestr(name, blob)
        zf.writestr("MANIFEST.sha256.json", json.dumps(manifest, indent=2))
    return buf.getvalue()


def render_sar_generator():
    mode = data.mode()
    as_of = data.as_of()
    ui.page_header(
        title="SAR Generator",
        subtitle="Evidence, narrative and regulatory basis assembled into an audit-ready STR/SAR — every citation "
                 "traced to a clause in the corpus.",
        eyebrow="Audit-ready reports", eyebrow_icon="description", mode=mode,
    )
    _filed_banner()

    alerts = data.alerts()
    eligible = alerts[alerts["ALERT_STATUS"].isin(data.ACTIVE_STATUSES) & ~alerts["SAR_FILED"]] if not alerts.empty else alerts
    if eligible.empty:
        ui.callout("No alerts awaiting a SAR", "Every active alert has been filed or closed.", tone="green",
                   callout_icon="task_alt")
        nav.link("audit", "View audit trail", icon=":material/history:")
        return

    ids = list(eligible["ALERT_ID"])
    preset = st.session_state.pop("sar_alert_id", None)
    if preset in ids:
        st.session_state["sar_alert_select"] = preset
    if st.session_state.get("sar_alert_select") not in ids:
        st.session_state["sar_alert_select"] = ids[0]
    labels = {r["ALERT_ID"]: f"{r['ALERT_ID']} — {r['ALERT_TYPE']} ({r['ALERT_SEVERITY']}) · {r['CUSTOMER']}"
              for r in eligible.to_dict("records")}
    doc = st.session_state.get("sar_doc")
    current = st.session_state["sar_alert_select"]
    _steps(3 if doc and doc["alert_id"] == current else 2)

    # ── 1. Select ─────────────────────────────────────────────
    ui.section("1 · Select alert", "Open, under-review or escalated alerts without a SAR", "checklist")
    aid = st.selectbox("Alert", ids, format_func=lambda x: labels[x], key="sar_alert_select", label_visibility="collapsed")
    alert = data.alert(aid)
    customer = data.customer(alert["CUSTOMER_ID"]) or {}
    accounts = data.accounts()
    accounts = accounts[accounts["CUSTOMER_ID"] == alert["CUSTOMER_ID"]]
    txns = data.transactions()
    evidence = txns[txns["TRANSACTION_ID"].isin(alert["TRANSACTION_IDS"])] if not txns.empty else txns
    if evidence.empty and not txns.empty:
        evidence = txns[txns["ACCOUNT_ID"].isin(accounts["ACCOUNT_ID"])].head(20)

    # ── 2. Evidence ───────────────────────────────────────────
    ui.section("2 · Evidence dossier", "Pulled live from AML_ALERTS, CUSTOMERS, ACCOUNTS and TRANSACTIONS", "folder_open")
    reg_col, _ = st.columns([1, 2])
    regulator = reg_col.selectbox("Regulator / recipient", REGULATORS, key="sar_regulator")
    clock = data.filing_clock(alert, regulator, reference=as_of)
    citations = data.citations_for_alert(alert, regulator, pep=bool(customer.get("PEP_FLAG")))

    with st.container(border=True):
        a_col, c_col, k_col = st.columns(3, gap="medium")
        with a_col:
            ui.render(
                f'<div class="sr-kpi-label">Alert</div><div class="sr-card-title">{ui.esc(alert["ALERT_ID"])}</div>'
                f'<div style="margin:.35rem 0">{ui.severity_badge(alert["ALERT_SEVERITY"])} {ui.status_badge(alert["ALERT_STATUS"])}</div>'
                f'<div class="sr-card-meta">{ui.esc(alert["ALERT_TYPE"])} · {ui.esc(data.format_inr(alert["TOTAL_AMOUNT_INR"]))}<br>'
                f'{ui.esc(alert.get("TRIGGER_RULE"))}</div>'
            )
        with c_col:
            flags = (ui.badge("PEP", "gold") if customer.get("PEP_FLAG") else "") + \
                    (ui.badge("Sanctions", "critical") if customer.get("SANCTIONS_FLAG") else "")
            ui.render(
                f'<div class="sr-kpi-label">Subject</div><div class="sr-card-title">{ui.esc(customer.get("FULL_NAME"))}</div>'
                f'<div style="margin:.35rem 0">{ui.badge("KYC " + str(customer.get("KYC_TIER", "—")), "neutral", dot=False)} {flags}</div>'
                f'<div class="sr-card-meta">{ui.esc(customer.get("ENTITY_TYPE"))} · {ui.esc(customer.get("COUNTRY_OF_ORIGIN"))} · '
                f'{ui.esc(customer.get("OCCUPATION"))}<br>Accounts: {ui.esc(", ".join(accounts["ACCOUNT_ID"]))}</div>'
            )
        with k_col:
            due = clock.get("due")
            ui.render(
                f'<div class="sr-kpi-label">Filing clock</div>'
                f'<div class="sr-card-title">{ui.esc(clock["report"])} due {due:%d %b %Y}</div>'
                f'<div style="margin:.35rem 0">{ui.clock_badge(clock)}</div>'
                f'<div class="sr-card-meta">{clock["days"]}-day window counted from the alert date '
                f'({ui.esc(clock["chunk_id"])}); measured against data as of {as_of:%d %b %Y}.</div>'
                if due is not None else '<div class="sr-kpi-label">Filing clock</div><div class="sr-card-meta">No alert date.</div>'
            )
        st.dataframe(
            evidence[["TRANSACTION_ID", "TRANSACTION_DATE", "ACCOUNT_ID", "COUNTERPARTY_ACCOUNT", "AMOUNT_INR",
                      "TRANSACTION_TYPE", "CHANNEL", "NARRATION"]],
            hide_index=True, width="stretch",
            column_config={"AMOUNT_INR": st.column_config.NumberColumn("Amount (₹)", format="%,.0f"),
                           "TRANSACTION_DATE": st.column_config.DatetimeColumn("When", format="DD MMM YYYY, HH:mm")},
        )
        with st.expander(f"Regulatory basis — {len(citations)} clause(s) from REGULATORY_DOCS_CHUNKS",
                         icon=":material/menu_book:"):
            for r in citations.to_dict("records"):
                st.markdown(f"**[{r['CHUNK_ID']}] {r['DOC_TYPE']} {r['SECTION_NUMBER']} — {r['SECTION_TITLE']}**  \n"
                            f"> {r['CHUNK_TEXT']}")

    # ── 3. Narrative ──────────────────────────────────────────
    ui.section("3 · Narrative", "Draft with Snowflake Cortex AI, then edit. Citations not in the corpus are stripped "
                                "automatically.", "edit_note")
    notes_key = f"sar_notes_{aid}"
    prefill = st.session_state.pop("sar_prefill", None)
    if prefill:
        base = alert.get("INVESTIGATION_NOTES") or ""
        st.session_state[notes_key] = (base + "\n\n" if base else "") + "Copilot findings:\n" + prefill
    st.session_state.setdefault(notes_key, alert.get("INVESTIGATION_NOTES") or "")

    def _draft():
        res = draft_narrative(alert, customer, evidence, citations, regulator, clock["report"], use_llm=data.is_live())
        st.session_state[notes_key] = res["text"]
        st.session_state[f"sar_source_{aid}"] = res["source"]
        st.session_state["sar_draft_info"] = res

    d1, d2 = st.columns([1.3, 3], vertical_alignment="center")
    d1.button("Draft with Cortex AI" if data.is_live() else "Draft narrative", icon=":material/auto_awesome:",
              on_click=_draft, width="stretch", type="primary")
    d2.caption(f"Engine: Snowflake Cortex COMPLETE · {model_name()} (falls back to a deterministic template)"
               if data.is_live() else "Engine: deterministic template from database fields (Cortex COMPLETE runs in live mode)")
    info = st.session_state.pop("sar_draft_info", None)
    if info:
        if info.get("llm_error"):
            st.warning(f"Cortex COMPLETE unavailable — used the template instead. {info['llm_error']}")
        if info.get("removed_citations"):
            st.warning(f"Removed unsupported citation(s): {', '.join(info['removed_citations'])}")
        else:
            st.success(f"Drafted by {info['source']} · all citations verified against REGULATORY_DOCS_CHUNKS.")
    narrative = st.text_area("Narrative", key=notes_key, height=220, label_visibility="collapsed",
                             placeholder="Describe who, what, when, how much and why it is suspicious…")

    # ── 4. Export ─────────────────────────────────────────────
    ui.section("4 · Export & file", "Generate the report, download the evidence package, then confirm the filing",
               "ios_share")
    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        reporting_officer = f1.text_input("Reporting officer", value=data.current_analyst(), key="sar_officer")
        institution = f2.text_input("Reporting institution", value="SentinelReg Bank Ltd", key="sar_institution")
        branch = f3.text_input("Branch / unit", value="Central Compliance Unit", key="sar_branch")
        g1, g2 = st.columns(2)
        filing_date = g1.date_input("Filing date", value=datetime.today(), key="sar_filing_date")
        sar_ref = g2.text_input("SAR reference no.", value=f"SAR-{datetime.now():%Y%m%d}-{aid.split('-')[-1]}",
                                key=f"sar_ref_{aid}")

        if st.button("Generate audit-ready SAR", icon=":material/verified:", type="primary", width="stretch"):
            with st.spinner("Assembling report and evidence package…"):
                generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cites = citations.to_dict("records")
                clean_narrative, removed = enforce_citations(narrative, set(citations["CHUNK_ID"]))
                sar_data = {
                    "sar_ref": sar_ref.strip() or f"SAR-{datetime.now():%Y%m%d}",
                    "filing_date": str(filing_date),
                    "reporting_officer": reporting_officer,
                    "institution": institution,
                    "branch": branch,
                    "regulator": regulator,
                    "alert": alert,
                    "customer": customer,
                    "accounts": accounts.to_dict("records"),
                    "transactions": evidence.to_dict("records"),
                    "investigation_notes": clean_narrative,
                    "citations": cites,
                    "filing_clock": clock,
                    "narrative_source": st.session_state.get(f"sar_source_{aid}", "Analyst (manual)"),
                    "generated_at": generated_at,
                }
                md = build_sar_markdown(sar_data)
                txt = build_sar_text(sar_data)
                doc_hash = hashlib.sha256(txt.encode("utf-8")).hexdigest()
                pdf = build_sar_pdf(sar_data, doc_hash)
                package = _evidence_package(sar_data, md, txt, pdf, doc_hash)
            st.session_state["sar_doc"] = {"alert_id": aid, "ref": sar_data["sar_ref"], "md": md, "txt": txt,
                                           "pdf": pdf, "zip": package, "hash": doc_hash, "removed": removed}
            data.log_event("SAR_GENERATED", aid, f"{sar_data['sar_ref']} for {regulator}; sha256 {doc_hash}")
            st.rerun()

    doc = st.session_state.get("sar_doc")
    if not doc or doc["alert_id"] != aid:
        return

    if doc.get("removed"):
        st.warning(f"Removed unsupported citation(s) from the narrative: {', '.join(doc['removed'])}")
    ui.callout("SAR generated", f"{doc['ref']} is ready. Review the preview, download the package, then confirm filing.",
               tone="green", callout_icon="verified")
    ui.render(f'<div class="sr-hash"><b>SHA-256</b> (text version) · {ui.esc(doc["hash"])}</div>')
    st.write("")
    e1, e2, e3, e4 = st.columns(4)
    e1.download_button("PDF report", doc["pdf"], file_name=f"{doc['ref']}.pdf", mime="application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch", type="primary")
    e2.download_button("Evidence package (.zip)", doc["zip"], file_name=f"{doc['ref']}_evidence.zip",
                       mime="application/zip", icon=":material/folder_zip:", width="stretch")
    e3.download_button("Markdown", doc["md"], file_name=f"{doc['ref']}.md", mime="text/markdown",
                       icon=":material/article:", width="stretch")
    e4.download_button("Plain text", doc["txt"], file_name=f"{doc['ref']}.txt", mime="text/plain",
                       icon=":material/description:", width="stretch")

    with st.expander("Report preview", expanded=True, icon=":material/visibility:"):
        st.markdown(doc["md"])

    with st.container(border=True):
        ui.section("Confirm filing", "Marks the alert CLOSED_SAR_FILED with this reference and writes the audit log",
                   "gavel")
        ack = st.checkbox("I have reviewed this report and submitted it to the regulator.", key=f"sar_ack_{aid}")
        if st.button("Confirm SAR filed", icon=":material/task_alt:", disabled=not ack, width="stretch", type="primary"):
            ok, err = data.mark_sar_filed(aid, doc["ref"])
            if ok:
                data.log_event("SAR_FILED", aid, f"{doc['ref']} filed; sha256 {doc['hash']}")
                st.session_state.pop("sar_doc", None)
                st.session_state["sar_filed_msg"] = f"Alert {aid} marked as SAR filed with reference {doc['ref']}."
                st.rerun()
            else:
                st.error(f"Failed to update alert: {err}")


def _filed_banner():
    msg = st.session_state.pop("sar_filed_msg", None)
    if msg:
        st.toast(msg, icon=":material/task_alt:")
        st.success(msg)

