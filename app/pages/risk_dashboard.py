"""
Risk Dashboard Page — SentinelReg
Live command center view of AML risk signals, alert queues, and account risk distribution.
"""

import os
import streamlit as st
import pandas as pd
from snowflake.snowpark import Session


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


def run_query(sql: str) -> pd.DataFrame:
    try:
        session = get_snowflake_session()
        return session.sql(sql).to_pandas()
    except Exception as exc:
        st.error(f"Query error: {exc}")
        return pd.DataFrame()


def render_dashboard():
    st.markdown("""
    <div class="sentinel-header">
        <h1>📊 Risk Command Center</h1>
        <p>Live overview of AML alerts, high-risk accounts, and transaction monitoring signals.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("*Auto-refreshes every 5 minutes. Data sourced from SENTINEL_REG.DATA.*")

    # ── Top KPI metrics ───────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)

    open_alerts_df = run_query("""
        SELECT COUNT(*) AS CNT FROM AML_ALERTS
        WHERE ALERT_STATUS IN ('OPEN', 'UNDER_REVIEW', 'ESCALATED')
    """)
    critical_df = run_query("""
        SELECT COUNT(*) AS CNT FROM AML_ALERTS
        WHERE ALERT_SEVERITY = 'CRITICAL' AND ALERT_STATUS != 'CLOSED_FALSE_POSITIVE'
    """)
    high_risk_df = run_query("""
        SELECT COUNT(*) AS CNT FROM ACCOUNTS WHERE RISK_SCORE > 0.7
    """)
    sar_pending_df = run_query("""
        SELECT COUNT(*) AS CNT FROM AML_ALERTS
        WHERE ALERT_STATUS = 'ESCALATED' AND SAR_FILED = FALSE
    """)

    def safe_count(df):
        return int(df.iloc[0, 0]) if not df.empty else "—"

    with m1:
        st.metric("🚨 Open Alerts", safe_count(open_alerts_df))
    with m2:
        st.metric("🔴 Critical", safe_count(critical_df))
    with m3:
        st.metric("⚠️ High-Risk Accounts", safe_count(high_risk_df))
    with m4:
        st.metric("📋 SAR Pending", safe_count(sar_pending_df))

    st.divider()

    # ── Two-column layout ─────────────────────────────────────
    left_col, right_col = st.columns([3, 2])

    # ── Alert queue ───────────────────────────────────────────
    with left_col:
        st.subheader("🚨 Active Alert Queue")

        alerts_df = run_query("""
            SELECT
                a.ALERT_ID,
                c.FULL_NAME         AS CUSTOMER,
                a.ALERT_TYPE,
                a.ALERT_SEVERITY,
                a.ALERT_STATUS,
                TO_CHAR(a.ALERT_DATE, 'YYYY-MM-DD HH24:MI') AS DETECTED_AT,
                TO_CHAR(a.TOTAL_AMOUNT_INR, '999,999,999,999') AS AMOUNT_INR,
                COALESCE(a.ANALYST_ASSIGNED, '⚠ Unassigned') AS ANALYST
            FROM AML_ALERTS a
            JOIN CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID
            WHERE a.ALERT_STATUS NOT IN ('CLOSED_FALSE_POSITIVE', 'CLOSED_SAR_FILED')
            ORDER BY
                CASE a.ALERT_SEVERITY
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM'   THEN 3 ELSE 4 END,
                a.ALERT_DATE DESC
        """)

        if alerts_df.empty:
            st.info("✅ No active alerts. All clear.")
        else:
            # Colour-code severity
            def severity_badge(val):
                colours = {
                    "CRITICAL": "background-color:#BA1A1A;color:#FFFFFF;font-weight:600",
                    "HIGH":     "background-color:#A9790A;color:#FFFFFF;font-weight:600",
                    "MEDIUM":   "background-color:#147C5B;color:#FFFFFF;font-weight:600",
                    "LOW":      "background-color:#6B7280;color:#FFFFFF;font-weight:600",
                }
                return colours.get(val, "")

            styled = alerts_df.style.applymap(severity_badge, subset=["ALERT_SEVERITY"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # Drill into a specific alert
            selected_alert = st.selectbox(
                "Drill into alert →",
                options=[""] + list(alerts_df["ALERT_ID"]),
                format_func=lambda x: "Select an alert to investigate..." if x == "" else x,
            )
            if selected_alert:
                detail_df = run_query(f"""
                    SELECT * FROM AML_ALERTS WHERE ALERT_ID = '{selected_alert}'
                """)
                if not detail_df.empty:
                    row = detail_df.iloc[0]
                    st.markdown(f"""
                    **Alert:** `{row['ALERT_ID']}` · **Type:** `{row['ALERT_TYPE']}` · **Severity:** `{row['ALERT_SEVERITY']}`

                    **Trigger Rule:** {row['TRIGGER_RULE']}

                    **Investigation Notes:** {row['INVESTIGATION_NOTES'] or '*None yet*'}
                    """)
                    if st.button("🔍 Investigate in Chat", key="investigate_btn"):
                        st.session_state["pending_prompt"] = (
                            f"Explain the AML alert {selected_alert} and provide a detailed investigation summary."
                        )
                        st.session_state["_page_override"] = "🔍 Investigation Chat"
                        st.info("Switch to **Investigation Chat** in the sidebar →")

    # ── High-risk accounts ────────────────────────────────────
    with right_col:
        st.subheader("⚠️ High-Risk Accounts")
        hr_df = run_query("""
            SELECT
                a.ACCOUNT_ID,
                c.FULL_NAME         AS CUSTOMER,
                c.KYC_TIER,
                c.PEP_FLAG,
                c.SANCTIONS_FLAG,
                ROUND(a.RISK_SCORE, 2) AS RISK_SCORE,
                a.STATUS
            FROM ACCOUNTS a
            JOIN CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID
            WHERE a.RISK_SCORE > 0.65
            ORDER BY a.RISK_SCORE DESC
            LIMIT 15
        """)
        if not hr_df.empty:
            st.dataframe(hr_df, use_container_width=True, hide_index=True)
        else:
            st.info("No high-risk accounts found.")

    st.divider()

    # ── Alert typology chart ──────────────────────────────────
    st.subheader("📈 Alert Distribution by Typology")
    typology_df = run_query("""
        SELECT ALERT_TYPE, ALERT_SEVERITY, COUNT(*) AS CNT
        FROM AML_ALERTS
        GROUP BY 1, 2
        ORDER BY CNT DESC
    """)
    if not typology_df.empty:
        st.bar_chart(typology_df.set_index("ALERT_TYPE")["CNT"])

    # ── Recent transactions heatmap ───────────────────────────
    st.subheader("🔥 Recent High-Value Cash Transactions")
    cash_df = run_query("""
        SELECT
            t.TRANSACTION_ID,
            t.ACCOUNT_ID,
            c.FULL_NAME AS CUSTOMER,
            TO_CHAR(t.TRANSACTION_DATE, 'YYYY-MM-DD') AS DATE,
            t.TRANSACTION_TYPE,
            t.AMOUNT_INR,
            t.IS_CASH
        FROM TRANSACTIONS t
        JOIN ACCOUNTS a ON t.ACCOUNT_ID = a.ACCOUNT_ID
        JOIN CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE t.IS_CASH = TRUE
          AND t.AMOUNT_INR >= 40000
        ORDER BY t.TRANSACTION_DATE DESC
        LIMIT 20
    """)
    if not cash_df.empty:
        st.dataframe(cash_df, use_container_width=True, hide_index=True)
    else:
        st.info("No high-value cash transactions found.")
