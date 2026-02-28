"""Benchmark panel: PQ scheme timing comparisons, entropy analysis, and
latency distribution.

Provides:
  - render_benchmark_panel: Bar charts for keygen/sign/verify timing,
    distribution histograms, and entropy comparison
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_benchmarks, get_entropy, resolve_with_options

# Map liboqs internal names back to user-friendly display names
_SCHEME_DISPLAY: dict[str, str] = {
    "SPHINCS+-SHA2-128s-simple": "SLH-DSA-128",
    "SPHINCS+-SHAKE-128s-simple": "SLH-DSA-128",
    "SPHINCS+-SHA256-128s-simple": "SLH-DSA-128",
    "SLH-DSA-SHA2-128s": "SLH-DSA-128",
    "SLH-DSA-SHAKE-128s": "SLH-DSA-128",
    "Dilithium3": "ML-DSA-65",
    "ML-DSA-44": "ML-DSA-65 (alt)",
    "Falcon-padded-512": "Falcon-512",
}


def _normalize_scheme(name: str) -> str:
    """Return a user-friendly scheme name for display."""
    return _SCHEME_DISPLAY.get(name, name)


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
    st.markdown(
        "Rigorous per-iteration benchmarks across all four signature schemes. "
        "Unlike the DNS Resolver tab (which measures full query latency including network), "
        "these benchmarks isolate the **cryptographic operations only** — keygen, sign, and verify — "
        "giving you clean numbers to compare PQ overhead independent of DNS lookup time."
    )

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
            st.warning(f"{_normalize_scheme(entry.get('scheme', '?'))}: {entry['error']}")
            continue

        raw_scheme = entry.get("scheme", "unknown")
        scheme = _normalize_scheme(raw_scheme)
        st.subheader(scheme)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Keygen",
                f"{entry.get('keygen_ms', 0):.2f} ms",
                help="Time to generate a fresh keypair. Averaged over 10 iterations. In practice, keys are generated once and cached.",
            )
        with col2:
            st.metric(
                "Sign",
                f"{entry.get('sign_ms', 0):.2f} ms",
                help="Time to sign a DNS response payload (~50 bytes). This is the per-query overhead added by PQ crypto.",
            )
        with col3:
            st.metric(
                "Verify",
                f"{entry.get('verify_ms', 0):.2f} ms",
                help="Time to verify the signature. Uses a cached verifier instance to avoid re-keying overhead.",
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric(
                "Public Key",
                f"{entry.get('public_key_bytes', 0):,} B",
                help="Public key size in bytes. Larger keys add overhead to DNSSEC zone transfers and certificate chains.",
            )
        with col5:
            st.metric(
                "Secret Key",
                f"{entry.get('secret_key_bytes', 0):,} B",
                help="Secret key size in bytes. Stored securely on the signing resolver; not transmitted.",
            )
        with col6:
            st.metric(
                "Signature",
                f"{entry.get('signature_bytes', 0):,} B",
                help="Signature size appended to each DNS response. Larger signatures increase DNS packet size and may require EDNS0 buffer extension.",
            )

        st.markdown("---")

    # Summary comparison bar chart
    chart_data = []
    for entry in data:
        if "error" not in entry:
            chart_data.append({
                "Scheme": _normalize_scheme(entry.get("scheme", "unknown")),
                "Keygen (ms)": entry.get("keygen_ms", 0),
                "Sign (ms)": entry.get("sign_ms", 0),
                "Verify (ms)": entry.get("verify_ms", 0),
            })
    if chart_data:
        df = pd.DataFrame(chart_data).set_index("Scheme")
        st.bar_chart(df, x_label="Scheme", y_label="Time (ms)")

        # Numeric summary table
        summary = df.copy()
        summary["Sign + Verify (ms)"] = summary["Sign (ms)"] + summary["Verify (ms)"]
        st.dataframe(summary.style.format("{:.2f}"), use_container_width=True)

        # Recommend fastest scheme
        fastest = min(chart_data, key=lambda x: x["Sign (ms)"] + x["Verify (ms)"])
        total_sv = fastest["Sign (ms)"] + fastest["Verify (ms)"]
        st.info(
            f"**Fastest for DNS:** {fastest['Scheme']} — "
            f"combined sign+verify: {total_sv:.2f} ms. "
            f"For context, a typical DNS lookup is 5–15 ms, so PQ signing adds minimal overhead."
        )


def _render_distribution() -> None:
    """Render latency distribution analysis with histograms and percentiles."""
    st.subheader("Latency Distribution")
    st.markdown(
        "Run multiple DNS resolution iterations with each scheme to measure "
        "latency distribution and compute percentiles (P50/P95/P99)."
    )

    with st.form("dist_controls_form"):
        st.markdown(
            '<span class="section-controls-form-marker"></span>',
            unsafe_allow_html=True,
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

        run_distribution = st.form_submit_button(
            "Run Distribution Analysis",
            type="primary",
            use_container_width=True,
        )

    if run_distribution and schemes:
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

        display_scheme = _normalize_scheme(results[0].get("scheme", scheme))
        st.markdown(f"#### {display_scheme}")
        latencies = [r.get("latency_ms", 0) for r in results]
        dns_times = [r.get("dns_lookup_ms", 0) for r in results]
        sign_times = [r.get("sign_ms", 0) for r in results]
        verify_times = [r.get("verify_ms", 0) for r in results]

        arr = np.array(latencies)
        col_p50, col_p95, col_p99, col_mean = st.columns(4)
        with col_p50:
            st.metric(
                "50th Percentile",
                f"{np.percentile(arr, 50):.1f} ms",
                help="Median latency — half of all requests complete faster than this value.",
            )
        with col_p95:
            st.metric(
                "95th Percentile",
                f"{np.percentile(arr, 95):.1f} ms",
                help="95% of requests complete within this time. A common SLA target for production services.",
            )
        with col_p99:
            st.metric(
                "99th Percentile",
                f"{np.percentile(arr, 99):.1f} ms",
                help="Worst-case latency — only 1 in 100 requests exceeds this. Captures tail latency spikes.",
            )
        with col_mean:
            st.metric(
                "Mean",
                f"{np.mean(arr):.1f} ms",
                help="Average latency across all iterations. Can be skewed by outliers — use 50th percentile for a more representative view.",
            )

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
        st.bar_chart(hist_df, x_label="Latency Range (ms)", y_label="Sample Count")
        st.caption(
            f"Range: {min(latencies):.1f}–{max(latencies):.1f} ms | "
            f"Samples: {len(latencies)} | "
            f"Median: {np.median(arr):.1f} ms"
        )

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
            st.session_state.pop("entropy_error", None)
        else:
            st.session_state["entropy_error"] = (
                "Entropy refresh failed. The results below are the last successful run."
            )

    data = st.session_state.get("entropy_data")
    if st.session_state.get("entropy_error"):
        st.error(st.session_state["entropy_error"])
    if not data:
        st.info("Click **Run Entropy Comparison** to compare QRNG vs PRNG randomness quality.")
        return

    import pandas as pd
    from datetime import datetime

    refreshed_at = data.get("refreshed_at_epoch")
    refreshed_label = "unknown"
    if isinstance(refreshed_at, (int, float)):
        refreshed_label = datetime.fromtimestamp(refreshed_at).strftime("%H:%M:%S")

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

    st.caption(
        f"Sample size: {data.get('sample_size', 0):,} bits | "
        f"Last refreshed: {refreshed_label}"
    )
    qrng_pool_bits = int(data.get("qrng_pool_bits", data.get("sample_size", 0)) or 0)
    qrng_fallback_bits = int(data.get("qrng_fallback_bits", 0) or 0)
    if qrng_fallback_bits > 0:
        if qrng_pool_bits == 0:
            st.warning(
                "QRNG pool is empty, so the QRNG column is currently using PRNG fallback bits. "
                "Refill the pool to see a true QRNG-vs-PRNG comparison."
            )
        else:
            st.warning(
                f"QRNG sample used {qrng_pool_bits:,} true QRNG bits and "
                f"{qrng_fallback_bits:,} PRNG fallback bits because the pool was low."
            )

    # --- Comparison bar charts with numeric values ---
    st.markdown("---")
    st.subheader("Comparison Plots")
    st.caption(
        "Each chart shows PRNG (classical os.urandom) vs QRNG (quantum circuit seeds). "
        "Both should be very close — the value is in the trust model and theoretical guarantees, not detectable statistical differences."
    )

    qrng_h = data.get("qrng_shannon_entropy", 0)
    prng_h = data.get("prng_shannon_entropy", 0)
    qrng_chi2 = data.get("qrng_chi_squared", 0)
    prng_chi2 = data.get("prng_chi_squared", 0)
    qrng_chi2_p = data.get("qrng_chi_squared_p", 0)
    prng_chi2_p = data.get("prng_chi_squared_p", 0)
    qrng_corr = abs(data.get("qrng_serial_correlation", 0))
    prng_corr = abs(data.get("prng_serial_correlation", 0))
    qrng_runs_p = data.get("qrng_runs_test_p", 0)
    prng_runs_p = data.get("prng_runs_test_p", 0)

    # 1. Shannon Entropy
    st.markdown("#### 1. Shannon Entropy — Information Content per Bit")
    st.caption(
        "Measures the average information content per bit. Ideal random source = **1.0 bit**. "
        "Values near 1.0 indicate the source is producing maximally unpredictable bits with no bias."
    )
    entropy_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Shannon Entropy (bits)": [prng_h, qrng_h],
    }).set_index("Source")
    st.bar_chart(entropy_df, x_label="Source", y_label="Shannon Entropy (bits)")
    st.caption(
        f"Ideal: 1.0 bit | PRNG: **{prng_h:.4f}** | QRNG: **{qrng_h:.4f}** | "
        f"Delta: {qrng_h - prng_h:+.6f}"
    )

    st.markdown("---")

    # 2. Chi-Squared
    st.markdown("#### 2. Chi-Squared Statistic — Byte Uniformity Test")
    st.caption(
        "Tests whether all 256 byte values appear with equal frequency. "
        "Lower chi-squared = more uniform distribution. Critical value ≈ 293 at p=0.05 (df=255). "
        "Values below this threshold indicate the byte distribution is consistent with true randomness."
    )
    chi2_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Chi-Squared": [prng_chi2, qrng_chi2],
    }).set_index("Source")
    st.bar_chart(chi2_df, x_label="Source", y_label="Chi-Squared Statistic")
    st.caption(
        f"Lower is better | Critical value ≈ 293 | "
        f"PRNG: **{prng_chi2:.2f}** | QRNG: **{qrng_chi2:.2f}**"
    )

    st.markdown("---")

    # 3. Serial Correlation
    st.markdown("#### 3. Serial Correlation (Lag-1) — Predictability of Consecutive Bits")
    st.caption(
        "Measures whether knowing one bit helps predict the next (lag-1 autocorrelation). "
        "Ideal = **0.0** (no correlation). Values near zero mean each bit is independent — "
        "a key requirement for cryptographically secure randomness."
    )
    corr_df = pd.DataFrame({
        "Source": ["PRNG", "QRNG"],
        "Serial Correlation |lag-1|": [prng_corr, qrng_corr],
    }).set_index("Source")
    st.bar_chart(corr_df, x_label="Source", y_label="Serial Correlation |lag-1|")
    st.caption(
        f"Closer to 0 is better | PRNG: **{prng_corr:.6f}** | QRNG: **{qrng_corr:.6f}**"
    )

    st.markdown("---")

    # 4. Combined p-values
    st.markdown("#### 4. Statistical Test p-values — Randomness Hypothesis")
    st.caption(
        "p-value from chi-squared and Wald-Wolfowitz runs tests. **Higher p-value = more consistent with true randomness.** "
        "Pass threshold: p > 0.01. Failure does not mean the source is broken — it may reflect "
        "insufficient sample size or natural variance. Both QRNG and PRNG should pass at this threshold."
    )
    pval_df = pd.DataFrame({
        "Test": ["Chi-Squared p", "Runs Test p"],
        "PRNG": [prng_chi2_p, prng_runs_p],
        "QRNG": [qrng_chi2_p, qrng_runs_p],
    }).set_index("Test")
    st.bar_chart(pval_df, x_label="Test", y_label="p-value")
    st.caption(
        f"Pass threshold: p > 0.01 | "
        f"Chi-Sq: PRNG={prng_chi2_p:.4f} ({'✓ PASS' if prng_chi2_p >= 0.01 else '✗ FAIL'}), "
        f"QRNG={qrng_chi2_p:.4f} ({'✓ PASS' if qrng_chi2_p >= 0.01 else '✗ FAIL'}) | "
        f"Runs: PRNG={prng_runs_p:.4f} ({'✓ PASS' if prng_runs_p >= 0.01 else '✗ FAIL'}), "
        f"QRNG={qrng_runs_p:.4f} ({'✓ PASS' if qrng_runs_p >= 0.01 else '✗ FAIL'})"
    )
