"""DNS Resolver panel: Query domains and view signed responses.

Provides:
  - render_resolver_panel: Domain input, resolve button, result display
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import resolve_domain


def render_resolver_panel() -> None:
    """Render the DNS resolution demo panel."""
    st.header("DNS Resolver")
    st.markdown(
        "Resolve domains with **post-quantum signed** DNS responses. "
        "Each response is signed using the selected PQ scheme with a "
        "quantum-random seed from the QRNG pool."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        domain = st.text_input(
            "Domain to resolve",
            value="example.com",
            placeholder="example.com",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        resolve_btn = st.button("Resolve", type="primary", use_container_width=True)

    if resolve_btn and domain:
        with st.spinner("Resolving..."):
            result = resolve_domain(domain)

        if result:
            # Status row
            col_ip, col_verified, col_latency = st.columns(3)
            with col_ip:
                ips = ", ".join(result.get("ip_addresses", []))
                st.metric("IP Addresses", ips or "NXDOMAIN")
            with col_verified:
                verified = result.get("verified", False)
                st.metric("Signature", "Verified" if verified else "FAILED")
            with col_latency:
                st.metric("Latency", f"{result.get('latency_ms', 0):.1f} ms")

            # Details
            st.markdown("---")
            col_scheme, col_source = st.columns(2)
            with col_scheme:
                st.markdown(f"**Scheme:** `{result.get('scheme', 'unknown')}`")
            with col_source:
                source = result.get("seed_source", "unknown")
                emoji = "quantum" if source == "qrng" else "classical"
                st.markdown(f"**Seed Source:** `{source}` ({emoji})")

            # Signature preview
            sig = result.get("signature", "")
            st.code(f"Signature (first 128 hex chars):\n{sig}", language="text")

            st.caption(f"Timestamp: {result.get('timestamp', '')}")
        else:
            st.error("Resolution failed. Check API connection.")
