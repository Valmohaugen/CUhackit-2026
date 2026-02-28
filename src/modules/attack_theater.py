"""Shor's algorithm demo and quantum-threat analysis module.

Provides:
  - run_shors: Execute Shor's algorithm on a quantum simulator to factor N
  - seed_recovery_analysis: Statistical quality tests on random seeds
  - hndl_analysis: Harvest-Now-Decrypt-Later threat timeline assessment
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import Counter
from fractions import Fraction
from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from scipy import stats as scipy_stats

from src.config.redis_keys import RedisKeys

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

_SHORS_DEFAULT_N = 15
_SHORS_DEFAULT_A = 7
_SHORS_SHOTS = 1024
_COUNTING_QUBITS = 8  # precision qubits for phase estimation


# =============================================================================
# Shor's Algorithm — Circuit Construction
# =============================================================================


def _c_amod15(a: int, power: int) -> QuantumCircuit:
    """Build a controlled unitary gate for a^(2^power) mod 15.

    Args:
        a: Base for modular exponentiation. Must be coprime to 15.
        power: The exponent k in a^(2^k) mod 15.

    Returns:
        A QuantumCircuit implementing controlled-U^(2^power) as a gate.
    """
    # 4 work qubits encode the value mod 15
    qc = QuantumCircuit(4, name=f"{a}^{2**power} mod 15")

    # Pre-compute the effective exponent: a^(2^power) mod 15
    exp = pow(a, 2**power, 15)

    # Hard-coded permutation unitaries for each residue mod 15
    # These are the minimal-gate decompositions for multiplication by exp mod 15
    if exp == 2:
        qc.swap(0, 1)
        qc.swap(1, 2)
        qc.swap(2, 3)
    elif exp == 4:
        qc.swap(0, 2)
        qc.swap(1, 3)
    elif exp == 7:
        qc.swap(2, 3)
        qc.swap(1, 2)
        qc.swap(0, 1)
        qc.x(0)
        qc.x(1)
        qc.x(2)
        qc.x(3)
    elif exp == 8:
        qc.swap(0, 3)
        qc.swap(1, 2)
    elif exp == 11:
        qc.swap(0, 1)
        qc.swap(1, 2)
        qc.swap(2, 3)
        qc.x(0)
        qc.x(1)
        qc.x(2)
        qc.x(3)
    elif exp == 13:
        qc.swap(0, 1)
        qc.swap(2, 3)
        qc.x(0)
        qc.x(1)
        qc.x(2)
        qc.x(3)
    elif exp == 1:
        pass  # identity
    else:
        raise ValueError(f"Unsupported residue {exp} for a={a} mod 15")

    gate = qc.to_gate()
    c_gate = gate.control(1)
    return c_gate


def _build_shors_circuit(n: int, a: int, n_count: int) -> QuantumCircuit:
    """Build the full Shor's algorithm circuit for factoring n.

    Uses quantum phase estimation to find the order of a mod n.
    Currently supports n=15 with known-good bases.

    Args:
        n: The integer to factor (must be 15 for this demo).
        a: The base for order finding (must be coprime to n).
        n_count: Number of counting (precision) qubits for QPE.

    Returns:
        A complete QuantumCircuit ready for execution.
    """
    # n_count counting qubits + 4 work qubits for mod-15 register
    qc = QuantumCircuit(n_count + 4, n_count)

    # -------------------------------------------------------------------------
    # Initialize work register to |1> (the identity element for multiplication)
    # -------------------------------------------------------------------------
    qc.x(n_count)  # qubit index n_count is the LSB of the work register

    # -------------------------------------------------------------------------
    # Put counting qubits into superposition
    # -------------------------------------------------------------------------
    for q in range(n_count):
        qc.h(q)

    # -------------------------------------------------------------------------
    # Controlled modular exponentiation: controlled-U^(2^j) for each counting
    # qubit j, where U implements multiplication by a mod n
    # -------------------------------------------------------------------------
    for q in range(n_count):
        c_gate = _c_amod15(a, q)
        # Control on counting qubit q, target on work register qubits
        qc.append(c_gate, [q] + list(range(n_count, n_count + 4)))

    # -------------------------------------------------------------------------
    # Inverse QFT on counting register
    # -------------------------------------------------------------------------
    _apply_iqft(qc, n_count)

    # -------------------------------------------------------------------------
    # Measure counting qubits
    # -------------------------------------------------------------------------
    qc.measure(range(n_count), range(n_count))

    return qc


def _apply_iqft(qc: QuantumCircuit, n: int) -> None:
    """Apply the inverse Quantum Fourier Transform in-place on the first n qubits.

    Args:
        qc: The quantum circuit to modify.
        n: Number of qubits for the inverse QFT.
    """
    # Swap qubits to reverse order (part of the QFT convention)
    for i in range(n // 2):
        qc.swap(i, n - i - 1)

    # Apply inverse QFT gates
    for target in range(n):
        # Controlled phase rotations from higher qubits
        for ctrl in range(target):
            angle = -math.pi / (2 ** (target - ctrl))
            qc.cp(angle, ctrl, target)
        # Hadamard on target qubit
        qc.h(target)


# =============================================================================
# Shor's Algorithm — Classical Post-Processing
# =============================================================================


def _extract_order(counts: dict[str, int], n_count: int, n: int, a: int) -> int | None:
    """Extract the order r from measurement results using continued fractions.

    Args:
        counts: Measurement outcome counts from the quantum circuit.
        n_count: Number of counting qubits used.
        n: The number being factored.
        a: The base used for order finding.

    Returns:
        The order r if found, or None if extraction fails.
    """
    measured_phases: list[tuple[int, int]] = []
    for bitstring, count in counts.items():
        decimal_value = int(bitstring, 2)
        measured_phases.append((decimal_value, count))

    # Sort by count descending to try the most frequent results first
    measured_phases.sort(key=lambda x: x[1], reverse=True)

    for phase_int, _ in measured_phases:
        if phase_int == 0:
            continue  # skip the trivial phase

        # Convert measurement to a phase fraction: phase_int / 2^n_count
        phase = phase_int / (2**n_count)

        # Use continued fractions to find s/r approximation
        frac = Fraction(phase).limit_denominator(n)
        r = frac.denominator

        # Validate the candidate order
        if r > 0 and pow(a, r, n) == 1:
            return r

    return None


def _compute_factors(n: int, a: int, r: int) -> list[int] | None:
    """Compute factors of n from the order r using gcd.

    Args:
        n: The number to factor.
        a: The base used in order finding.
        r: The order of a modulo n.

    Returns:
        A sorted list of non-trivial factors, or None if the order is
        not useful (odd r or trivial factors).
    """
    if r % 2 != 0:
        logger.warning("[SHORS] Order r=%d is odd, cannot extract factors", r)
        return None

    guess_plus = math.gcd(pow(a, r // 2) + 1, n)
    guess_minus = math.gcd(pow(a, r // 2) - 1, n)

    factors: set[int] = set()
    for g in (guess_plus, guess_minus):
        if 1 < g < n:
            factors.add(g)
            factors.add(n // g)

    if factors:
        return sorted(factors)
    return None


# =============================================================================
# Shor's Algorithm — Public Entry Point
# =============================================================================


async def run_shors(n: int, redis_client: Any) -> dict:
    """Run Shor's algorithm to factor n on a quantum simulator.

    Builds a quantum phase estimation circuit for order-finding, executes
    it on the Qiskit AerSimulator, and performs classical post-processing
    with continued fractions to recover factors of n.

    For the demo the canonical target is N=15, which factors into 3 and 5.

    Args:
        n: The integer to factor (currently supports 15).
        redis_client: An async Redis client instance (redis.asyncio.Redis).

    Returns:
        A dict containing factored (bool), factors (list), n (int),
        qubits_used (int), shots (int), time_seconds (float), and
        circuit_depth (int).
    """
    logger.info("[SHORS] Starting Shor's algorithm for N=%d", n)
    await redis_client.set(RedisKeys.ATTACK_SHORS_STATUS, "running")

    t_start = time.perf_counter()

    # Choose base a coprime to n
    a = _SHORS_DEFAULT_A
    if math.gcd(a, n) != 1:
        # Lucky case: gcd itself is a non-trivial factor
        factor = math.gcd(a, n)
        result = {
            "factored": True,
            "factors": sorted([factor, n // factor]),
            "n": n,
            "qubits_used": 0,
            "shots": 0,
            "time_seconds": round(time.perf_counter() - t_start, 4),
            "circuit_depth": 0,
        }
        await _store_result(redis_client, result, status="complete")
        return result

    # -------------------------------------------------------------------------
    # Build circuit
    # -------------------------------------------------------------------------
    n_count = _COUNTING_QUBITS
    circuit = _build_shors_circuit(n, a, n_count)
    qubits_used = circuit.num_qubits
    logger.info(
        "[SHORS] Circuit built: %d qubits, depth %d (pre-transpile)",
        qubits_used,
        circuit.depth(),
    )

    # -------------------------------------------------------------------------
    # Execute on simulator
    # -------------------------------------------------------------------------
    backend = AerSimulator()
    transpiled = transpile(circuit, backend)
    circuit_depth = transpiled.depth()

    logger.info(
        "[SHORS] Transpiled circuit depth: %d, running %d shots",
        circuit_depth,
        _SHORS_SHOTS,
    )

    job_result = backend.run(transpiled, shots=_SHORS_SHOTS).result()
    counts = job_result.get_counts()

    # -------------------------------------------------------------------------
    # Classical post-processing
    # -------------------------------------------------------------------------
    order = _extract_order(counts, n_count, n, a)
    factors: list[int] | None = None
    if order is not None:
        logger.info("[SHORS] Found order r=%d for a=%d mod %d", order, a, n)
        factors = _compute_factors(n, a, order)

    t_elapsed = round(time.perf_counter() - t_start, 4)
    factored = factors is not None and len(factors) >= 2

    result: dict = {
        "factored": factored,
        "factors": factors if factored else [],
        "n": n,
        "qubits_used": qubits_used,
        "shots": _SHORS_SHOTS,
        "time_seconds": t_elapsed,
        "circuit_depth": circuit_depth,
    }

    status = "complete" if factored else "failed"
    await _store_result(redis_client, result, status=status)

    if factored:
        logger.info("[SHORS] Successfully factored %d = %s in %.4fs", n, factors, t_elapsed)
    else:
        logger.warning("[SHORS] Failed to factor %d after %.4fs", n, t_elapsed)

    return result


async def _store_result(redis_client: Any, result: dict, status: str) -> None:
    """Persist Shor's result and status to Redis.

    Args:
        redis_client: Async Redis client.
        result: The result dictionary to store as JSON.
        status: Status string (running / complete / failed).
    """
    await redis_client.set(RedisKeys.ATTACK_SHORS_RESULT, json.dumps(result))
    await redis_client.set(RedisKeys.ATTACK_SHORS_STATUS, status)
    logger.info("[SHORS] Stored result in Redis, status=%s", status)


# =============================================================================
# Seed Recovery Analysis — Statistical Tests
# =============================================================================


def seed_recovery_analysis(seed_bytes: bytes) -> dict:
    """Run statistical quality tests on a random seed.

    Performs four NIST-inspired tests to evaluate the randomness quality
    of the provided seed bytes:
      1. Bit balance — proportion of 1-bits vs expected 0.5
      2. Runs test — number of uninterrupted sequences of identical bits
      3. Chi-squared — goodness-of-fit for byte value distribution
      4. Autocorrelation — lag-1 correlation in the bit sequence

    Args:
        seed_bytes: The raw seed bytes to analyze.

    Returns:
        A dict with keys for each test containing the test statistic,
        p-value (where applicable), and a pass/fail verdict.
    """
    logger.info("[SEED_ANALYSIS] Analyzing seed of %d bytes", len(seed_bytes))

    if len(seed_bytes) == 0:
        return {
            "error": "Empty seed provided",
            "bit_balance": None,
            "runs_test": None,
            "chi_squared": None,
            "autocorrelation": None,
        }

    # Convert to bit array
    bits = np.unpackbits(np.frombuffer(seed_bytes, dtype=np.uint8))
    n_bits = len(bits)

    # -------------------------------------------------------------------------
    # 1. Bit Balance (Monobit / Frequency Test)
    # -------------------------------------------------------------------------
    ones_count = int(np.sum(bits))
    proportion = ones_count / n_bits
    # Z-statistic for proportion test against 0.5
    z_stat = (ones_count - n_bits / 2) / math.sqrt(n_bits / 4)
    p_balance = 2 * (1 - scipy_stats.norm.cdf(abs(z_stat)))

    bit_balance = {
        "ones": ones_count,
        "zeros": n_bits - ones_count,
        "total_bits": n_bits,
        "proportion": round(proportion, 6),
        "z_statistic": round(z_stat, 6),
        "p_value": round(p_balance, 6),
        "pass": p_balance >= 0.01,
    }

    # -------------------------------------------------------------------------
    # 2. Runs Test (Wald-Wolfowitz)
    # -------------------------------------------------------------------------
    runs = 1
    for i in range(1, n_bits):
        if bits[i] != bits[i - 1]:
            runs += 1

    pi = proportion
    # Expected runs and variance under randomness hypothesis
    expected_runs = 1 + 2 * n_bits * pi * (1 - pi)
    variance_runs = (2 * n_bits * pi * (1 - pi) * (2 * n_bits * pi * (1 - pi) - 1)) / (
        n_bits - 1
    ) if n_bits > 1 else 1.0

    z_runs = (runs - expected_runs) / math.sqrt(max(variance_runs, 1e-10))
    p_runs = 2 * (1 - scipy_stats.norm.cdf(abs(z_runs)))

    runs_test = {
        "observed_runs": runs,
        "expected_runs": round(expected_runs, 2),
        "z_statistic": round(z_runs, 6),
        "p_value": round(p_runs, 6),
        "pass": p_runs >= 0.01,
    }

    # -------------------------------------------------------------------------
    # 3. Chi-Squared (Byte Distribution)
    # -------------------------------------------------------------------------
    byte_values = list(seed_bytes)
    byte_counts = Counter(byte_values)
    observed = np.array([byte_counts.get(i, 0) for i in range(256)], dtype=float)
    expected_freq = len(seed_bytes) / 256.0

    chi2_stat = float(np.sum((observed - expected_freq) ** 2 / expected_freq))
    p_chi2 = 1.0 - float(scipy_stats.chi2.cdf(chi2_stat, df=255))

    chi_squared = {
        "chi2_statistic": round(chi2_stat, 4),
        "degrees_of_freedom": 255,
        "p_value": round(p_chi2, 6),
        "pass": p_chi2 >= 0.01,
        "unique_bytes": len(byte_counts),
    }

    # -------------------------------------------------------------------------
    # 4. Autocorrelation (Lag-1)
    # -------------------------------------------------------------------------
    bits_float = bits.astype(float)
    mean_bits = float(np.mean(bits_float))
    # Center the sequence
    centered = bits_float - mean_bits
    variance = float(np.sum(centered**2))
    if variance > 0 and n_bits > 1:
        autocorr = float(np.sum(centered[:-1] * centered[1:])) / variance
    else:
        autocorr = 0.0

    # Under the null hypothesis, lag-1 autocorrelation is approximately
    # N(0, 1/n) for large n
    z_autocorr = autocorr * math.sqrt(n_bits)
    p_autocorr = 2 * (1 - scipy_stats.norm.cdf(abs(z_autocorr)))

    autocorrelation = {
        "lag1_correlation": round(autocorr, 6),
        "z_statistic": round(z_autocorr, 6),
        "p_value": round(p_autocorr, 6),
        "pass": p_autocorr >= 0.01,
    }

    # -------------------------------------------------------------------------
    # Aggregate
    # -------------------------------------------------------------------------
    all_pass = all([
        bit_balance["pass"],
        runs_test["pass"],
        chi_squared["pass"],
        autocorrelation["pass"],
    ])

    result = {
        "seed_length_bytes": len(seed_bytes),
        "total_bits": n_bits,
        "overall_pass": all_pass,
        "bit_balance": bit_balance,
        "runs_test": runs_test,
        "chi_squared": chi_squared,
        "autocorrelation": autocorrelation,
    }

    logger.info(
        "[SEED_ANALYSIS] Analysis complete: overall_pass=%s, tests=%d/4",
        all_pass,
        sum([bit_balance["pass"], runs_test["pass"], chi_squared["pass"], autocorrelation["pass"]]),
    )

    return result


# =============================================================================
# Harvest-Now-Decrypt-Later (HNDL) Timeline Analysis
# =============================================================================


def hndl_analysis() -> dict:
    """Assess the Harvest-Now-Decrypt-Later quantum threat timeline.

    Computes urgency scores and estimated time horizons for various
    cryptographic primitives under the assumption that a cryptographically
    relevant quantum computer (CRQC) will become available within the
    projected timeline.

    Returns:
        A dict containing per-algorithm threat assessments, data shelf-life
        estimates, migration urgency score, and recommendations.
    """
    logger.info("[HNDL] Running Harvest-Now-Decrypt-Later timeline analysis")

    # -------------------------------------------------------------------------
    # Threat timeline estimates (years from now until quantum break)
    # Based on current research projections and NIST guidance
    # -------------------------------------------------------------------------
    current_year = 2026

    threat_timeline: dict[str, dict[str, Any]] = {
        "RSA-2048": {
            "algorithm_type": "asymmetric",
            "estimated_break_year": 2035,
            "years_until_threat": 2035 - current_year,
            "qubits_required": 4098,
            "quantum_algorithm": "Shor's algorithm",
            "status": "vulnerable",
            "migration_target": "ML-KEM-768 / ML-DSA-65",
        },
        "ECC-256": {
            "algorithm_type": "asymmetric",
            "estimated_break_year": 2033,
            "years_until_threat": 2033 - current_year,
            "qubits_required": 2330,
            "quantum_algorithm": "Shor's (ECDLP variant)",
            "status": "vulnerable",
            "migration_target": "ML-KEM-768 / ML-DSA-65",
        },
        "AES-128": {
            "algorithm_type": "symmetric",
            "estimated_break_year": 2050,
            "years_until_threat": 2050 - current_year,
            "qubits_required": 2953,
            "quantum_algorithm": "Grover's algorithm (quadratic speedup)",
            "status": "weakened",
            "migration_target": "AES-256",
        },
        "AES-256": {
            "algorithm_type": "symmetric",
            "estimated_break_year": 2080,
            "years_until_threat": 2080 - current_year,
            "qubits_required": 6681,
            "quantum_algorithm": "Grover's algorithm (quadratic speedup)",
            "status": "safe",
            "migration_target": "No migration needed",
        },
    }

    # -------------------------------------------------------------------------
    # Data shelf-life categories — how long captured data remains valuable
    # -------------------------------------------------------------------------
    data_shelf_life: dict[str, dict[str, Any]] = {
        "financial_transactions": {
            "shelf_life_years": 7,
            "classification": "medium",
            "at_risk": True,
            "reasoning": "Tax and audit records must be retained 7 years; "
                         "intercepted TLS sessions could expose account data.",
        },
        "medical_records": {
            "shelf_life_years": 50,
            "classification": "critical",
            "at_risk": True,
            "reasoning": "HIPAA requires long-term retention; patient data "
                         "remains sensitive for a lifetime.",
        },
        "government_classified": {
            "shelf_life_years": 75,
            "classification": "critical",
            "at_risk": True,
            "reasoning": "State secrets can remain classified for decades; "
                         "adversaries have strong incentives to stockpile.",
        },
        "personal_communications": {
            "shelf_life_years": 10,
            "classification": "medium",
            "at_risk": True,
            "reasoning": "Private messages and emails may contain sensitive "
                         "personal or professional information.",
        },
        "ephemeral_web_traffic": {
            "shelf_life_years": 1,
            "classification": "low",
            "at_risk": False,
            "reasoning": "Short-lived session data with minimal long-term value.",
        },
    }

    # -------------------------------------------------------------------------
    # Urgency score computation
    # Urgency = max(0, data_shelf_life - years_until_threat) / data_shelf_life
    # Higher score means the data will still be valuable when quantum arrives
    # -------------------------------------------------------------------------
    min_asymmetric_break = min(
        v["years_until_threat"]
        for v in threat_timeline.values()
        if v["algorithm_type"] == "asymmetric"
    )

    urgency_scores: dict[str, float] = {}
    for category, info in data_shelf_life.items():
        overlap = info["shelf_life_years"] - min_asymmetric_break
        if overlap > 0:
            score = min(1.0, overlap / info["shelf_life_years"])
        else:
            score = 0.0
        urgency_scores[category] = round(score, 3)

    overall_urgency = round(
        sum(urgency_scores.values()) / len(urgency_scores), 3
    )

    # -------------------------------------------------------------------------
    # Recommendations
    # -------------------------------------------------------------------------
    recommendations = [
        "Begin hybrid (classical + PQC) TLS deployment immediately.",
        "Prioritize migration of long-lived data protection keys (RSA/ECC).",
        "Adopt NIST post-quantum standards: ML-KEM-768 for key exchange, "
        "ML-DSA-65 for digital signatures.",
        "Upgrade symmetric ciphers from AES-128 to AES-256 where possible.",
        "Inventory all cryptographic assets and classify by data shelf life.",
        "Implement crypto-agility to enable rapid algorithm swaps.",
        "Monitor NIST and ETSI timelines for updated threat estimates.",
    ]

    result: dict[str, Any] = {
        "analysis_date": f"{current_year}-01-01",
        "threat_timeline": threat_timeline,
        "data_shelf_life": data_shelf_life,
        "urgency_scores": urgency_scores,
        "overall_urgency_score": overall_urgency,
        "min_years_until_asymmetric_break": min_asymmetric_break,
        "recommendations": recommendations,
    }

    logger.info(
        "[HNDL] Analysis complete: overall_urgency=%.3f, "
        "earliest asymmetric threat in %d years",
        overall_urgency,
        min_asymmetric_break,
    )

    return result
