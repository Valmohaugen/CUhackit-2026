"""Attack Theater panel: Shor's algorithm demo and HNDL analysis.

Provides:
  - render_attack_panel: Shor's factoring demo, seed analysis, HNDL timeline
"""

from __future__ import annotations

import time

import streamlit as st

from src.dashboard.utils import get_shors_status, start_shors


def render_attack_panel() -> None:
    """Render the attack theater panel."""
    st.header("Attack Theater")
    st.markdown(
        "Demonstrate the quantum threat to classical cryptography using "
        "**Shor's algorithm** on a quantum simulator."
    )

    tab_shors, tab_hndl = st.tabs(["Shor's Algorithm", "HNDL Analysis"])

    with tab_shors:
        _render_shors_demo()

    with tab_hndl:
        _render_hndl_analysis()


def _render_shors_demo() -> None:
    """Render Shor's algorithm factoring demo."""
    st.subheader("Shor's Factoring Demo")
    st.markdown(
        "Factor a number using a quantum circuit. For the demo, N=15 "
        "is factored into 3 x 5 using quantum phase estimation."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        n = st.number_input("Number to factor (N)", min_value=4, max_value=100, value=15)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("Run Shor's", type="primary", use_container_width=True)

    if run_btn:
        result = start_shors(n)
        if result and result.get("status") == "started":
            st.info("Shor's algorithm running on quantum simulator...")
        elif result and result.get("status") == "already_running":
            st.warning("Already running — please wait.")

    # Poll for results
    status_data = get_shors_status()
    if status_data:
        status = status_data.get("status", "idle")

        if status == "running":
            st.info("Computing... this may take 5-30 seconds.")
            time.sleep(2)
            st.rerun()

        elif status == "done" and status_data.get("result"):
            result = status_data["result"]
            st.success("Factoring complete!")

            col_n, col_factors, col_time = st.columns(3)
            with col_n:
                st.metric("N", result.get("n", "?"))
            with col_factors:
                factors = result.get("factors", [])
                st.metric("Factors", " x ".join(str(f) for f in factors) if factors else "Failed")
            with col_time:
                st.metric("Time", f"{result.get('time_seconds', 0):.2f}s")

            col_qubits, col_shots, col_depth = st.columns(3)
            with col_qubits:
                st.metric("Qubits Used", result.get("qubits_used", "?"))
            with col_shots:
                st.metric("Shots", result.get("shots", "?"))
            with col_depth:
                st.metric("Circuit Depth", result.get("circuit_depth", "?"))

            if result.get("factored"):
                st.markdown(
                    f"**RSA-2048 implication:** A sufficiently powerful quantum computer "
                    f"could factor the 617-digit RSA-2048 modulus using ~4,000 logical qubits. "
                    f"This demo used {result.get('qubits_used', '?')} qubits to factor N={result.get('n', '?')}."
                )
            else:
                st.warning("Factoring did not find non-trivial factors in this run. Try again.")

        elif status == "error":
            st.error(f"Error: {status_data.get('result', {}).get('error', 'Unknown')}")


def _render_hndl_analysis() -> None:
    """Render Harvest-Now-Decrypt-Later threat analysis."""
    st.subheader("Harvest-Now-Decrypt-Later (HNDL)")
    st.markdown(
        "Adversaries can **record encrypted traffic today** and decrypt it "
        "when quantum computers become powerful enough. The threat depends on "
        "data shelf life vs. time until quantum computers can break each algorithm."
    )

    # Static threat timeline data
    threats = [
        {"Algorithm": "RSA-2048", "Est. Break Year": "2030-2035", "Qubits Needed": "~4,000", "Status": "Vulnerable", "Migrate To": "ML-DSA-65"},
        {"Algorithm": "ECC-256", "Est. Break Year": "2030-2035", "Qubits Needed": "~2,330", "Status": "Vulnerable", "Migrate To": "ML-DSA-65"},
        {"Algorithm": "AES-128", "Est. Break Year": "2040+", "Qubits Needed": "~2,953", "Status": "Weakened (Grover)", "Migrate To": "AES-256"},
        {"Algorithm": "AES-256", "Est. Break Year": "Never (practical)", "Qubits Needed": "~6,681", "Status": "Safe", "Migrate To": "No change"},
    ]
    st.table(threats)

    st.markdown("### Data Shelf Life vs. Quantum Timeline")
    shelf_life = [
        {"Data Type": "Financial records", "Required Secrecy": "20+ years", "Urgency": "CRITICAL"},
        {"Data Type": "Medical records", "Required Secrecy": "50+ years", "Urgency": "CRITICAL"},
        {"Data Type": "Government classified", "Required Secrecy": "25-75 years", "Urgency": "CRITICAL"},
        {"Data Type": "Personal communications", "Required Secrecy": "5-10 years", "Urgency": "HIGH"},
        {"Data Type": "Ephemeral session keys", "Required Secrecy": "< 1 year", "Urgency": "LOW"},
    ]
    st.table(shelf_life)

    st.info(
        "Organizations handling data with long secrecy requirements should "
        "begin post-quantum migration **immediately** to protect against HNDL attacks."
    )
