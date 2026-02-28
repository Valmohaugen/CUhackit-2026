"""Shor's algorithm demo and quantum-threat analysis module.

Provides:
  - run_shors: Execute Shor's algorithm on a quantum simulator to factor N
  - seed_recovery_analysis: Statistical quality tests on random seeds
  - hndl_analysis: Harvest-Now-Decrypt-Later threat timeline assessment

References:
  [1] Shor, P.W. (1994). "Algorithms for Quantum Computation: Discrete
      Logarithms and Factoring." Proc. 35th Annual Symp. on Foundations of
      Computer Science (FOCS '94), pp. 124-134.
  [2] Gidney, C. & Ekera, M. (2021). "How to Factor 2048-Bit RSA Integers
      in 8 Hours Using 20 Million Noisy Qubits." Quantum 5:433.
  [3] Mosca, M. & Piani, M. (2024). "Quantum Threat Timeline Report."
      Global Risk Institute.
  [4] ETSI White Paper No. 8 (2015). "Quantum Safe Cryptography and
      Security." European Telecommunications Standards Institute.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections import Counter
from fractions import Fraction
from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import UnitaryGate
from qiskit_aer import AerSimulator
from scipy import stats as scipy_stats

from src.config.redis_keys import RedisKeys

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

_COUNTING_QUBITS = 8  # precision qubits for phase estimation

# Known semiprime factorizations for fallback when quantum circuit doesn't converge
_KNOWN_FACTORS: dict[int, list[int]] = {
    15: [3, 5],
    21: [3, 7],
    33: [3, 11],
    35: [5, 7],
    55: [5, 11],
    77: [7, 11],
    91: [7, 13],
}


def _get_shors_shots(n: int) -> int:
    """Scale shot count based on the number being factored.

    Larger numbers need more measurement shots for the quantum phase
    estimation to converge on the correct period.
    """
    if n < 16:
        return 2048
    elif n <= 25:
        return 4096
    elif n <= 50:
        return 8192
    else:
        return 16384


def _find_coprime_bases(n: int, max_bases: int = 5) -> list[int]:
    """Find suitable coprime bases for Shor's algorithm.

    Args:
        n: The number to factor.
        max_bases: Maximum number of bases to return.

    Returns:
        List of integers coprime to n, suitable as bases for order-finding.
    """
    bases = []
    for a in range(2, min(n, 30)):
        if math.gcd(a, n) == 1:
            bases.append(a)
        if len(bases) >= max_bases:
            break
    return bases


def _n_work_qubits(n: int) -> int:
    """Compute number of work qubits needed for modular arithmetic on n.

    Returns ceil(log2(n)) — the minimum number of qubits to represent
    values in [0, n-1].
    """
    return max(1, math.ceil(math.log2(n))) if n > 1 else 1


# =============================================================================
# Shor's Algorithm — Circuit Construction (Generalized)
# =============================================================================


def _build_mod_mult_unitary(a: int, n: int, n_work: int) -> np.ndarray:
    """Build the unitary matrix for modular multiplication |x⟩ → |a·x mod n⟩.

    Constructs a permutation matrix that maps each computational basis state
    |x⟩ to |a·x mod n⟩ for x < n, and acts as identity for x >= n.

    Args:
        a: The multiplier (must be coprime to n).
        n: The modulus.
        n_work: Number of qubits in the work register.

    Returns:
        A 2^n_work × 2^n_work unitary (permutation) matrix.
    """
    dim = 2 ** n_work
    U = np.zeros((dim, dim), dtype=complex)
    for x in range(dim):
        if x < n:
            y = (a * x) % n
        else:
            y = x  # identity for out-of-range states
        U[y, x] = 1.0
    return U


def _c_amod_n(a: int, power: int, n: int, n_work: int):
    """Build a controlled unitary gate for a^(2^power) mod n.

    Uses UnitaryGate to construct a generalized modular multiplication
    gate that works for any semiprime n, not just 15.

    Args:
        a: Base for modular exponentiation. Must be coprime to n.
        power: The exponent k in a^(2^k) mod n.
        n: The modulus (the number being factored).
        n_work: Number of work qubits.

    Returns:
        A controlled gate implementing U^(2^power) where U|x⟩ = |a·x mod n⟩.
    """
    exp = pow(a, 2**power, n)
    U = _build_mod_mult_unitary(exp, n, n_work)
    gate = UnitaryGate(U, label=f"{a}^{2**power} mod {n}")
    c_gate = gate.control(1)
    return c_gate


def _build_shors_circuit(n: int, a: int, n_count: int) -> QuantumCircuit:
    """Build the full Shor's algorithm circuit for factoring n.

    Uses quantum phase estimation to find the order of a mod n.
    Supports any semiprime n by using UnitaryGate for the modular
    multiplication operation.

    Args:
        n: The integer to factor.
        a: The base for order finding (must be coprime to n).
        n_count: Number of counting (precision) qubits for QPE.

    Returns:
        A complete QuantumCircuit ready for execution.
    """
    n_work = _n_work_qubits(n)
    qc = QuantumCircuit(n_count + n_work, n_count)

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
        c_gate = _c_amod_n(a, q, n, n_work)
        # Control on counting qubit q, target on work register qubits
        qc.append(c_gate, [q] + list(range(n_count, n_count + n_work)))

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
    # Ref: The inverse QFT reverses the standard QFT defined in Nielsen &
    # Chuang (2010), Ch. 5. The bit-reversal swap and negated rotation angles
    # convert the Fourier basis back to the computational basis.

    # QFT formula: QFT|x⟩ = (1/√N) Σ_{k=0}^{N-1} exp(2πixk/N)|k⟩
    # The inverse QFT negates rotation angles to map Fourier basis → computational basis.

    # Swap qubits to reverse order (bit-reversal step of the QFT convention)
    for i in range(n // 2):
        qc.swap(i, n - i - 1)

    # Apply inverse QFT gates: negative rotation angles undo the forward QFT
    for target in range(n):
        # Controlled phase rotations with angle -pi/2^(target-ctrl)
        for ctrl in range(target):
            angle = -math.pi / (2 ** (target - ctrl))
            qc.cp(angle, ctrl, target)
        # Hadamard projects back onto computational basis
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
    # Ref: Shor [1] -- QPE yields measurement m such that m/2^n_count ≈ s/r
    # for some integer s. The continued fractions algorithm recovers r (the
    # period) from this rational approximation with high probability.

    # Continued fractions: m/2^n_count ≈ s/r where s is an integer.
    # The convergents of this fraction yield candidate periods r.
    # Validation: check a^r ≡ 1 (mod N) to confirm the true period.

    measured_phases: list[tuple[int, int]] = []
    for bitstring, count in counts.items():
        decimal_value = int(bitstring, 2)
        measured_phases.append((decimal_value, count))

    # Sort by count descending to try the most frequent results first
    measured_phases.sort(key=lambda x: x[1], reverse=True)

    for phase_int, _ in measured_phases:
        if phase_int == 0:
            continue  # skip the trivial phase (s=0 gives no period info)

        # Convert measurement to a phase fraction: phase_int / 2^n_count ≈ s/r
        phase = phase_int / (2**n_count)

        # Continued fractions: find the best rational approximation s/r with r <= n.
        # The denominator of this fraction is our candidate period r.
        frac = Fraction(phase).limit_denominator(n)
        r = frac.denominator

        # Validate: r is the true order only if a^r ≡ 1 (mod n)
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


def _run_shors_sync(n: int) -> dict:
    """Synchronous CPU-heavy Shor's computation. Safe to run in a thread pool.

    Separated from run_shors so it can be offloaded via asyncio.to_thread()
    without blocking the async event loop during Qiskit circuit simulation.

    Args:
        n: The integer to factor.

    Returns:
        A dict with factoring results, circuit info, and timing.
    """
    logger.info("[SHORS] Starting Shor's algorithm for N=%d", n)
    t_start = time.perf_counter()

    bases = _find_coprime_bases(n)
    if not bases:
        return {
            "factored": False,
            "factors": [],
            "n": n,
            "qubits_used": 0,
            "shots": 0,
            "time_seconds": round(time.perf_counter() - t_start, 4),
            "circuit_depth": 0,
            "method": "none",
            "bases_tried": [],
            "circuit_text": "",
            "measurement_counts": {},
            "total_unique_outcomes": 0,
            "n_work_qubits": 0,
        }

    n_count = _COUNTING_QUBITS
    n_work = _n_work_qubits(n)
    shots = _get_shors_shots(n)
    backend = AerSimulator()

    best_circuit_text = ""
    best_measurement_counts: dict = {}
    best_total_unique = 0
    best_qubits = 0
    best_depth = 0
    bases_tried = []
    factors: list[int] | None = None

    for a in bases:
        bases_tried.append(a)
        logger.info("[SHORS] Trying base a=%d for N=%d", a, n)

        try:
            circuit = _build_shors_circuit(n, a, n_count)
            qubits_used = circuit.num_qubits
            logger.info(
                "[SHORS] Circuit built: %d qubits (%d counting + %d work), depth %d",
                qubits_used, n_count, n_work, circuit.depth(),
            )

            transpiled = transpile(circuit, backend)
            circuit_depth = transpiled.depth()

            logger.info(
                "[SHORS] Transpiled depth: %d, running %d shots (base a=%d)",
                circuit_depth, shots, a,
            )

            job_result = backend.run(transpiled, shots=shots).result()
            counts = job_result.get_counts()

            if not best_circuit_text:
                try:
                    best_circuit_text = circuit.draw("text").__str__()
                except Exception:
                    best_circuit_text = ""
                sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                best_measurement_counts = {k: v for k, v in sorted_counts[:16]}
                best_total_unique = len(counts)
                best_qubits = qubits_used
                best_depth = circuit_depth

            order = _extract_order(counts, n_count, n, a)
            if order is not None:
                logger.info("[SHORS] Found order r=%d for a=%d mod %d", order, a, n)
                factors = _compute_factors(n, a, order)
                if factors:
                    break
        except Exception as e:
            logger.warning("[SHORS] Error with base a=%d: %s", a, e)
            continue

    t_elapsed = round(time.perf_counter() - t_start, 4)
    factored = factors is not None and len(factors) >= 2

    method = "quantum"
    if not factored and n in _KNOWN_FACTORS:
        logger.warning(
            "[SHORS] Quantum circuit failed to factor %d; using precomputed fallback", n
        )
        factors = _KNOWN_FACTORS[n]
        factored = True
        method = "precomputed"

    result: dict = {
        "factored": factored,
        "factors": factors if factored else [],
        "n": n,
        "qubits_used": best_qubits or (n_count + n_work),
        "shots": shots,
        "time_seconds": t_elapsed,
        "circuit_depth": best_depth,
        "method": method,
        "bases_tried": bases_tried,
        "circuit_text": best_circuit_text,
        "measurement_counts": best_measurement_counts,
        "total_unique_outcomes": best_total_unique,
        "n_work_qubits": n_work,
    }

    if factored:
        logger.info(
            "[SHORS] Successfully factored %d = %s in %.4fs (method=%s, bases=%s)",
            n, factors, t_elapsed, method, bases_tried,
        )
    else:
        logger.warning("[SHORS] Failed to factor %d after %.4fs (bases=%s)", n, t_elapsed, bases_tried)

    return result


async def run_shors(n: int, redis_client: Any) -> dict:
    """Run Shor's algorithm to factor n on a quantum simulator.

    Offloads the CPU-heavy Qiskit circuit simulation to a thread pool via
    asyncio.to_thread() so the async event loop stays unblocked and can
    continue serving API requests and Redis operations while the simulation runs.

    Args:
        n: The integer to factor.
        redis_client: An async Redis client instance (redis.asyncio.Redis).

    Returns:
        A dict containing factored (bool), factors (list), n (int),
        qubits_used (int), shots (int), time_seconds (float), and
        circuit_depth (int).
    """
    logger.info("[SHORS] Launching Shor's algorithm for N=%d (thread pool)", n)
    await redis_client.set(RedisKeys.ATTACK_SHORS_STATUS, "running")

    try:
        result = await asyncio.to_thread(_run_shors_sync, n)
    except Exception as e:
        logger.error("[SHORS] Thread-pool execution failed: %s", e)
        result = {
            "factored": False,
            "factors": [],
            "n": n,
            "qubits_used": 0,
            "shots": 0,
            "time_seconds": 0.0,
            "circuit_depth": 0,
            "method": "error",
            "bases_tried": [],
            "circuit_text": "",
            "measurement_counts": {},
            "total_unique_outcomes": 0,
            "n_work_qubits": 0,
            "error": str(e),
        }

    status = "done" if result.get("factored") else "failed"
    await _store_result(redis_client, result, status=status)
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
        "pass": bool(p_balance >= 0.01),
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
        "pass": bool(p_runs >= 0.01),
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
        "pass": bool(p_chi2 >= 0.01),
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
        "pass": bool(p_autocorr >= 0.01),
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
    # Ref: Mosca & Piani [3] -- HNDL threat model: adversaries record encrypted
    # traffic today and decrypt it once a CRQC becomes available.
    # Ref: ETSI [4] -- "Quantum Safe Cryptography and Security" recommends
    # immediate migration planning for data whose secrecy outlasts the quantum timeline.
    logger.info("[HNDL] Running Harvest-Now-Decrypt-Later timeline analysis")

    # -------------------------------------------------------------------------
    # Threat timeline estimates (years from now until quantum break).
    # Ref: Gidney & Ekera [2] estimate 20M noisy qubits to break RSA-2048;
    # qubit counts below are scaled from that baseline.
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


# =============================================================================
# Security Margin Analysis
# =============================================================================


def security_margin_analysis(sign_ms: float, verify_ms: float, scheme: str) -> dict:
    """Compare real operation timing vs estimated quantum attack time.

    Estimates how long a quantum computer would need to forge a signature
    for the given scheme and compares it to the measured sign/verify time.

    Args:
        sign_ms: Measured signing time in milliseconds.
        verify_ms: Measured verification time in milliseconds.
        scheme: Scheme identifier.

    Returns:
        Dict with security_ratio, nist_level, verdict, and details.
    """
    # Ref: NIST SP 800-208 & FIPS 203/204/205 define security levels 1-5
    # corresponding to the equivalent classical security of AES-128 through
    # AES-256. Levels below 1 indicate quantum-vulnerable schemes.

    # Quantum attack complexity:
    # - Shor's algorithm: O((log N)^3) for factoring → breaks RSA/ECC
    # - Grover's algorithm: O(√N) brute-force → halves symmetric key length
    # - Lattice problems (LWE/SVP): best quantum = O(2^(n/2)) → no polynomial speedup

    # Maps all known scheme name variants (including liboqs internal names) to info.
    # liboqs may return names like "SPHINCS+-SHA2-128s-simple" for what we call SLH-DSA-128.
    _slh_dsa_entry: dict[str, Any] = {
        "nist_level": 1,
        "classical_bits": 128,
        "quantum_attack_years": 1e8,
        "basis": "Hash-based (SPHINCS+)",
        "display_name": "SLH-DSA-128",
    }

    scheme_info: dict[str, dict[str, Any]] = {
        "ML-DSA-65": {
            "nist_level": 3,
            "classical_bits": 192,
            "quantum_attack_years": 1e12,
            "basis": "Module-LWE lattice",
            "display_name": "ML-DSA-65",
        },
        "Dilithium3": {
            "nist_level": 3,
            "classical_bits": 192,
            "quantum_attack_years": 1e12,
            "basis": "Module-LWE lattice",
            "display_name": "ML-DSA-65",
        },
        "ML-DSA-44": {
            "nist_level": 2,
            "classical_bits": 128,
            "quantum_attack_years": 1e8,
            "basis": "Module-LWE lattice",
            "display_name": "ML-DSA-44",
        },
        "Falcon-512": {
            "nist_level": 1,
            "classical_bits": 128,
            "quantum_attack_years": 1e8,
            "basis": "NTRU lattice",
            "display_name": "Falcon-512",
        },
        "Falcon-padded-512": {
            "nist_level": 1,
            "classical_bits": 128,
            "quantum_attack_years": 1e8,
            "basis": "NTRU lattice",
            "display_name": "Falcon-512",
        },
        # SLH-DSA-128 / SPHINCS+ — all liboqs name variants
        "SLH-DSA-128": _slh_dsa_entry,
        "SLH-DSA-SHA2-128s": _slh_dsa_entry,
        "SLH-DSA-SHAKE-128s": _slh_dsa_entry,
        "SPHINCS+-SHA2-128s-simple": _slh_dsa_entry,
        "SPHINCS+-SHAKE-128s-simple": _slh_dsa_entry,
        "SPHINCS+-SHA256-128s-simple": _slh_dsa_entry,
        "slh-dsa-128": _slh_dsa_entry,
        "RSA-2048": {
            "nist_level": 0,
            "classical_bits": 112,
            "quantum_attack_years": 0.001,  # Shor's: near-instant with CRQC
            "basis": "Integer factoring (Shor-vulnerable)",
            "display_name": "RSA-2048",
        },
        "HMAC-SHA256": {
            "nist_level": 0,
            "classical_bits": 128,
            "quantum_attack_years": 1e4,  # Grover's: quadratic speedup
            "basis": "Symmetric (Grover speedup only)",
            "display_name": "HMAC-SHA256",
        },
    }

    # Find matching info (exact match first, then case-insensitive, then prefix)
    info = scheme_info.get(scheme) or scheme_info.get(scheme.lower())
    if not info:
        scheme_lower = scheme.lower()
        for key, val in scheme_info.items():
            if key.lower() == scheme_lower:
                info = val
                break
    if not info:
        # Prefix match: e.g. "sphincs+" prefix catches any SPHINCS+ variant
        prefix = scheme.lower().split("-")[0].split("+")[0]
        for key, val in scheme_info.items():
            if key.lower().startswith(prefix) and len(prefix) > 2:
                info = val
                break
    if not info:
        info = {
            "nist_level": 0,
            "classical_bits": 0,
            "quantum_attack_years": 0,
            "basis": "Unknown scheme",
            "display_name": scheme,
        }

    attack_years = info["quantum_attack_years"]
    # Convert sign time to years for ratio calculation
    sign_years = sign_ms / (1000 * 60 * 60 * 24 * 365.25) if sign_ms > 0 else 1e-20
    security_ratio = attack_years / sign_years if sign_years > 0 else float("inf")

    if info["nist_level"] >= 1:
        verdict = "QUANTUM-RESISTANT"
    elif attack_years < 1:
        verdict = "QUANTUM-VULNERABLE"
    else:
        verdict = "WEAKENED"

    return {
        "scheme": scheme,
        "display_name": info.get("display_name", scheme),
        "nist_level": info["nist_level"],
        "classical_security_bits": info["classical_bits"],
        "quantum_attack_estimate_years": attack_years,
        "sign_ms": round(sign_ms, 3),
        "verify_ms": round(verify_ms, 3),
        "security_ratio": round(security_ratio, 2) if security_ratio < 1e15 else "inf",
        "verdict": verdict,
        "basis": info["basis"],
    }
