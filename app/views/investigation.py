"""
Investigation Copilot Page — SentinelReg
Natural-language AML investigation: Cortex Analyst (text-to-SQL) when
Snowflake is reachable, the deterministic offline router otherwise.
"""

import altair as alt
import pandas as pd
import streamlit as st

from utils import copilot_offline, data, nav, ui
from utils.agent_client import analyst_available, build_message, stream_agent_response

SUGGESTED_QUESTIONS = [
    "Why was account ACC-9823 flagged for AML?",
    "Show all structuring transactions in the last 30 days",
    "Which accounts have a risk score above 0.7?",
    "What does RBI say about suspicious transaction reporting timelines?",
    "List all open CRITICAL alerts with their total amounts",
    "Summarise the round-trip transfer pattern on account ACC-0009",
    "How many cash deposits were made just below ₹50,000 this month?",
    "What is the regulatory definition of structuring under RBI guidelines?",
]


def _auto_chart(df: pd.DataFrame):
    """Small bar chart when a result is one label column + one numeric column."""
    if df is None or df.empty or len(df) > 30 or len(df) < 2:
        return
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]
    cat = [c for c in df.columns if df[c].dtype == object or pd.api.types.is_string_dtype(df[c])]
    if len(num) != 1 or not cat:
        return
    chart = alt.Chart(df).mark_bar(cornerRadiusEnd=5, color="#0E6B4E").encode(
        x=alt.X(f"{num[0]}:Q"), y=alt.Y(f"{cat[0]}:N", sort="-x", title=None), tooltip=list(df.columns[:6]),
    )
    st.altair_chart(ui.style_chart(chart.properties(height=min(40 * len(df), 320))), width="stretch")


def _render_answer(msg: dict, idx: int):
    if msg.get("error"):
        st.error(msg["error"])
    if msg.get("text"):
        st.markdown(msg["text"])
    if msg.get("sql"):
        with st.expander("Generated SQL (Cortex Analyst)", icon=":material/code:"):
            st.code(msg["sql"], language="sql")
    df = msg.get("df")
    if isinstance(df, pd.DataFrame):
        if df.empty:
            st.info("Query returned no rows.")
        else:
            st.dataframe(df, hide_index=True, width="stretch",
                         column_config={"AMOUNT_INR": st.column_config.NumberColumn("AMOUNT_INR", format="%,.0f"),
                                        "TOTAL_AMOUNT_INR": st.column_config.NumberColumn("TOTAL_AMOUNT_INR", format="%,.0f")})
            if msg.get("source") == "cortex":
                _auto_chart(df)
    st.caption(f"Answered by {msg.get('source_label', '')}")


def _ask(prompt: str, use_cortex: bool) -> dict:
    if use_cortex:
        history = []
        for m in st.session_state.chat_history:
            if m["role"] == "user":
                history.append(build_message("user", m["text"]))
            elif not m.get("error"):
                history.append(build_message("analyst", m.get("text", ""), m.get("sql")))
        history.append(build_message("user", prompt))
        text, sql, df, error = "", None, None, None
        for event in stream_agent_response(history):
            if event["type"] == "text":
                text += event["data"]
            elif event["type"] == "sql":
                sql = event["data"]
            elif event["type"] == "table":
                df = event["data"]
            elif event["type"] == "error":
                error = event["data"]
        if error and not text and sql is None:
            fallback = copilot_offline.answer(prompt)
            return {"role": "analyst", "text": fallback["text"], "df": fallback["df"], "source": "offline",
                    "error": f"Cortex Analyst error — answered offline instead. {error}",
                    "source_label": "offline router (Cortex Analyst unavailable)"}
        return {"role": "analyst", "text": text, "sql": sql, "df": df, "source": "cortex",
                "error": error, "source_label": "Snowflake Cortex Analyst · semantic_model/aml_risk_model.yaml"}
    res = copilot_offline.answer(prompt)
    return {"role": "analyst", "text": res["text"], "df": res["df"], "source": "offline",
            "source_label": "offline router — deterministic answers from the data and REGULATORY_DOCS_CHUNKS"}


def render_investigation():
    mode = data.mode()
    use_cortex = analyst_available()
    ui.page_header(
        title="Investigation Copilot",
        subtitle="Ask about accounts, transactions and regulations in plain English. Answers come back with the "
                 "SQL, the rows and the regulatory clause behind them.",
        eyebrow="Natural-language Q&A", eyebrow_icon="forum",
        chips=[("psychology", "Cortex Analyst · text-to-SQL" if use_cortex else "Offline router · no LLM"),
               ("lock", "Data never leaves Snowflake" if use_cortex else "Runs on the demo snapshot")],
        mode=mode,
    )
    if not use_cortex:
        ui.callout(
            "Cortex Analyst is not connected",
            "Answers below come from a deterministic router over the same tables (and verbatim regulatory clauses). "
            "Connect Snowflake with SENTINEL_REG_PAT and SENTINEL_REG_HOST to switch to Cortex Analyst.",
            callout_icon="info",
        )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_full_response" not in st.session_state:
        st.session_state.last_full_response = ""

    if not st.session_state.chat_history:
        with st.container(border=True):
            ui.section("Try asking", "One click runs the question", "lightbulb")
            cols = st.columns(2)
            for i, q in enumerate(SUGGESTED_QUESTIONS):
                if cols[i % 2].button(q, key=f"suggest_{i}", width="stretch"):
                    st.session_state.pending_prompt = q
                    st.rerun()

    for i, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(msg["text"])
        else:
            with st.chat_message("assistant", avatar=":material/shield:"):
                _render_answer(msg, i)

    pending = st.session_state.pop("pending_prompt", None)
    prompt = st.chat_input("Ask about accounts, transactions, or regulations...") or pending

    if prompt:
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar=":material/shield:"):
            with st.spinner("Analysing…"):
                reply = _ask(prompt, use_cortex)
            _render_answer(reply, len(st.session_state.chat_history) + 1)
        st.session_state.chat_history.append({"role": "user", "text": prompt})
        st.session_state.chat_history.append(reply)
        if reply.get("text"):
            st.session_state.last_full_response = f"Q: {prompt}\n\n{reply['text']}"
        data.log_event("COPILOT_QUERY", "copilot", f"{prompt} [{reply.get('source')}]")

    if st.session_state.chat_history:
        c1, c2, c3 = st.columns([1, 1.3, 1.3])
        if c1.button("Clear chat", icon=":material/delete:", width="stretch"):
            st.session_state.chat_history = []
            st.session_state.last_full_response = ""
            st.rerun()
        if st.session_state.last_full_response and c2.button(
            "Send to SAR Generator", icon=":material/description:", width="stretch", type="primary"
        ):
            nav.goto("sar", sar_prefill=st.session_state.last_full_response)
        with c3:
            nav.link("regulatory", "Regulatory Library", icon=":material/menu_book:")
