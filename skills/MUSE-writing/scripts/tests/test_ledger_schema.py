"""lint_resolution_ledger schema contract tests."""
from __future__ import annotations

from ledger_schema import validate_ledger_merged_into, validate_ledger_v1_triage_entry


def test_ledger_v1_triage_supports_cluster_id():
    entry = {
        "cluster_id": "S01-contrastive_negation_assertion-1",
        "family": "contrastive_negation_assertion",
        "count": 6,
        "distribution_mode": "distributed",
        "triage": {"status": "finding", "severity": "major"},
        "governance_compliance": {"individual_exemption_allowed": False},
    }
    assert validate_ledger_v1_triage_entry(entry) is True


def test_ledger_merged_into_requires_cluster_id_exists():
    cluster_entry = {
        "cluster_id": "S01-contrastive_negation_assertion-1",
        "family": "contrastive_negation_assertion",
        "count": 6,
        "distribution_mode": "distributed",
        "triage": {"status": "finding", "severity": "major"},
        "governance_compliance": {"individual_exemption_allowed": False},
    }
    merged_entry = {
        "lint_id": "S01-notAisB-1",
        "triage": {"status": "merged", "merged_into": "S01-contrastive_negation_assertion-1"},
    }
    assert validate_ledger_merged_into([cluster_entry, merged_entry]) is True

    merged_bad = {
        "lint_id": "S01-x-1",
        "triage": {"status": "merged", "merged_into": "S01-nonexistent-1"},
    }
    assert validate_ledger_merged_into([cluster_entry, merged_bad]) is False
