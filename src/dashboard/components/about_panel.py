"""About panel: Project overview, lattice-based crypto education, QRNG explainer,
architecture, FAQ, and the migration matrix (compact).

Written for a general/business audience — minimal jargon, visual analogies.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.utils import get_migration


def render_about_panel() -> None:
    """Render the About section with educational sub-tabs."""
    st.header("About Quantum DNS Shield")

    tab_overview, tab_lattice, tab_qrng, tab_arch, tab_faq, tab_migration = st.tabs([
        "Overview",
        "Lattice Crypto",
        "QRNG",
        "Architecture",
        "FAQ",
        "Migration Matrix",
    ])

    with tab_overview:
        _render_overview()
    with tab_lattice:
        _render_lattice()
    with tab_qrng:
        _render_qrng()
    with tab_arch:
        _render_architecture()
    with tab_faq:
        _render_faq()
    with tab_migration:
        _render_migration_compact()


# ---------------------------------------------------------------------------
# Sub-tab renderers
# ---------------------------------------------------------------------------


def _render_overview() -> None:
    st.subheader("Why Post-Quantum DNS?")
    st.markdown("""
Today's internet relies on **RSA** and **ECC** to secure DNS, TLS, and digital signatures.
These algorithms are efficient and well-tested — but they share a fatal flaw: they can be
broken by a sufficiently powerful **quantum computer** running **Shor's algorithm**.

#### The HNDL Threat
Adversaries are already performing **Harvest-Now, Decrypt-Later (HNDL)** attacks — recording
encrypted traffic today with the expectation of decrypting it once quantum computers mature.
Data with long secrecy requirements (medical records, classified intelligence, financial data)
is at risk **right now**.

#### What This Project Demonstrates
- **Real DNS resolution** with post-quantum signatures (ML-DSA-65, Falcon-512, SLH-DSA-128)
- **Quantum random number generation** via Qiskit quantum circuits
- **Shor's algorithm** running on a quantum simulator to factor integers
- **Side-by-side benchmarks** comparing PQ vs classical performance
- **Live metrics** and latency breakdowns for every query

#### NIST Post-Quantum Standards (2024)
NIST finalized three post-quantum standards:
| Standard | Type | Based On |
|----------|------|----------|
| ML-KEM (FIPS 203) | Key Encapsulation | Module-LWE lattice |
| ML-DSA (FIPS 204) | Digital Signature | Module-LWE lattice |
| SLH-DSA (FIPS 205) | Digital Signature | Hash functions |

This project implements **ML-DSA-65** and **Falcon-512** (lattice-based) plus
**SLH-DSA-128** (hash-based) for DNS response signing.
""")


def _render_lattice() -> None:
    st.subheader("Lattice-Based Cryptography")
    st.markdown("""
#### What Is a Lattice?
Imagine an infinite grid of evenly-spaced dots in 2D space (like graph paper). A **lattice**
is the mathematical generalization of this to many dimensions. In 2D, it's easy to find the
closest dot to any point. But in **hundreds of dimensions**, finding the closest lattice point
becomes extraordinarily hard — even for quantum computers.

#### The LWE Problem
**Learning With Errors (LWE)** is the mathematical foundation of ML-DSA and ML-KEM:

1. Start with a secret vector **s** (the private key)
2. Publish **A * s + e** where **A** is a random matrix and **e** is small random noise
3. The challenge: recover **s** from the noisy product

This is equivalent to finding the closest lattice point in a high-dimensional space with added
noise. No known quantum algorithm can solve this efficiently.

#### Why Lattices Resist Quantum Attacks
- **Shor's algorithm** exploits the *periodic structure* of modular exponentiation — lattices
  have no such structure
- **Grover's algorithm** only provides a quadratic speedup for brute-force search — not enough
  to break lattice problems at standard security levels
- The **Shortest Vector Problem (SVP)** and **Closest Vector Problem (CVP)** remain hard even
  with quantum computers

#### Schemes in This Project

| Scheme | Type | Basis | NIST Level | Key Size | Signature Size |
|--------|------|-------|-----------|----------|----------------|
| ML-DSA-65 | Lattice | Module-LWE | 3 | 1,952 B | 3,309 B |
| Falcon-512 | Lattice | NTRU | 1 | 897 B | 666 B |
| SLH-DSA-128 | Hash-based | SPHINCS+ | 1 | 32 B | 7,856 B |
| RSA-2048 | Classical | Factoring | 0 (PQ) | 256 B | 256 B |

**ML-DSA-65** offers the best balance of security level vs performance.
**Falcon-512** has the smallest signatures but requires careful floating-point handling.
**SLH-DSA-128** makes no lattice assumptions — purely hash-based, conservative choice.
""")


def _render_qrng() -> None:
    st.subheader("Quantum Random Number Generation")
    st.markdown("""
#### Classical vs Quantum Randomness
Classical random number generators (PRNGs) are **deterministic** — given the same seed, they
produce the same output. They are "pseudorandom": statistically random but fundamentally
predictable if the internal state is known.

**Quantum randomness** is fundamentally different. When a qubit in superposition is measured,
the outcome is **truly unpredictable** — not because we lack information, but because the
universe hasn't decided yet.

#### How Our QRNG Works

```
1. Initialize qubits to |0⟩
2. Apply Hadamard gate (H): |0⟩ → (|0⟩ + |1⟩) / sqrt(2)
3. Measure: 50% chance of 0, 50% chance of 1
4. Repeat with many qubits and shots
5. Apply entropy extraction (Von Neumann / Toeplitz / FFT)
6. Store 32-byte seeds in Redis pool
```

The **Hadamard gate** puts each qubit into an equal superposition of 0 and 1.
Measurement collapses this superposition — the outcome is governed by quantum mechanics,
not any deterministic algorithm.

