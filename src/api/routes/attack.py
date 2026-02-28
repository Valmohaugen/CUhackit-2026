"""Shor's algorithm attack demo and security analysis endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Request

from src.api.models.schemas import ShorsRequest, ShorsStatusResponse
from src.config.redis_keys import RedisKeys
from src.modules.attack_theater import run_shors, security_margin_analysis
from src.modules.pq_crypto import benchmark_scheme

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
    # Normalize: "complete" → "done" for backwards compat
    if status == "complete":
        status = "done"
    result = None

    if status in ("done", "failed"):
        raw = await r.get(RedisKeys.ATTACK_SHORS_RESULT)
        if raw:
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    return ShorsStatusResponse(status=status, result=result)


# Computes sign/verify latency plus estimated quantum-attack cost for each scheme.
@router.get("/api/attack/security-margin")
async def get_security_margins() -> list[dict]:
    """Run benchmark + security margin analysis for all schemes."""
    from src.modules.benchmarks import SCHEMES

    results = []
    for scheme in SCHEMES:
        try:
            bench = benchmark_scheme(scheme, iterations=5)
            margin = security_margin_analysis(bench.sign_ms, bench.verify_ms, bench.scheme)
            results.append(margin)
        except Exception as e:
            results.append({"scheme": scheme, "error": str(e)})
    return results
