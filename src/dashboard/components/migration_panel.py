"""Migration Matrix panel: PQ migration planning by scenario.

Provides:
  - render_migration_panel: Interactive matrix and recommendations
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_migration


def render_migration_panel() -> None:
    """Render the migration matrix panel."""
    st.header("Post-Quantum Migration Matrix")
    st.markdown(
        "Plan your organization's migration to post-quantum cryptography. "
        "The matrix shows cost, risk, and timeline for each deployment "
        "scenario across migration phases."
    )

    data = get_migration()
    if not data:
        st.error("Failed to load migration data.")
        return

    tab_matrix, tab_rec = st.tabs(["Migration Matrix", "Recommendations"])

    with tab_matrix:
        _render_matrix(data.get("matrix", []))

    with tab_rec:
        _render_recommendations(data)


def _render_matrix(matrix: list[dict]) -> None:
    """Render the migration matrix as a table."""
    if not matrix:
        st.info("No matrix data available.")
        return

    import pandas as pd
    df = pd.DataFrame(matrix)

    # Display as styled table
    display_cols = [
        "scenario", "phase", "scheme", "key_size_bytes", "signature_bytes",
        "latency_overhead_pct", "implementation_cost", "risk_level", "timeline_months",
    ]
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available_cols],
        use_container_width=True,
        hide_index=True,
    )


def _render_recommendations(data: dict) -> None:
    """Render scenario-specific recommendations."""
    # Current recommendation
    rec = data.get("recommendation", {})
    if rec and "error" not in rec:
        st.subheader(f"Recommendation: {rec.get('scenario', '')}")

        col1, col2, col3 = st.columns(3)
        with col1:
            urgency = rec.get("urgency", "unknown")
            colors = {"critical": "red", "high": "orange", "medium": "yellow", "low": "green"}
            st.markdown(f"**Urgency:** :{colors.get(urgency, 'blue')}[{urgency.upper()}]")
        with col2:
            st.markdown(f"**Recommended Scheme:** `{rec.get('recommended_scheme', '')}`")
        with col3:
            st.markdown(f"**Timeline:** {rec.get('estimated_timeline', '')}")

        st.markdown(rec.get("summary", ""))

        st.markdown("### Migration Steps")
        for i, step in enumerate(rec.get("migration_steps", []), 1):
            st.markdown(f"{i}. {step}")

    # All recommendations summary
    st.markdown("---")
    st.subheader("All Scenarios")
    all_recs = data.get("all_recommendations", [])
    for r in all_recs:
        if "error" in r:
            continue
        with st.expander(f"{r.get('scenario', 'Unknown')} — {r.get('urgency', '').upper()}"):
            st.markdown(f"**Scheme:** `{r.get('recommended_scheme', '')}`")
            st.markdown(f"**Timeline:** {r.get('estimated_timeline', '')}")
            st.markdown(r.get("summary", ""))