#### Entropy Extraction
Raw quantum measurements may have slight biases (hardware imperfections). We apply
**post-processing** to distill high-quality randomness:

- **Von Neumann**: Pairs of bits → discard (0,0) and (1,1), map (0,1)→0 and (1,0)→1
- **Toeplitz**: Multiply bit vector by a random Toeplitz matrix for universal hashing
- **FFT-Toeplitz**: Fast Fourier Transform acceleration of Toeplitz extraction
- **Parity**: XOR groups of bits together for simple bias removal

#### Why It Matters for Keys
Cryptographic keys must be generated from **high-entropy** sources. If an attacker can predict
the random seed used to generate a signing key, they can reconstruct the key. QRNG provides
an additional layer of assurance that the entropy source is fundamentally unpredictable.
""")


def _render_architecture() -> None:
    st.subheader("System Architecture")
    st.markdown("""
```
┌─────────────────────────────────────────────────┐
│                   AWS Cloud                      │
│                                                  │
│  ┌──────────┐    ┌──────────────────────────┐   │
│  │   ALB    │───→│  ECS Fargate (2 tasks)   │   │
│  │ (HTTPS)  │    │  ┌────────┐ ┌──────────┐ │   │
│  └──────────┘    │  │FastAPI │ │Streamlit │ │   │
│                  │  │ :8000  │ │  :8501   │ │   │
│                  │  └───┬────┘ └────┬─────┘ │   │
│                  └──────┼───────────┼───────┘   │
│                         │           │            │
│                  ┌──────┴───────────┘            │
│                  ▼                                │
│           ┌────────────┐   ┌──────────────────┐  │
│           │ ElastiCache│   │ Lambda (QRNG)    │  │
│           │   Redis    │◄──│ Every 5 min      │  │
│           └────────────┘   │ Qiskit AerSim    │  │
│                            └──────────────────┘  │
│                                                  │
│  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ S3 Bucket  │  │ Secrets  │  │ CloudWatch  │  │
│  │ (audit)    │  │ Manager  │  │ (monitoring)│  │
│  └────────────┘  └──────────┘  └─────────────┘  │
└─────────────────────────────────────────────────┘
```

#### Component Roles
- **FastAPI** (port 8000): REST API for DNS resolution, benchmarks, attacks, metrics
- **Streamlit** (port 8501): Interactive dashboard calling the FastAPI backend
- **Redis**: Ephemeral state — seed pool, config toggles, live metrics, query history
- **Lambda**: Scheduled QRNG seed generation every 5 minutes using Qiskit
- **S3**: Audit logs of QRNG generation batches
- **Secrets Manager**: IBM Quantum token and Redis auth credentials
- **ALB**: Routes `/api/*` to FastAPI, everything else to Streamlit

#### Why This Architecture?
- **Single container** for FastAPI + Streamlit simplifies deployment
- **Lambda for QRNG** keeps the seed pool filled without blocking the main app
- **Redis** enables real-time dashboard updates and sub-millisecond seed retrieval
- **CDK** (Infrastructure as Code) makes the entire stack reproducible
""")


def _render_faq() -> None:
    st.subheader("Frequently Asked Questions")

    faqs = [
        (
            "Is this actually quantum-secure?",
            "Yes — ML-DSA-65, Falcon-512, and SLH-DSA-128 are all NIST-standardized "
            "post-quantum algorithms. They are designed to resist attacks from both "
            "classical and quantum computers. RSA-2048 is included only as a "
            "classical baseline for comparison."
        ),
        (
            "Does this use a real quantum computer?",
            "By default, it uses Qiskit's AerSimulator (a classical simulation of "
            "quantum circuits). The architecture supports connecting to IBM Quantum "
            "hardware via the IBM Quantum token, but the simulator produces "
            "statistically equivalent random numbers for this use case."
        ),
        (
            "Why is the QRNG pool sometimes empty?",
            "The Lambda function fills the pool every 5 minutes. If you've just "
            "deployed, run the local seed fill script: `python scripts/local_seed_fill.py`. "
            "When the pool is empty, the system falls back to os.urandom (PRNG)."
        ),
        (
            "What is the performance overhead of PQ crypto?",
            "ML-DSA-65 signing is typically 0.5-2ms — comparable to RSA-2048. "
            "Key and signature sizes are larger (3KB signatures vs 256B for RSA), "
            "but DNS responses are small enough that this is negligible."
        ),
        (
            "Can Shor's algorithm really break RSA?",
            "Yes, given a quantum computer with ~4,000 error-corrected logical qubits. "
            "Current quantum computers have ~1,000 noisy physical qubits. Most estimates "
            "place the threat at 2030-2040, but the HNDL risk exists today."
        ),
        (
            "What is crypto-agility?",
            "The ability to quickly swap cryptographic algorithms without redesigning "
            "your system. This project demonstrates crypto-agility via the sidebar "
            "toggle — switch between ML-DSA, Falcon, SLH-DSA, and RSA in real time."
        ),
    ]

    for q, a in faqs:
        with st.expander(q):
            st.markdown(a)


def _render_migration_compact() -> None:
    """Compact migration matrix (moved from standalone tab)."""
    st.subheader("Post-Quantum Migration Matrix")
    st.markdown(
        "Migration roadmap by deployment scenario. Shows cost, risk, "
        "and timeline for each phase."
    )

    data = get_migration()
    if not data:
        st.info("Migration data unavailable.")
        return

    matrix = data.get("matrix", [])
    if matrix:
        import pandas as pd
        df = pd.DataFrame(matrix)
        display_cols = [
            "scenario", "phase", "scheme", "latency_overhead_pct",
            "risk_level", "timeline_months",
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
