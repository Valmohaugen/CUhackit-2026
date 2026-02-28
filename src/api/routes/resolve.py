"""DNS resolution endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.models.schemas import ResolveRequest, ResolveResponse
from src.config.redis_keys import RedisKeys
from src.config.settings import settings
from src.modules.dns_resolver import resolve

router = APIRouter()


@router.post("/api/resolve", response_model=ResolveResponse)
async def resolve_domain(body: ResolveRequest, request: Request) -> ResolveResponse:
    """Resolve a domain with PQ-signed DNS response."""
    r = request.app.state.redis

    # Read current config toggles
    source = await r.get(RedisKeys.CONFIG_SOURCE) or "qrng"
    scheme = await r.get(RedisKeys.CONFIG_SCHEME) or "ml-dsa-65"

    result = await resolve(
        domain=body.domain,
        r=r,
        scheme=scheme,
        use_qrng=(source == "qrng"),
        upstream=settings.dns_upstream,
    )

    return ResolveResponse(**result.to_dict())
