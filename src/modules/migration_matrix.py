"""Module 4: Post-quantum migration matrix and recommendations.

Provides:
  - get_migration_matrix: Full matrix of scenarios × phases
  - get_recommendation: Scenario-specific recommendation
  - Cost/benefit/risk/timeline analysis per deployment scenario
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MigrationEntry:
    """Single cell in the migration matrix."""

    scenario: str
    phase: str
    scheme: str
    key_size_bytes: int
    signature_bytes: int
    latency_overhead_pct: float
    packet_size_increase_pct: float
    implementation_cost: str  # low / medium / high
    risk_level: str  # low / medium / high / critical
    timeline_months: int
    notes: str


@dataclass
class ScenarioRecommendation:
    """Recommendation for a specific scenario."""

    scenario: str
    recommended_phase: str
    recommended_scheme: str
    urgency: str  # low / medium / high / critical
    summary: str
    migration_steps: list[str]
    estimated_cost: str
    estimated_timeline: str


# ---------------------------------------------------------------------------
# Migration matrix data
# ---------------------------------------------------------------------------

_SCHEMES_INFO = {
    "ml-dsa-65": {
        "key_size_bytes": 1952,
        "signature_bytes": 3293,
        "latency_factor": 1.2,
        "packet_factor": 3.5,
    },
    "falcon-512": {
        "key_size_bytes": 897,
        "signature_bytes": 666,
        "latency_factor": 1.1,
        "packet_factor": 1.8,
    },
    "rsa-2048": {
        "key_size_bytes": 256,
        "signature_bytes": 256,
        "latency_factor": 1.0,
        "packet_factor": 1.0,
    },
}

_SCENARIO_CONFIGS = {
    "web": {
        "label": "Web Services",
        "description": "Public-facing web applications, APIs, CDNs",
        "urgency": "medium",
        "primary_scheme": "ml-dsa-65",
        "phases": {
            "classical": {"cost": "low", "risk": "high", "timeline": 0},
            "hybrid": {"cost": "medium", "risk": "medium", "timeline": 6},
            "pq_only": {"cost": "medium", "risk": "low", "timeline": 12},
        },
        "recommendation": (
            "Web services should begin hybrid migration within 6 months. "
            "ML-DSA-65 offers the best balance of security and compatibility. "
            "Larger signature sizes are manageable for HTTPS but may impact "
            "mobile clients on slow connections."
        ),
        "steps": [
            "Audit current TLS certificate infrastructure",
            "Deploy hybrid ML-DSA-65 + ECDSA certificates",
            "Update CDN edge nodes to support PQ key exchange",
            "Monitor packet size impact on mobile clients",
            "Full PQ migration after NIST final standards ratification",
        ],
    },
    "iot": {
        "label": "IoT / Embedded",
        "description": "Resource-constrained devices, sensors, edge computing",
        "urgency": "high",
        "primary_scheme": "falcon-512",
        "phases": {
            "classical": {"cost": "low", "risk": "critical", "timeline": 0},
            "hybrid": {"cost": "high", "risk": "medium", "timeline": 12},
            "pq_only": {"cost": "high", "risk": "low", "timeline": 24},
        },
        "recommendation": (
            "IoT devices have 10-20 year lifespans and are already vulnerable "
            "to harvest-now-decrypt-later attacks. Falcon-512 is preferred due "
            "to smaller signatures (666 bytes vs 3293 for ML-DSA). Firmware "
            "update mechanisms must be PQ-secured first."
        ),
        "steps": [
            "Inventory all deployed devices and firmware update capabilities",
            "Prioritize devices handling sensitive data for early migration",
            "Deploy Falcon-512 for constrained devices (smaller signatures)",
            "Implement PQ-secured firmware update channels",
            "Plan hardware refresh for devices that cannot be updated",
        ],
    },
    "enterprise": {
        "label": "Enterprise",
        "description": "Corporate networks, email, VPN, internal services",
        "urgency": "medium",
        "primary_scheme": "ml-dsa-65",
        "phases": {
            "classical": {"cost": "low", "risk": "high", "timeline": 0},
            "hybrid": {"cost": "medium", "risk": "low", "timeline": 3},
            "pq_only": {"cost": "medium", "risk": "low", "timeline": 9},
        },
        "recommendation": (
            "Enterprise environments should prioritize VPN and email encryption "
            "migration. ML-DSA-65 is well-suited for server-to-server communication. "
            "Hybrid mode provides backward compatibility during transition."
        ),
        "steps": [
            "Assess cryptographic inventory across all services",
            "Upgrade VPN concentrators to support PQ key exchange",
            "Deploy hybrid PQ certificates on internal CAs",
            "Update email encryption (S/MIME or PGP) to PQ algorithms",
            "Train security team on PQ cryptography operations",
        ],
    },
    "critical": {
        "label": "Critical Infrastructure",
        "description": "Power grid, water, transportation, healthcare",
        "urgency": "critical",
        "primary_scheme": "ml-dsa-65",
        "phases": {
            "classical": {"cost": "low", "risk": "critical", "timeline": 0},
            "hybrid": {"cost": "high", "risk": "medium", "timeline": 6},
            "pq_only": {"cost": "high", "risk": "low", "timeline": 18},
        },
        "recommendation": (
            "Critical infrastructure is the highest-priority target for HNDL "
            "attacks. SCADA/ICS protocols must be upgraded to PQ-secured variants. "
            "Regulatory compliance (NIST, CISA) will mandate PQ migration. "
            "Begin immediately with hybrid deployment."
        ),
        "steps": [
            "Conduct quantum risk assessment per CISA guidelines",
            "Identify SCADA/ICS systems with cryptographic dependencies",
            "Deploy PQ-secured communication channels for control systems",
            "Implement quantum-safe key management infrastructure",
            "Coordinate with sector-specific regulators on compliance timeline",
            "Establish quantum-safe backup and recovery procedures",
        ],
    },
    "financial": {
        "label": "Financial Services",
        "description": "Banking, trading, payment processing, HSMs",
        "urgency": "critical",
        "primary_scheme": "ml-dsa-65",
        "phases": {
            "classical": {"cost": "low", "risk": "critical", "timeline": 0},
            "hybrid": {"cost": "high", "risk": "medium", "timeline": 3},
            "pq_only": {"cost": "high", "risk": "low", "timeline": 12},
        },
        "recommendation": (
            "Financial data has extremely long confidentiality requirements "
            "(20+ years). HNDL attacks are already economically viable. "
            "HSM vendors are adding PQ support — prioritize HSM firmware updates. "
            "PCI DSS will require PQ readiness; begin hybrid deployment immediately."
        ),
        "steps": [
            "Upgrade HSMs to PQ-capable firmware",
            "Deploy hybrid PQ certificates on payment gateways",
            "Update SWIFT and interbank communication protocols",
            "Implement PQ-secured transaction signing",
            "Audit third-party integrations for PQ readiness",
            "Document compliance with emerging PQ regulations",
        ],
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_migration_matrix() -> list[dict]:
    """Get the full migration matrix as a list of entries.

    Returns
    -------
    list[dict]
        All migration entries across all scenarios and phases.
    """
    entries = []

    for scenario_key, config in _SCENARIO_CONFIGS.items():
        scheme_key = config["primary_scheme"]
        scheme_info = _SCHEMES_INFO[scheme_key]

        for phase_key, phase_config in config["phases"].items():
            # Classical phase uses RSA baseline
            if phase_key == "classical":
                active_scheme = "rsa-2048"
                active_info = _SCHEMES_INFO["rsa-2048"]
            elif phase_key == "hybrid":
                active_scheme = f"{scheme_key} + RSA-2048"
                active_info = scheme_info  # PQ overhead dominates
            else:
                active_scheme = scheme_key
                active_info = scheme_info

            entry = MigrationEntry(
                scenario=config["label"],
                phase=phase_key,
                scheme=active_scheme,
                key_size_bytes=active_info["key_size_bytes"],
                signature_bytes=active_info["signature_bytes"],
                latency_overhead_pct=round((active_info["latency_factor"] - 1) * 100, 1),
                packet_size_increase_pct=round((active_info["packet_factor"] - 1) * 100, 1),
                implementation_cost=phase_config["cost"],
                risk_level=phase_config["risk"],
                timeline_months=phase_config["timeline"],
                notes=config["description"],
            )
            entries.append(asdict(entry))

    return entries


def get_recommendation(scenario: str) -> dict:
    """Get migration recommendation for a specific scenario.

    Parameters
    ----------
    scenario : str
        One of: web, iot, enterprise, critical, financial.

    Returns
    -------
    dict
        ScenarioRecommendation as a dictionary.
    """
    config = _SCENARIO_CONFIGS.get(scenario)
    if config is None:
        return {"error": f"Unknown scenario: {scenario}"}

    rec = ScenarioRecommendation(
        scenario=config["label"],
        recommended_phase="hybrid",
        recommended_scheme=config["primary_scheme"],
        urgency=config["urgency"],
        summary=config["recommendation"],
        migration_steps=config["steps"],
        estimated_cost=config["phases"]["pq_only"]["cost"],
        estimated_timeline=f"{config['phases']['pq_only']['timeline']} months to full PQ",
    )

    return asdict(rec)


def get_all_recommendations() -> list[dict]:
    """Get recommendations for all scenarios."""
    return [get_recommendation(s) for s in _SCENARIO_CONFIGS]
