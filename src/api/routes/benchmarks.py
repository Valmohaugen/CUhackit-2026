"""Benchmark endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.config.redis_keys import RedisKeys
from src.modules.benchmarks import run_all_benchmarks

router = APIRouter()


@router.get("/api/benchmarks")
async def get_benchmarks(request: Request) -> list[dict]:
    """Run or retrieve cached benchmarks for all PQ schemes."""
    r = request.app.state.redis
    source = await r.get(RedisKeys.CONFIG_SOURCE) or "qrng"
    return await run_all_benchmarks(r, source=source)
