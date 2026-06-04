"""Quantitative research data from 50+ academic papers (2020-2026).

Centralized constants sourced from RESEARCH_DATA.md. Import from here
rather than hardcoding numbers in display or logic modules.

References:
  [1] Demir, Bilgin & Onbasli (2025). "Performance Analysis and Industry
      Deployment of PQC Algorithms." arXiv:2503.12952.
  [2] Root et al. (2025). "Gate-Based and Boson Sampling QRNG on IBM and
      Xanadu Devices." arXiv:2507.03823.
  [3] Strydom & Tame (2021). "Random number generation using IBM quantum
      processors." SAIP2021 Proceedings, pp. 630-635.
  [4] Li et al. (2021). "QRNG using a cloud superconducting quantum computer
      based on source-independent protocol." Sci. Rep. 11:23873.
  [5] Bruynsteen et al. (2023). "100-Gbit/s Integrated QRNG Based on Vacuum
      Fluctuations." PRX Quantum 4:010330.
  [6] IDC/EfficientIP (2023). "Global DNS Threat Report."
  [7] Cloudflare (2024-2025). DDoS Threat Reports Q1 2024-Q4 2025.
  [8] Goertzen, Thomassen & Wisiol (2024). "Field Experiments on Post-Quantum
      DNSSEC." RWC 2025/RIPE 89/DNS-OARC 43.
  [9] CRYSTALS-Kyber Round 3 Specification. pq-crystals.org.
  [10] Weibel (2025). "ML-KEM post-quantum TLS now supported in AWS KMS."
       AWS Security Blog, April 7.
  [11] IETF draft-ietf-tls-ecdhe-mlkem (Kwiatkowski et al., Feb 2026).
  [12] Martinez et al. (2018). "Advanced Statistical Testing of QRNGs."
       Entropy 20(11):886.
  [13] Hurley-Smith & Hernandez-Castro (2020). "Quantum Leap and Crash."
       ACM TOPS 23(3).
  [14] Rawat & Jhanwar (2024). "Post-Quantum DNSSEC with Faster TCP
       Fallbacks." INDOCRYPT 2024, LNCS 15496.
  [15] Muller et al. (2020). "Retrofitting PQC in Internet Protocols."
       ACM SIGCOMM CCR 50(4):49-57.
  [16] Schutijser et al. (2025). "Evaluating PQC in DNSSEC Signing for
       TLD Operators." TMA 2025, IEEE/IFIP.
"""

from __future__ import annotations

# =========================================================================
# ML-DSA (Dilithium) — Timing Benchmarks
# Source: Demir et al. 2025 [1], AVX2 @ 3.3 GHz
# =========================================================================
MLDSA44_KEYGEN_MS = 0.026
MLDSA44_SIGN_MS = 0.077
MLDSA44_VERIFY_MS = 0.028

MLDSA65_KEYGEN_MS = 0.045
MLDSA65_SIGN_MS = 0.120
MLDSA65_VERIFY_MS = 0.045

MLDSA87_KEYGEN_MS = 0.070
MLDSA87_SIGN_MS = 0.144
MLDSA87_VERIFY_MS = 0.071

# CPU cycle counts — pq-crystals.org, Skylake AVX2
MLDSA65_SIGN_CYCLES = 529_106
MLDSA65_VERIFY_CYCLES = 179_424

# =========================================================================
# Falcon-512 / FN-DSA-512
# Source: pq-crystals.org, falcon-sign.info
# =========================================================================
FALCON512_KEYGEN_MS = 5.7  # 19.87M cycles — NTRU basis computation
FALCON512_SIGN_MS = 0.111  # 387K cycles
FALCON512_VERIFY_MS = 0.024  # 82K cycles

# =========================================================================
# RSA-2048 (classical baseline) — OpenSSL benchmarks
# =========================================================================
RSA2048_SIGN_MS = 0.991
RSA2048_VERIFY_MS = 0.045

# =========================================================================
# ECDSA-P256 (classical baseline)
# =========================================================================
ECDSAP256_SIGN_MS = 0.049
ECDSAP256_VERIFY_MS = 0.152

# =========================================================================
# ML-KEM-768 (CRYSTALS-Kyber) — pq-crystals.org, Haswell 3.5 GHz AVX2
# =========================================================================
MLKEM768_KEYGEN_US = 15.1
MLKEM768_ENCAPS_US = 19.3
MLKEM768_DECAPS_US = 15.2

