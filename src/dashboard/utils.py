"""HTTP client wrapper for Streamlit → FastAPI communication.

Provides:
  - APIClient: Synchronous wrapper around httpx for Streamlit components
"""

from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE = os.getenv("API_URL", "http://localhost:8000")
TIMEOUT = 10.0


def _get(path: str) -> dict | list | None:
    """GET request to FastAPI backend."""
    try:
        resp = httpx.get(f"{API_BASE}{path}", timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _post(path: str, json_data: dict | None = None) -> dict | list | None:
    """POST request to FastAPI backend."""
    try:
        resp = httpx.post(f"{API_BASE}{path}", json=json_data or {}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Typed API methods
# ---------------------------------------------------------------------------

def get_health() -> dict | None:
    return _get("/api/health")


def get_config() -> dict | None:
    return _get("/api/config")


def set_config(updates: dict) -> dict | None:
    return _post("/api/config", updates)


def resolve_domain(domain: str) -> dict | None:
    return _post("/api/resolve", {"domain": domain})


def get_live_metrics() -> dict | None:
    return _get("/api/metrics/live")


def get_qrng_status() -> dict | None:
    return _get("/api/qrng/status")


def get_entropy() -> dict | None:
    return _get("/api/entropy")


def start_shors(n: int = 15) -> dict | None:
    return _post("/api/attack/shors", {"n": n})


def get_shors_status() -> dict | None:
    return _get("/api/attack/shors")


def get_benchmarks() -> list | None:
    return _get("/api/benchmarks")


def get_migration() -> dict | None:
    return _get("/api/migration")
