"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.models.schemas import HealthResponse
from src.redis_client import check_health

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Health check — verifies Redis connectivity."""
    r = request.app.state.redis
    redis_ok = await check_health(r)
    return HealthResponse(
        status="ok" if redis_ok else "degraded",
        redis=redis_ok,
    )
