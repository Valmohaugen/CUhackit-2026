"""DNS Resolver panel: View signed DNS responses.

Provides:
  - render_resolver_panel: Result display with per-step latency breakdown
    and quantum readiness indicators. The domain input form lives in app.py
    so it remains sticky across all tabs.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_qrng_status


def render_resolver_panel() -> None:
    """Render the DNS resolution results panel."""
    st.header("DNS Resolver")

    result = st.session_state.get("last_resolve_result")
    if result:
        _render_result(result)
    else:
        st.info("Enter a domain above and click **Resolve** to query DNS.")


def _render_result(result: dict) -> None:
    """Render a single resolve result with latency breakdown and quantum indicators."""
    # Quantum source badge
    source = result.get("seed_source", "unknown")
    scheme = result.get("scheme", "unknown")
    is_quantum_seed = source == "qrng"
    is_pq_scheme = scheme.lower() not in ("rsa-2048", "hmac-sha256")

    _render_quantum_readiness(is_quantum_seed, is_pq_scheme, scheme, source)

    # Status row
    col_ip, col_verified, col_latency = st.columns(3)
    with col_ip:
        ips = ", ".join(result.get("ip_addresses", []))
        st.metric("IP Addresses", ips or "NXDOMAIN", help="Resolved A-record addresses")
    with col_verified:
        verified = result.get("verified", False)
        st.metric(
            "Signature",
            "Verified" if verified else "FAILED",
            help="Whether the PQ signature verified successfully",
        )
    with col_latency:
        st.metric("Total Latency", f"{result.get('latency_ms', 0):.1f} ms", help="End-to-end time")

    # Per-step latency breakdown: 4-column layout isolates each pipeline stage for quick visual comparison
    st.markdown("#### Latency Breakdown")
    col_dns, col_sign, col_verify, col_seed = st.columns(4)
    with col_dns:
        st.metric(
            "DNS Lookup",
            f"{result.get('dns_lookup_ms', 0):.1f} ms",
            help="Time to query the upstream DNS resolver",
        )
    with col_sign:
        st.metric(
            "Signing",
            f"{result.get('sign_ms', 0):.1f} ms",
            help="Time to create the cryptographic signature",
        )
    with col_verify:
        st.metric(
            "Verification",
            f"{result.get('verify_ms', 0):.1f} ms",
            help="Time to verify the signature",
        )
    with col_seed:
        st.metric(
            "Seed Fetch",
            f"{result.get('seed_fetch_ms', 0):.1f} ms",
            help="Time to retrieve a seed from the QRNG pool",
        )

    # Signature preview
    st.markdown("---")
    sig = result.get("signature", "")
    st.code(f"Signature ({result.get('scheme', '?')}, first 128 hex chars):\n{sig}", language="text")

    st.caption(f"Timestamp: {result.get('timestamp', '')}")


def _render_quantum_readiness(
    is_quantum_seed: bool,
    is_pq_scheme: bool,
    scheme: str,
    source: str,
) -> None:
    """Render quantum readiness indicators for the current query."""
    # Compute readiness score: 0-100
    score = 0
    components = []

    if is_pq_scheme:
        score += 50
        components.append("Post-quantum scheme")
    else:
        components.append("Classical scheme (Shor-vulnerable)")

    if is_quantum_seed:
        score += 30
        components.append("QRNG seed (quantum entropy)")
    else:
        components.append("PRNG seed (classical entropy)")

    # Pool health check
    pool_status = get_qrng_status()
    pool_size = pool_status.get("pool_size", 0) if pool_status else 0
    if pool_size > 10000:
        score += 20
        components.append("QRNG pool healthy")
    elif pool_size > 0:
        score += 10
        components.append("QRNG pool low")
    else:
        components.append("QRNG pool empty")

    # Display badges
    col_badge, col_scheme_badge, col_score = st.columns(3)
    with col_badge:
        if is_quantum_seed:
            st.success(f"QUANTUM SEED ({source.upper()})")
        else:
            st.warning(f"CLASSICAL SEED ({source.upper()})")
    with col_scheme_badge:
        if is_pq_scheme:
            st.success(f"POST-QUANTUM ({scheme})")
        else:
            st.error(f"VULNERABLE ({scheme})")
    with col_score:
        st.metric("Quantum Readiness", f"{score}%", help=" + ".join(components))
    st.progress(score / 100)
