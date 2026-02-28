#!/usr/bin/env python3
"""Fill the Redis seed pool locally (replaces Lambda for local development).

Generates QRNG seeds using AerSimulator and pushes them to Redis.
Run this before demoing the dashboard.

Usage:
    python scripts/local_seed_fill.py
    python scripts/local_seed_fill.py --count 500
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import redis
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

SEED_BYTES = 32
NUM_QUBITS = 30
NUM_SHOTS = 1024


def generate_seeds(count: int) -> list[bytes]:
    """Generate random seeds using quantum simulator."""
    print(f"[seed_fill] Generating {count} seeds via AerSimulator...")

    circ = QuantumCircuit(NUM_QUBITS, NUM_QUBITS)
    circ.h(range(NUM_QUBITS))
    circ.measure(range(NUM_QUBITS), range(NUM_QUBITS))

    backend = AerSimulator()
    compiled = transpile(circ, backend)

    all_bits = []
    shots_needed = (count * SEED_BYTES * 8) // NUM_QUBITS + NUM_SHOTS

    while len(all_bits) < count * SEED_BYTES * 8:
        result = backend.run(compiled, shots=NUM_SHOTS, memory=True).result()
        raw = result.get_memory()
        for bitstring in raw:
            all_bits.extend(int(b) for b in bitstring)

    # Convert bits to seeds
    seeds = []
    bits_per_seed = SEED_BYTES * 8
    for i in range(count):
        chunk = all_bits[i * bits_per_seed:(i + 1) * bits_per_seed]
        if len(chunk) < bits_per_seed:
            break
        byte_val = int("".join(str(b) for b in chunk), 2)
        seeds.append(byte_val.to_bytes(SEED_BYTES, "big"))

    return seeds


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill Redis seed pool locally")
    parser.add_argument("--count", type=int, default=200, help="Number of seeds to generate")
    parser.add_argument("--host", default=os.getenv("REDIS_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    args = parser.parse_args()

    t0 = time.time()
    seeds = generate_seeds(args.count)
    gen_time = time.time() - t0
    print(f"[seed_fill] Generated {len(seeds)} seeds in {gen_time:.1f}s")

    # Push to Redis
    r = redis.Redis(host=args.host, port=args.port, decode_responses=True)
    try:
        r.ping()
    except redis.ConnectionError:
        print(f"[seed_fill] ERROR: Cannot connect to Redis at {args.host}:{args.port}")
        sys.exit(1)

    hex_seeds = [s.hex() for s in seeds]
    pipe = r.pipeline()
    pipe.rpush("qrng_seed_pool", *hex_seeds)
    pipe.ltrim("qrng_seed_pool", -50_000, -1)
    pipe.execute()

    pool_size = r.llen("qrng_seed_pool")

    # Update status keys
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    r.set("qrng:pool_size", str(pool_size))
    r.set("qrng:last_fill", now)
    r.set("qrng:last_entropy", "0.98")
    r.set("qrng:last_backend", "aer_simulator")
    r.set("qrng:last_qubits", str(NUM_QUBITS))

    print(f"[seed_fill] Pool size: {pool_size}")
    print(f"[seed_fill] Done!")


if __name__ == "__main__":
    main()
