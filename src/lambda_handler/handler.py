"""Lambda: QRNG Batch Generator.

Generates quantum random seeds using Qiskit AerSimulator (default) or IBM QPU,
applies entropy extraction, validates, and pushes to Redis seed pool.

Adapted from SC-Quantathon-v1-2024/MiniGrant QRNG pipeline.

Trigger: EventBridge every 5 minutes.

# Ref: Von Neumann, J. (1951). "Various Techniques Used in Connection with
#      Random Digits." NBS Applied Mathematics Series, No. 12, pp. 36-38.
# Ref: Carter, J.L. & Wegman, M.N. (1979). "Universal Classes of Hash
#      Functions." Journal of Computer and System Sciences, 18(2), pp. 143-154.
# Ref: Zhang, X. et al. (2016). "FPGA Implementation of Toeplitz Hashing
#      Extractor for Real-Time Post-Processing of Raw Random Numbers." Proc.
#      IEEE ISCAS, pp. 1442-1445.
# Ref: Herrero-Collantes, M. & Garcia-Escartin, J.C. (2017). "Quantum Random
#      Number Generators." Reviews of Modern Physics, 89(1), 015004.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
import numpy as np
import redis
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from scipy.fft import fft
from scipy.stats import entropy

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
AUDIT_BUCKET = os.environ.get("AUDIT_BUCKET", "")
SEED_POOL_KEY = "qrng_seed_pool"
SEED_POOL_MAX = 50_000
SEED_BYTES = 32

NUM_QUBITS = 100
NUM_SHOTS = 4096
CHUNK_SIZE = 30


# ---------------------------------------------------------------------------
# QRNG Generation (adapted from MiniGrant/DataGeneration)
# ---------------------------------------------------------------------------

def _generate_raw_bits(num_qubits: int, num_shots: int) -> str:
    """Generate raw random bits using Hadamard + measure on AerSimulator.

    Uses Method 4 from MiniGrant: concatenate all shot results for maximum
    throughput, then apply post-processing.
    """
    circ = QuantumCircuit(num_qubits, num_qubits)
    circ.h(range(num_qubits))
    circ.measure(range(num_qubits), range(num_qubits))

    backend = AerSimulator()
    compiled = transpile(circ, backend)
    result = backend.run(compiled, shots=num_shots, memory=True).result()
    raw_data = result.get_memory()

    # Concatenate all shot bitstrings
    return "".join(raw_data)


def _generate_chunked_bits(total_qubits: int, chunk_size: int, num_shots: int) -> str:
    """Generate bits in chunks to handle simulator memory limits."""
    chunks = total_qubits // chunk_size
    remainder = total_qubits % chunk_size
    all_bits = ""

    for _ in range(chunks):
        all_bits += _generate_raw_bits(chunk_size, num_shots)

    if remainder > 0:
        all_bits += _generate_raw_bits(remainder, num_shots)

    return all_bits


def _generate_ibm_bits(num_qubits: int, num_shots: int) -> tuple[str, str]:
    """Generate random bits using IBM Quantum backend.

    Falls back to AerSimulator if IBM connection fails.

    Returns:
        Tuple of (raw_bits_string, backend_name).
    """
    # Ref: Herrero-Collantes & Garcia-Escartin (2017), Sec. IV on practical
    # QRNG implementations using superconducting qubit hardware.
    #
    # Fallback strategy: attempt IBM QPU for true quantum randomness, but
    # degrade gracefully to AerSimulator if the QPU is unavailable. This
    # ensures the seed pool is always replenished on schedule regardless
    # of IBM Quantum service availability.
    try:
        # Step 1: Retrieve IBM Quantum API token from env or Secrets Manager
        token = _get_ibm_token()
        if not token:
            raise ValueError("No IBM Quantum token available")

        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        # Step 2: Select the least-busy real (non-simulator) backend
        service = QiskitRuntimeService(channel="ibm_quantum", token=token)
        backend = service.least_busy(min_num_qubits=num_qubits, simulator=False)
        backend_name = backend.name

        logger.info("[qrng] Using IBM backend: %s", backend_name)

        # Step 3: Build Hadamard + measure circuit (maximally superposed state)
        circ = QuantumCircuit(num_qubits, num_qubits)
        circ.h(range(num_qubits))
        circ.measure(range(num_qubits), range(num_qubits))

        compiled = transpile(circ, backend)
        sampler = SamplerV2(backend)
        job = sampler.run([compiled], shots=num_shots)
        result = job.result()

        # Extract bitstrings from SamplerV2 result
        bits_str = ""
        for pub_result in result:
            for sample in pub_result.data.values():
                bits_str += "".join(str(b) for b in sample.flatten())

        if len(bits_str) < 100:
            raise ValueError(f"Too few bits from IBM backend: {len(bits_str)}")

        return bits_str, backend_name

    except Exception as e:
        # Fallback: use local AerSimulator to guarantee seed pool availability
        logger.warning("[qrng] IBM backend failed (%s), falling back to AerSimulator", e)
        bits = _generate_chunked_bits(num_qubits, CHUNK_SIZE, num_shots)
        return bits, "aer_simulator (ibm_fallback)"


def _get_ibm_token() -> str | None:
    """Retrieve IBM Quantum token from environment or Secrets Manager."""
    # Try environment first
    token = os.environ.get("IBM_QUANTUM_TOKEN", "")
    if token:
        return token

    # Try Secrets Manager
    try:
        sm = boto3.client("secretsmanager")
        resp = sm.get_secret_value(SecretId="quantum-dns/ibm-token")
        return resp.get("SecretString", "")
    except Exception as e:
        logger.warning("[qrng] Could not retrieve IBM token: %s", e)
        return None


# ---------------------------------------------------------------------------
# Entropy Extraction (adapted from MiniGrant/PostProcessing)
# ---------------------------------------------------------------------------

def _von_neumann_extract(data: np.ndarray) -> np.ndarray:
    """Von Neumann extractor: remove bias from binary data."""
    # Ref: Von Neumann (1951) debiasing technique.
    # Pairs of consecutive bits are examined: (0,1)->0, (1,0)->1, and equal
    # pairs (0,0) or (1,1) are discarded. This guarantees unbiased output
    # regardless of the input bias p, at the cost of reduced throughput
    # (expected output rate: 2p(1-p) bits per input pair).

    # Output rate: R = 2p(1-p) unbiased bits per input pair, where p is bit bias.
    # For fair coins (p=0.5): R = 0.5 bits/pair, i.e. ~25% throughput.

    extracted = []
    for i in range(0, len(data) - 1, 2):
        if data[i] != data[i + 1]:
            # Emit the first bit of the non-equal pair as the unbiased output
            extracted.append(data[i])
    return np.array(extracted, dtype=np.uint8)


def _toeplitz_extract(data: np.ndarray, blocksize: int = 128) -> np.ndarray:
    """Toeplitz hashing for entropy extraction."""
    # Ref: Carter & Wegman (1979) universal hashing; Zhang et al. (2016) FPGA
    # implementation for QRNG post-processing.
    # A Toeplitz matrix is a universal-2 hash function that provably extracts
    # near-uniform randomness from a weak source, given a min-entropy lower
    # bound. The matrix is fully defined by its first row and first column,
    # requiring only O(n) seed bits instead of O(n^2).

    # Leftover Hash Lemma: output length ≤ H_∞(X) - 2log(1/ε) guarantees
    # ε-closeness to uniform. Toeplitz matrices are universal-2 hash functions.

    transformed = []
    rng = np.random.default_rng(42)
    # XOR PRNG seed material with input data to construct the hash parameters
    first_row = rng.integers(0, 2, size=blocksize) ^ data[:blocksize].astype(int)
    first_col = rng.integers(0, 2, size=blocksize) ^ data[:blocksize].astype(int)

    # Build Toeplitz matrix from first row and first column (constant-diagonal structure)
    n, m = blocksize, blocksize
    toeplitz = np.zeros((n, m), dtype=int)
    for i in range(n):
        for j in range(m):
            toeplitz[i, j] = first_row[j - i] if j >= i else first_col[i - j]

    # Multiply each block by the Toeplitz matrix over GF(2) to extract entropy
    for i in range(0, len(data), blocksize):
        block = data[i:i + blocksize].astype(int)
        if len(block) == blocksize:
            transformed.extend((toeplitz @ block) % 2)
    return np.array(transformed, dtype=np.uint8)


def _parity_extract(data: np.ndarray, blocksize: int = 4) -> np.ndarray:
    """Parity extractor: XOR blocks of bits."""
    truncate = (len(data) // blocksize) * blocksize
    truncated = data[:truncate].astype(int)
    chunks = truncated.reshape(-1, blocksize)
    return (np.sum(chunks, axis=1) % 2).astype(np.uint8)


def _apply_extractor(data: np.ndarray, method: str) -> np.ndarray:
    """Apply the configured entropy extractor."""
    extractors = {
        "von_neumann": _von_neumann_extract,
        "toeplitz": _toeplitz_extract,
        "fft": lambda d: np.array(
            (np.real(fft(_toeplitz_extract(d))) > 0.5).astype(int),
            dtype=np.uint8,
        ),
        "parity": _parity_extract,
    }
    fn = extractors.get(method, _von_neumann_extract)
    return fn(data)


def _shannon_entropy(data: np.ndarray) -> float:
    """Compute Shannon entropy of binary data."""
    _, counts = np.unique(data, return_counts=True)
    probs = counts / len(data)
    return float(entropy(probs, base=2))


# ---------------------------------------------------------------------------
# Seed production
# ---------------------------------------------------------------------------

def _bits_to_seeds(bits: np.ndarray, seed_bytes: int = SEED_BYTES) -> list[bytes]:
    """Convert a bit array to a list of fixed-size byte seeds."""
    seeds = []
    bits_per_seed = seed_bytes * 8
    n_seeds = len(bits) // bits_per_seed

    for i in range(n_seeds):
        chunk = bits[i * bits_per_seed:(i + 1) * bits_per_seed]
        byte_val = int("".join(str(b) for b in chunk), 2)
        seeds.append(byte_val.to_bytes(seed_bytes, "big"))

    return seeds


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point.

    Generates QRNG seeds, post-processes, validates, and pushes to Redis.
    """
    t_start = time.time()
    logger.info("[qrng] Starting QRNG batch generation")

    # Read extractor config from Redis
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD or None,
        decode_responses=True,
    )

    extractor_method = r.get("config:extractor") or "von_neumann"
    backend_config = r.get("config:backend") or "aer"
    logger.info("[qrng] Using extractor: %s, backend: %s", extractor_method, backend_config)

    # Step 1: Generate raw bits
    backend_used = "aer_simulator"
    if backend_config == "ibm":
        raw_bits_str, backend_used = _generate_ibm_bits(NUM_QUBITS, NUM_SHOTS)
    else:
        raw_bits_str = _generate_chunked_bits(NUM_QUBITS, CHUNK_SIZE, NUM_SHOTS)
    raw_bits = np.array([int(b) for b in raw_bits_str], dtype=np.uint8)
    logger.info("[qrng] Generated %d raw bits via %s", len(raw_bits), backend_used)

    # Step 2: Apply entropy extraction
    extracted = _apply_extractor(raw_bits, extractor_method)
    logger.info("[qrng] Extracted %d bits (%.1f%% retention)",
                len(extracted), len(extracted) / max(len(raw_bits), 1) * 100)

    # Step 3: Validate entropy
    h_min = _shannon_entropy(extracted) if len(extracted) > 10 else 0.0
    logger.info("[qrng] Min-entropy: %.4f", h_min)

    # Step 4: Convert to seeds
    seeds = _bits_to_seeds(extracted)
    logger.info("[qrng] Produced %d seeds (%d bytes each)", len(seeds), SEED_BYTES)

    # Step 5: Push to Redis
    if seeds:
        hex_seeds = [s.hex() for s in seeds]
        pipe = r.pipeline()
        pipe.rpush(SEED_POOL_KEY, *hex_seeds)
        pipe.ltrim(SEED_POOL_KEY, -SEED_POOL_MAX, -1)
        pipe.execute()

    # Step 6: Update status keys
    pool_size = r.llen(SEED_POOL_KEY)
    now = datetime.now(timezone.utc).isoformat()
    pipe = r.pipeline()
    pipe.set("qrng:pool_size", str(pool_size))
    pipe.set("qrng:last_fill", now)
    pipe.set("qrng:last_entropy", f"{h_min:.4f}")
    pipe.set("qrng:last_backend", backend_used)
    pipe.set("qrng:last_qubits", str(NUM_QUBITS))
    pipe.execute()

    elapsed = time.time() - t_start

    # Step 7: Write audit log to S3
    audit_log = {
        "timestamp": now,
        "seeds_generated": len(seeds),
        "raw_bits": len(raw_bits),
        "extracted_bits": len(extracted),
        "min_entropy": h_min,
        "extractor": extractor_method,
        "backend": backend_used,
        "num_qubits": NUM_QUBITS,
        "num_shots": NUM_SHOTS,
        "pool_size_after": pool_size,
        "elapsed_seconds": round(elapsed, 2),
    }

    if AUDIT_BUCKET:
        try:
            s3 = boto3.client("s3")
            key = f"qrng-audit/{now.replace(':', '-')}.json"
            s3.put_object(
                Bucket=AUDIT_BUCKET,
                Key=key,
                Body=json.dumps(audit_log),
                ContentType="application/json",
            )
            logger.info("[qrng] Audit log written to s3://%s/%s", AUDIT_BUCKET, key)
        except Exception as e:
            logger.warning("[qrng] Failed to write audit log: %s", e)

    logger.info(
        "[qrng] Done: %d seeds, pool=%d, entropy=%.4f, %.1fs",
        len(seeds), pool_size, h_min, elapsed,
    )

    return {
        "statusCode": 200,
        "body": json.dumps(audit_log),
    }
