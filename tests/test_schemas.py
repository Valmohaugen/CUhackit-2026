"""Tests for Pydantic request/response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.models.schemas import (
    BenchmarkEntry,
    ConfigPayload,
    ConfigResponse,
    HealthResponse,
    LiveMetrics,
    QRNGStatus,
    ResolveRequest,
    ResolveResponse,
    ShorsRequest,
    ShorsStatusResponse,
)


class TestConfigSchemas:
    """Tests for config request/response models."""

    def test_config_payload_partial(self) -> None:
        payload = ConfigPayload(source="qrng")
        assert payload.source == "qrng"
        assert payload.scheme is None

    def test_config_payload_full(self) -> None:
        payload = ConfigPayload(
            source="prng",
            backend="aer",
            scheme="falcon-512",
            phase="hybrid",
            scenario="web",
            extractor="toeplitz",
            qrng_method="multi_run",
        )
        assert payload.backend == "aer"

    def test_config_response(self) -> None:
        resp = ConfigResponse(
            source="qrng",
            backend="aer",
            scheme="ml-dsa-65",
            phase="hybrid",
            scenario="enterprise",
            extractor="von_neumann",
            qrng_method="multi_run",
        )
        assert resp.scheme == "ml-dsa-65"


class TestResolveSchemas:
    """Tests for resolve request/response models."""

    def test_resolve_request(self) -> None:
        req = ResolveRequest(domain="example.com")
        assert req.domain == "example.com"

    def test_resolve_request_requires_domain(self) -> None:
        with pytest.raises(ValidationError):
            ResolveRequest()

    def test_resolve_response(self) -> None:
        resp = ResolveResponse(
            domain="example.com",
            ip_addresses=["1.2.3.4"],
            signature="abcdef",
            scheme="ML-DSA-65",
            verified=True,
            seed_source="qrng",
            latency_ms=5.0,
            timestamp="2026-02-27T00:00:00Z",
        )
        assert resp.verified is True
        assert len(resp.ip_addresses) == 1


class TestShorsSchemas:
    """Tests for Shor's algorithm schemas."""

    def test_shors_request_default(self) -> None:
        req = ShorsRequest()
        assert req.n == 15

    def test_shors_request_custom(self) -> None:
        req = ShorsRequest(n=21)
        assert req.n == 21

    def test_shors_request_too_small(self) -> None:
        with pytest.raises(ValidationError):
            ShorsRequest(n=2)

    def test_shors_status(self) -> None:
        resp = ShorsStatusResponse(status="running", result=None)
        assert resp.status == "running"


class TestBenchmarkEntry:
    """Tests for benchmark entry model."""

    def test_with_error(self) -> None:
        entry = BenchmarkEntry(scheme="test", error="liboqs not installed")
        assert entry.error is not None
        assert entry.keygen_ms is None

    def test_with_results(self) -> None:
        entry = BenchmarkEntry(
            scheme="ML-DSA-65",
            keygen_ms=1.5,
            sign_ms=0.8,
            verify_ms=0.3,
            public_key_bytes=1952,
            secret_key_bytes=4000,
            signature_bytes=3293,
        )
        assert entry.keygen_ms == 1.5


class TestLiveMetrics:
    """Tests for live metrics model."""

    def test_creation(self) -> None:
        metrics = LiveMetrics(
            recent_queries=[{"domain": "test.com"}],
            total_queries=100,
            fallback_count=5,
        )
        assert metrics.total_queries == 100
        assert len(metrics.recent_queries) == 1


class TestHealthResponse:
    """Tests for health response model."""

    def test_creation(self) -> None:
        resp = HealthResponse(status="ok", redis=True)
        assert resp.status == "ok"
        assert resp.version == "1.0.0"