# =========================================================================
# DNSSEC Signing Throughput — Muller et al. 2020 [15]
# Intel Xeon Silver 4110 @ 2.10 GHz, single-core, liboqs
# =========================================================================
DNSSEC_VERIFY_PER_SEC = {
    "RSA-2048": 49_367,
    "Falcon-512": 20_228,
    "ECDSA-P256": 13_078,
}
DNSSEC_SIGN_PER_SEC = {
    "RSA-2048": 1_485,
    "Falcon-512": 3_307,
    "ECDSA-P256": 40_509,
}

# =========================================================================
# Lattice Security Estimates (core-SVP)
# Source: CRYSTALS-Kyber Round 3 Specification [9]
# Sieving: 2^(0.292*beta) classical, 2^(0.265*beta) quantum
# =========================================================================
LATTICE_SECURITY: dict[str, dict] = {
    "ML-KEM-512": {
        "bkz_beta": 385,
        "classical_bits": 118,
        "quantum_bits": 107,
        "nist_level": 1,
    },
    "ML-KEM-768": {
        "bkz_beta": 612,
        "classical_bits": 182,
        "quantum_bits": 165,
        "nist_level": 3,
    },
    "ML-KEM-1024": {
        "bkz_beta": 861,
        "classical_bits": 256,
        "quantum_bits": 232,
        "nist_level": 5,
    },
    "ML-DSA-44": {
        "bkz_beta": 423,
        "classical_bits": 123,
        "quantum_bits": 112,
        "nist_level": 2,
    },
    "ML-DSA-65": {
        "bkz_beta": 624,
        "classical_bits": 182,
        "quantum_bits": 165,
        "nist_level": 3,
    },
    "ML-DSA-87": {
        "bkz_beta": 863,
        "classical_bits": 252,
        "quantum_bits": 230,
        "nist_level": 5,
    },
}

# =========================================================================
# Hybrid X25519+ML-KEM-768 Overhead
# Source: AWS Security Blog [10]; IETF draft-ietf-tls-ecdhe-mlkem [11]
# =========================================================================
HYBRID_OVERHEAD_WITH_REUSE_PCT = 0.05  # 0.05% throughput loss
HYBRID_OVERHEAD_NO_REUSE_PCT = 2.3
HYBRID_EXTRA_BYTES = 2336  # ~2,336 bytes vs 64 for X25519 alone
HYBRID_BANDWIDTH_MULTIPLIER = 36  # ~36x increase in key exchange payload

# =========================================================================
# PQ Adoption — Cloudflare "State of the Post-Quantum Internet" Oct 2025
# =========================================================================
PQ_HTTPS_ADOPTION_PCT = 50  # >50% of human-initiated HTTPS traffic
PQ_ADOPTION_SOURCE = "Cloudflare, Oct 2025"

# =========================================================================
# IBM QRNG Entropy Characterization
# Sources: Root et al. 2025 [2]; Strydom & Tame 2021 [3]; Li et al. 2021 [4]
# =========================================================================
IBM_QRNG_THROUGHPUT_KBPS = 90.6  # Root et al. — Sherbrooke 127-qubit Eagle r3
IBM_QRNG_COST_PER_MBIT = 17.67  # USD per million unbiased bits ($96/min rate)
IBM_QRNG_VN_EFFICIENCY_PCT = 24.96  # Von Neumann extraction efficiency

IBM_MELBOURNE_RAW_BIAS_P0 = 0.5262  # Strydom & Tame — 15 qubits
IBM_MELBOURNE_RAW_HMIN = 0.927  # bits/bit
IBM_MODERN_ESTIMATED_HMIN = 0.990  # bits/bit for Eagle/Heron processors
IBM_NIST_TESTS_PASSED = "15/15"  # Strydom & Tame, after VN debiasing

IBM_LIMA_SI_EXTRACTION_RATE = 0.7589  # Li et al. — certified bits per raw bit
IBM_LIMA_ERROR_RATE = 0.039318  # X-basis bit error rate

# =========================================================================
# Photonic QRNG Throughput Records
# Source: Bruynsteen et al. 2023 [5]
# =========================================================================
PHOTONIC_QRNG_RECORD_GBPS = 100
PHOTONIC_QRNG_SOURCE = "Bruynsteen et al., PRX Quantum 4:010330, 2023"

# Commercial: IDQuantique IDQ20MC1
IDQ_QUANTUM_ENTROPY_MBPS = 19.64
IDQ_RNG_OUTPUT_MBPS = 4.90

# =========================================================================
# DNS Threat Statistics
# Source: IDC/EfficientIP 2023 [6]; Cloudflare 2024-2025 [7]
# =========================================================================
DNS_ORGS_ATTACKED_PCT = 90  # 90% of organizations
DNS_ATTACKS_PER_ORG_PER_YEAR = 7.5
DNS_AVG_COST_PER_ATTACK = 1_100_000  # $1.1 million
DNS_FINANCIAL_COST_PER_ATTACK = 1_200_000  # $1.2 million (financial sector)
DNS_HIJACKING_PCT = 47  # 47% reported DNS hijacking

