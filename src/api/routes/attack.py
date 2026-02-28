"""Shor's algorithm attack demo endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Request

from src.api.models.schemas import ShorsRequest, ShorsStatusResponse
from src.config.redis_keys import RedisKeys
from src.modules.attack_theater import run_shors

router = APIRouter()


@router.post("/api/attack/shors")
async def start_shors(
    body: ShorsRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict:
    """Launch Shor's algorithm demo as a background task."""
    r = request.app.state.redis

    # Check if already running
    status = await r.get(RedisKeys.ATTACK_SHORS_STATUS)
    if status == "running":
        return {"status": "already_running"}

    await r.set(RedisKeys.ATTACK_SHORS_STATUS, "running")
    background_tasks.add_task(run_shors, body.n, r)

    return {"status": "started", "n": body.n}


@router.get("/api/attack/shors", response_model=ShorsStatusResponse)
async def get_shors_status(request: Request) -> ShorsStatusResponse:
    """Get the status and result of the Shor's demo."""
    r = request.app.state.redis

    status = await r.get(RedisKeys.ATTACK_SHORS_STATUS) or "idle"
    result = None

    if status == "done":
        raw = await r.get(RedisKeys.ATTACK_SHORS_RESULT)
        if raw:
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    return ShorsStatusResponse(status=status, result=result)
