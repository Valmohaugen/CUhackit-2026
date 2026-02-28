"""Entropy comparison endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.modules.benchmarks import compare_entropy

router = APIRouter()


@router.get("/api/entropy")
async def get_entropy_comparison(request: Request) -> dict:
    """Compare QRNG vs PRNG entropy with statistical tests."""
    r = request.app.state.redis
    return await compare_entropy(r)
