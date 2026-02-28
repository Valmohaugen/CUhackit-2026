"""Live metrics and QRNG status endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from src.api.models.schemas import LiveMetrics, QRNGStatus
from src.config.redis_keys import RedisKeys

router = APIRouter()


@router.get("/api/metrics/live", response_model=LiveMetrics)
async def get_live_metrics(request: Request) -> LiveMetrics:
    """Get recent DNS query metrics from Redis."""
    r = request.app.state.redis

    # Recent queries (last 50 for API response)
    raw_queries = await r.lrange(RedisKeys.LIVE_QUERIES, 0, 49)
    queries = []
    for raw in raw_queries:
        try:
            queries.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue

    total = await r.get(RedisKeys.RESOLVER_TOTAL_QUERIES)
    fallback = await r.get(RedisKeys.RESOLVER_FALLBACK_COUNT)

    return LiveMetrics(
        recent_queries=queries,
        total_queries=int(total) if total else 0,
        fallback_count=int(fallback) if fallback else 0,
    )


@router.get("/api/qrng/status", response_model=QRNGStatus)
async def get_qrng_status(request: Request) -> QRNGStatus:
    """Get QRNG pool status from Redis."""
    r = request.app.state.redis

    pool_size = await r.llen(RedisKeys.SEED_POOL)

    return QRNGStatus(
        pool_size=pool_size,
        last_fill=await r.get(RedisKeys.QRNG_LAST_FILL) or "never",
        last_entropy=await r.get(RedisKeys.QRNG_LAST_ENTROPY) or "0.0",
        last_backend=await r.get(RedisKeys.QRNG_LAST_BACKEND) or "none",
        last_qubits=await r.get(RedisKeys.QRNG_LAST_QUBITS) or "0",
    )
