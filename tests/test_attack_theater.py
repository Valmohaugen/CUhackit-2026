"""Tests for attack theater module (Shor's algorithm, HNDL analysis)."""

from __future__ import annotations

import pytest

from src.modules.attack_theater import (
    _build_shors_circuit,
    _compute_factors,
    _extract_order,
    hndl_analysis,
    run_shors,
    seed_recovery_analysis,
)


class TestShorsCircuit:
    """Tests for Shor's circuit construction."""

    def test_circuit_built(self) -> None:
        circuit = _build_shors_circuit(n=15, a=7, n_count=8)
        assert circuit.num_qubits == 12  # 8 counting + 4 work
        assert circuit.num_clbits == 8

    def test_circuit_depth_positive(self) -> None:
        circuit = _build_shors_circuit(n=15, a=7, n_count=4)
        assert circuit.depth() > 0


class TestComputeFactors:
    """Tests for classical post-processing."""

    def test_correct_factors_for_15(self) -> None:
        # order of 7 mod 15 is 4
        factors = _compute_factors(n=15, a=7, r=4)
        assert factors is not None
        assert set(factors) == {3, 5}

    def test_odd_order_returns_none(self) -> None:
        factors = _compute_factors(n=15, a=7, r=3)
        assert factors is None


class TestExtractOrder:
    """Tests for order extraction from measurement results."""

    def test_known_phase(self) -> None:
        # For a=7 mod 15, order=4. Phase s/r where r=4.
        # Measurement 64 out of 256 = 0.25 = 1/4
        counts = {"01000000": 500, "10000000": 300, "00000000": 200}
        order = _extract_order(counts, n_count=8, n=15, a=7)
        # Should find order 4 (since 64/256 = 1/4, denominator=4, and 7^4 mod 15 = 1)
        assert order is not None
        assert pow(7, order, 15) == 1


@pytest.mark.asyncio
class TestRunShors:
    """Tests for the full Shor's algorithm execution."""

    async def test_factors_15(self, fake_redis) -> None:
        result = await run_shors(n=15, redis_client=fake_redis)
        assert result["n"] == 15
        assert result["factored"] is True
        assert set(result["factors"]) == {3, 5}
        assert result["qubits_used"] == 12
        assert result["time_seconds"] > 0


class TestSeedRecoveryAnalysis:
    """Tests for statistical seed quality tests."""

    def test_random_seed_passes(self) -> None:
        import os
        seed = os.urandom(256)  # 2048 bits
        result = seed_recovery_analysis(seed)

        assert result["total_bits"] == 2048
        assert "bit_balance" in result
        assert "runs_test" in result
        assert "chi_squared" in result
        assert "autocorrelation" in result

    def test_empty_seed(self) -> None:
        result = seed_recovery_analysis(b"")
        assert result.get("error") is not None

    def test_biased_seed_detected(self) -> None:
        # All zeros — should fail bit balance
        seed = b"\x00" * 256
        result = seed_recovery_analysis(seed)
        assert result["bit_balance"]["pass"] is False


class TestHNDLAnalysis:
    """Tests for HNDL threat timeline."""

    def test_returns_expected_keys(self) -> None:
        result = hndl_analysis()
        assert "threat_timeline" in result
        assert "data_shelf_life" in result
        assert "urgency_scores" in result
        assert "recommendations" in result

    def test_rsa_is_vulnerable(self) -> None:
        result = hndl_analysis()
        assert result["threat_timeline"]["RSA-2048"]["status"] == "vulnerable"

    def test_aes256_is_safe(self) -> None:
        result = hndl_analysis()
        assert result["threat_timeline"]["AES-256"]["status"] == "safe"

    def test_urgency_score_range(self) -> None:
        result = hndl_analysis()
        for score in result["urgency_scores"].values():
            assert 0.0 <= score <= 1.0
