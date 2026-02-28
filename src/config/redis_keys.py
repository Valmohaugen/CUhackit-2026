"""All Redis key name constants.

Provides:
  - RedisKeys class with all key names used throughout the application
  - Centralized key management to prevent typos and enable refactoring
"""

from __future__ import annotations


class RedisKeys:
    """Redis key name constants."""

    # ---------------------------------------------------------------------------
    # Seed Pool
    # ---------------------------------------------------------------------------
    SEED_POOL = "qrng_seed_pool"
    SEED_POOL_MAX = 50_000

    # ---------------------------------------------------------------------------
    # QRNG Status
    # ---------------------------------------------------------------------------
    QRNG_POOL_SIZE = "qrng:pool_size"
    QRNG_LAST_FILL = "qrng:last_fill"
    QRNG_LAST_ENTROPY = "qrng:last_entropy"
    QRNG_LAST_BACKEND = "qrng:last_backend"
    QRNG_LAST_QUBITS = "qrng:last_qubits"

    # ---------------------------------------------------------------------------
    # Config (Master Toggles)
    # ---------------------------------------------------------------------------
    CONFIG_SOURCE = "config:source"
    CONFIG_BACKEND = "config:backend"
    CONFIG_SCHEME = "config:scheme"
    CONFIG_PHASE = "config:phase"
    CONFIG_SCENARIO = "config:scenario"
    CONFIG_EXTRACTOR = "config:extractor"
    CONFIG_QRNG_METHOD = "config:qrng_method"

    # ---------------------------------------------------------------------------
    # Live Metrics
    # ---------------------------------------------------------------------------
    LIVE_QUERIES = "live_queries"
    LIVE_QUERIES_MAX = 500
    RESOLVER_TOTAL_QUERIES = "resolver:total_queries"
    RESOLVER_FALLBACK_COUNT = "resolver:fallback_count"

    # ---------------------------------------------------------------------------
    # Attack Results
    # ---------------------------------------------------------------------------
    ATTACK_SHORS_RESULT = "attack:shors:result"
    ATTACK_SHORS_STATUS = "attack:shors:status"

    # ---------------------------------------------------------------------------
    # Historical Queries (sorted set keyed by timestamp)
    # ---------------------------------------------------------------------------
    HISTORY_QUERIES = "history:queries"
    HISTORY_QUERIES_MAX = 10_000

    # ---------------------------------------------------------------------------
    # Benchmark Cache
    # ---------------------------------------------------------------------------
    @staticmethod
    def bench_key(source: str, scheme: str) -> str:
        return f"bench:{source}_{scheme}"

    BENCH_ENTROPY_COMPARISON = "bench:entropy_comparison"

    # ---------------------------------------------------------------------------
    # All config keys (for batch read/write)
    # ---------------------------------------------------------------------------
    ALL_CONFIG_KEYS = [
        CONFIG_SOURCE,
        CONFIG_BACKEND,
        CONFIG_SCHEME,
        CONFIG_PHASE,
        CONFIG_SCENARIO,
        CONFIG_EXTRACTOR,
        CONFIG_QRNG_METHOD,
    ]
