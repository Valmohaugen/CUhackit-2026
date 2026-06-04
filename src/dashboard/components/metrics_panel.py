"""Live Metrics panel: DNS query feed and QRNG status.

Provides:
  - render_metrics_panel: Metrics display with auto-refresh
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_history, get_live_metrics, get_qrng_status


def render_metrics_panel() -> None:
    """Render the live metrics panel with auto-refresh."""
    st.header("Live Metrics")

    tab_live, tab_quantum, tab_history = st.tabs(["Live Feed", "Quantum Status", "Historical"])

    with tab_live:
        _render_live_feed_auto()

    with tab_quantum:
        _render_quantum_status()

    with tab_history:
        _render_history()


@st.fragment(run_every=5)
def _render_live_feed_auto() -> None:
    """Auto-refreshing live feed fragment (updates every 5 seconds)."""
    col_metrics, col_pool = st.columns([2, 1])

    with col_metrics:
        _render_query_metrics()

    with col_pool:
        _render_pool_status()


def _render_query_metrics() -> None:
    """Render DNS query metrics."""
    st.subheader("DNS Queries")

    data = get_live_metrics()
    if not data:
        st.info("No metrics available. Run some DNS queries first.")
        return

    # Summary counters
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Queries", f"{data.get('total_queries', 0):,}")
    with col2:
        st.metric("PRNG Fallbacks", f"{data.get('fallback_count', 0):,}")
    with col3:
        total = data.get("total_queries", 0)
        fallback = data.get("fallback_count", 0)
        qrng_pct = ((total - fallback) / total * 100) if total > 0 else 0
        st.metric("QRNG Usage", f"{qrng_pct:.0f}%")

    # Recent queries table
    queries = data.get("recent_queries", [])
    if queries:
        import pandas as pd
        display_data = []
        for q in queries[:20]:  # Show last 20
            display_data.append({
                "Domain": q.get("domain", ""),
                "IPs": ", ".join(q.get("ip_addresses", [])),
                "Scheme": q.get("scheme", ""),
                "Source": q.get("seed_source", ""),
                "Verified": "Yes" if q.get("verified") else "No",
                "Latency": f"{q.get('latency_ms', 0):.1f}ms",
            })
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
    else:
        st.info("No recent queries.")


def _render_pool_status() -> None:
    """Render QRNG pool status."""
    st.subheader("QRNG Pool")

    status = get_qrng_status()
    if not status:
        st.warning("Pool status unavailable.")
        return

    pool_size = status.get("pool_size", 0)
    max_pool = 50_000
    pct = min(pool_size / max_pool, 1.0)

    # Pool gauge
    st.progress(pct)
    st.metric("Seeds Available", f"{pool_size:,}")

    st.markdown("---")
    st.metric("Last Backend", status.get("last_backend", "none"))
    st.metric("Last Entropy", status.get("last_entropy", "0.0"))
    st.caption(f"Last fill: {status.get('last_fill', 'never')}")


def _render_quantum_status() -> None:
    """Render quantum advantage summary with QRNG circuit and pool analytics."""
    st.subheader("Quantum Random Number Generation")

    # QRNG circuit visualization
    st.markdown("#### QRNG Circuit (Hadamard + Measure)")
    st.caption(
        "Each QRNG batch applies Hadamard gates to 100 qubits, creating an equal "
        "superposition of all 2^100 states. Measurement collapses each qubit to |0> or |1> "
        "with true quantum randomness — fundamentally unpredictable, unlike PRNGs."
    )

    # ASCII representation of the QRNG circuit (simplified for display)
    qrng_circuit = """     ┌───┐┌─┐
q_0: ┤ H ├┤M├──────
     ├───┤└╥┘┌─┐
q_1: ┤ H ├─╫─┤M├───
     ├───┤ ║ └╥┘┌─┐
q_2: ┤ H ├─╫──╫─┤M├
     ├───┤ ║  ║ └╥┘
 ..    ..  ║  ║  ║
     ├───┤ ║  ║  ║ ┌─┐
q_99:┤ H ├─╫──╫──╫─┤M├
     └───┘ ║  ║  ║ └╥┘
c: 100/════╩══╩══╩══╩═
           0  1  2  99

