"""Tests for FastAPI API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.config.toggles import TOGGLES


@pytest.fixture
def api_app(fake_redis):
    """Create a FastAPI app with all routes for testing."""
    from fastapi import FastAPI
    from src.api.routes.health import router as health_router
    from src.api.routes.config_routes import router as config_router
    from src.api.routes.migration import router as migration_router
    from src.api.routes.benchmarks import router as benchmarks_router

    app = FastAPI()
    app.state.redis = fake_redis

    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(migration_router)
    app.include_router(benchmarks_router)

    return app


@pytest_asyncio.fixture
async def client(api_app):
    """Async HTTP test client."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# Need the import at module level for the fixture decorator
import pytest_asyncio


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Tests for GET /api/health."""

    async def test_health_ok(self, client) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["redis"] is True


@pytest.mark.asyncio
class TestConfigEndpoints:
    """Tests for config GET/POST endpoints."""

    async def test_get_config(self, client) -> None:
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        # Verify all toggle keys are present
        for key in TOGGLES:
            assert key in data

    async def test_post_config(self, client) -> None:
        resp = await client.post("/api/config", json={"source": "prng"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "prng"

    async def test_get_config_reflects_changes(self, client) -> None:
        await client.post("/api/config", json={"scheme": "falcon-512"})
        resp = await client.get("/api/config")
        assert resp.json()["scheme"] == "falcon-512"


@pytest.mark.asyncio
class TestMigrationEndpoint:
    """Tests for GET /api/migration."""

    async def test_migration_returns_data(self, client) -> None:
        resp = await client.get("/api/migration")
        assert resp.status_code == 200
        data = resp.json()
        assert "matrix" in data
        assert "recommendation" in data
        assert len(data["matrix"]) == 15  # 5 scenarios × 3 phases
