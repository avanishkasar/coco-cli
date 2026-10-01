"""
SentinelReg — AML Risk & Regulatory Intelligence Copilot
Main Streamlit application entry point
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="SentinelReg | AML Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils import data, nav, ui  # noqa: E402  (after set_page_config)
from utils.db import demo_forced, reset_connection  # noqa: E402
from views.audit_trail import render_audit_trail  # noqa: E402
from views.entity_360 import render_entity_360  # noqa: E402
from views.investigation import render_investigation  # noqa: E402
from views.network import render_network  # noqa: E402
from views.overview import render_overview  # noqa: E402
from views.regulatory_library import render_regulatory_library  # noqa: E402
from views.risk_dashboard import render_dashboard  # noqa: E402
from views.sar_generator import render_sar_generator  # noqa: E402

ui.inject_theme()
st.logo(str(ui.ASSETS / "wordmark.svg"), icon_image=str(ui.ASSETS / "logo.svg"), size="large")

PAGES = {
    "overview": st.Page(render_overview, title="Overview", icon=":material/space_dashboard:",
                        url_path="overview", default=True),
    "triage": st.Page(render_dashboard, title="Alert Triage", icon=":material/notifications_active:",
                      url_path="triage"),
    "copilot": st.Page(render_investigation, title="Investigation Copilot", icon=":material/forum:",
                       url_path="copilot"),
    "entity": st.Page(render_entity_360, title="Entity 360", icon=":material/person_search:", url_path="entity-360"),
    "network": st.Page(render_network, title="Network Intelligence", icon=":material/hub:", url_path="network"),
    "regulatory": st.Page(render_regulatory_library, title="Regulatory Library", icon=":material/menu_book:",
                          url_path="regulations"),
    "sar": st.Page(render_sar_generator, title="SAR Generator", icon=":material/description:", url_path="sar"),
    "audit": st.Page(render_audit_trail, title="Audit Trail", icon=":material/verified_user:", url_path="audit"),
}
for key, page in PAGES.items():
    nav.register(key, page)

pg = st.navigation(
    {
        "Command": [PAGES["overview"], PAGES["triage"]],
        "Investigate": [PAGES["copilot"], PAGES["entity"], PAGES["network"]],
        "Comply": [PAGES["regulatory"], PAGES["sar"], PAGES["audit"]],
    },
    position="sidebar",
)

with st.sidebar:
    st.divider()
    st.text_input("Signed in as", key="analyst_name", placeholder="Compliance Analyst",
                  help="Recorded on every triage decision, SAR and audit-log entry.")
    status = data.connection_status()
    live = status["live"]
    ui.render(
        f'<div class="sr-side-label">Data source</div>'
        f'<div class="sr-conn {"live" if live else "demo"}"><div class="sr-conn-row"><span class="sr-conn-dot"></span>'
        f'{"Snowflake · live" if live else "Demo snapshot"}</div>'
        f'<div class="sr-conn-sub">{"SENTINEL_REG.DATA via Snowpark" if live else ui.esc(status["reason"] or "")}</div></div>'
    )
    if not live and not demo_forced():
        if st.button("Retry connection", icon=":material/refresh:", width="stretch"):
            reset_connection()
            st.rerun()
    ui.render(
        '<div class="sr-side-label" style="margin-top:.8rem">Engines</div><div class="sr-engine">'
        '<span>Cortex Analyst</span><span>Cortex COMPLETE</span><span>Snowpark ML</span>'
        '<span>Rule engine · 5 typologies</span><span>SHA-256 audit chain</span></div>'
        '<div class="sr-side-foot">Snowflake CoCo CLI Hackathon 2026 · GCC Edition<br>'
        'Risk, Fraud &amp; Regulatory Intelligence Copilot</div>'
    )

pg.run()
