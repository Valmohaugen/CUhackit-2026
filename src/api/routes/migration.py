"""Migration matrix endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.config.redis_keys import RedisKeys
from src.modules.migration_matrix import (
    get_all_recommendations,
    get_migration_matrix,
    get_recommendation,
)

router = APIRouter()


@router.get("/api/migration")
async def get_migration(request: Request) -> dict:
    """Get migration matrix and recommendations for current scenario."""
    r = request.app.state.redis
    scenario = await r.get(RedisKeys.CONFIG_SCENARIO) or "enterprise"

    return {
        "matrix": get_migration_matrix(),
        "recommendation": get_recommendation(scenario),
        "all_recommendations": get_all_recommendations(),
    }
