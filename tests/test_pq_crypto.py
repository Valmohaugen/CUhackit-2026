"""Tests for post-quantum cryptography module."""

from __future__ import annotations

from src.modules.pq_crypto import (
    BenchmarkResult,
    ClassicalFallback,
    RSASigner,
    create_signer,
)


class TestClassicalFallback:
    """Tests for HMAC-SHA256 fallback signer."""

    def test_sign_and_verify(self) -> None:
        signer = ClassicalFallback()
        msg = b"test message"
        sig = signer.sign(msg)

        assert len(sig) == 32  # SHA-256 digest
        assert signer.verify(msg, sig) is True

    def test_wrong_message_fails(self) -> None:
        signer = ClassicalFallback()
        sig = signer.sign(b"correct message")
        assert signer.verify(b"wrong message", sig) is False

    def test_scheme_name(self) -> None:
        signer = ClassicalFallback()
        assert "fallback" in signer.scheme_name.lower()

    def test_keys_are_bytes(self) -> None:
        signer = ClassicalFallback()
        assert isinstance(signer.public_key, bytes)
        assert isinstance(signer.secret_key, bytes)
        assert len(signer.public_key) == 32


class TestRSASigner:
    """Tests for RSA-2048 demo signer."""

    def test_sign_and_verify(self) -> None:
        signer = RSASigner()
        msg = b"rsa test"
        sig = signer.sign(msg)

        assert signer.verify(msg, sig) is True

    def test_scheme_name(self) -> None:
        signer = RSASigner()
        assert "RSA" in signer.scheme_name


class TestCreateSigner:
    """Tests for the signer factory."""

    def test_rsa_returns_rsa_signer(self) -> None:
        signer = create_signer("rsa-2048")
        assert isinstance(signer, RSASigner)

    def test_unknown_scheme_returns_fallback(self) -> None:
        signer = create_signer("nonexistent-algo")
        # Should fall back to ClassicalFallback when liboqs not available
        assert signer is not None
        msg = b"hello"
        sig = signer.sign(msg)
        assert signer.verify(msg, sig) is True

    def test_signer_protocol_compliance(self) -> None:
        """Verify all signers implement the required interface."""
        for scheme in ["rsa-2048"]:
            signer = create_signer(scheme)
            assert hasattr(signer, "scheme_name")
            assert hasattr(signer, "public_key")
            assert hasattr(signer, "secret_key")
            assert hasattr(signer, "sign")
            assert hasattr(signer, "verify")


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_creation(self) -> None:
        result = BenchmarkResult(
            scheme="test",
            keygen_ms=1.0,
            sign_ms=0.5,
            verify_ms=0.3,
            public_key_bytes=32,
            secret_key_bytes=64,
            signature_bytes=32,
        )
        assert result.scheme == "test"
        assert result.keygen_ms == 1.0
