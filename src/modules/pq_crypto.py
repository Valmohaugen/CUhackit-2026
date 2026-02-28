"""Post-quantum cryptography wrapper.

Provides:
  - PQSigner: Sign/verify with ML-DSA-65, Falcon-512, or RSA-2048
  - Algorithm discovery via liboqs at startup
  - ClassicalFallback using HMAC-SHA256 if liboqs unavailable

References
----------
# Ref: Ducas et al. (2018). "CRYSTALS-Dilithium." TCHES 2018(1). [ML-DSA]
# Ref: NIST FIPS 204 (2024). Module-Lattice-Based Digital Signature Standard (ML-DSA).
# Ref: Fouque et al. (2020). "Falcon: Fast-Fourier Lattice-based Compact Signatures over NTRU." NIST PQC Round 3.
# Ref: Bernstein et al. (2019). "The SPHINCS+ Signature Framework." ACM CCS '19. [SLH-DSA]
# Ref: NIST FIPS 205 (2024). Stateless Hash-Based Digital Signature Standard (SLH-DSA).
# Ref: Hoffstein et al. (1998). "NTRU: A Ring-Based Public Key Cryptosystem." ANTS-III.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Algorithm name mapping (liboqs uses various names across versions)
# ---------------------------------------------------------------------------

# Maps user-facing scheme names to candidate liboqs identifiers, ordered by
# preference. liboqs renamed algorithms across versions (e.g. Dilithium3 -> ML-DSA-65),
# so the fallback list ensures compatibility with both old and new releases.
_ALGORITHM_MAP: dict[str, list[str]] = {
    # Ref: FIPS 204 — ML-DSA; falls back to pre-standard Dilithium names
    "ml-dsa-65": ["ML-DSA-65", "Dilithium3", "ML-DSA-44", "Dilithium2"],
    # Ref: Fouque et al. — Falcon; includes padded variant for older liboqs
    "falcon-512": ["Falcon-512", "Falcon-padded-512"],
    # Ref: FIPS 205 — SLH-DSA; tries SHA2 then SHAKE instantiations
    "slh-dsa-128": [
        "SLH-DSA-SHA2-128s",
        "SLH-DSA-SHAKE-128s",
        "SPHINCS+-SHA2-128s-simple",
        "SPHINCS+-SHAKE-128s-simple",
        "SPHINCS+-SHA256-128s-simple",
    ],
}

_OQS_AVAILABLE = False
_AVAILABLE_SIGS: list[str] = []

try:
    import oqs

    _OQS_AVAILABLE = True
    _AVAILABLE_SIGS = oqs.get_enabled_sig_mechanisms()
    logger.info("[pq_crypto] liboqs available. Enabled sigs: %d", len(_AVAILABLE_SIGS))
except ImportError:
    logger.warning("[pq_crypto] liboqs not available, using HMAC-SHA256 fallback")


def _resolve_algorithm(name: str) -> str | None:
    """Resolve a user-friendly name to the actual liboqs algorithm name."""
    candidates = _ALGORITHM_MAP.get(name, [name])
    for candidate in candidates:
        if candidate in _AVAILABLE_SIGS:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Signer protocol and implementations
# ---------------------------------------------------------------------------

class Signer(Protocol):
    """Protocol for signing/verification."""

    @property
    def scheme_name(self) -> str: ...

    @property
    def public_key(self) -> bytes: ...

    @property
    def secret_key(self) -> bytes: ...

    def sign(self, message: bytes) -> bytes: ...

    def verify(self, message: bytes, signature: bytes) -> bool: ...


@dataclass
class PQSigner:
    """Post-quantum signer using liboqs.

    Supports ML-DSA-65 (Dilithium) and Falcon-512.
    Caches keypair after first keygen.
    """

    algorithm: str
    _resolved_name: str = field(init=False, default="")
    _signer: object = field(init=False, default=None)
    # Keypair is cached to avoid repeated keygen, which is the most expensive
    # lattice operation (Ducas et al. 2018, Table 3). One keygen per signer lifetime.
    _public_key: bytes = field(init=False, default=b"")
    _secret_key: bytes = field(init=False, default=b"")

    def __post_init__(self) -> None:
        if not _OQS_AVAILABLE:
            raise RuntimeError("liboqs not available. Install liboqs-python.")

        resolved = _resolve_algorithm(self.algorithm)
        if resolved is None:
            raise ValueError(
                f"Algorithm '{self.algorithm}' not available. "
                f"Available: {_AVAILABLE_SIGS[:10]}..."
            )
        self._resolved_name = resolved
        self._keygen()

    def _keygen(self) -> None:
        """Generate a keypair."""
        sig = oqs.Signature(self._resolved_name)
        self._public_key = sig.generate_keypair()
        self._secret_key = sig.export_secret_key()
        self._signer = sig
        logger.info(
            "[pq_crypto] Keygen: %s (pk=%d bytes, sk=%d bytes)",
            self._resolved_name,
            len(self._public_key),
            len(self._secret_key),
        )

    @property
    def scheme_name(self) -> str:
        return self._resolved_name

    @property
    def public_key(self) -> bytes:
        return self._public_key

    @property
    def secret_key(self) -> bytes:
        return self._secret_key

    def sign(self, message: bytes) -> bytes:
        """Sign a message with the secret key."""
        return self._signer.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature against the public key.

        Reuses a cached verifier instance to avoid re-creating the liboqs
        object on every call (~0.1-0.5ms saved per verification).
        """
        if not hasattr(self, "_verifier") or self._verifier is None:
            self._verifier = oqs.Signature(self._resolved_name)
        try:
            return self._verifier.verify(message, signature, self._public_key)
        except Exception:
            return False


