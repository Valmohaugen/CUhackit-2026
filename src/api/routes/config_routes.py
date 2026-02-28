"""Config toggle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.models.schemas import ConfigPayload, ConfigResponse
from src.config.redis_keys import RedisKeys
from src.config.toggles import TOGGLES

router = APIRouter()


@router.get("/api/config", response_model=ConfigResponse)
async def get_config(request: Request) -> ConfigResponse:
    """Read all current toggle values from Redis."""
    r = request.app.state.redis
    values = {}
    for name, toggle in TOGGLES.items():
        val = await r.get(toggle.redis_key)
        values[name] = val if val is not None else toggle.default
    return ConfigResponse(**values)


@router.post("/api/config", response_model=ConfigResponse)
async def set_config(payload: ConfigPayload, request: Request) -> ConfigResponse:
    """Write toggle values to Redis. Only non-None fields are updated."""
    r = request.app.state.redis
    updates = payload.model_dump(exclude_none=True)

    for name, value in updates.items():
        toggle = TOGGLES.get(name)
        if toggle is None:
            continue
        if value not in toggle.options:
            continue
        await r.set(toggle.redis_key, value)

    # Return current state
    return await get_config(request)
