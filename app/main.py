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

# ── Custom CSS — elegant emerald-on-ivory enterprise theme ────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --sr-green-900: #0B2E22;
        --sr-green-700: #0B4F3A;
        --sr-green-600: #0E6B4E;
        --sr-green-500: #147C5B;
        --sr-gold: #C8A24A;
        --sr-ivory: #FBFAF6;
        --sr-cream: #F3F1E9;
        --sr-ink: #16241E;
        --sr-muted: #5B6B62;
        --sr-critical: #8C1C13;
        --sr-high: #B8791A;
        --sr-medium: #147C5B;
        --sr-low: #6B7280;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--sr-ivory);
        color: var(--sr-ink);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1, h2, h3, .sentinel-header h1 {
        font-family: 'Fraunces', Georgia, serif;
        font-weight: 600;
        color: var(--sr-green-900);
    }
    [data-testid="stHeader"] { background: transparent; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sr-green-900) 0%, var(--sr-green-700) 100%);
        border-right: 1px solid var(--sr-gold);
    }
    [data-testid="stSidebar"] * { color: #EFEAD9 !important; }
    [data-testid="stSidebar"] h2 {
        font-family: 'Fraunces', Georgia, serif;
        color: #FFFFFF !important;
        letter-spacing: 0.02em;
    }
    [data-testid="stSidebar"] hr { border-color: rgba(200,162,74,0.35) !important; }
    [data-testid="stSidebar"] code {
        background: rgba(255,255,255,0.08) !important;
        color: var(--sr-gold) !important;
        border: 1px solid rgba(200,162,74,0.3);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 6px;
        padding: 0.4rem 0.6rem;
        margin-bottom: 2px;
        transition: background 0.15s ease;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(200,162,74,0.12);
    }

    /* Main header banner */
    .sentinel-header {
        background: linear-gradient(90deg, var(--sr-green-900) 0%, var(--sr-green-600) 100%);
        padding: 1.6rem 2.2rem;
        border-radius: 10px;
        margin-bottom: 1.75rem;
        color: #FFFFFF;
        border-bottom: 3px solid var(--sr-gold);
        box-shadow: 0 4px 18px rgba(11,46,34,0.18);
    }
    .sentinel-header h1 { margin: 0; font-size: 1.9rem; color: #FFFFFF !important; }
    .sentinel-header p  { margin: 0.4rem 0 0 0; font-size: 0.98rem; opacity: 0.88; font-family: 'Inter', sans-serif; }

    /* Alert / severity badges */
    .badge-critical { background: var(--sr-critical); color:#FFF9F0; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }
    .badge-high     { background: var(--sr-high);     color:#FFF9F0; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }
    .badge-medium   { background: var(--sr-medium);   color:#FFF9F0; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }
    .badge-low      { background: var(--sr-low);      color:#FFF9F0; padding:3px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; letter-spacing:0.03em; }

    /* Metric / stat cards */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E7E2D3;
        border-left: 4px solid var(--sr-green-600);
        border-radius: 10px;
        padding: 1.1rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(11,46,34,0.05);
    }
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E7E2D3;
        border-left: 4px solid var(--sr-green-600);
        border-radius: 10px;
        padding: 0.9rem 1rem;
        box-shadow: 0 2px 10px rgba(11,46,34,0.05);
    }
    [data-testid="stMetricValue"] {
        color: var(--sr-green-900);
        font-family: 'Fraunces', Georgia, serif;
    }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
        background: var(--sr-green-700);
        color: #FFFFFF;
        border: 1px solid var(--sr-green-900);
        border-radius: 6px;
        font-weight: 500;
        transition: background 0.15s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: var(--sr-green-600);
        border-color: var(--sr-gold);
        color: #FFFFFF;
    }
    .stButton > button[kind="primary"] {
        background: var(--sr-green-600);
        border: 1px solid var(--sr-gold);
    }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: #FFFFFF;
        border: 1px solid #E7E2D3;
        border-radius: 10px;
        box-shadow: 0 1px 6px rgba(11,46,34,0.04);
    }

    /* Dataframes / tables */
    [data-testid="stDataFrame"] { border: 1px solid #E7E2D3; border-radius: 8px; }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] {
        border-radius: 6px !important;
        border-color: #D8D2BF !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--sr-green-600) !important;
        box-shadow: 0 0 0 1px var(--sr-green-600) !important;
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

    st.markdown("**Engine:**")
    st.code("Cortex Analyst · Text-to-SQL", language=None)

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
