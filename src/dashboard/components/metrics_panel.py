"""Live Metrics panel: Real-time DNS query feed and QRNG status.

Provides:
  - render_metrics_panel: Auto-refreshing metrics display
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_live_metrics, get_qrng_status


def render_metrics_panel() -> None:
    """Render the live metrics panel with auto-refresh."""
    st.header("Live Metrics")
    st.markdown("Real-time monitoring of DNS resolution and QRNG operations.")

    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh (2s)", value=True)

    col_metrics, col_pool = st.columns([2, 1])

    with col_metrics:
        _render_query_metrics()

    with col_pool:
        _render_pool_status()

    if auto_refresh:
        import time
        time.sleep(2)
        st.rerun()


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
