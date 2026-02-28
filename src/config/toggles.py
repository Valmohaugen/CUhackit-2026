"""Runtime feature toggle definitions.

Provides:
  - ToggleDefinition dataclass describing each toggle
  - TOGGLES dict mapping toggle names to their definitions
  - All valid options for each toggle
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.redis_keys import RedisKeys


@dataclass(frozen=True)
class ToggleDefinition:
    """Definition of a single runtime toggle."""

    redis_key: str
    options: list[str]
    default: str
    label: str
    description: str


TOGGLES: dict[str, ToggleDefinition] = {
    "source": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_SOURCE,
        options=["qrng", "prng"],
        default="qrng",
        label="Random Source",
        description="Quantum random (QRNG) or classical pseudorandom (PRNG)",
    ),
    "backend": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_BACKEND,
        options=["aer", "ibm"],
        default="aer",
        label="Quantum Backend",
        description="Qiskit Aer simulator (default) or IBM QPU",
    ),
    "scheme": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_SCHEME,
        options=["ml-dsa-65", "falcon-512", "rsa-2048"],
        default="ml-dsa-65",
        label="Signature Scheme",
        description="Post-quantum or classical signature algorithm",
    ),
    "phase": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_PHASE,
        options=["classical", "hybrid", "pq_only"],
        default="hybrid",
        label="Migration Phase",
        description="Classical-only, hybrid transition, or full post-quantum",
    ),
    "scenario": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_SCENARIO,
        options=["web", "iot", "enterprise", "critical", "financial"],
        default="enterprise",
        label="Deployment Scenario",
        description="Target deployment environment for migration analysis",
    ),
    "extractor": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_EXTRACTOR,
        options=["von_neumann", "toeplitz", "fft", "parity"],
        default="von_neumann",
        label="Entropy Extractor",
        description="Post-processing method for QRNG output",
    ),
    "qrng_method": ToggleDefinition(
        redis_key=RedisKeys.CONFIG_QRNG_METHOD,
        options=["mod2_xor", "iteration", "concatenation", "multi_run"],
        default="multi_run",
        label="QRNG Generation Method",
        description="Quantum random number generation algorithm",
    ),
}
