"""
Investigation Chat Page — SentinelReg
Natural language AML investigation interface powered by Cortex Analyst.
"""

import streamlit as st
from utils.agent_client import stream_agent_response, build_message
from utils.db import run_query


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


def render_investigation():
    # ── Header ────────────────────────────────────────────────
    st.markdown("""
    <div class="sentinel-header">
        <h1>🔍 Investigation Copilot</h1>
        <p>Ask questions about accounts, transactions, and regulatory requirements in plain English.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex; gap:0.6rem; flex-wrap:wrap; margin-bottom:1.1rem;">
        <span class="badge-medium">🧠 Cortex Analyst · Text-to-SQL</span>
        <span class="badge-low">🔒 Runs natively inside Snowflake</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Regulatory citation search (deterministic, bypasses the LLM) ──
    with st.expander("📚 Regulatory Reference Library — instant keyword lookup", expanded=False):
        st.caption(
            "Searches `REGULATORY_DOCS_CHUNKS` directly by keyword — no LLM in the loop, "
            "so results are exact matches from the source text, useful when you need a "
            "citation you can defend to an examiner without waiting on a model response."
        )
        reg_query = st.text_input(
            "Keyword",
            placeholder="e.g. structuring, SAR, PEP, layering, CTR…",
            label_visibility="collapsed",
            key="regulatory_search_term",
        )
        if reg_query:
            safe_term = reg_query.replace("'", "''")
            reg_results = run_query(f"""
                SELECT DOC_NAME, DOC_TYPE, SECTION_NUMBER, SECTION_TITLE, CHUNK_TEXT, JURISDICTION
                FROM REGULATORY_DOCS_CHUNKS
                WHERE CHUNK_TEXT ILIKE '%{safe_term}%' OR SECTION_TITLE ILIKE '%{safe_term}%'
                ORDER BY DOC_TYPE, SECTION_NUMBER
            """)
            if reg_results.empty:
                st.info("No regulatory chunks matched that keyword.")
            else:
                st.caption(f"{len(reg_results)} matching clause(s):")
                for _, row in reg_results.iterrows():
                    st.markdown(f"""
                    **{row['DOC_TYPE']} — {row['SECTION_NUMBER']}: {row['SECTION_TITLE']}**
                    *({row['JURISDICTION']} · {row['DOC_NAME']})*

                    {row['CHUNK_TEXT']}
                    """)
                    st.divider()

    # ── Session state ─────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_full_response" not in st.session_state:
        st.session_state.last_full_response = ""

    # ── Suggested prompts ─────────────────────────────────────
    if not st.session_state.chat_history:
        with st.container(border=True):
            st.markdown("#### 💡 Try asking")
            cols = st.columns(2)
            for i, q in enumerate(SUGGESTED_QUESTIONS):
                if cols[i % 2].button(q, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.pending_prompt = q

    # ── Render existing chat history ──────────────────────────
    for msg in st.session_state.chat_history:
        role  = msg["role"]
        text  = msg["content"][0]["text"] if isinstance(msg["content"], list) else msg["content"]
        icon  = "🧑‍💼" if role == "user" else "🛡️"
        with st.chat_message(role, avatar=icon):
            st.markdown(text)

    # ── Chat input ────────────────────────────────────────────
    pending = st.session_state.pop("pending_prompt", None)
    prompt  = st.chat_input("Ask about accounts, transactions, or regulations...") or pending

    if prompt:
        # Display user message
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(prompt)

        user_msg = build_message("user", prompt)
        st.session_state.chat_history.append(user_msg)

        # Get agent response (Cortex Analyst: text + generated SQL + query results)
        with st.chat_message("assistant", avatar="🛡️"):
            full_text  = ""
            sql_text   = None
            result_df  = None

            with st.spinner("Analysing..."):
                for event in stream_agent_response(st.session_state.chat_history):
                    match event["type"]:
                        case "text":
                            full_text += event["data"]

                        case "sql":
                            sql_text = event["data"]

                        case "table":
                            result_df = event["data"]

                        case "error":
                            st.error(f"❌ Agent error: {event['data']}")
                            st.session_state.chat_history.pop()  # remove failed user message
                            return

                        case "done":
                            break

            if full_text:
                st.markdown(full_text)
            if sql_text:
                with st.expander("🔍 Generated SQL", expanded=False):
                    st.code(sql_text, language="sql")
            if result_df is not None and not result_df.empty:
                st.dataframe(result_df, use_container_width=True)
            elif result_df is not None:
                st.info("Query returned no rows.")

            st.session_state.last_full_response = full_text

        # Store assistant response in history
        assistant_msg = build_message("assistant", full_text)
        st.session_state.chat_history.append(assistant_msg)

    # ── Controls ──────────────────────────────────────────────
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 6])
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        with col2:
            if st.session_state.last_full_response:
                if st.button("📋 Send to SAR Generator", use_container_width=True):
                    st.session_state["sar_prefill"] = st.session_state.last_full_response
                    st.info("Evidence saved. Navigate to **SAR Generator** in the sidebar.")
