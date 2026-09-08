#!/usr/bin/env python3
"""Post-revision pattern diagnostics and compatibility helpers."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

FORBIDDEN_MIGRATION_PATTERNS_YAML = (
    Path(__file__).parent.parent / "skills" / "prose-craft" / "references" / "forbidden_migration_patterns.yaml"
)

FAMILY_TO_FUNCTION = {
    "contrastive_negation_assertion": "contrastive_explanation",
    "ordinal_gravity_marker": "ordinal_significance",
    "state_persistence_template": "state_label_assessment",
}


def _load_forbidden_migration_patterns() -> dict[str, dict[str, re.Pattern[str]]]:
    """Load the prose-craft SSOT pattern table at import time."""
    with FORBIDDEN_MIGRATION_PATTERNS_YAML.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return {
        function: {name: re.compile(pattern) for name, pattern in patterns.items()}
        for function, patterns in data.items()
    }


FORBIDDEN_MIGRATION_PATTERNS = _load_forbidden_migration_patterns()


def check_cluster_patch_gate(patch: dict, cluster_alert: dict) -> dict:
    """Validate a supplied kind; old cluster suggestions are diagnostic only.

    The patch schema owns supported operations. Whether an operation repairs
    the confirmed defect is checked in the revised text by the reviewer.
    """
    patch_kind = patch.get("patch_kind")
    if not isinstance(patch_kind, str) or not patch_kind.strip():
        return {"gate_pass": False, "reason": "patch_kind is required"}
    governance = cluster_alert.get("governance", {})
    allowed = governance.get("required_patch_kind_options", [])
    if patch_kind not in allowed:
        return {
            "gate_pass": True,
            "reason": f"cluster suggested {allowed}; assess '{patch_kind}' against the actual defect",
            "forbidden_matched": patch_kind in governance.get("forbidden_patch_kind", []),
        }
    return {"gate_pass": True}


def _regex_text(text: str) -> str:
    """Normalize punctuation for compact Chinese regexes without changing semantics."""
    return text.replace("，", "").replace(",", "")


def check_semantic_function_migration(v1_anchor_text: str, v2_anchor_text: str, family: str) -> dict:
    """Locate a newly matching expression for semantic review; a match proves no defect."""
    function = FAMILY_TO_FUNCTION.get(family)
    if not function:
        return {"detected": False}

    patterns = FORBIDDEN_MIGRATION_PATTERNS.get(function, {})
    old_text = _regex_text(v1_anchor_text)
    new_text = _regex_text(v2_anchor_text)
    for pattern_name, regex in patterns.items():
        old_match = regex.search(old_text)
        new_match = regex.search(new_text)
        if new_match and not old_match:
            return {
                "detected": True,
                "old_function": function,
                "matched_pattern": pattern_name,
                "matched_text": new_match.group(0),
            }
    return {"detected": False}


def on_semantic_migration_fail(ledger: dict, failed_patch_ids: list[str]) -> dict:
    """Record reviewer-confirmed failed repairs; regex matches alone cannot call this."""
    state = ledger.get("semantic_migration_state")
    if not isinstance(state, dict):
        state = {"attempt_count": 0, "last_failed_patch_ids": []}
    state["attempt_count"] = int(state.get("attempt_count", 0)) + 1
    state["last_failed_patch_ids"] = list(failed_patch_ids)
    ledger["semantic_migration_state"] = state
    return ledger


def decide_escalation(ledger: dict) -> str:
    """Return confirmed failures to the caller to assess cause and repair scope."""
    state = ledger.get("semantic_migration_state")
    if isinstance(state, dict) and state.get("last_failed_patch_ids"):
        return "orchestrator_escalate"
    return "reviser_retry"
