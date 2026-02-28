"""Benchmark panel: PQ scheme timing comparisons and entropy analysis.

Provides:
  - render_benchmark_panel: Bar charts for keygen/sign/verify timing
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_benchmarks, get_entropy


def render_benchmark_panel() -> None:
    """Render the benchmarks panel."""
    st.header("Cryptographic Benchmarks")
    st.markdown(
        "Compare keygen, sign, and verify performance across "
        "post-quantum and classical signature schemes."
    )

    tab_timing, tab_entropy = st.tabs(["Scheme Timing", "Entropy Comparison"])

    with tab_timing:
        _render_timing()

    with tab_entropy:
        _render_entropy()


def _render_timing() -> None:
    """Render scheme timing benchmarks."""
    if st.button("Run Benchmarks", type="primary"):
        st.session_state["run_benchmarks"] = True

    if st.session_state.get("run_benchmarks"):
        with st.spinner("Benchmarking all schemes..."):
            data = get_benchmarks()

        if data:
            for entry in data:
                if "error" in entry:
                    st.warning(f"{entry['scheme']}: {entry['error']}")
                    continue

                scheme = entry.get("scheme", "unknown")
                st.subheader(scheme)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Keygen", f"{entry.get('keygen_ms', 0):.2f} ms")
                with col2:
                    st.metric("Sign", f"{entry.get('sign_ms', 0):.2f} ms")
                with col3:
                    st.metric("Verify", f"{entry.get('verify_ms', 0):.2f} ms")

                col4, col5, col6 = st.columns(3)
                with col4:
                    st.metric("Public Key", f"{entry.get('public_key_bytes', 0):,} bytes")
                with col5:
                    st.metric("Secret Key", f"{entry.get('secret_key_bytes', 0):,} bytes")
                with col6:
                    st.metric("Signature", f"{entry.get('signature_bytes', 0):,} bytes")

                st.markdown("---")

            # Summary comparison bar chart
            import pandas as pd
            chart_data = []
            for entry in data:
                if "error" not in entry:
                    chart_data.append({
                        "Scheme": entry["scheme"],
                        "Keygen (ms)": entry.get("keygen_ms", 0),
                        "Sign (ms)": entry.get("sign_ms", 0),
                        "Verify (ms)": entry.get("verify_ms", 0),
                    })
            if chart_data:
                df = pd.DataFrame(chart_data).set_index("Scheme")
                st.bar_chart(df)
        else:
            st.error("Failed to fetch benchmarks.")


def _render_entropy() -> None:
    """Render QRNG vs PRNG entropy comparison."""
    st.subheader("QRNG vs PRNG Entropy")
    st.markdown(
        "Statistical comparison of quantum-generated random numbers vs "
        "classical pseudorandom numbers (os.urandom)."
    )

    if st.button("Run Entropy Comparison", type="primary"):
        with st.spinner("Running statistical tests..."):
            data = get_entropy()

        if data:
            col_qrng, col_prng = st.columns(2)

            with col_qrng:
                st.markdown("### QRNG")
                st.metric("Shannon Entropy", f"{data.get('qrng_shannon_entropy', 0):.4f}")
                st.metric("Chi-Squared", f"{data.get('qrng_chi_squared', 0):.2f}")
                st.metric("Chi-Squared p-value", f"{data.get('qrng_chi_squared_p', 0):.4f}")
                st.metric("Serial Correlation", f"{data.get('qrng_serial_correlation', 0):.6f}")
                st.metric("Runs Test p-value", f"{data.get('qrng_runs_test_p', 0):.4f}")

            with col_prng:
                st.markdown("### PRNG")
                st.metric("Shannon Entropy", f"{data.get('prng_shannon_entropy', 0):.4f}")
                st.metric("Chi-Squared", f"{data.get('prng_chi_squared', 0):.2f}")
                st.metric("Chi-Squared p-value", f"{data.get('prng_chi_squared_p', 0):.4f}")
                st.metric("Serial Correlation", f"{data.get('prng_serial_correlation', 0):.6f}")
                st.metric("Runs Test p-value", f"{data.get('prng_runs_test_p', 0):.4f}")

            st.caption(f"Sample size: {data.get('sample_size', 0):,} bits")
        else:
            st.error("Failed to run entropy comparison.")
