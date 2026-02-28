"""Module 0: QRNG Seed Pool.

Provides:
  - get_seed: Consume a seed from the Redis QRNG pool or fall back to os.urandom
  - get_pool_size: Check current pool depth
  - SeedSource enum for tracking provenance

References
----------
# Ref: Herrero-Collantes & Garcia-Escartin (2017). "Quantum Random Number Generators." Rev. Mod. Phys. 89, 015004.
"""

from __future__ import annotations

import logging
import os
from enum import Enum

import redis.asyncio as aioredis

from src.config.redis_keys import RedisKeys

logger = logging.getLogger(__name__)


class SeedSource(str, Enum):
    """Tracks where a seed came from."""

    QRNG = "qrng"
    PRNG = "prng"


# ---------------------------------------------------------------------------
# Core seed operations
# ---------------------------------------------------------------------------

async def get_seed(r: aioredis.Redis, force_prng: bool = False) -> tuple[bytes, SeedSource]:
    """Consume a 32-byte seed from the QRNG pool, falling back to os.urandom.

    Parameters
    ----------
    r : aioredis.Redis
        Active Redis connection.
    force_prng : bool
        If True, skip the pool and use os.urandom directly.

    Returns
    -------
    tuple[bytes, SeedSource]
        The 32-byte seed and its source.
    """
    if force_prng:
        seed = os.urandom(32)
        await r.incr(RedisKeys.RESOLVER_FALLBACK_COUNT)
        logger.debug("[seed_pool] PRNG fallback (forced)")
        return seed, SeedSource.PRNG

    # Try LPOP from the QRNG pool
    try:
        raw = await r.lpop(RedisKeys.SEED_POOL)
        if raw is not None:
            # Seeds are stored as hex strings
            seed = bytes.fromhex(raw) if isinstance(raw, str) else raw
            logger.debug("[seed_pool] QRNG seed consumed, pool -1")
            return seed, SeedSource.QRNG
    except Exception as e:
        logger.warning("[seed_pool] Redis error during LPOP: %s", e)

    # Fallback to PRNG: os.urandom draws from the OS CSPRNG (/dev/urandom or CryptGenRandom),
    # which is cryptographically secure though not quantum-random (Herrero-Collantes 2017, Sec. II).
    seed = os.urandom(32)
    await _safe_incr(r, RedisKeys.RESOLVER_FALLBACK_COUNT)
    logger.info("[seed_pool] PRNG fallback (pool empty or Redis error)")
    return seed, SeedSource.PRNG


async def get_pool_size(r: aioredis.Redis) -> int:
    """Get the current number of seeds in the pool."""
    try:
        return await r.llen(RedisKeys.SEED_POOL)
    except Exception:
        return 0


async def push_seeds(r: aioredis.Redis, seeds: list[bytes]) -> int:
    """Push seeds to the pool and trim to max size.

    Parameters
    ----------
    r : aioredis.Redis
        Active Redis connection.
    seeds : list[bytes]
        List of 32-byte seeds to push.

    Returns
    -------
    int
        Number of seeds successfully pushed.
    """
    if not seeds:
        return 0

    # Store as hex strings for Redis string compatibility
    hex_seeds = [s.hex() for s in seeds]
    pipe = r.pipeline()
    pipe.rpush(RedisKeys.SEED_POOL, *hex_seeds)
    pipe.ltrim(RedisKeys.SEED_POOL, -RedisKeys.SEED_POOL_MAX, -1)
    results = await pipe.execute()

    count = len(hex_seeds)
    logger.info("[seed_pool] Pushed %d seeds to pool", count)
    return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_incr(r: aioredis.Redis, key: str) -> None:
    """Increment a Redis counter, ignoring errors."""
    try:
        await r.incr(key)
    except Exception:
        pass
