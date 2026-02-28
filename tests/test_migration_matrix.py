"""Tests for migration matrix module."""

from __future__ import annotations

from src.modules.migration_matrix import (
    get_all_recommendations,
    get_migration_matrix,
    get_recommendation,
)

SCENARIOS = ["web", "iot", "enterprise", "critical", "financial"]
PHASES = ["classical", "hybrid", "pq_only"]


class TestGetMigrationMatrix:
    """Tests for get_migration_matrix."""

    def test_returns_entries(self) -> None:
        matrix = get_migration_matrix()
        assert len(matrix) > 0
        # 5 scenarios × 3 phases = 15 entries
        assert len(matrix) == 15

    def test_entry_structure(self) -> None:
        matrix = get_migration_matrix()
        entry = matrix[0]

        required_keys = {
            "scenario", "phase", "scheme", "key_size_bytes",
            "signature_bytes", "latency_overhead_pct",
            "packet_size_increase_pct", "implementation_cost",
            "risk_level", "timeline_months", "notes",
        }
        assert required_keys.issubset(set(entry.keys()))

    def test_all_scenarios_present(self) -> None:
        matrix = get_migration_matrix()
        scenario_labels = {e["scenario"] for e in matrix}
        # Check that we have entries for all scenario types
        assert len(scenario_labels) == 5

    def test_all_phases_present(self) -> None:
        matrix = get_migration_matrix()
        phases = {e["phase"] for e in matrix}
        assert phases == set(PHASES)

    def test_classical_uses_rsa(self) -> None:
        matrix = get_migration_matrix()
        classical_entries = [e for e in matrix if e["phase"] == "classical"]
        for entry in classical_entries:
            assert entry["scheme"] == "rsa-2048"


class TestGetRecommendation:
    """Tests for get_recommendation."""

    def test_valid_scenario(self) -> None:
        for scenario in SCENARIOS:
            rec = get_recommendation(scenario)
            assert "error" not in rec
            assert rec["recommended_phase"] == "hybrid"
            assert "migration_steps" in rec
            assert len(rec["migration_steps"]) > 0

    def test_unknown_scenario(self) -> None:
        rec = get_recommendation("nonexistent")
        assert "error" in rec

    def test_urgency_levels(self) -> None:
        critical_rec = get_recommendation("critical")
        assert critical_rec["urgency"] == "critical"

        web_rec = get_recommendation("web")
        assert web_rec["urgency"] == "medium"


class TestGetAllRecommendations:
    """Tests for get_all_recommendations."""

    def test_returns_all_scenarios(self) -> None:
        recs = get_all_recommendations()
        assert len(recs) == 5

    def test_each_has_summary(self) -> None:
        recs = get_all_recommendations()
        for rec in recs:
            assert "summary" in rec
            assert len(rec["summary"]) > 0
