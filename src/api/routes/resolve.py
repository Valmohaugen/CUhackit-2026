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

    # Per-request body fields override the global Redis toggles, falling back to defaults.
    source = body.source or await r.get(RedisKeys.CONFIG_SOURCE) or "qrng"
    scheme = body.scheme or await r.get(RedisKeys.CONFIG_SCHEME) or "ml-dsa-65"

    # Client IP from ASGI scope; may be the proxy IP if behind a reverse proxy.
    client_ip = ""
    if request.client:
        client_ip = request.client.host

    result = await resolve(
        domain=body.domain,
        r=r,
        scheme=scheme,
        use_qrng=(source == "qrng"),
        upstream=settings.dns_upstream,
        client_ip=client_ip,
    )

    return ResolveResponse(**result.to_dict())
