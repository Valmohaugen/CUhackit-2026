"""Async Redis connection pool factory.

Provides:
  - get_redis: Create or retrieve async Redis connection
  - init_defaults: Initialize Redis with default toggle values
  - check_health: Verify Redis connectivity
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from src.config.defaults import DEFAULTS
from src.config.settings import settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the async Redis connection."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        logger.info("[redis] Connected to %s:%s", settings.redis_host, settings.redis_port)
    return _pool


async def init_defaults(r: aioredis.Redis) -> None:
    """Initialize Redis with default toggle values if not already set."""
    for key, value in DEFAULTS.items():
        existing = await r.get(key)
        if existing is None:
            await r.set(key, value)
            logger.info("[redis] Set default %s = %s", key, value)


async def check_health(r: aioredis.Redis) -> bool:
    """Check Redis connectivity with PING."""
    try:
        return await r.ping()
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("[redis] Connection closed")
