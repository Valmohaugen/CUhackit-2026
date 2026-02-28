"""FastAPI application factory.

Provides:
  - create_app: Factory function that creates the FastAPI app
  - Lifespan management for Redis connection
  - CORS middleware
  - All route registration
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.redis_client import close_redis, get_redis, init_defaults

logger = logging.getLogger(__name__)

QRNG_REFILL_INTERVAL = 300  # 5 minutes


def _run_qrng_batch() -> None:
    """Run one QRNG seed generation batch (synchronous)."""
    from src.lambda_handler.handler import lambda_handler
    lambda_handler({}, None)


async def _qrng_refill_loop() -> None:
    """Background loop that refills the QRNG seed pool every 5 minutes."""
    while True:
        await asyncio.sleep(QRNG_REFILL_INTERVAL)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _run_qrng_batch)
            logger.info("[api] QRNG background refill completed")
        except Exception:
            logger.warning("[api] QRNG background refill failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Redis connection lifecycle and background QRNG refill."""
    # Startup
    logger.info("[api] Starting Quantum DNS Shield API")
    r = await get_redis()
    await init_defaults(r)
    app.state.redis = r  # Stored on app.state so every route handler can access it via request.app.state.redis.
    logger.info("[api] Redis initialized with defaults")

    # Start background QRNG seed refill (runs every 5 minutes)
    refill_task = asyncio.create_task(_qrng_refill_loop())
    logger.info("[api] QRNG background refill scheduled every %ds", QRNG_REFILL_INTERVAL)

    yield

    # Shutdown
    refill_task.cancel()
    await close_redis()
    logger.info("[api] Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Quantum DNS Shield",
        description="Post-quantum DNS security with QRNG seed management",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — allow Streamlit dashboard to call API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Lazy imports inside the factory avoid circular dependencies and keep startup explicit.
    from src.api.routes.attack import router as attack_router
    from src.api.routes.benchmarks import router as benchmarks_router
    from src.api.routes.chatbot import router as chatbot_router
    from src.api.routes.config_routes import router as config_router
    from src.api.routes.entropy import router as entropy_router
    from src.api.routes.health import router as health_router
    from src.api.routes.metrics import router as metrics_router
    from src.api.routes.migration import router as migration_router
    from src.api.routes.resolve import router as resolve_router

    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(resolve_router)
    app.include_router(metrics_router)
    app.include_router(entropy_router)
    app.include_router(attack_router)
    app.include_router(benchmarks_router)
    app.include_router(migration_router)
    app.include_router(chatbot_router)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    return app
