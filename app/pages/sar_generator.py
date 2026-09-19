"""
SAR Generator Page — SentinelReg
Generates audit-ready Suspicious Activity Reports from AML alerts.
"""

import os
from datetime import datetime
import streamlit as st
from snowflake.snowpark import Session
from utils.sar_builder import build_sar_markdown, build_sar_text


@st.cache_resource
def get_snowflake_session() -> Session:
    return Session.builder.configs({
        "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
        "user":      os.getenv("SNOWFLAKE_USER"),
        "password":  os.getenv("SNOWFLAKE_PASSWORD"),
        "role":      os.getenv("SNOWFLAKE_ROLE",      "SENTINEL_REG_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE",  "SENTINEL_REG_WH"),
        "database":  os.getenv("SNOWFLAKE_DATABASE",   "SENTINEL_REG"),
        "schema":    os.getenv("SNOWFLAKE_SCHEMA",     "DATA"),
    }).create()


def query(sql: str):
    try:
        return get_snowflake_session().sql(sql).to_pandas()
    except Exception as exc:
        st.error(f"Query error: {exc}")
        return None


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

        st.success("✅ SAR generated successfully.")
        st.divider()
        st.markdown("### 📄 SAR Preview")
        st.markdown(sar_markdown, unsafe_allow_html=False)

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
