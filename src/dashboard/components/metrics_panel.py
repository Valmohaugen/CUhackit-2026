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

    limit = st.slider("History limit", 50, 500, 200, key="history_limit")

    data = get_history(limit)
    if not data:
        st.info("No historical data yet. Run some DNS queries first.")
        return

    st.metric("Historical Queries", len(data))

    # Latency over time
    st.markdown("#### Latency Over Time")
    chart_rows = []
    for q in reversed(data):  # oldest first for line chart
        row = {
            "timestamp": q.get("timestamp", ""),
            "Total (ms)": q.get("latency_ms", 0),
            "DNS (ms)": q.get("dns_lookup_ms", 0),
            "Sign (ms)": q.get("sign_ms", 0),
            "Verify (ms)": q.get("verify_ms", 0),
        }
        chart_rows.append(row)

    if chart_rows:
        df = pd.DataFrame(chart_rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.set_index("timestamp")
        st.line_chart(df)

    # Scheme usage distribution
    st.markdown("#### Scheme Usage Distribution")
    scheme_counts = Counter(q.get("scheme", "unknown") for q in data)
    if scheme_counts:
        df_scheme = pd.DataFrame.from_dict(scheme_counts, orient="index", columns=["Count"])
        st.bar_chart(df_scheme)

    # Seed source distribution
    st.markdown("#### Seed Source Distribution")
    source_counts = Counter(q.get("seed_source", "unknown") for q in data)
    if source_counts:
        df_source = pd.DataFrame.from_dict(source_counts, orient="index", columns=["Count"])
        st.bar_chart(df_source)