# DDoS growth — Cloudflare DDoS Threat Reports
DNS_DDOS_YOY_GROWTH_2024_PCT = 80
DNS_DDOS_SHARE_OF_NETWORK_ATTACKS_PCT = 54
DDOS_ATTACKS_2024_TOTAL_MILLIONS = 21.3
DDOS_RECORD_ATTACK_TBPS = 5.6

# =========================================================================
# PQ-DNSSEC Field Measurements
# Source: Goertzen et al. 2024 [8]; Rawat & Jhanwar 2023-2024 [14]
# =========================================================================
PQ_DNSSEC_FALCON512_UDP_DELIVERY_PCT = 90
PQ_DNSSEC_DILITHIUM_UDP_DELIVERY_PCT = 50
PQ_DNSSEC_TCP_FALLBACK_LATENCY_MS = 83  # ±1 ms, Rawat & Jhanwar

# Zone signing — Schutijser et al. 2025 [16], .nl zone (10M+ RRsets)
FALCON512_ZONE_SIGNING_SLOWDOWN_AVX2 = 2.1  # x slower than ECDSA-P256

# =========================================================================
# PQ-DNSSEC UDP Payload Limit
# DNS Flag Day 2020
# =========================================================================
DNS_UDP_PAYLOAD_LIMIT_BYTES = 1232

# =========================================================================
# Competing PQ-DNS Approaches
# =========================================================================
COMPETING_APPROACHES: dict[str, str] = {
    "TurboDNS": (
        "Eliminates TCP fallback; PQ-DNSSEC as fast as classical "
        "(Rawat & Jhanwar, INDOCRYPT 2024)"
    ),
    "OQS-BIND9": (
        "Fork of BIND 9.19.17 with liboqs; Falcon-512, ML-DSA-44, SPHINCS+ "
        "(github.com/desec-io/OQS-bind)"
    ),
    "CoreDNS-PQC": (
        "dnssec_pqc plugin, 18 algorithms across 5 families, 15-50ms signing, "
        "3-4 MB overhead (arXiv:2507.09301, July 2025)"
    ),
    "MTL-DNSSEC": (
        "Verisign Merkle Tree Ladder; half the zone-signing time of ECDSA "
        "(IETF PLANTS WG)"
    ),
    "SL-DNSSEC": (
        "Signatureless DNSSEC via KEM+HMAC; 50-60% faster resolution "
        "(ePrint 2024/1319)"
    ),
}

# =========================================================================
# QRNG vs PRNG — Key Insight
# Sources: Martinez et al. 2018 [12]; Hurley-Smith & Hernandez-Castro 2020 [13]
# =========================================================================
QRNG_PRNG_INSIGHT = (
    "Commercial QRNGs often fail TestU01 suites (Alphabit, Rabbit) even when "
    "passing NIST SP 800-22 and Dieharder. Well-designed CSPRNGs (ChaCha20, "
    "AES-CTR-DRBG) pass all known statistical tests. The value of QRNG is "
    "information-theoretic security (unpredictability guaranteed by physics), "
    "not superior statistical properties."
)

# =========================================================================
# Citation Shorthand — for inline use in display strings
# =========================================================================
CITE_DEMIR_2025 = "Demir, Bilgin & Onbasli, arXiv:2503.12952, 2025"
CITE_ROOT_2025 = "Root et al., arXiv:2507.03823, 2025"
CITE_STRYDOM_2021 = "Strydom & Tame, SAIP2021, pp. 630-635"
CITE_LI_2021 = "Li et al., Sci. Rep. 11:23873, 2021"
CITE_BRUYNSTEEN_2023 = "Bruynsteen et al., PRX Quantum 4:010330, 2023"
CITE_IDC_2023 = "IDC/EfficientIP, 2023 Global DNS Threat Report"
CITE_CLOUDFLARE_2025 = "Cloudflare, State of the Post-Quantum Internet, Oct 2025"
CITE_AWS_2025 = "Weibel, AWS Security Blog, April 2025"
CITE_GOERTZEN_2024 = "Goertzen, Thomassen & Wisiol, RWC 2025/RIPE 89, 2024"
CITE_KYBER_R3 = "CRYSTALS-Kyber Round 3 Specification"
CITE_RAWAT_2024 = "Rawat & Jhanwar, INDOCRYPT 2024, LNCS 15496"
CITE_MARTINEZ_2018 = "Martinez et al., Entropy 20(11):886, 2018"
CITE_HURLEY_SMITH_2020 = "Hurley-Smith & Hernandez-Castro, ACM TOPS 23(3), 2020"
