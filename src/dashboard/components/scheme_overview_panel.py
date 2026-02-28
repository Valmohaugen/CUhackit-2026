"""Scheme Overview panel: Comprehensive charts comparing all PQ schemes.

Provides:
  - render_scheme_overview: Auto-loading charts comparing timing, sizes,
    and QRNG vs PRNG across all signature schemes
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_benchmarks, resolve_with_options


_ALL_SCHEMES = ["ml-dsa-65", "falcon-512", "slh-dsa-128", "rsa-2048"]


def render_scheme_overview() -> None:
    """Render comprehensive scheme comparison charts."""
    st.subheader("Scheme Comparison")
    st.markdown(
        "Compare all signature schemes across performance, size, and entropy metrics."
    )

    # Auto-load or use cached benchmark data
    if "overview_bench" not in st.session_state:
        with st.spinner("Loading scheme benchmarks..."):
            data = get_benchmarks()
        if data:
            st.session_state["overview_bench"] = data

    data = st.session_state.get("overview_bench")
    if not data:
        if st.button("Load Scheme Data", type="primary", key="overview_load"):
            with st.spinner("Loading scheme benchmarks..."):
                data = get_benchmarks()
            if data:
                st.session_state["overview_bench"] = data
                st.rerun()
        return

    import pandas as pd

    # Filter out errored entries
    valid = [e for e in data if "error" not in e]
    if not valid:
        st.warning("No benchmark data available.")
        return

    # --- 1. Timing Comparison (Keygen / Sign / Verify) ---
    st.markdown("#### Keygen / Sign / Verify Timing")
    timing_rows = []
    for entry in valid:
        timing_rows.append({
            "Scheme": entry["scheme"],
            "Keygen (ms)": entry.get("keygen_ms", 0),
            "Sign (ms)": entry.get("sign_ms", 0),
            "Verify (ms)": entry.get("verify_ms", 0),
        })
    timing_df = pd.DataFrame(timing_rows).set_index("Scheme")
    st.bar_chart(timing_df)

    # Numeric caption
    captions = []
    for row in timing_rows:
        total = row["Keygen (ms)"] + row["Sign (ms)"] + row["Verify (ms)"]
        captions.append(f"{row['Scheme']}: {total:.2f} ms total")
    fastest = min(timing_rows, key=lambda x: x["Sign (ms)"] + x["Verify (ms)"])
    st.caption(
        f"Fastest sign+verify: **{fastest['Scheme']}** "
        f"({fastest['Sign (ms)'] + fastest['Verify (ms)']:.2f} ms) | "
        + " | ".join(captions)
    )

    # --- 2. Key and Signature Sizes ---
    st.markdown("#### Key & Signature Sizes")
    size_rows = []
    for entry in valid:
        size_rows.append({
            "Scheme": entry["scheme"],
            "Public Key (bytes)": entry.get("public_key_bytes", 0),
            "Secret Key (bytes)": entry.get("secret_key_bytes", 0),
            "Signature (bytes)": entry.get("signature_bytes", 0),
        })
    size_df = pd.DataFrame(size_rows).set_index("Scheme")
    st.bar_chart(size_df)

    # Numeric caption
    size_captions = []
    for row in size_rows:
        size_captions.append(
            f"{row['Scheme']}: PK={row['Public Key (bytes)']:,}B, "
            f"Sig={row['Signature (bytes)']:,}B"
        )
    smallest_sig = min(size_rows, key=lambda x: x["Signature (bytes)"])
    st.caption(
        f"Smallest signature: **{smallest_sig['Scheme']}** "
        f"({smallest_sig['Signature (bytes)']:,} bytes) | "
        + " | ".join(size_captions)
    )

    # --- 3. Sign vs Verify Scatter (metric cards) ---
    st.markdown("#### Sign vs Verify Breakdown")
    cols = st.columns(len(valid))
    for i, entry in enumerate(valid):
        with cols[i]:
            scheme = entry["scheme"]
            sign_ms = entry.get("sign_ms", 0)
            verify_ms = entry.get("verify_ms", 0)
            st.metric(scheme, f"{sign_ms + verify_ms:.2f} ms",
                       help=f"Sign: {sign_ms:.2f} ms, Verify: {verify_ms:.2f} ms")
            st.caption(f"Sign: {sign_ms:.2f}")
            st.caption(f"Verify: {verify_ms:.2f}")

    # --- 4. QRNG vs PRNG Latency per Scheme ---
    st.markdown("---")
    st.markdown("#### QRNG vs PRNG Latency per Scheme")

    if "overview_qrng_prng" not in st.session_state:
        with st.spinner("Resolving across all schemes with QRNG and PRNG..."):
            qp_results = _resolve_all_schemes_both_sources()
        if qp_results:
            st.session_state["overview_qrng_prng"] = qp_results

    qp_data = st.session_state.get("overview_qrng_prng")
    if qp_data:
        _render_qrng_prng_charts(qp_data)
    else:
        if st.button("Load QRNG vs PRNG Data", key="overview_qp_load"):
            with st.spinner("Resolving across all schemes..."):
                qp_results = _resolve_all_schemes_both_sources()
            if qp_results:
                st.session_state["overview_qrng_prng"] = qp_results
                st.rerun()

    # --- 5. Refresh button ---
    st.markdown("---")
    if st.button("Refresh All Data", key="overview_refresh"):
        for key in ["overview_bench", "overview_qrng_prng"]:
            st.session_state.pop(key, None)
        st.rerun()


def _resolve_all_schemes_both_sources() -> list[dict] | None:
    """Resolve example.com with every scheme using both QRNG and PRNG."""
    domain = st.session_state.get("resolved_domain", "example.com")
    results = []
    for scheme in _ALL_SCHEMES:
        for source in ["qrng", "prng"]:
            result = resolve_with_options(domain, scheme=scheme, source=source)
            if result:
                result["_scheme"] = result.get("scheme", scheme)
                result["_source"] = source
                results.append(result)
    return results if results else None


def _render_qrng_prng_charts(results: list[dict]) -> None:
    """Render QRNG vs PRNG comparison charts from resolve results."""
    import pandas as pd

    qrng_results = [r for r in results if r["_source"] == "qrng"]
    prng_results = [r for r in results if r["_source"] == "prng"]

    # Total latency comparison
    latency_rows = []
    for qr in qrng_results:
        scheme = qr["_scheme"]
        pr = next((p for p in prng_results if p["_scheme"] == scheme), None)
        if pr:
            latency_rows.append({
                "Scheme": scheme,
                "QRNG (ms)": qr.get("latency_ms", 0),
                "PRNG (ms)": pr.get("latency_ms", 0),
            })

    if latency_rows:
        lat_df = pd.DataFrame(latency_rows).set_index("Scheme")
        st.bar_chart(lat_df)

        # Numeric captions with deltas
        captions = []
        for row in latency_rows:
            delta = row["QRNG (ms)"] - row["PRNG (ms)"]
            captions.append(
                f"{row['Scheme']}: QRNG={row['QRNG (ms)']:.1f}, "
                f"PRNG={row['PRNG (ms)']:.1f} ({delta:+.1f})"
            )
        st.caption(" | ".join(captions))

    # Per-step breakdown: signing time QRNG vs PRNG
    st.markdown("#### Signing Time: QRNG vs PRNG")
    sign_rows = []
    for qr in qrng_results:
        scheme = qr["_scheme"]
        pr = next((p for p in prng_results if p["_scheme"] == scheme), None)
        if pr:
            sign_rows.append({
                "Scheme": scheme,
                "QRNG Sign (ms)": qr.get("sign_ms", 0),
                "PRNG Sign (ms)": pr.get("sign_ms", 0),
            })

    if sign_rows:
        sign_df = pd.DataFrame(sign_rows).set_index("Scheme")
        st.bar_chart(sign_df)

    # Verification time QRNG vs PRNG
    st.markdown("#### Verification Time: QRNG vs PRNG")
    verify_rows = []
    for qr in qrng_results:
        scheme = qr["_scheme"]
        pr = next((p for p in prng_results if p["_scheme"] == scheme), None)
        if pr:
            verify_rows.append({
                "Scheme": scheme,
                "QRNG Verify (ms)": qr.get("verify_ms", 0),
                "PRNG Verify (ms)": pr.get("verify_ms", 0),
            })

    if verify_rows:
        verify_df = pd.DataFrame(verify_rows).set_index("Scheme")
        st.bar_chart(verify_df)

    # Seed fetch time QRNG vs PRNG
    st.markdown("#### Seed Fetch Time: QRNG vs PRNG")
    seed_rows = []
    for qr in qrng_results:
        scheme = qr["_scheme"]
        pr = next((p for p in prng_results if p["_scheme"] == scheme), None)
        if pr:
            seed_rows.append({
                "Scheme": scheme,
                "QRNG Seed (ms)": qr.get("seed_fetch_ms", 0),
                "PRNG Seed (ms)": pr.get("seed_fetch_ms", 0),
            })

    if seed_rows:
        seed_df = pd.DataFrame(seed_rows).set_index("Scheme")
        st.bar_chart(seed_df)
        st.caption("QRNG seeds are fetched from the Redis pool; PRNG uses os.urandom (near-zero latency).")
