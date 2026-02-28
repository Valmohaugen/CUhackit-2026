"""Tests for Lambda QRNG handler."""

from __future__ import annotations

import numpy as np

from src.lambda_handler.handler import (
    _apply_extractor,
    _bits_to_seeds,
    _generate_raw_bits,
    _shannon_entropy,
    _von_neumann_extract,
    _parity_extract,
)


class TestGenerateRawBits:
    """Tests for raw bit generation via AerSimulator."""

    def test_generates_bitstring(self) -> None:
        result = _generate_raw_bits(num_qubits=4, num_shots=10)
        assert isinstance(result, str)
        assert len(result) > 0
        assert all(c in ("0", "1") for c in result)

    def test_output_length(self) -> None:
        result = _generate_raw_bits(num_qubits=4, num_shots=10)
        # Each shot produces num_qubits bits
        assert len(result) == 4 * 10


class TestExtractors:
    """Tests for entropy extraction functions."""

    def test_von_neumann(self) -> None:
        data = np.array([0, 1, 0, 1, 1, 0, 0, 1, 1, 0] * 10, dtype=np.uint8)
        extracted = _von_neumann_extract(data)
        assert isinstance(extracted, np.ndarray)
        assert len(extracted) <= len(data) // 2

    def test_parity(self) -> None:
        data = np.array([0, 1, 0, 1, 1, 0, 0, 1] * 20, dtype=np.uint8)
        extracted = _parity_extract(data)
        assert isinstance(extracted, np.ndarray)
        assert len(extracted) > 0


class TestApplyExtractor:
    """Tests for extractor dispatch."""

    def test_von_neumann_dispatch(self) -> None:
        data = np.array([0, 1, 0, 1, 1, 0] * 20, dtype=np.uint8)
        result = _apply_extractor(data, "von_neumann")
        assert isinstance(result, np.ndarray)

    def test_parity_dispatch(self) -> None:
        data = np.array([0, 1, 0, 1, 1, 0, 0, 1] * 20, dtype=np.uint8)
        result = _apply_extractor(data, "parity")
        assert isinstance(result, np.ndarray)

    def test_unknown_uses_von_neumann(self) -> None:
        data = np.array([0, 1, 0, 1] * 20, dtype=np.uint8)
        result = _apply_extractor(data, "nonexistent")
        expected = _von_neumann_extract(data)
        np.testing.assert_array_equal(result, expected)


class TestShannonEntropy:
    """Tests for Shannon entropy computation."""

    def test_uniform_binary(self) -> None:
        data = np.array([0, 1] * 500, dtype=np.uint8)
        h = _shannon_entropy(data)
        assert abs(h - 1.0) < 0.01

    def test_constant(self) -> None:
        data = np.zeros(100, dtype=np.uint8)
        h = _shannon_entropy(data)
        assert h == 0.0


class TestBitsToSeeds:
    """Tests for bit-to-seed conversion."""

    def test_produces_seeds(self) -> None:
        bits = np.array([0, 1] * 128, dtype=np.uint8)  # 256 bits = 1 seed
        seeds = _bits_to_seeds(bits, seed_bytes=32)
        assert len(seeds) == 1
        assert len(seeds[0]) == 32

    def test_insufficient_bits(self) -> None:
        bits = np.array([0, 1, 0], dtype=np.uint8)
        seeds = _bits_to_seeds(bits, seed_bytes=32)
        assert len(seeds) == 0
