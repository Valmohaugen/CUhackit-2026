"""Environment variables and infrastructure settings.

Provides:
  - Settings dataclass loaded from environment variables
  - All infrastructure-level configuration (hosts, ports, credentials)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


# Frozen dataclass ensures settings are immutable after construction from env vars.
@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Redis
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_password: str = field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))

    # IBM Quantum (empty = simulator only)
    ibm_quantum_token: str = field(default_factory=lambda: os.getenv("IBM_QUANTUM_TOKEN", ""))

    # AWS
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    audit_bucket: str = field(default_factory=lambda: os.getenv("AUDIT_BUCKET", ""))

    # Application
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "localhost"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    dashboard_port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8501")))

    # DNS
    dns_upstream: str = field(default_factory=lambda: os.getenv("DNS_UPSTREAM", "8.8.8.8"))

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def has_ibm_token(self) -> bool:
        return bool(self.ibm_quantum_token)


# Singleton instance
settings = Settings()
