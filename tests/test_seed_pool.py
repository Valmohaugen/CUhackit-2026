"""Tests for the QRNG seed pool module."""

from __future__ import annotations

import pytest

from src.config.redis_keys import RedisKeys
from src.modules.seed_pool import SeedSource, get_pool_size, get_seed, push_seeds


# Verifies seed retrieval: PRNG fallback on empty pool, force-PRNG bypass, and QRNG seed consumption
@pytest.mark.asyncio
class TestGetSeed:
    """Tests for get_seed function."""

    async def test_prng_fallback_when_pool_empty(self, fake_redis) -> None:
        seed, source = await get_seed(fake_redis)
        assert len(seed) == 32
        assert source == SeedSource.PRNG

    async def test_force_prng(self, fake_redis) -> None:
        # Push a seed first
        await push_seeds(fake_redis, [b"\xaa" * 32])

        seed, source = await get_seed(fake_redis, force_prng=True)
        assert len(seed) == 32
        assert source == SeedSource.PRNG

        # Seed should still be in pool (not consumed)
        pool_size = await get_pool_size(fake_redis)
        assert pool_size == 1

    async def test_qrng_seed_consumed(self, fake_redis) -> None:
        test_seed = b"\xbb" * 32
        await push_seeds(fake_redis, [test_seed])

        seed, source = await get_seed(fake_redis)
        assert source == SeedSource.QRNG
        assert len(seed) == 32

        # Pool should be empty now
        pool_size = await get_pool_size(fake_redis)
        assert pool_size == 0


# Verifies pushing seeds into the Redis-backed pool, including batch insert and empty-list edge case
@pytest.mark.asyncio
class TestPushSeeds:
    """Tests for push_seeds function."""

    async def test_push_multiple(self, fake_redis) -> None:
        seeds = [b"\x00" * 32, b"\x01" * 32, b"\x02" * 32]
        count = await push_seeds(fake_redis, seeds)
        assert count == 3

        pool_size = await get_pool_size(fake_redis)
        assert pool_size == 3

    async def test_push_empty_list(self, fake_redis) -> None:
        count = await push_seeds(fake_redis, [])
        assert count == 0


# Verifies pool size reporting for both empty and populated states
@pytest.mark.asyncio
class TestGetPoolSize:
    """Tests for get_pool_size function."""

    async def test_empty_pool(self, fake_redis) -> None:
        size = await get_pool_size(fake_redis)
        assert size == 0

    async def test_after_push(self, fake_redis) -> None:
        await push_seeds(fake_redis, [b"\xff" * 32] * 5)
        size = await get_pool_size(fake_redis)
        assert size == 5


# Verifies the SeedSource enum exposes the expected "qrng" and "prng" string values
class TestSeedSource:
    """Tests for SeedSource enum."""

    def test_values(self) -> None:
        assert SeedSource.QRNG.value == "qrng"
        assert SeedSource.PRNG.value == "prng"
