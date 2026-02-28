"""Tests for configuration module."""

from __future__ import annotations

from src.config.defaults import DEFAULTS
from src.config.redis_keys import RedisKeys
from src.config.settings import Settings
from src.config.toggles import TOGGLES, ToggleDefinition


class TestSettings:
    """Tests for Settings dataclass."""

    def test_defaults(self) -> None:
        s = Settings()
        assert s.redis_host == "localhost"
        assert s.redis_port == 6379
        assert s.api_port == 8000
        assert s.dashboard_port == 8501
        assert s.dns_upstream == "8.8.8.8"

    def test_redis_url_no_password(self) -> None:
        s = Settings()
        assert s.redis_url == "redis://localhost:6379/0"

    def test_has_ibm_token_false(self) -> None:
        s = Settings()
        assert s.has_ibm_token is False


class TestToggles:
    """Tests for toggle definitions."""

    def test_all_toggles_present(self) -> None:
        expected = {"source", "backend", "scheme", "phase", "scenario", "extractor", "qrng_method"}
        assert set(TOGGLES.keys()) == expected

    def test_toggle_defaults_valid(self) -> None:
        for name, toggle in TOGGLES.items():
            assert toggle.default in toggle.options, (
                f"Toggle '{name}' default '{toggle.default}' not in options {toggle.options}"
            )

    def test_toggle_has_redis_key(self) -> None:
        for name, toggle in TOGGLES.items():
            assert toggle.redis_key.startswith("config:"), (
                f"Toggle '{name}' redis_key should start with 'config:'"
            )


class TestRedisKeys:
    """Tests for Redis key constants."""

    def test_seed_pool_key(self) -> None:
        assert RedisKeys.SEED_POOL == "qrng_seed_pool"

    def test_config_keys_exist(self) -> None:
        assert RedisKeys.CONFIG_SOURCE == "config:source"
        assert RedisKeys.CONFIG_SCHEME == "config:scheme"
        assert RedisKeys.CONFIG_BACKEND == "config:backend"

    def test_bench_key_factory(self) -> None:
        key = RedisKeys.bench_key("qrng", "ml-dsa-65")
        assert "bench:" in key
        assert "qrng" in key
        assert "ml-dsa-65" in key


class TestDefaults:
    """Tests for default values."""

    def test_defaults_match_toggles(self) -> None:
        for name, toggle in TOGGLES.items():
            assert toggle.redis_key in DEFAULTS, (
                f"Toggle '{name}' key '{toggle.redis_key}' missing from DEFAULTS"
            )
            assert DEFAULTS[toggle.redis_key] == toggle.default
