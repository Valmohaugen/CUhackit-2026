"""Tests for DNS resolver module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.modules.dns_resolver import ResolveResult, clear_signer_cache, resolve


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear signer cache before each test."""
    clear_signer_cache()
    yield
    clear_signer_cache()


@pytest.mark.asyncio
class TestResolve:
    """Tests for the resolve function."""

    @patch("src.modules.dns_resolver.dns.asyncresolver.Resolver")
    async def test_resolve_returns_result(self, mock_resolver_cls, fake_redis) -> None:
        # Mock DNS response
        mock_answer = AsyncMock()
        mock_rdata = type("MockRdata", (), {"address": "93.184.216.34"})()
        mock_answer.__aiter__ = lambda self: iter([mock_rdata])
        mock_answer.__iter__ = lambda self: iter([mock_rdata])

        mock_instance = mock_resolver_cls.return_value
        mock_instance.resolve = AsyncMock(return_value=[mock_rdata])

        result = await resolve(
            domain="example.com",
            r=fake_redis,
            scheme="rsa-2048",
            use_qrng=False,
        )

        assert isinstance(result, ResolveResult)
        assert result.domain == "example.com"
        assert result.verified is True
        assert result.seed_source == "prng"
        assert result.latency_ms >= 0

    @patch("src.modules.dns_resolver.dns.asyncresolver.Resolver")
    async def test_resolve_with_qrng_seed(self, mock_resolver_cls, fake_redis) -> None:
        from src.modules.seed_pool import push_seeds

        # Add seeds to pool
        await push_seeds(fake_redis, [b"\xcc" * 32])

        mock_rdata = type("MockRdata", (), {"address": "1.2.3.4"})()
        mock_instance = mock_resolver_cls.return_value
        mock_instance.resolve = AsyncMock(return_value=[mock_rdata])

        result = await resolve(
            domain="test.com",
            r=fake_redis,
            scheme="rsa-2048",
            use_qrng=True,
        )

        assert result.seed_source == "qrng"


class TestResolveResult:
    """Tests for ResolveResult dataclass."""

    def test_to_dict(self) -> None:
        result = ResolveResult(
            domain="example.com",
            ip_addresses=["1.2.3.4"],
            signature="abcdef",
            scheme="test-scheme",
            verified=True,
            seed_source="qrng",
            latency_ms=5.0,
            timestamp="2026-02-27T00:00:00Z",
        )
        d = result.to_dict()
        assert d["domain"] == "example.com"
        assert d["ip_addresses"] == ["1.2.3.4"]
        assert d["verified"] is True
