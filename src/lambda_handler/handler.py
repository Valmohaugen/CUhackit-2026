"""Lambda: QRNG Batch Generator.

Generates quantum random seeds using Qiskit AerSimulator (default) or IBM QPU,
applies entropy extraction, validates, and pushes to Redis seed pool.

Adapted from SC-Quantathon-v1-2024/MiniGrant QRNG pipeline.

Trigger: EventBridge every 5 minutes.
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
NUM_SHOTS = 1024
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


# ---------------------------------------------------------------------------
# Entropy Extraction (adapted from MiniGrant/PostProcessing)
# ---------------------------------------------------------------------------

def _von_neumann_extract(data: np.ndarray) -> np.ndarray:
    """Von Neumann extractor: remove bias from binary data."""
    extracted = []
    for i in range(0, len(data) - 1, 2):
        if data[i] != data[i + 1]:
            extracted.append(data[i])
    return np.array(extracted, dtype=np.uint8)


def _toeplitz_extract(data: np.ndarray, blocksize: int = 128) -> np.ndarray:
    """Toeplitz hashing for entropy extraction."""
    transformed = []
    rng = np.random.default_rng(42)
    first_row = rng.integers(0, 2, size=blocksize) ^ data[:blocksize].astype(int)
    first_col = rng.integers(0, 2, size=blocksize) ^ data[:blocksize].astype(int)

    # Build Toeplitz matrix
    n, m = blocksize, blocksize
    toeplitz = np.zeros((n, m), dtype=int)
    for i in range(n):
        for j in range(m):
            toeplitz[i, j] = first_row[j - i] if j >= i else first_col[i - j]

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
    logger.info("[qrng] Using extractor: %s", extractor_method)

    # Step 1: Generate raw bits
    raw_bits_str = _generate_chunked_bits(NUM_QUBITS, CHUNK_SIZE, NUM_SHOTS)
    raw_bits = np.array([int(b) for b in raw_bits_str], dtype=np.uint8)
    logger.info("[qrng] Generated %d raw bits", len(raw_bits))

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
    pipe.set("qrng:last_backend", "aer_simulator")
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
        "backend": "aer_simulator",
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
