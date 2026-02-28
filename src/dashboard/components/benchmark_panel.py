"""Benchmark panel: PQ scheme timing comparisons, entropy analysis, and
latency distribution.

Provides:
  - render_benchmark_panel: Bar charts for keygen/sign/verify timing,
    distribution histograms, and entropy comparison
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_benchmarks, get_entropy, resolve_with_options


def render_benchmark_panel() -> None:
    """Render the benchmarks panel."""
    st.header("Cryptographic Benchmarks")

    tab_timing, tab_distribution, tab_entropy = st.tabs([
        "Scheme Timing", "Latency Distribution", "Entropy Comparison",
    ])

    with tab_timing:
        _render_timing()

    with tab_distribution:
        _render_distribution()

    with tab_entropy:
        _render_entropy()


def _render_timing() -> None:
    """Render scheme timing benchmarks with state persistence."""
    if st.button("Run Benchmarks", type="primary"):
        with st.spinner("Benchmarking all schemes..."):
            data = get_benchmarks()
        if data:
            st.session_state["benchmark_data"] = data

    data = st.session_state.get("benchmark_data")
    if not data:
        st.info("Click **Run Benchmarks** to measure keygen/sign/verify timing for all schemes.")
        return

    import pandas as pd

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

        # Numeric summary table
        summary = df.copy()
        summary["Total (ms)"] = summary.sum(axis=1)
        st.dataframe(summary.style.format("{:.2f}"), use_container_width=True)

        # Recommend fastest scheme
        fastest = min(chart_data, key=lambda x: x["Sign (ms)"] + x["Verify (ms)"])
        total_sv = fastest["Sign (ms)"] + fastest["Verify (ms)"]
        st.info(
            f"**Fastest scheme:** {fastest['Scheme']} — "
            f"combined sign+verify: {total_sv:.2f} ms"
        )


def _render_distribution() -> None:
    """Render latency distribution analysis with histograms and percentiles."""
    st.subheader("Latency Distribution")
    st.markdown(
        "Run multiple DNS resolution iterations with each scheme to measure "
        "latency distribution and compute percentiles (P50/P95/P99)."
    )

    col_domain, col_iter = st.columns([3, 1])
    with col_domain:
        domain = st.text_input("Domain", value="example.com", key="dist_domain")
    with col_iter:
        iterations = st.number_input("Iterations", min_value=5, max_value=50, value=10, key="dist_iter")

    schemes = st.multiselect(
        "Schemes to test",
        ["ml-dsa-65", "falcon-512", "slh-dsa-128", "rsa-2048"],
        default=["ml-dsa-65", "rsa-2048"],
        key="dist_schemes",
    )

    if st.button("Run Distribution Analysis", type="primary") and schemes:
        import numpy as np
        import pandas as pd

        all_results: dict[str, list[dict]] = {s: [] for s in schemes}
        progress = st.progress(0)
        total = len(schemes) * iterations
        idx = 0

        for scheme in schemes:
            for _ in range(iterations):
                result = resolve_with_options(domain, scheme=scheme, source="qrng")
                if result:
                    all_results[scheme].append(result)
                idx += 1
                progress.progress(idx / total)

        progress.empty()
        st.session_state["dist_results"] = all_results

    all_results = st.session_state.get("dist_results")
    if not all_results:
        st.info("Click **Run Distribution Analysis** to measure latency distributions.")
        return

    import numpy as np
    import pandas as pd

    for scheme, results in all_results.items():
        if not results:
            st.warning(f"No results for {scheme}")
            continue

        st.markdown(f"#### {results[0].get('scheme', scheme)}")
        latencies = [r.get("latency_ms", 0) for r in results]
        dns_times = [r.get("dns_lookup_ms", 0) for r in results]
        sign_times = [r.get("sign_ms", 0) for r in results]
        verify_times = [r.get("verify_ms", 0) for r in results]

        arr = np.array(latencies)
        col_p50, col_p95, col_p99, col_mean = st.columns(4)
        with col_p50:
            st.metric("P50", f"{np.percentile(arr, 50):.1f} ms", help="Median latency")
        with col_p95:
            st.metric("P95", f"{np.percentile(arr, 95):.1f} ms", help="95th percentile")
        with col_p99:
            st.metric("P99", f"{np.percentile(arr, 99):.1f} ms", help="99th percentile")
        with col_mean:
            st.metric("Mean", f"{np.mean(arr):.1f} ms", help="Average latency")

        # Per-component means
        col_d, col_s, col_v = st.columns(3)
        with col_d:
            st.metric("Avg DNS", f"{np.mean(dns_times):.1f} ms")
        with col_s:
            st.metric("Avg Sign", f"{np.mean(sign_times):.1f} ms")
        with col_v:
            st.metric("Avg Verify", f"{np.mean(verify_times):.1f} ms")

        # Fixed histogram using np.histogram
        counts, edges = np.histogram(latencies, bins=10)
        labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(len(counts))]
        hist_df = pd.DataFrame({"Count": counts}, index=labels)
        hist_df.index.name = "Latency Range (ms)"
        st.bar_chart(hist_df)

        st.markdown("---")


def _render_entropy() -> None:
    """Render QRNG vs PRNG entropy comparison with side-by-side plots."""
    st.subheader("QRNG vs PRNG Entropy")
    st.markdown(
        "Statistical comparison of quantum-generated random numbers vs "
        "classical pseudorandom numbers (os.urandom). "
        "Ideal Shannon entropy = 1.0 bit, serial correlation near 0, "
        "chi-squared p-value > 0.01."
    )

    if st.button("Run Entropy Comparison", type="primary"):
        with st.spinner("Running statistical tests..."):
            data = get_entropy()
        if data:
            st.session_state["entropy_data"] = data

    data = st.session_state.get("entropy_data")
    if not data:
        st.info("Click **Run Entropy Comparison** to compare QRNG vs PRNG randomness quality.")
        return

    import pandas as pd

    # --- Side-by-side metric cards (PRNG left, QRNG right — matches bar chart order) ---
    col_prng, col_qrng = st.columns(2)

    with col_prng:
        st.markdown("### PRNG (Classical)")
        st.metric("Shannon Entropy", f"{data.get('prng_shannon_entropy', 0):.4f}")
        st.metric("Chi-Squared", f"{data.get('prng_chi_squared', 0):.2f}")
        st.metric("Chi-Squared p-value", f"{data.get('prng_chi_squared_p', 0):.4f}")
        st.metric("Serial Correlation", f"{data.get('prng_serial_correlation', 0):.6f}")
        st.metric("Runs Test p-value", f"{data.get('prng_runs_test_p', 0):.4f}")

    with col_qrng:
        st.markdown("### QRNG (Quantum)")
        st.metric("Shannon Entropy", f"{data.get('qrng_shannon_entropy', 0):.4f}")
        st.metric("Chi-Squared", f"{data.get('qrng_chi_squared', 0):.2f}")
        st.metric("Chi-Squared p-value", f"{data.get('qrng_chi_squared_p', 0):.4f}")
        st.metric("Serial Correlation", f"{data.get('qrng_serial_correlation', 0):.6f}")
        st.metric("Runs Test p-value", f"{data.get('qrng_runs_test_p', 0):.4f}")

    st.caption(f"Sample size: {data.get('sample_size', 0):,} bits")

    # --- Comparison bar charts with numeric values ---
    st.markdown("---")
    st.markdown("### Comparison Plots")

    # 1. Shannon Entropy
    st.markdown("#### Shannon Entropy")
    qrng_h = data.get("qrng_shannon_entropy", 0)
    prng_h = data.get("prng_shannon_entropy", 0)
    entropy_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Shannon Entropy": [prng_h, qrng_h],
    }).set_index("Source")
    st.bar_chart(entropy_df)
    st.caption(
        f"Ideal: 1.0 bit | PRNG: {prng_h:.4f} | QRNG: {qrng_h:.4f} | "
        f"Delta (QRNG-PRNG): {qrng_h - prng_h:+.4f}"
    )

    # 2. Chi-Squared
    st.markdown("#### Chi-Squared Statistic")
    qrng_chi2 = data.get("qrng_chi_squared", 0)
    prng_chi2 = data.get("prng_chi_squared", 0)
    chi2_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Chi-Squared": [prng_chi2, qrng_chi2],
    }).set_index("Source")
    st.bar_chart(chi2_df)
    st.caption(
        f"Lower is better (critical ~293 at p=0.05) | "
        f"PRNG: {prng_chi2:.2f} | QRNG: {qrng_chi2:.2f}"
    )

    # 3. Serial Correlation
    st.markdown("#### Serial Correlation (Lag-1)")
    qrng_corr = abs(data.get("qrng_serial_correlation", 0))
    prng_corr = abs(data.get("prng_serial_correlation", 0))
    corr_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Serial Correlation": [prng_corr, qrng_corr],
    }).set_index("Source")
    st.bar_chart(corr_df)
    st.caption(
        f"Closer to 0 is better | PRNG: {prng_corr:.6f} | QRNG: {qrng_corr:.6f}"
    )

    # 4. Combined p-values
    st.markdown("#### Statistical Test p-values (Higher = More Random)")
    qrng_chi2_p = data.get("qrng_chi_squared_p", 0)
    prng_chi2_p = data.get("prng_chi_squared_p", 0)
    qrng_runs_p = data.get("qrng_runs_test_p", 0)
    prng_runs_p = data.get("prng_runs_test_p", 0)
    pval_df = pd.DataFrame({
        "Test": ["Chi-Squared", "Runs Test"],
        "PRNG": [prng_chi2_p, prng_runs_p],
        "QRNG": [qrng_chi2_p, qrng_runs_p],
    }).set_index("Test")
    st.bar_chart(pval_df)
    st.caption(
        f"Pass threshold: p > 0.01 | "
        f"Chi-Sq: PRNG={prng_chi2_p:.4f} ({'PASS' if prng_chi2_p >= 0.01 else 'FAIL'}), "
        f"QRNG={qrng_chi2_p:.4f} ({'PASS' if qrng_chi2_p >= 0.01 else 'FAIL'}) | "
        f"Runs: PRNG={prng_runs_p:.4f} ({'PASS' if prng_runs_p >= 0.01 else 'FAIL'}), "
        f"QRNG={qrng_runs_p:.4f} ({'PASS' if qrng_runs_p >= 0.01 else 'FAIL'})"
    )
