"""Pydantic request/response models for the API.

Provides:
  - All request/response schemas for FastAPI endpoints
  - Validation and serialization for API payloads
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ConfigPayload(BaseModel):
    """Request body for POST /api/config."""

    source: str | None = None
    backend: str | None = None
    scheme: str | None = None
    phase: str | None = None
    scenario: str | None = None
    extractor: str | None = None
    qrng_method: str | None = None


class ConfigResponse(BaseModel):
    """Response for GET /api/config."""

    source: str
    backend: str
    scheme: str
    phase: str
    scenario: str
    extractor: str
    qrng_method: str


# ---------------------------------------------------------------------------
# DNS Resolution
# ---------------------------------------------------------------------------

class ResolveRequest(BaseModel):
    """Request body for POST /api/resolve."""

    domain: str = Field(..., examples=["example.com"])
    scheme: str | None = None  # Optional per-request override
    source: str | None = None  # Optional per-request override ("qrng" or "prng")


class ResolveResponse(BaseModel):
    """Response for POST /api/resolve."""

    domain: str
    ip_addresses: list[str]
    signature: str
    scheme: str
    verified: bool
    seed_source: str
    latency_ms: float
    timestamp: str
    # Per-step timing breakdown
    seed_fetch_ms: float = 0.0
    dns_lookup_ms: float = 0.0
    sign_ms: float = 0.0
    verify_ms: float = 0.0
    client_ip: str = ""
    entropy_source_detail: str = ""


# ---------------------------------------------------------------------------
# QRNG Status
# ---------------------------------------------------------------------------

class QRNGStatus(BaseModel):
    """Response for GET /api/qrng/status."""

    pool_size: int
    last_fill: str
    last_entropy: str
    last_backend: str
    last_qubits: str


# ---------------------------------------------------------------------------
# Attack
# ---------------------------------------------------------------------------

class ShorsRequest(BaseModel):
    """Request body for POST /api/attack/shors."""

    n: int = Field(default=15, ge=4, le=100)


class ShorsStatusResponse(BaseModel):
    """Response for GET /api/attack/shors."""

    status: str
    result: dict | None = None


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

class BenchmarkEntry(BaseModel):
    """Single benchmark result."""

    scheme: str
    keygen_ms: float | None = None
    sign_ms: float | None = None
    verify_ms: float | None = None
    public_key_bytes: int | None = None
    secret_key_bytes: int | None = None
    signature_bytes: int | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class LiveMetrics(BaseModel):
    """Response for GET /api/metrics/live."""

    recent_queries: list[dict]
    total_queries: int
    fallback_count: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str
    redis: bool
    version: str = "1.0.0"
