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

# ── Custom CSS — refined emerald & gold enterprise theme ──────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');

    :root {
        --sr-green-900: #0B2E22;
        --sr-green-700: #0B4F3A;
        --sr-green-600: #0E6B4E;
        --sr-green-500: #147C5B;
        --sr-slate: #23322B;
        --sr-gold: #A9790A;
        --sr-gold-light: #EAC166;
        --sr-ivory: #FAF9F5;
        --sr-cream: #F3F1E9;
        --sr-ink: #1B1C1A;
        --sr-muted: #5B6B62;
        --sr-border: #E3E2DF;
        --sr-critical: #BA1A1A;
        --sr-high: #A9790A;
        --sr-medium: #147C5B;
        --sr-low: #6B7280;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--sr-ivory);
        color: var(--sr-ink);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1, h2, h3, .sentinel-header h1 {
        font-family: 'Playfair Display', Georgia, serif;
        font-weight: 600;
        color: var(--sr-green-900);
    }
    code, pre, .stCodeBlock, [data-testid="stCodeBlock"] {
        font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace !important;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { visibility: visible; }
    .block-container { padding-top: 2rem; max-width: 1200px; }

    /* ── Sidebar ─────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sr-green-900) 0%, var(--sr-green-700) 100%);
        border-right: 1px solid var(--sr-gold);
    }
    [data-testid="stSidebar"] * { color: #EFEAD9 !important; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-family: 'Playfair Display', Georgia, serif;
        color: #FFFFFF !important;
        letter-spacing: 0.01em;
    }
    [data-testid="stSidebar"] hr { border-color: rgba(200,162,74,0.3) !important; margin: 1.1rem 0; }

    /* Native st.navigation widget */
    [data-testid="stSidebarNav"] {
        padding-top: 0.25rem;
    }
    [data-testid="stSidebarNav"] a {
        border-radius: 8px;
        margin: 2px 0.5rem;
        padding: 0.5rem 0.75rem !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(200,162,74,0.14) !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: rgba(200,162,74,0.22) !important;
        border-left: 3px solid var(--sr-gold);
    }
    [data-testid="stSidebarNav"] span { font-weight: 500; }

    /* Sidebar info "chips" (replaces unreadable st.code boxes) */
    .sr-chip-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--sr-gold) !important;
        margin: 0.9rem 0.1rem 0.25rem 0.1rem;
    }
    .sr-chip {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(200,162,74,0.35);
        border-radius: 6px;
        padding: 0.45rem 0.7rem;
        font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: 0.82rem;
        color: #F3F1E9 !important;
        word-break: break-all;
    }
    .sr-brand {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.15rem;
    }
    .sr-brand-icon { font-size: 1.6rem; }
    .sr-brand-name {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.35rem;
        font-weight: 600;
        color: #FFFFFF !important;
    }
    .sr-brand-tag {
        font-size: 0.82rem;
        font-style: italic;
        color: #C9D6CC !important;
        margin-bottom: 0.5rem;
    }
    .sr-footer {
        font-size: 0.72rem;
        color: #9AA89E !important;
        letter-spacing: 0.02em;
    }

    /* ── Main header banner ──────────────────────────────── */
    .sentinel-header {
        position: relative;
        overflow: hidden;
        background: linear-gradient(90deg, var(--sr-green-900) 0%, var(--sr-green-600) 100%);
        padding: 1.6rem 2.2rem;
        border-radius: 12px;
        margin-bottom: 1.75rem;
        color: #FFFFFF;
        border-bottom: 3px solid var(--sr-gold);
        box-shadow: 0 6px 20px rgba(11,46,34,0.18);
    }
    .sentinel-header::before {
        content: "";
        position: absolute;
        top: -60px;
        right: -60px;
        width: 220px;
        height: 220px;
        border-radius: 50%;
        background: rgba(234,193,102,0.12);
        filter: blur(20px);
        pointer-events: none;
    }
    .sentinel-header h1, .sentinel-header p { position: relative; z-index: 1; }
    .sentinel-header h1 { margin: 0; font-size: 1.85rem; color: #FFFFFF !important; }
    .sentinel-header p  { margin: 0.4rem 0 0 0; font-size: 0.98rem; opacity: 0.88; font-family: 'Inter', sans-serif; }

    /* ── Severity badges (dot + pill, matching row-accent style) ── */
    .badge-critical, .badge-high, .badge-medium, .badge-low {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #FFFFFF;
        padding: 3px 12px 3px 9px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-critical, .badge-high, .badge-medium, .badge-low {
        position: relative;
    }
    .badge-critical::before, .badge-high::before, .badge-medium::before, .badge-low::before {
        content: "";
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: rgba(255,255,255,0.85);
        flex-shrink: 0;
    }
    .badge-critical { background: var(--sr-critical); }
    .badge-high     { background: var(--sr-high); }
    .badge-medium   { background: var(--sr-medium); }
    .badge-low      { background: var(--sr-low); }

    /* ── Cards / metrics ─────────────────────────────────── */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid var(--sr-border);
        border-left: 4px solid var(--sr-green-600);
        border-radius: 10px;
        padding: 1.1rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(11,46,34,0.05);
    }
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--sr-border);
        border-left: 4px solid var(--sr-green-600);
        border-radius: 10px;
        padding: 0.95rem 1.1rem;
        box-shadow: 0 2px 10px rgba(11,46,34,0.05);
    }
    [data-testid="stMetricValue"] {
        color: var(--sr-green-900);
        font-family: 'Playfair Display', Georgia, serif;
    }
    [data-testid="stMetricLabel"] { color: var(--sr-muted); }

    /* ── Buttons ──────────────────────────────────────────
       Default (secondary) buttons = outlined pill chips,
       used for suggested questions & utility actions.
       Primary buttons = solid emerald fill, used for the
       one main call-to-action per page. */
    .stButton > button, .stDownloadButton > button {
        background: #FFFFFF;
        color: var(--sr-green-700);
        border: 1.5px solid var(--sr-green-600);
        border-radius: 999px;
        font-weight: 500;
        padding: 0.5rem 1.1rem;
        transition: all 0.15s ease;
        box-shadow: 0 1px 4px rgba(11,46,34,0.04);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: var(--sr-green-600);
        color: #FFFFFF;
        border-color: var(--sr-green-600);
    }
    .stButton > button[kind="primary"] {
        background: var(--sr-green-700);
        color: #FFFFFF;
        border: 1.5px solid var(--sr-gold);
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--sr-green-900);
        border-color: var(--sr-gold);
    }

    /* ── Chat ─────────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        background: #FFFFFF;
        border: 1px solid var(--sr-border);
        border-radius: 12px;
        box-shadow: 0 1px 8px rgba(11,46,34,0.05);
        padding: 0.25rem 0.5rem;
    }
    [data-testid="stChatInput"] textarea {
        border-radius: 10px !important;
    }

    /* ── Tables / dataframes ──────────────────────────────── */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--sr-border);
        border-radius: 10px;
        overflow: hidden;
    }

    /* ── Inputs ───────────────────────────────────────────── */
    .stTextInput input, .stTextArea textarea, .stDateInput input,
    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 8px !important;
        border-color: var(--sr-border) !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--sr-green-600) !important;
        box-shadow: 0 0 0 1px var(--sr-green-600) !important;
    }

    /* ── Expanders ────────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--sr-border);
        border-radius: 10px;
        background: #FFFFFF;
    }

    /* ── Alerts / callouts ────────────────────────────────── */
    [data-testid="stAlertContentInfo"] { color: var(--sr-green-900); }
    div[data-baseweb="notification"] { border-radius: 10px; }
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

# ── Sidebar branding + connection info ────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sr-brand">
        <span class="sr-brand-icon">🛡️</span>
        <span class="sr-brand-name">SentinelReg</span>
    </div>
    <div class="sr-brand-tag">AML &amp; Regulatory Intelligence</div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="sr-chip-label" style="margin-top:0;">Core Modules</div>', unsafe_allow_html=True)

# ── Page routing via native Streamlit navigation ──────────────
from pages.investigation import render_investigation
from pages.risk_dashboard import render_dashboard
from pages.sar_generator import render_sar_generator

pg = st.navigation(
    [
        st.Page(render_investigation, title="Investigation Chat", icon="🔍", default=True),
        st.Page(render_dashboard, title="Risk Dashboard", icon="📊"),
        st.Page(render_sar_generator, title="SAR Generator", icon="📋"),
    ],
    position="sidebar",
)

with st.sidebar:
    st.divider()
    st.markdown('<div class="sr-chip-label">Connected to</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sr-chip">{os.getenv("SENTINEL_REG_HOST", "—")}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sr-chip-label">Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sr-chip">Cortex Analyst · Text-to-SQL</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="sr-footer">Snowflake CoCo CLI Hackathon 2026</div>', unsafe_allow_html=True)

pg.run()
