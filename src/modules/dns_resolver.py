"""Module 1: Async DNS Resolver with post-quantum signing.

Provides:
  - resolve: Query upstream DNS, sign response with PQ crypto, log metrics
  - ResolveResult dataclass with full resolution details
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import dns.asyncresolver
import redis.asyncio as aioredis

from src.config.redis_keys import RedisKeys
from src.modules.pq_crypto import Signer, create_signer
from src.modules.seed_pool import SeedSource, get_seed

logger = logging.getLogger(__name__)


@dataclass
class ResolveResult:
    """Result of a DNS resolution with PQ signing."""

    domain: str
    ip_addresses: list[str]
    signature: str  # hex-encoded
    scheme: str
    verified: bool
    seed_source: str  # "qrng" or "prng"
    latency_ms: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Signer cache (avoid re-keygen on every request)
# ---------------------------------------------------------------------------

_signer_cache: dict[str, Signer] = {}


def _get_signer(scheme: str) -> Signer:
    """Get or create a cached signer for the given scheme."""
    if scheme not in _signer_cache:
        _signer_cache[scheme] = create_signer(scheme)
        logger.info("[dns_resolver] Created signer for %s", scheme)
    return _signer_cache[scheme]


def clear_signer_cache() -> None:
    """Clear the signer cache (used when scheme toggle changes)."""
    _signer_cache.clear()


# ---------------------------------------------------------------------------
# Core resolve function
# ---------------------------------------------------------------------------

async def resolve(
    domain: str,
    r: aioredis.Redis,
    scheme: str = "ml-dsa-65",
    use_qrng: bool = True,
    upstream: str = "8.8.8.8",
) -> ResolveResult:
    """Resolve a domain, sign the response with PQ crypto, and log metrics.

    Parameters
    ----------
    domain : str
        Domain name to resolve (e.g., "example.com").
    r : aioredis.Redis
        Active Redis connection.
    scheme : str
        Signature scheme (ml-dsa-65, falcon-512, rsa-2048).
    use_qrng : bool
        Whether to use QRNG seeds (True) or PRNG (False).
    upstream : str
        Upstream DNS server IP.

    Returns
    -------
    ResolveResult
        Full resolution result with signature and metrics.
    """
    t_start = time.perf_counter()

    # Step 1: Get a seed
    seed, seed_source = await get_seed(r, force_prng=not use_qrng)

    # Step 2: DNS query
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = [upstream]
    resolver.lifetime = 5.0

    try:
        answers = await resolver.resolve(domain, "A")
        ip_addresses = [rdata.address for rdata in answers]
    except dns.asyncresolver.NXDOMAIN:
        ip_addresses = []
        logger.warning("[dns_resolver] NXDOMAIN: %s", domain)
    except Exception as e:
        ip_addresses = []
        logger.error("[dns_resolver] DNS error for %s: %s", domain, e)

    # Step 3: Build message to sign (domain + IPs + seed)
    message = f"{domain}|{'|'.join(ip_addresses)}|{seed.hex()}".encode()

    # Step 4: Sign with PQ crypto
    signer = _get_signer(scheme)
    signature = signer.sign(message)

    # Step 5: Verify signature
    verified = signer.verify(message, signature)

    t_end = time.perf_counter()
    latency_ms = round((t_end - t_start) * 1000, 2)

    result = ResolveResult(
        domain=domain,
        ip_addresses=ip_addresses,
        signature=signature.hex()[:128],  # Truncate for display
        scheme=signer.scheme_name,
        verified=verified,
        seed_source=seed_source.value,
        latency_ms=latency_ms,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Step 6: Log to Redis
    await _log_query(r, result)

    logger.info(
        "[dns_resolver] %s → %s (%s, %s, %.1fms)",
        domain,
        ip_addresses,
        signer.scheme_name,
        seed_source.value,
        latency_ms,
    )

    return result


# ---------------------------------------------------------------------------
# Metrics logging
# ---------------------------------------------------------------------------

async def _log_query(r: aioredis.Redis, result: ResolveResult) -> None:
    """Log a query result to Redis live_queries list."""
    try:
        pipe = r.pipeline()
        pipe.lpush(RedisKeys.LIVE_QUERIES, json.dumps(result.to_dict()))
        pipe.ltrim(RedisKeys.LIVE_QUERIES, 0, RedisKeys.LIVE_QUERIES_MAX - 1)
        pipe.incr(RedisKeys.RESOLVER_TOTAL_QUERIES)
        await pipe.execute()
    except Exception as e:
        logger.warning("[dns_resolver] Failed to log query: %s", e)
