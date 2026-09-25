"""
Investigation Chat Page — SentinelReg
Natural language AML investigation interface powered by Cortex Analyst.
"""

import streamlit as st
from utils.agent_client import stream_agent_response, build_message


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

    # ── Session state ─────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_full_response" not in st.session_state:
        st.session_state.last_full_response = ""

    # ── Suggested prompts ─────────────────────────────────────
    if not st.session_state.chat_history:
        st.markdown("#### 💡 Try asking:")
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
