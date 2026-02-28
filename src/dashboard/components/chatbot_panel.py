"""AI Assistant — main-page chat tab.

Renders as a full tab panel in the main content area.

Exports:
  - render_chat_tab: Renders the AI assistant as a tab panel.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import _post, get_config, get_qrng_status


SUGGESTED_QUESTIONS = [
    "What is lattice-based cryptography?",
    "Compare ML-DSA-65 vs Falcon-512",
    "How does the QRNG seed pool work?",
    "What is Harvest-Now-Decrypt-Later?",
    "Explain Shor's algorithm vs RSA",
]


def render_chat_tab() -> None:
    """Render the AI assistant chat interface as a main-page tab."""
    st.header("AI Assistant")
    st.caption("Ask about post-quantum cryptography, QRNG, or this project.")

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Suggested questions when no history
    if not st.session_state.chat_history:
        cols = st.columns(len(SUGGESTED_QUESTIONS))
        for col, question in zip(cols, SUGGESTED_QUESTIONS):
            with col:
                if st.button(question, key=f"suggest_{question[:10]}", use_container_width=True):
                    _send_message(question)
                    st.rerun()

    # Chat input — works at page root / inside tabs
    if user_input := st.chat_input("Ask a question...", key="chat_input"):
        _send_message(user_input)
        st.rerun()

    # Clear button
    if st.session_state.chat_history:
        if st.button("Clear conversation"):
            st.session_state.chat_history = []
            st.rerun()


def _send_message(message: str) -> None:
    """Send a message and get a response from the chatbot API."""
    st.session_state.chat_history.append({"role": "user", "content": message})

    context = _build_context()
    api_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_history[:-1]
    ]

    response = _post("/api/chatbot", {
        "message": message,
        "context": context,
        "history": api_history,
    })

    if response and "response" in response:
        assistant_msg = response["response"]
    else:
        assistant_msg = (
            "Unable to connect to the AI backend. Ensure "
            "OPENAI_API_KEY is set and the API is running."
        )

    st.session_state.chat_history.append({"role": "assistant", "content": assistant_msg})


def _build_context() -> dict:
    """Build context dict from current app state for the chatbot."""
    context: dict = {}

    config = get_config()
    if config:
        context["config"] = config

    status = get_qrng_status()
    if status:
        context["pool_size"] = status.get("pool_size", 0)

    if "last_resolve_result" in st.session_state:
        context["last_query"] = st.session_state["last_resolve_result"]

    # Include benchmark data if available
    if "benchmark_data" in st.session_state:
        context["benchmarks"] = st.session_state["benchmark_data"]

    # Include entropy comparison data if available
    if "entropy_data" in st.session_state:
        context["entropy"] = st.session_state["entropy_data"]

    return context
