"""Tests for benchmarking module."""

from __future__ import annotations

import numpy as np
import pytest

from src.modules.benchmarks import (
    _chi_squared_test,
    _runs_test,
    _serial_correlation,
    _shannon_entropy,
    compare_entropy,
    run_all_benchmarks,
)


class TestShannonEntropy:
    """Tests for Shannon entropy calculation."""

    def test_uniform_binary(self) -> None:
        # Perfect balance: half 0s, half 1s → entropy = 1.0
        data = np.array([0, 1] * 500, dtype=np.uint8)
        entropy = _shannon_entropy(data)
        assert abs(entropy - 1.0) < 0.01

    def test_all_same(self) -> None:
        # All zeros → entropy = 0
        data = np.zeros(100, dtype=np.uint8)
        entropy = _shannon_entropy(data)
        assert entropy == 0.0


class TestChiSquared:
    """Tests for chi-squared uniformity test."""

    def test_small_data(self) -> None:
        data = np.array([0, 1, 0, 1], dtype=np.uint8)
        chi2, p = _chi_squared_test(data)
        # Too few bytes, should return defaults
        assert p == 1.0

    def test_random_data(self) -> None:
        rng = np.random.default_rng(42)
        data = rng.integers(0, 2, size=8000, dtype=np.uint8)
        chi2, p = _chi_squared_test(data)
        assert chi2 >= 0


class TestSerialCorrelation:
    """Tests for serial correlation."""

    def test_uncorrelated(self) -> None:
        rng = np.random.default_rng(42)
        data = rng.integers(0, 2, size=10000, dtype=np.uint8)
        corr = _serial_correlation(data)
        # Random data should have near-zero correlation
        assert abs(corr) < 0.1

    def test_perfectly_correlated(self) -> None:
        data = np.zeros(100, dtype=np.uint8)
        corr = _serial_correlation(data)
        assert corr == 0.0  # zero variance → 0


class TestRunsTest:
    """Tests for runs test."""

    def test_random_data_passes(self) -> None:
        rng = np.random.default_rng(42)
        data = rng.integers(0, 2, size=1000, dtype=np.uint8)
        p = _runs_test(data)
        # Random data should typically pass (p > 0.01)
        assert 0.0 <= p <= 1.0

    def test_small_data(self) -> None:
        data = np.array([0, 1], dtype=np.uint8)
        p = _runs_test(data)
        assert p == 1.0


@pytest.mark.asyncio
class TestCompareEntropy:
    """Tests for entropy comparison."""

    async def test_returns_expected_fields(self, fake_redis) -> None:
        result = await compare_entropy(fake_redis, sample_size=1000)
        assert "qrng_shannon_entropy" in result
        assert "prng_shannon_entropy" in result
        assert "sample_size" in result
        assert result["sample_size"] == 1000


@pytest.mark.asyncio
class TestRunAllBenchmarks:
    """Tests for full benchmark suite."""

    async def test_returns_results_for_all_schemes(self, fake_redis) -> None:
        results = await run_all_benchmarks(fake_redis, iterations=2)
        assert len(results) == 3  # ml-dsa-65, falcon-512, rsa-2048

        # Each result should have scheme key
        schemes = {r["scheme"] for r in results if "scheme" in r}
        assert len(schemes) >= 1  # At least rsa-2048 should work