H = Hadamard: |0⟩ → (|0⟩+|1⟩)/√2
Each qubit: 50% |0⟩, 50% |1⟩
4,096 shots × 100 qubits = 409,600 raw bits per batch"""
    st.code(qrng_circuit, language=None)

    # QRNG throughput context — research data
    st.markdown("#### QRNG Throughput in Context")
    st.markdown(
        "Our Qiskit-based QRNG achieves **~90.6 kbit/s** on IBM Sherbrooke (127-qubit Eagle r3) "
        "with Von Neumann debiasing at 24.96% extraction efficiency (Root et al. 2025). "
        "For comparison, state-of-the-art photonic QRNGs reach **100 Gbps** using silicon photonic "
        "chips (Bruynsteen et al. 2023) — six orders of magnitude faster. The IBM approach offers "
        "a different value proposition: well-characterized gate-model operations with certifiable "
        "min-entropy rather than assumptions about optical components."
    )
    st.markdown(
        "| QRNG Platform | Throughput | Trust Model |\n"
        "|---|---|---|\n"
        "| IBM Sherbrooke (this project) | ~90.6 kbit/s | Gate-model, certifiable H_min ~0.99 |\n"
        "| IBM Melbourne (older) | Lower | H_min ~0.927 (raw), passes 15/15 NIST after VN |\n"
        "| IDQuantique IDQ20MC1 | 19.64 Mbps / 4.90 Mbps RNG | Chip-scale, NIST 800-90B cert |\n"
        "| Photonic integrated (record) | 100 Gbps | Vacuum fluctuation homodyne |"
    )

    # Entropy extraction pipeline
    st.markdown("#### Entropy Extraction Pipeline")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**Von Neumann**")
        st.caption("Pairs: (0,1)→0, (1,0)→1, discard equal. Provably unbiased. ~25% throughput.")
    with col2:
        st.markdown("**Toeplitz Hash**")
        st.caption("Universal-2 hash function (Carter-Wegman 1979). Matrix multiply over GF(2).")
    with col3:
        st.markdown("**FFT-Toeplitz**")
        st.caption("FFT-accelerated Toeplitz hashing. Higher throughput for large blocks.")
    with col4:
        st.markdown("**Parity**")
        st.caption("XOR blocks of bits. Simple, ~50% throughput. Reduces bias.")

    st.markdown("---")

    # Live QRNG pool analytics
    st.markdown("#### QRNG Pool Analytics")
    status = get_qrng_status()
    if status:
        pool_size = status.get("pool_size", 0)
        max_pool = 50_000
        pct = min(pool_size / max_pool, 1.0) if max_pool > 0 else 0

        col_pool, col_backend, col_entropy, col_qubits = st.columns(4)
        with col_pool:
            st.metric("Pool Size", f"{pool_size:,} / {max_pool:,}")
            st.progress(pct)
        with col_backend:
            backend = status.get("last_backend", "none")
            if "ibm" in backend.lower():
                st.success(f"Backend: {backend}")
            else:
                st.info(f"Backend: {backend}")
        with col_entropy:
            h = status.get("last_entropy", "0.0")
            st.metric("Shannon Entropy", h, help="Ideal = 1.0 bit")
        with col_qubits:
            st.metric("Qubits Used", status.get("last_qubits", "100"))

        st.caption(f"Last refill: {status.get('last_fill', 'never')}")
    else:
        st.warning("QRNG pool status unavailable.")

    # IBM QPU entropy characterization — research data
    st.markdown("---")
    st.markdown("#### IBM QPU Entropy Characterization")
    st.markdown(
        "Raw IBM QPU output shows systematic bias toward |0> from T1 relaxation during readout. "
        "On Melbourne (15 qubits): raw P(0) = 0.5262, yielding **H_min ~ 0.927 bits/bit**. "
        "Modern Eagle/Heron processors achieve **H_min ~ 0.990 bits/bit**. Von Neumann debiasing "
        "corrects this to P(0) = 0.5001, passing all **15/15 NIST SP 800-22 tests** "
        "(Strydom & Tame 2021). The cost is ~$17.67 per million unbiased bits at IBM's "
        "$96/min rate (Root et al. 2025)."
    )

    # Why quantum randomness matters
    st.markdown("---")
    st.markdown("#### Why Quantum Randomness Matters")
    st.markdown(
        "**Classical PRNGs** (like os.urandom) are *deterministic* algorithms seeded "
        "from environmental noise. Given the seed, the entire output sequence is predictable. "
        "A sufficiently powerful adversary who compromises the seed state can predict all future outputs.\n\n"
        "**Quantum RNGs** derive randomness from quantum mechanical measurement — "
        "the collapse of superposition states. This randomness is *fundamentally unpredictable* "
        "by the laws of physics (Born's rule). No amount of computational power can predict "
        "the outcome of a quantum measurement, making QRNG seeds information-theoretically secure.\n\n"
        "In our system, QRNG seeds are used for:\n"
        "- **Nonce generation** in post-quantum signature schemes\n"
        "- **Key derivation** material for lattice-based cryptography\n"
        "- **Anti-replay tokens** bound into each signed DNS response"
    )

    st.markdown(
        "**Important nuance:** Commercial QRNGs frequently perform *worse* than well-designed "
        "PRNGs on statistical test suites like TestU01 (Martinez et al. 2018; Hurley-Smith & "
        "Hernandez-Castro 2020). NIST SP 800-22 and Dieharder cannot distinguish QRNG from a "
        "good CSPRNG; only TestU01's BigCrush/Rabbit/Alphabit batteries reveal failures in "
        "commercial QRNGs. The security advantage of QRNG is **information-theoretic** "
        "(unpredictability guaranteed by physics), not statistical superiority."
    )

    # Quantum vs Classical comparison
    data = get_live_metrics()
    if data:
        total = data.get("total_queries", 0)
        fallback = data.get("fallback_count", 0)
        qrng_count = total - fallback
        if total > 0:
            st.markdown("#### Quantum Seed Usage")
            col_q, col_c, col_rate = st.columns(3)
            with col_q:
                st.metric("Queries with QRNG Seeds", f"{qrng_count:,}")
            with col_c:
                st.metric("Queries with PRNG Fallback", f"{fallback:,}")
            with col_rate:
                rate = qrng_count / total * 100
                st.metric("QRNG Hit Rate", f"{rate:.1f}%")
            st.progress(rate / 100)


def _render_history() -> None:
    """Render historical query time-series charts."""
    import pandas as pd
    from collections import Counter

    with st.form("history_controls_form"):
        st.markdown(
            '<span class="section-controls-form-marker"></span>',
            unsafe_allow_html=True,
        )
        col_limit, col_action = st.columns([3, 1])
        with col_limit:
            limit = st.slider(
                "History limit",
                50, 500, 200,
                key="history_limit",
                help="Number of most recent queries to include in historical charts.",
            )
        with col_action:
            st.markdown("<br>", unsafe_allow_html=True)
            st.form_submit_button(
                "Update History",
                use_container_width=True,
            )

    data = get_history(limit)
    if not data:
        st.info("No historical data yet. Run some DNS queries first.")
        return

    st.metric(
        "Queries Loaded",
        len(data),
        help="Total number of historical DNS queries available for analysis.",
    )

    # -------------------------------------------------------------------------
    # Chart 1: Request Volume Breakdown Over Time
    # -------------------------------------------------------------------------
    st.markdown("### Request Volume Breakdown Over Time")
    st.caption(
        "Stacked bar chart showing how many queries used each signature scheme per time window. "
        "Helps visualize scheme usage trends as you switch between configurations."
    )

    chart_rows = []
    for q in reversed(data):  # oldest first
        chart_rows.append({
            "timestamp": q.get("timestamp", ""),
            "scheme": q.get("scheme", "unknown"),
            "seed_source": q.get("seed_source", "unknown"),
        })

    if chart_rows:
        df_vol = pd.DataFrame(chart_rows)
        df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"], errors="coerce")
        df_vol = df_vol.dropna(subset=["timestamp"])

        if not df_vol.empty:
            # Group into ~20 time windows for readability
            df_vol = df_vol.sort_values("timestamp")
            n_bins = min(20, len(df_vol))
            df_vol["window"] = pd.cut(
                df_vol["timestamp"].view("int64"),
                bins=n_bins,
                labels=False,
            )
            scheme_pivot = (
                df_vol.groupby(["window", "scheme"])
                .size()
                .unstack(fill_value=0)
            )
            # Use window index as simple x-axis
            scheme_pivot.index = [f"W{i+1}" for i in scheme_pivot.index]
            st.bar_chart(scheme_pivot, x_label="Time Window", y_label="Query Count")
            st.caption(
                "Total per scheme: "
                + " | ".join(f"{col}: {scheme_pivot[col].sum()}" for col in scheme_pivot.columns)
            )
        else:
            st.info("Not enough timestamp data to build volume chart.")

    # Scheme and source summary
    col_s, col_src = st.columns(2)
    with col_s:
        st.markdown("**Queries by Scheme**")
        scheme_counts = Counter(q.get("scheme", "unknown") for q in data)
        df_sc = pd.DataFrame.from_dict(scheme_counts, orient="index", columns=["Count"])
        st.bar_chart(df_sc, x_label="Scheme", y_label="Query Count")
        st.caption(" | ".join(f"{k}: {v}" for k, v in scheme_counts.items()))
    with col_src:
        st.markdown("**Queries by Seed Source**")
        source_counts = Counter(q.get("seed_source", "unknown") for q in data)
        df_src = pd.DataFrame.from_dict(source_counts, orient="index", columns=["Count"])
        st.bar_chart(df_src, x_label="Source", y_label="Query Count")
        st.caption(" | ".join(f"{k}: {v}" for k, v in source_counts.items()))

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Chart 2: Per-Operation Latency Distribution (Box Plots)
    # -------------------------------------------------------------------------
    st.markdown("### Per-Operation Latency Distribution")
    st.caption(
        "Box plots showing the spread of latency for each operation: DNS lookup, "
        "PQ signing, signature verification, and total end-to-end. "
        "The box spans the 25th–75th percentile (IQR); the line is the median; "
        "whiskers extend to 1.5× IQR; dots are outliers."
    )

    dns_times = [q.get("dns_lookup_ms", 0) for q in data if q.get("dns_lookup_ms")]
    sign_times = [q.get("sign_ms", 0) for q in data if q.get("sign_ms")]
    verify_times = [q.get("verify_ms", 0) for q in data if q.get("verify_ms")]
    total_times = [q.get("latency_ms", 0) for q in data if q.get("latency_ms")]

    plot_data = {}
    if dns_times:
        plot_data["DNS Lookup"] = dns_times
    if sign_times:
        plot_data["Sign"] = sign_times
    if verify_times:
        plot_data["Verify"] = verify_times
    if total_times:
        plot_data["Total"] = total_times

    if plot_data:
        try:
            import matplotlib.pyplot as plt
        except ModuleNotFoundError:
            st.warning(
                "Install `matplotlib` to view the latency box plot. "
                "The summary statistics table below is still available."
            )
        else:
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.boxplot(
                plot_data.values(),
                labels=plot_data.keys(),
                patch_artist=True,
                boxprops=dict(facecolor="#F56600", alpha=0.6),
                medianprops=dict(color="#1a1a1a", linewidth=2),
                whiskerprops=dict(color="#666666"),
                capprops=dict(color="#666666"),
                flierprops=dict(marker="o", color="#F56600", alpha=0.4, markersize=4),
            )
            ax.set_xlabel("Operation")
            ax.set_ylabel("Latency (ms)")
            ax.set_title("DNS Operation Latency — Box Plot Distribution")
            ax.grid(axis="y", alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    # Summary stats table
    if plot_data:
        import numpy as np
        summary_rows = []
        for op, times in plot_data.items():
            arr = np.array(times)
            summary_rows.append({
                "Operation": op,
                "Median (ms)": f"{np.median(arr):.2f}",
                "Mean (ms)": f"{np.mean(arr):.2f}",
                "50th Pct (ms)": f"{np.percentile(arr, 50):.2f}",
                "95th Pct (ms)": f"{np.percentile(arr, 95):.2f}",
                "99th Pct (ms)": f"{np.percentile(arr, 99):.2f}",
                "Max (ms)": f"{np.max(arr):.2f}",
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
