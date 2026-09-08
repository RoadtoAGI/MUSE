#!/usr/bin/env python3
"""Small validators for lint_resolution_ledger schema fragments."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def validate_ledger_v1_triage_entry(entry: Mapping[str, object]) -> bool:
    """Validate the two v1_triage entry shapes currently consumed by gates."""
    if "cluster_id" in entry:
        required = (
            "family",
            "count",
            "distribution_mode",
            "triage",
            "governance_compliance",
        )
        return (
            all(key in entry for key in required)
            and isinstance(entry.get("triage"), Mapping)
            and isinstance(entry.get("governance_compliance"), Mapping)
        )

    if "lint_id" in entry:
        return isinstance(entry.get("triage"), Mapping)

    return False


def validate_ledger_merged_into(entries: Sequence[Mapping[str, object]]) -> bool:
    """Merged lint hits must point at an existing cluster-level ledger entry."""
    cluster_ids = {entry["cluster_id"] for entry in entries if "cluster_id" in entry}
    for entry in entries:
        triage = entry.get("triage")
        if not isinstance(triage, Mapping) or triage.get("status") != "merged":
            continue
        merged_into = triage.get("merged_into")
        if merged_into not in cluster_ids:
            return False
    return True


def validate_semantic_migration_state_sibling(ledger: Mapping[str, object]) -> bool:
    """Validate the Rn+1 sibling field without changing post_revision_updates shape."""
    if "post_revision_updates" in ledger and not isinstance(ledger["post_revision_updates"], list):
        return False
    state = ledger.get("semantic_migration_state")
    if state is None:
        return True
    return (
        isinstance(state, Mapping)
        and isinstance(state.get("attempt_count"), int)
        and isinstance(state.get("last_failed_patch_ids"), list)
    )
