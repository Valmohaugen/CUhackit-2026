"""Attack Theater panel: Shor's algorithm demo, HNDL analysis,
threat model explainer, and security margin analysis.

Provides:
  - render_attack_panel: Shor's factoring demo, HNDL timeline,
    threat model matrix, and security margins
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_shors_status, start_shors, _get, get_config, set_config


# Preset configs for deployment simulation
_PRESETS = {
    "Enterprise (balanced)": {
        "scheme": "ml-dsa-65",
        "source": "qrng",
        "extractor": "toeplitz",
        "phase": "hybrid",
        "scenario": "enterprise",
        "description": "Best balance of security and performance. ML-DSA-65 NIST Level 3, QRNG seeds, hybrid migration phase.",
    },
    "IoT / Constrained device": {
        "scheme": "falcon-512",
        "source": "prng",
        "extractor": "von_neumann",
        "phase": "pq_only",
        "scenario": "iot",
        "description": "Smallest signatures (666 B), lowest overhead. Ideal for bandwidth-constrained devices.",
    },
    "Web Application": {
        "scheme": "ml-dsa-65",
        "source": "qrng",
        "extractor": "toeplitz",
        "phase": "hybrid",
        "scenario": "web",
        "description": "Standard web deployment. ML-DSA-65 with hybrid phase supports gradual migration.",
    },
    "Maximum security (conservative)": {
        "scheme": "slh-dsa-128",
        "source": "qrng",
        "extractor": "fft",
        "phase": "pq_only",
        "scenario": "critical",
        "description": "SPHINCS+ hash-based — no lattice assumptions. Slowest but most conservative. For high-value, low-volume signing.",
    },
    "Financial / Critical infrastructure": {
        "scheme": "ml-dsa-65",
        "source": "qrng",
        "extractor": "fft",
        "phase": "pq_only",
        "scenario": "financial",
        "description": "Full PQ-only deployment with QRNG and FFT-Toeplitz extraction. Highest assurance.",
    },
    "Classical baseline (pre-migration)": {
        "scheme": "rsa-2048",
        "source": "prng",
        "extractor": "von_neumann",
        "phase": "classical",
        "scenario": "web",
        "description": "Current state before PQ migration. RSA-2048 is quantum-vulnerable via Shor's algorithm.",
    },
}


def render_attack_panel() -> None:
    """Render the attack theater panel."""
    st.header("Attack Theater")

    tab_shors, tab_hndl, tab_threat, tab_margin = st.tabs([
        "Shor's Algorithm", "HNDL Analysis", "Threat Model", "Security Margins",
    ])

    with tab_shors:
        _render_shors_demo()

    with tab_hndl:
        _render_hndl_analysis()

    with tab_threat:
        _render_threat_model()

    with tab_margin:
        _render_security_margins()


def _render_shors_demo() -> None:
    """Render Shor's algorithm factoring demo."""
    st.subheader("Shor's Factoring Demo")
    st.markdown(
        "Factor a semiprime using a real quantum circuit (QPE + modular exponentiation). "
        "Supports N = 15, 21, 33, 35, 55, 77, 91 and others up to 100. "
        "The algorithm tries multiple coprime bases to find the period."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        n = st.number_input("Number to factor (N)", min_value=4, max_value=100, value=15)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("Run Shor's", type="primary", use_container_width=True)

    if run_btn:
        result = start_shors(n)
        if result and result.get("status") == "started":
            st.info("Shor's algorithm running on quantum simulator...")
        elif result and result.get("status") == "already_running":
            st.warning("Already running — please wait.")

    # Poll for Shor's status — manual refresh via button instead of auto-rerun
    status_data = get_shors_status()
    if status_data:
        status = status_data.get("status", "idle")

        if status == "running":
            st.info("Computing... this may take 5-30 seconds.")
            st.button("Check Status", key="check_shors", type="primary")

        elif status == "done" and status_data.get("result"):
            result = status_data["result"]
            method = result.get("method", "quantum")
            if method == "precomputed":
                st.success("Factoring complete (precomputed fallback)")
            elif method == "gcd":
                st.success("Factoring complete (GCD shortcut — a base shared a factor)")
            else:
                st.success("Factoring complete via quantum circuit!")

            col_n, col_factors, col_time = st.columns(3)
            with col_n:
                st.metric("N", result.get("n", "?"))
            with col_factors:
                factors = result.get("factors", [])
                st.metric("Factors", " x ".join(str(f) for f in factors) if factors else "Failed")
            with col_time:
                st.metric("Time", f"{result.get('time_seconds', 0):.2f}s")

            col_qubits, col_shots, col_depth = st.columns(3)
            with col_qubits:
                n_work = result.get("n_work_qubits", "?")
                st.metric(
                    "Qubits Used",
                    result.get("qubits_used", "?"),
                    help=f"8 counting + {n_work} work qubits",
                )
            with col_shots:
                st.metric("Shots", f"{result.get('shots', '?'):,}")
            with col_depth:
                st.metric("Circuit Depth", f"{result.get('circuit_depth', '?'):,}")

            # Bases tried
            bases_tried = result.get("bases_tried", [])
            if bases_tried:
                st.caption(f"Coprime bases tried: {bases_tried}")

            if result.get("factored"):
                nn = result.get("n", "?")
                st.markdown(
                    f"**RSA-2048 implication:** A sufficiently powerful quantum computer "
                    f"could factor the 617-digit RSA-2048 modulus in ~8 hours using 20 million "
                    f"noisy qubits (Gidney & Ekera 2021). This demo used "
                    f"{result.get('qubits_used', '?')} qubits to factor N={nn}."
                )

                # --- Quantum Attack Timing Comparison ---
                _render_attack_timing(result)

                if method == "precomputed":
                    st.caption(
                        f"Note: The simulator did not converge on this run, "
                        f"so the known factors of {nn} were used. "
                        f"This is expected — real quantum hardware has higher fidelity."
                    )
            else:
                st.warning("Factoring did not find non-trivial factors in this run. Try again.")

            # --- Quantum Circuit Visualization ---
            _render_circuit_and_histogram(result)

        elif status == "failed" and status_data.get("result"):
            result = status_data["result"]
            st.warning(
                f"Factoring N={result.get('n', '?')} did not find factors "
                f"after {result.get('shots', '?')} shots in {result.get('time_seconds', 0):.2f}s. "
                "Try running again."
            )

        elif status == "error":
            st.error(f"Error: {status_data.get('result', {}).get('error', 'Unknown')}")

    # --- Attack Timing: Shor's vs Post-Quantum Schemes ---
    _render_scheme_defense_comparison()


def _render_attack_timing(result: dict) -> None:
    """Show how long Shor's took vs. how long attacking PQ schemes would take."""
    shor_time = result.get("time_seconds", 0)
    n_val = result.get("n", 15)

    st.markdown("#### Attack Time vs. Defense")

    import pandas as pd

    # Estimated quantum attack times for each scheme
    attack_data = [
        {
            "Scheme": "RSA-2048",
            "Shor's Attack Time": "~8 hours (20M qubits)",
            "NIST Level": 0,
            "Status": "BROKEN by Shor's",
        },
        {
            "Scheme": "ML-DSA-65",
            "Shor's Attack Time": "~10^12 years (no known quantum attack)",
            "NIST Level": 3,
            "Status": "RESISTANT — lattice problem",
        },
        {
            "Scheme": "Falcon-512",
            "Shor's Attack Time": "~10^8 years (no known quantum attack)",
            "NIST Level": 1,
            "Status": "RESISTANT — NTRU lattice",
        },
        {
            "Scheme": "SLH-DSA-128",
            "Shor's Attack Time": "~10^8 years (no known quantum attack)",
            "NIST Level": 1,
            "Status": "RESISTANT — hash-based",
        },
    ]

    df = pd.DataFrame(attack_data)

    def _color_status(val: str) -> str:
        if "BROKEN" in val:
            return "background-color: #ff4444; color: white"
        elif "RESISTANT" in val:
            return "background-color: #44bb44; color: white"
        return "color: #333333"

    st.dataframe(
        df.style.map(_color_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"This demo factored N={n_val} in {shor_time:.2f}s using a quantum simulator. "
        f"Scaling to RSA-2048 (617 digits) requires ~20 million noisy qubits and ~8 hours "
        f"(Gidney & Ekera 2021). Post-quantum lattice schemes have no known polynomial "
        f"quantum speedup — attacks remain exponential even with a quantum computer."
    )


def _render_scheme_defense_comparison() -> None:
    """Render a comparison of quantum attack times vs. signature speeds."""
    st.markdown("---")
    st.markdown("#### Quantum Attack Timeline")
    st.markdown(
        "How long would a quantum computer take to break each scheme? "
        "Post-quantum schemes resist Shor's algorithm because they rely on "
        "lattice problems, not factoring or discrete logarithms."
    )

    import pandas as pd

    timeline_data = {
        "Scheme": ["RSA-2048", "ECC-256", "ML-DSA-65", "Falcon-512", "SLH-DSA-128", "AES-256"],
        "Classical Attack": ["2^112 ops", "2^128 ops", "2^192 ops", "2^128 ops", "2^128 ops", "2^256 ops"],
        "Quantum Attack": ["O((log N)^3)", "O((log N)^3)", "2^96 ops (Grover)", "2^64 ops (Grover)", "2^64 ops (Grover)", "2^128 ops (Grover)"],
        "Years to Break": ["~8 hours*", "~4 hours*", "~10^12", "~10^8", "~10^8", "~10^38"],
        "Shor Vulnerable": ["YES", "YES", "NO", "NO", "NO", "NO"],
    }

    df = pd.DataFrame(timeline_data).set_index("Scheme")

    def _color_vuln(val: str) -> str:
        if val == "YES":
            return "background-color: #ff4444; color: white"
        return "background-color: #44bb44; color: white"

    st.dataframe(
        df.style.map(_color_vuln, subset=["Shor Vulnerable"]),
        use_container_width=True,
    )

    st.caption(
        "* With a cryptographically relevant quantum computer (CRQC). "
        "Lattice-based and hash-based schemes have NO known polynomial quantum speedup — "
        "the best quantum advantage is Grover's quadratic speedup on brute-force search, "
        "which only halves the effective key length."
    )


def _render_circuit_and_histogram(result: dict) -> None:
    """Render the quantum circuit diagram and measurement histogram."""
    # Circuit diagram
    circuit_text = result.get("circuit_text", "")
    if circuit_text:
        st.markdown("#### Quantum Phase Estimation Circuit")
        n_work = result.get("n_work_qubits", "?")
        st.caption(
            f"{result.get('qubits_used', '?')} qubits: "
            f"8 counting (phase estimation) + {n_work} work (mod-N register). "
            f"Transpiled depth: {result.get('circuit_depth', '?'):,} gates."
        )
        st.code(circuit_text, language=None)

    # Measurement histogram — shows quantum interference pattern
    measurement_counts = result.get("measurement_counts", {})
    if measurement_counts:
        import pandas as pd

        st.markdown("#### Measurement Distribution")
        st.caption(
            f"Top {len(measurement_counts)} of {result.get('total_unique_outcomes', '?')} "
            f"unique outcomes from {result.get('shots', '?')} shots. "
            "Peaks correspond to phases s/r where r is the period of a mod N."
        )
        df = pd.DataFrame(
            list(measurement_counts.items()),
            columns=["Bitstring", "Count"],
        ).set_index("Bitstring")
        st.bar_chart(df)

        st.markdown(
            "The **interference pattern** above is the hallmark of quantum computing. "
            "Classical computers cannot efficiently produce this distribution — "
            "the peaks encode the period *r* needed to factor N via continued fractions."
        )


def _render_hndl_analysis() -> None:
    """Render Harvest-Now-Decrypt-Later threat analysis."""
    st.subheader("Harvest-Now-Decrypt-Later (HNDL)")
    st.markdown(
        "Adversaries can **record encrypted traffic today** and decrypt it "
        "when quantum computers become powerful enough. The threat depends on "
        "data shelf life vs. time until quantum computers can break each algorithm."
    )

    # Deployment simulation presets — replaces the global migration phase/scenario controls
    with st.expander("Deployment Simulation Presets", expanded=False):
        st.markdown(
            "Select a deployment scenario to automatically configure the controls above "
            "and simulate how a real-world system would be set up. Each preset sets the "
            "signature scheme, random source, entropy extractor, and migration phase."
        )
        preset_name = st.selectbox(
            "Scenario",
            list(_PRESETS.keys()),
            key="hndl_preset_select",
            help="Each preset represents a different deployment context with recommended PQ settings.",
        )
        preset = _PRESETS[preset_name]
        st.caption(preset["description"])

        if st.button("Apply Preset", type="primary", key="apply_preset_btn"):
            config_update = {k: v for k, v in preset.items() if k != "description"}
            set_config(config_update)
            st.success(f"Applied: {preset_name}")
            st.rerun()

    st.markdown("---")

    import pandas as pd

    # Static threat timeline data
    threats = [
        {"Algorithm": "RSA-2048", "Est. Break Year": "2030-2035", "Qubits Needed": "~4,000", "Status": "Vulnerable", "Migrate To": "ML-DSA-65"},
        {"Algorithm": "ECC-256", "Est. Break Year": "2030-2035", "Qubits Needed": "~2,330", "Status": "Vulnerable", "Migrate To": "ML-DSA-65"},
        {"Algorithm": "AES-128", "Est. Break Year": "2040+", "Qubits Needed": "~2,953", "Status": "Weakened (Grover)", "Migrate To": "AES-256"},
        {"Algorithm": "AES-256", "Est. Break Year": "Never (practical)", "Qubits Needed": "~6,681", "Status": "Safe", "Migrate To": "No change"},
    ]
    df_threats = pd.DataFrame(threats)

    def _color_status(val: str) -> str:
        if "Vulnerable" in val:
            return "background-color: #ff4444; color: white"
        elif "Weakened" in val:
            return "background-color: #ffaa00; color: #1a1a1a"
        elif "Safe" in val:
            return "background-color: #44bb44; color: white"
        return "color: #333333"

    st.dataframe(
        df_threats.style.map(_color_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Data Shelf Life vs. Quantum Timeline")
    shelf_life = [
        {"Data Type": "Financial records", "Required Secrecy": "20+ years", "Urgency": "CRITICAL"},
        {"Data Type": "Medical records", "Required Secrecy": "50+ years", "Urgency": "CRITICAL"},
        {"Data Type": "Government classified", "Required Secrecy": "25-75 years", "Urgency": "CRITICAL"},
        {"Data Type": "Personal communications", "Required Secrecy": "5-10 years", "Urgency": "HIGH"},
        {"Data Type": "Ephemeral session keys", "Required Secrecy": "< 1 year", "Urgency": "LOW"},
    ]
    df_shelf = pd.DataFrame(shelf_life)

    def _color_urgency(val: str) -> str:
        if val == "CRITICAL":
            return "background-color: #ff4444; color: white"
        elif val == "HIGH":
            return "background-color: #ffaa00; color: #1a1a1a"
        elif val == "LOW":
            return "background-color: #44bb44; color: white"
        return "color: #333333"

    st.dataframe(
        df_shelf.style.map(_color_urgency, subset=["Urgency"]),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "Organizations handling data with long secrecy requirements should "
        "begin post-quantum migration **immediately** to protect against HNDL attacks."
    )


def _render_threat_model() -> None:
    """Render the threat model matrix: attacks x schemes."""
    st.subheader("Threat Model Matrix")
    st.markdown(
        "How different attack vectors affect each signature scheme. "
        "**Green** = resistant, **Red** = vulnerable, **Yellow** = weakened."
    )

    import pandas as pd

    attacks = [
        "Shor's (factoring/ECDLP)",
        "Grover's (brute force)",
        "HNDL (harvest & decrypt)",
        "Side-channel (timing)",
        "Man-in-the-Middle",
    ]

    schemes = {
        "RSA-2048": ["VULNERABLE", "WEAKENED", "VULNERABLE", "RESISTANT", "VULNERABLE*"],
        "ML-DSA-65": ["RESISTANT", "RESISTANT", "RESISTANT", "WEAKENED", "RESISTANT"],
        "Falcon-512": ["RESISTANT", "RESISTANT", "RESISTANT", "WEAKENED", "RESISTANT"],
        "SLH-DSA-128": ["RESISTANT", "RESISTANT", "RESISTANT", "RESISTANT", "RESISTANT"],
    }

    df = pd.DataFrame(schemes, index=attacks)

    def _color_cell(val: str) -> str:
        if val == "VULNERABLE" or val == "VULNERABLE*":
            return "background-color: #ff4444; color: white"
        elif val == "WEAKENED":
            return "background-color: #ffaa00; color: black"
        else:
            return "background-color: #44bb44; color: white"

    styled = df.style.map(_color_cell)
    st.dataframe(styled, use_container_width=True)

    st.caption(
        "* RSA is vulnerable to MITM if the key exchange itself uses RSA. "
        "Post-quantum schemes resist quantum-capable MITM attackers."
    )


def _render_security_margins() -> None:
    """Render security margin analysis: real timing vs quantum attack estimates."""
    st.subheader("Security Margin Analysis")
    st.markdown(
        "Compares measured signing/verification speed against estimated "
        "quantum attack time for each scheme."
    )

    if st.button("Run Security Analysis", type="primary"):
        with st.spinner("Benchmarking and analyzing..."):
            data = _get("/api/attack/security-margin")

        if data:
            for entry in data:
                if "error" in entry:
                    st.warning(f"{entry.get('scheme', '?')}: {entry['error']}")
                    continue

                # Use normalized display name (e.g. SLH-DSA-128 instead of SPHINCS+-SHA2-128s-simple)
                display = entry.get("display_name") or entry.get("scheme", "?")
                verdict = entry.get("verdict", "?")

                if verdict == "QUANTUM-RESISTANT":
                    st.success(f"**{display}** — {verdict}")
                elif verdict == "QUANTUM-VULNERABLE":
                    st.error(f"**{display}** — {verdict}")
                else:
                    st.warning(f"**{display}** — {verdict}")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    nist = entry.get("nist_level", "?")
                    nist_help = {
                        0: "Not post-quantum secure — vulnerable to Shor's algorithm",
                        1: "Equivalent to AES-128 security (128-bit quantum security)",
                        2: "Equivalent to SHA-256 collision resistance",
                        3: "Equivalent to AES-192 security (192-bit quantum security)",
                        5: "Equivalent to AES-256 security — highest NIST level",
                    }.get(nist, "NIST post-quantum security level (1–5)")
                    st.metric("NIST Level", nist, help=nist_help)
                with col2:
                    st.metric(
                        "Sign Time",
                        f"{entry.get('sign_ms', 0):.2f} ms",
                        help="Average time to sign a DNS response payload. Measured locally over 5 iterations.",
                    )
                with col3:
                    atk = entry.get("quantum_attack_estimate_years", 0)
                    if atk >= 1e10:
                        label = f"{atk:.0e} yrs"
                    elif atk >= 1:
                        label = f"{atk:.0f} yrs"
                    else:
                        label = f"{atk:.4f} yrs"
                    st.metric(
                        "Est. Quantum Attack",
                        label,
                        help="Estimated time for a cryptographically relevant quantum computer (CRQC) to forge a signature for this scheme. Lattice and hash schemes have no known polynomial quantum speedup.",
                    )
                with col4:
                    basis = entry.get("basis", "?")
                    # Show short label in metric; full text in help tooltip
                    short_basis = basis.split("(")[0].strip() if "(" in basis else basis
                    st.metric("Basis", short_basis, help=basis)

                st.markdown("---")
        else:
            st.error("Failed to run security analysis.")