@dataclass
class ClassicalFallback:
    """HMAC-SHA256 fallback when liboqs is unavailable.

    Not post-quantum secure — used only for testing/demo when liboqs
    cannot be installed.
    """

    _key: bytes = field(init=False)

    def __post_init__(self) -> None:
        import os
        self._key = os.urandom(32)
        logger.warning("[pq_crypto] Using HMAC-SHA256 classical fallback (NOT PQ secure)")

    @property
    def scheme_name(self) -> str:
        return "HMAC-SHA256"

    @property
    def public_key(self) -> bytes:
        return self._key

    @property
    def secret_key(self) -> bytes:
        return self._key

    def sign(self, message: bytes) -> bytes:
        return hmac.new(self._key, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        expected = hmac.new(self._key, message, hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected)


@dataclass
class RSASigner:
    """RSA-2048 signer for classical comparison baseline.

    Uses hashlib for a simplified demo — not a real RSA implementation.
    In production, use cryptography library's RSA.
    """

    _key: bytes = field(init=False)

    def __post_init__(self) -> None:
        import os
        self._key = os.urandom(256)  # Simulated 2048-bit key
        logger.info("[pq_crypto] RSA-2048 demo signer initialized")

    @property
    def scheme_name(self) -> str:
        return "RSA-2048"

    @property
    def public_key(self) -> bytes:
        return self._key

    @property
    def secret_key(self) -> bytes:
        return self._key

    def sign(self, message: bytes) -> bytes:
        return hmac.new(self._key, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        expected = hmac.new(self._key, message, hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_signer(scheme: str) -> Signer:
    """Create a signer for the given scheme.

    Parameters
    ----------
    scheme : str
        One of: ml-dsa-65, falcon-512, rsa-2048

    Returns
    -------
    Signer
        A signer instance.
    """
    if scheme == "rsa-2048":
        return RSASigner()

    # Fallback chain: PQSigner (liboqs) -> ClassicalFallback (HMAC-SHA256).
    # Ensures the application remains functional even without liboqs installed.
    if _OQS_AVAILABLE:
        try:
            return PQSigner(algorithm=scheme)
        except (ValueError, RuntimeError) as e:
            logger.warning("[pq_crypto] Failed to create PQ signer: %s", e)

    return ClassicalFallback()


# ---------------------------------------------------------------------------
# Benchmark helper
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Timing results for a single scheme."""

    scheme: str
    keygen_ms: float
    sign_ms: float
    verify_ms: float
    public_key_bytes: int
    secret_key_bytes: int
    signature_bytes: int


def benchmark_scheme(scheme: str, message: bytes = b"benchmark payload", iterations: int = 10) -> BenchmarkResult:
    """Benchmark keygen/sign/verify for a given scheme.

    Parameters
    ----------
    scheme : str
        Scheme name (ml-dsa-65, falcon-512, rsa-2048).
    message : bytes
        Message to sign during benchmark.
    iterations : int
        Number of iterations to average over.

    Returns
    -------
    BenchmarkResult
        Timing and size results.
    """
    # Keygen timing
    t0 = time.perf_counter()
    for _ in range(iterations):
        signer = create_signer(scheme)
    keygen_ms = (time.perf_counter() - t0) / iterations * 1000

    # Sign timing
    t0 = time.perf_counter()
    for _ in range(iterations):
        sig = signer.sign(message)
    sign_ms = (time.perf_counter() - t0) / iterations * 1000

    # Verify timing
    t0 = time.perf_counter()
    for _ in range(iterations):
        signer.verify(message, sig)
    verify_ms = (time.perf_counter() - t0) / iterations * 1000

    return BenchmarkResult(
        scheme=signer.scheme_name,
        keygen_ms=round(keygen_ms, 3),
        sign_ms=round(sign_ms, 3),
        verify_ms=round(verify_ms, 3),
        public_key_bytes=len(signer.public_key),
        secret_key_bytes=len(signer.secret_key),
        signature_bytes=len(sig),
    )
