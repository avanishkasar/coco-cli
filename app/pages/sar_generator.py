"""
SAR Generator Page — SentinelReg
Generates audit-ready Suspicious Activity Reports from AML alerts.
"""

import hashlib
from datetime import datetime
import streamlit as st
from utils.db import get_snowflake_session, run_query as query
from utils.sar_builder import build_sar_markdown, build_sar_text


def render_sar_generator():
    st.markdown("""
    <div class="sentinel-header">
        <h1>📋 SAR Generator</h1>
        <p>Generate audit-ready Suspicious Activity Reports (STR/SAR) from confirmed AML alerts.</p>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "Select an alert to pre-populate the SAR, or paste investigation findings from the "
        "**Investigation Chat** page. The generated SAR follows the FIU-IND / FinCEN format."
    )

    st.markdown("""
    <div class="sr-step-ribbon">
        <div class="sr-step-chip"><span class="sr-step-num">1</span><span class="sr-step-label">Select Alert</span></div>
        <div class="sr-step-chip"><span class="sr-step-num">2</span><span class="sr-step-label">Case Details</span></div>
        <div class="sr-step-chip"><span class="sr-step-num">3</span><span class="sr-step-label">Generate &amp; Export</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Alert selector ────────────────────────────────────────
    st.subheader("1️⃣ Select Alert")
    alerts_df = query("""
        SELECT ALERT_ID, CUSTOMER_ID, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS,
               TOTAL_AMOUNT_INR, TRIGGER_RULE, INVESTIGATION_NOTES,
               TO_CHAR(ALERT_DATE, 'YYYY-MM-DD') AS ALERT_DATE
        FROM AML_ALERTS
        WHERE ALERT_STATUS IN ('OPEN', 'UNDER_REVIEW', 'ESCALATED')
          AND SAR_FILED = FALSE
        ORDER BY CASE ALERT_SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 ELSE 3 END
    """)

    if alerts_df is None or alerts_df.empty:
        st.success("✅ No open alerts eligible for SAR filing.")
        return

    alert_options = {
        f"{row['ALERT_ID']} — {row['ALERT_TYPE']} ({row['ALERT_SEVERITY']})": row
        for _, row in alerts_df.iterrows()
    }
    selected_label = st.selectbox("Choose alert:", list(alert_options.keys()))
    alert = alert_options[selected_label]

    # ── Fetch supporting data ─────────────────────────────────
    customer_df = query(f"""
        SELECT * FROM CUSTOMERS WHERE CUSTOMER_ID = '{alert['CUSTOMER_ID']}'
    """)
    account_df = query(f"""
        SELECT * FROM ACCOUNTS WHERE CUSTOMER_ID = '{alert['CUSTOMER_ID']}'
    """)
    txn_df = query(f"""
        SELECT TRANSACTION_ID, TRANSACTION_DATE, AMOUNT_INR, TRANSACTION_TYPE, CHANNEL, NARRATION
        FROM TRANSACTIONS
        WHERE ACCOUNT_ID IN (
            SELECT ACCOUNT_ID FROM ACCOUNTS WHERE CUSTOMER_ID = '{alert['CUSTOMER_ID']}'
        )
        ORDER BY TRANSACTION_DATE DESC LIMIT 20
    """)

    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Alert Summary**")
            st.table({
                "Alert ID":   [alert["ALERT_ID"]],
                "Type":       [alert["ALERT_TYPE"]],
                "Severity":   [alert["ALERT_SEVERITY"]],
                "Date":       [alert["ALERT_DATE"]],
                "Amount INR": [f"₹{alert['TOTAL_AMOUNT_INR']:,}"],
            })
        with col_b:
            if customer_df is not None and not customer_df.empty:
                c = customer_df.iloc[0]
                st.markdown("**Subject Customer**")
                st.table({
                    "Name":      [c["FULL_NAME"]],
                    "Entity":    [c["ENTITY_TYPE"]],
                    "KYC Tier":  [c["KYC_TIER"]],
                    "PEP":       ["Yes" if c["PEP_FLAG"] else "No"],
                    "Sanctions": ["Yes" if c["SANCTIONS_FLAG"] else "No"],
                })

        txn_count = len(txn_df) if txn_df is not None else 0
        st.caption(f"📎 {txn_count} supporting transaction(s) retrieved for this dossier.")

    # ── SAR metadata form ─────────────────────────────────────
    st.subheader("2️⃣ SAR Details")
    sar_col1, sar_col2 = st.columns(2)
    with sar_col1:
        reporting_officer = st.text_input("Reporting Officer", value="Compliance Officer")
        filing_date       = st.date_input("Filing Date", value=datetime.today())
        sar_ref           = st.text_input("SAR Reference No.", value=f"SAR-{datetime.now().strftime('%Y%m%d')}-001")
    with sar_col2:
        institution       = st.text_input("Reporting Institution", value="SentinelReg Bank Ltd")
        branch            = st.text_input("Branch / Unit", value="Central Compliance Unit")
        regulator         = st.selectbox("Regulator / Recipient", ["FIU-IND (RBI)", "FinCEN (US)", "MLRO (UK)"])

    # Prefill investigation notes from chat page if available
    prefill = st.session_state.pop("sar_prefill", "")
    investigation_notes = st.text_area(
        "Investigation Findings",
        value=prefill or alert.get("INVESTIGATION_NOTES", ""),
        height=150,
        help="Paste findings from the Investigation Chat or write your own summary.",
    )

    # ── Generate ──────────────────────────────────────────────
    st.subheader("3️⃣ Generate SAR")
    if st.button("🖨️ Generate Audit-Ready SAR", type="primary", use_container_width=True):
        with st.spinner("Generating SAR document..."):
            customer = customer_df.iloc[0].to_dict() if customer_df is not None and not customer_df.empty else {}

            sar_data = {
                "sar_ref":            sar_ref,
                "filing_date":        str(filing_date),
                "reporting_officer":  reporting_officer,
                "institution":        institution,
                "branch":             branch,
                "regulator":          regulator,
                "alert":              alert.to_dict(),
                "customer":           customer,
                "transactions":       txn_df.to_dict(orient="records") if txn_df is not None else [],
                "investigation_notes": investigation_notes,
            }

            sar_markdown = build_sar_markdown(sar_data)
            sar_text     = build_sar_text(sar_data)
            doc_hash     = hashlib.sha256(sar_text.encode("utf-8")).hexdigest()

        st.success("✅ SAR generated successfully.")
        st.divider()
        st.markdown("### 📄 SAR Preview")
        with st.container(border=True):
            st.markdown(sar_markdown, unsafe_allow_html=False)
        st.markdown(
            f'<div class="sr-doc-hash">🔐 Document Integrity Hash (SHA-256): {doc_hash}</div>',
            unsafe_allow_html=True,
        )

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="⬇️ Download SAR (.txt)",
                data=sar_text,
                file_name=f"{sar_ref}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                label="⬇️ Download SAR (.md)",
                data=sar_markdown,
                file_name=f"{sar_ref}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # Mark alert as SAR filed (update via Snowflake)
        if st.button("✅ Confirm SAR Filed — Update Alert Status", use_container_width=True):
            try:
                get_snowflake_session().sql(f"""
                    UPDATE AML_ALERTS
                    SET SAR_FILED = TRUE,
                        SAR_REFERENCE = '{sar_ref}',
                        ALERT_STATUS = 'CLOSED_SAR_FILED',
                        UPDATED_AT = CURRENT_TIMESTAMP()
                    WHERE ALERT_ID = '{alert['ALERT_ID']}'
                """).collect()
                st.success(f"Alert `{alert['ALERT_ID']}` marked as SAR filed with reference `{sar_ref}`.")
            except Exception as exc:
                st.error(f"Failed to update alert: {exc}")
