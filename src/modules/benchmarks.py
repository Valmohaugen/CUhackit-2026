"""Module 3: Cryptographic benchmarking and entropy comparison.

Provides:
  - run_all_benchmarks: Time keygen/sign/verify for all PQ schemes
  - compare_entropy: Statistical comparison of QRNG vs PRNG
  - EntropyComparison dataclass with test results

# Ref: NIST SP 800-22 Rev. 1a (2010). "A Statistical Test Suite for Random
#      and Pseudorandom Number Generators for Cryptographic Applications."
#      https://csrc.nist.gov/publications/detail/sp/800-22/rev-1a/final
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

import redis.asyncio as aioredis

from src.config.redis_keys import RedisKeys
from src.modules.pq_crypto import BenchmarkResult, benchmark_scheme

logger = logging.getLogger(__name__)

SCHEMES = ["ml-dsa-65", "falcon-512", "slh-dsa-128", "rsa-2048"]


# ---------------------------------------------------------------------------
# Benchmark suite
# ---------------------------------------------------------------------------

async def run_all_benchmarks(
    r: aioredis.Redis,
    source: str = "qrng",
    iterations: int = 10,
) -> list[dict]:
    """Run keygen/sign/verify benchmarks for all schemes.

    Parameters
    ----------
    r : aioredis.Redis
        Active Redis connection for caching results.
    source : str
        Random source label for cache key.
    iterations : int
        Number of iterations per benchmark.

    Returns
    -------
    list[dict]
        Benchmark results for each scheme.
    """
    results = []
    for scheme in SCHEMES:
        try:
            result = benchmark_scheme(scheme, iterations=iterations)
            result_dict = asdict(result)
            results.append(result_dict)

            # Cache in Redis
            cache_key = RedisKeys.bench_key(source, scheme)
            await r.set(cache_key, json.dumps(result_dict), ex=300)  # 5 min TTL

            logger.info(
                "[benchmarks] %s: keygen=%.1fms sign=%.1fms verify=%.1fms",
                scheme,
                result.keygen_ms,
                result.sign_ms,
                result.verify_ms,
            )
        except Exception as e:
            logger.warning("[benchmarks] Failed to benchmark %s: %s", scheme, e)
            results.append({
                "scheme": scheme,
                "error": str(e),
            })

    return results


# ---------------------------------------------------------------------------
# Entropy comparison
# ---------------------------------------------------------------------------

@dataclass
class EntropyComparison:
    """Statistical comparison between QRNG and PRNG."""

    qrng_shannon_entropy: float
    prng_shannon_entropy: float
    qrng_chi_squared: float
    prng_chi_squared: float
    qrng_chi_squared_p: float
    prng_chi_squared_p: float
    qrng_serial_correlation: float
    prng_serial_correlation: float
    qrng_runs_test_p: float
    prng_runs_test_p: float
    sample_size: int


# Shannon entropy: H(X) = -Σ p_i log₂(p_i), ideal H = 1.0 for unbiased binary source
def _shannon_entropy(data: np.ndarray) -> float:
    """Compute Shannon entropy of binary data."""
    # Measures average information content per bit (NIST SP 800-22, Sec. 5.1).
    # Ideal random source yields H = 1.0 bit; lower values indicate bias.
    _, counts = np.unique(data, return_counts=True)
    probabilities = counts / len(data)
    return float(stats.entropy(probabilities, base=2))


# Chi-squared: χ² = Σ (O_i - E_i)² / E_i, tests byte uniformity (df = 255)
def _chi_squared_test(data: np.ndarray) -> tuple[float, float]:
    """Chi-squared test for uniform distribution of bytes."""
    # Tests whether the observed byte frequency distribution deviates from
    # uniform (NIST SP 800-22, Sec. 5.2). A high p-value indicates the byte
    # distribution is consistent with a truly random source.
    # Group bits into bytes
    n_bytes = len(data) // 8
    if n_bytes < 10:
        return 0.0, 1.0

    byte_values = []
    for i in range(n_bytes):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | int(data[i * 8 + j])
        byte_values.append(byte_val)

    # Count byte frequencies
    observed = np.bincount(byte_values, minlength=256)
    expected = np.full(256, n_bytes / 256)

    chi2, p_value = stats.chisquare(observed, expected)
    return float(chi2), float(p_value)


# Serial correlation: C = Σ(x_i - x̄)(x_{i+1} - x̄) / Σ(x_i - x̄)², ideal C ≈ 0
def _serial_correlation(data: np.ndarray) -> float:
    """Compute serial correlation coefficient."""
    # Measures linear dependency between consecutive values (lag-1
    # autocorrelation). Values near zero indicate no predictable relationship
    # between successive bits; significant deviation suggests structural
    # patterns in the generator output (NIST SP 800-22, Sec. 5.7).
    if len(data) < 2:
        return 0.0
    x = data.astype(float)
    n = len(x)
    mean = np.mean(x)
    var = np.var(x)
    if var == 0:
        return 0.0
    autocorr = np.sum((x[:-1] - mean) * (x[1:] - mean)) / ((n - 1) * var)
    return float(autocorr)


# Runs test: Expected runs = 1 + 2n₀n₁/n, z = (R - E[R]) / √Var(R)
def _runs_test(data: np.ndarray) -> float:
    """Runs test for randomness. Returns p-value."""
    # Counts the number of uninterrupted runs of identical bits and compares
    # to the expected count under true randomness (NIST SP 800-22, Sec. 5.3).
    # Too few runs implies clustering; too many implies oscillation. A p-value
    # below 0.01 rejects the null hypothesis of randomness.
    n = len(data)
    if n < 20:
        return 1.0

    n1 = np.sum(data)
    n0 = n - n1

    # Count runs
    runs = 1
    for i in range(1, n):
        if data[i] != data[i - 1]:
            runs += 1

    # Expected runs and variance
    expected = 1 + (2 * n0 * n1) / n
    if n <= 1:
        return 1.0
    variance = (2 * n0 * n1 * (2 * n0 * n1 - n)) / (n * n * (n - 1))
    if variance <= 0:
        return 1.0

    z = (runs - expected) / np.sqrt(variance)
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    return float(p_value)


async def compare_entropy(
    r: aioredis.Redis,
    sample_size: int = 10000,
) -> dict:
    """Compare QRNG seeds from Redis pool vs PRNG (os.urandom).

    Parameters
    ----------
    r : aioredis.Redis
        Active Redis connection.
    sample_size : int
        Number of bits to compare.

    Returns
    -------
    dict
        EntropyComparison as a dictionary.
    """
    # Get QRNG data from seed pool
    qrng_bits = []
    seeds_needed = (sample_size + 255) // 256  # 32 bytes = 256 bits per seed
    raw_seeds = await r.lrange(RedisKeys.SEED_POOL, 0, seeds_needed - 1)

    for raw in raw_seeds:
        seed_bytes = bytes.fromhex(raw) if isinstance(raw, str) else raw
        for byte in seed_bytes:
            for bit in range(8):
                qrng_bits.append((byte >> bit) & 1)

    # If not enough QRNG data, pad with what we have (or use simulator)
    if len(qrng_bits) < sample_size:
        logger.warning(
            "[benchmarks] Only %d QRNG bits available (wanted %d), padding with PRNG",
            len(qrng_bits),
            sample_size,
        )
        while len(qrng_bits) < sample_size:
            qrng_bits.append(int.from_bytes(os.urandom(1)) & 1)

    qrng_data = np.array(qrng_bits[:sample_size], dtype=np.uint8)

    # Generate PRNG data
    prng_bytes = os.urandom(sample_size // 8 + 1)
    prng_bits = []
    for byte in prng_bytes:
        for bit in range(8):
            prng_bits.append((byte >> bit) & 1)
    prng_data = np.array(prng_bits[:sample_size], dtype=np.uint8)

    # Run statistical tests
    qrng_chi2, qrng_chi2_p = _chi_squared_test(qrng_data)
    prng_chi2, prng_chi2_p = _chi_squared_test(prng_data)

    comparison = EntropyComparison(
        qrng_shannon_entropy=_shannon_entropy(qrng_data),
        prng_shannon_entropy=_shannon_entropy(prng_data),
        qrng_chi_squared=qrng_chi2,
        prng_chi_squared=prng_chi2,
        qrng_chi_squared_p=qrng_chi2_p,
        prng_chi_squared_p=prng_chi2_p,
        qrng_serial_correlation=_serial_correlation(qrng_data),
        prng_serial_correlation=_serial_correlation(prng_data),
        qrng_runs_test_p=_runs_test(qrng_data),
        prng_runs_test_p=_runs_test(prng_data),
        sample_size=sample_size,
    )

    # Cache result
    result_dict = asdict(comparison)
    await r.set(RedisKeys.BENCH_ENTROPY_COMPARISON, json.dumps(result_dict), ex=60)

    logger.info(
        "[benchmarks] Entropy comparison: QRNG H=%.4f, PRNG H=%.4f",
        comparison.qrng_shannon_entropy,
        comparison.prng_shannon_entropy,
    )

    return result_dict
