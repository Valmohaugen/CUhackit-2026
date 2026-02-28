"""Side-by-side scheme comparison tool.

Resolves the same domain with multiple schemes and seed sources,
then displays grouped bar charts and a results table.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import resolve_with_options

AVAILABLE_SCHEMES = ["ml-dsa-65", "falcon-512", "slh-dsa-128", "rsa-2048"]
AVAILABLE_SOURCES = ["qrng", "prng"]


def render_comparison_panel() -> None:
    """Render the side-by-side comparison tool."""
    st.subheader("Side-by-Side Comparison")

    # Reuse domain from resolver panel if available
    default_domain = st.session_state.get("resolved_domain", "example.com")

    domain = st.text_input(
        "Domain to compare",
        value=default_domain,
        key="comparison_domain",
    )

    col_schemes, col_sources = st.columns(2)
    with col_schemes:
        schemes = st.multiselect(
            "Schemes",
            AVAILABLE_SCHEMES,
            default=["ml-dsa-65", "falcon-512", "rsa-2048"],
        )
    with col_sources:
        sources = st.multiselect(
            "Seed Sources",
            AVAILABLE_SOURCES,
            default=["qrng", "prng"],
        )

    if st.button("Run Comparison", type="primary") and domain and schemes and sources:
        results = []
        progress = st.progress(0)
        total = len(schemes) * len(sources)
        idx = 0

        # Resolve the same domain across every scheme x source combination for side-by-side comparison
        for scheme in schemes:
            for source in sources:
                with st.spinner(f"Resolving with {scheme} / {source}..."):
                    result = resolve_with_options(domain, scheme=scheme, source=source)
                if result:
                    result["_label"] = f"{result.get('scheme', scheme)} ({source})"
                    results.append(result)
                idx += 1
                progress.progress(idx / total)

        progress.empty()

        if results:
            _render_comparison_results(results)
        else:
            st.error("No results returned. Check API connection.")


def _render_comparison_results(results: list[dict]) -> None:
    """Render grouped comparison charts and table."""
    import pandas as pd

    # Build chart data
    chart_data = []
    for r in results:
        chart_data.append({
            "Configuration": r["_label"],
            "DNS Lookup (ms)": r.get("dns_lookup_ms", 0),
            "Signing (ms)": r.get("sign_ms", 0),
            "Verification (ms)": r.get("verify_ms", 0),
            "Seed Fetch (ms)": r.get("seed_fetch_ms", 0),
            "Total (ms)": r.get("latency_ms", 0),
        })

    df = pd.DataFrame(chart_data).set_index("Configuration")

    st.markdown("#### Latency Comparison")
    st.bar_chart(df[["DNS Lookup (ms)", "Signing (ms)", "Verification (ms)", "Seed Fetch (ms)"]])

    # Numeric summary for latency comparison
    fastest = df[["DNS Lookup (ms)", "Signing (ms)", "Verification (ms)", "Seed Fetch (ms)"]].sum(axis=1)
    best_cfg = fastest.idxmin()
    st.caption(
        f"Fastest config: **{best_cfg}** — "
        + " | ".join(f"{cfg}: {fastest[cfg]:.1f} ms" for cfg in fastest.index)
    )

    st.markdown("#### Total End-to-End Latency")
    st.bar_chart(df[["Total (ms)"]])

    # Numeric summary for total latency
    st.caption(
        " | ".join(f"{cfg}: {df.loc[cfg, 'Total (ms)']:.1f} ms" for cfg in df.index)
    )

    # Results table
    st.markdown("#### Detailed Results")
    table_data = []
    for r in results:
        table_data.append({
            "Config": r["_label"],
            "IPs": ", ".join(r.get("ip_addresses", [])),
            "Verified": "Yes" if r.get("verified") else "No",
            "DNS (ms)": f"{r.get('dns_lookup_ms', 0):.1f}",
            "Sign (ms)": f"{r.get('sign_ms', 0):.1f}",
            "Verify (ms)": f"{r.get('verify_ms', 0):.1f}",
            "Total (ms)": f"{r.get('latency_ms', 0):.1f}",
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # QRNG vs PRNG overlay: group by scheme, show both sources on same chart
    qrng_results = [r for r in results if "(qrng)" in r["_label"]]
    prng_results = [r for r in results if "(prng)" in r["_label"]]

    if qrng_results and prng_results:
        st.markdown("#### QRNG vs PRNG Latency by Scheme")
        overlay_data = []
        for qr in qrng_results:
            scheme = qr.get("scheme", "?")
            pr = next((p for p in prng_results if p.get("scheme") == scheme), None)
            if pr:
                overlay_data.append({
                    "Scheme": scheme,
                    "QRNG Total (ms)": qr.get("latency_ms", 0),
                    "PRNG Total (ms)": pr.get("latency_ms", 0),
                })
        if overlay_data:
            overlay_df = pd.DataFrame(overlay_data).set_index("Scheme")
            st.bar_chart(overlay_df)
            # Numeric values for QRNG vs PRNG
            captions = []
            for row in overlay_data:
                delta = row["QRNG Total (ms)"] - row["PRNG Total (ms)"]
                captions.append(
                    f"{row['Scheme']}: QRNG={row['QRNG Total (ms)']:.1f} ms, "
                    f"PRNG={row['PRNG Total (ms)']:.1f} ms (delta: {delta:+.1f} ms)"
                )
            st.caption(" | ".join(captions))
