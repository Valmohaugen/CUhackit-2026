"""Shared test fixtures for Quantum DNS Shield.

Provides:
  - fakeredis async client
  - Mock signer for PQ crypto
  - FastAPI test client
"""

from __future__ import annotations

from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio

from src.config.defaults import DEFAULTS
from src.config.redis_keys import RedisKeys


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fake_redis():
    """Async fakeredis client with defaults initialized."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    # Seed defaults
    for key, value in DEFAULTS.items():
        await r.set(key, value)

    yield r
    await r.flushall()
    await r.aclose()


# ---------------------------------------------------------------------------
# Mock Signer
# ---------------------------------------------------------------------------

class MockSigner:
    """Deterministic signer for tests (no liboqs dependency)."""

    def __init__(self, name: str = "mock-signer") -> None:
        self._name = name

    @property
    def scheme_name(self) -> str:
        return self._name

    @property
    def public_key(self) -> bytes:
        return b"\x01" * 32

    @property
    def secret_key(self) -> bytes:
        return b"\x02" * 32

    def sign(self, message: bytes) -> bytes:
        import hashlib
        return hashlib.sha256(message + self.secret_key).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        import hashlib
        expected = hashlib.sha256(message + self.secret_key).digest()
        return signature == expected


@pytest.fixture
def mock_signer():
    """A deterministic mock signer."""
    return MockSigner()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(fake_redis):
    """Create a FastAPI test app with fake Redis."""
    from fastapi import FastAPI
    from src.api.routes.health import router as health_router
    from src.api.routes.config_routes import router as config_router
    from src.api.routes.migration import router as migration_router

    app = FastAPI()
    app.state.redis = fake_redis

    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(migration_router)

    return app
