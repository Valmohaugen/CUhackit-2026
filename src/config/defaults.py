"""Default values for all toggles.

Provides:
  - DEFAULTS dict mapping Redis keys to their default values
  - Used to initialize Redis on first startup
"""

from __future__ import annotations

from src.config.toggles import TOGGLES


# Derived from ToggleDefinition.default so toggle metadata is the single source of truth.
DEFAULTS: dict[str, str] = {
    toggle.redis_key: toggle.default for toggle in TOGGLES.values()
}

# QRNG generation parameters
QRNG_NUM_QUBITS = 100
QRNG_NUM_SHOTS = 1024
QRNG_CHUNK_SIZE = 30
QRNG_MOD2_ITERATIONS = 3
QRNG_SEED_BYTES = 32
