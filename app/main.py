"""
SentinelReg — AML Risk & Regulatory Intelligence Copilot
Main Streamlit application entry point
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="SentinelReg | AML Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }
    [data-testid="stSidebar"] * {
        color: #c9d1d9 !important;
    }
    /* Main header */
    .sentinel-header {
        background: linear-gradient(90deg, #0d419d 0%, #1f6feb 100%);
        padding: 1.2rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .sentinel-header h1 { margin: 0; font-size: 1.8rem; }
    .sentinel-header p  { margin: 0.3rem 0 0 0; font-size: 0.95rem; opacity: 0.85; }
    /* Alert badges */
    .badge-critical { background:#da3633; color:white; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
    .badge-high     { background:#d29922; color:white; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
    .badge-medium   { background:#3fb950; color:white; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; }
    /* Card style */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Connection validation ────────────────────────────────────
required_vars = ["SENTINEL_REG_PAT", "SENTINEL_REG_HOST"]
missing = [v for v in required_vars if not os.getenv(v)]

if missing:
    st.error(
        f"⚠️ Missing environment variables: `{', '.join(missing)}`  \n"
        "Copy `.env.example` to `.env` and fill in your Snowflake credentials."
    )
    st.stop()

# ── Sidebar navigation ───────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ SentinelReg")
    st.markdown("*AML & Regulatory Intelligence*")
    st.divider()

    page = st.radio(
        "Navigate",
        options=[
            "🔍 Investigation Chat",
            "📊 Risk Dashboard",
            "📋 SAR Generator",
        ],
        label_visibility="collapsed",
    )
    st.divider()

    st.markdown("**Connected to:**")
    host = os.getenv("SENTINEL_REG_HOST", "—")
    st.code(host, language=None)

    st.markdown("**Agent:**")
    st.code(os.getenv("SENTINEL_REG_AGENT_NAME", "AML_RISK_AGENT"), language=None)

    st.divider()
    st.caption("Snowflake CoCo CLI Hackathon 2026")

# ── Route to pages ───────────────────────────────────────────
if page == "🔍 Investigation Chat":
    from pages.investigation import render_investigation
    render_investigation()

elif page == "📊 Risk Dashboard":
    from pages.risk_dashboard import render_dashboard
    render_dashboard()

elif page == "📋 SAR Generator":
    from pages.sar_generator import render_sar_generator
    render_sar_generator()
