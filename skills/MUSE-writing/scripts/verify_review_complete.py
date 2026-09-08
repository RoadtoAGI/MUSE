#!/usr/bin/env python3
"""Phase 6→7 admission gate with independent human and machine scans."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

from release_eligibility import (
    admission_input_manifest,
    protected_artifact_manifest,
    strict_phase6_scenes,
    write_admission,
)

VALID_VERDICTS = {"PASS", "PATCH", "ROLLBACK", "REWRITE"}
VALID_RUN_INTENTS = {"smoke", "evaluation", "release"}
HUMAN_SKIPPABLE_CHECKS = frozenset({
    "scene_review",
    "patch_application",
    "post_revision_review",
})
OPEN_MACHINE_STATES = frozenset({"pending", "escalated", "unknown"})
CLOSED_MACHINE_STATES = frozenset({"resolved", "objection_granted"})


def _warn(message: str) -> None:
    print(f"[verify_review_complete WARN] {message}", file=sys.stderr)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_mapping(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 mapping")
    return data


def _run_intent(work_dir: Path) -> tuple[str | None, str | None]:
    path = work_dir / "pipeline" / "run_state.yaml"
    try:
        data = _load_mapping(path)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        return None, f"run_intent_missing_or_invalid:{exc}"
    intent = data.get("run_intent")
    if intent not in VALID_RUN_INTENTS:
        return None, f"run_intent_missing_or_invalid:{intent!r}"
    return str(intent), None


def _skip_config(work_dir: Path) -> tuple[list[str], list[str]]:
    path = work_dir / "pipeline" / "audit" / "skip_review.yaml"
    if not path.exists():
        return [], []
    try:
        data = _load_mapping(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [], [f"skipped_checks_invalid:{exc}"]
    raw = data.get("skipped_checks")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        return [], ["skipped_checks_invalid:must_be_string_list"]
    skipped = list(dict.fromkeys(raw))
    unknown = sorted(set(skipped) - HUMAN_SKIPPABLE_CHECKS)
    if unknown:
        return skipped, [f"skipped_checks_invalid:{unknown}"]
    return skipped, []


def _ai_pattern_gate_closed(post_revision: dict, current_machine_channel: bool = False) -> tuple[bool, str | None]:
    gate = post_revision.get("ai_pattern_gate")
    if not isinstance(gate, dict):
        return True, None
    if str(gate.get("reviewer_gate") or "").lower() == "fail":
        return False, "reviewer_gate_fail"
    if current_machine_channel:
        return True, None  # Current machine obligations are checked independently.
    machine_gate = str(gate.get("machine_gate") or "").lower()
    if machine_gate != "fail":
        return True, None
    override = gate.get("override") or {}
    if not isinstance(override, dict):
        return False, "machine_fail_no_override"
    if bool(override.get("applied")) and str(override.get("override_reason") or "").strip():
        return True, None
    return False, "machine_fail_no_override"


def _protected_integrity_closed(work_dir: Path, scene_id: str) -> tuple[bool, str]:
    """Require the post-revision proof and re-evaluate its active projection."""
    state_path = work_dir / "pipeline" / f"scene_{scene_id}" / "protected_integrity.yaml"
    applied_path = (
        work_dir / "pipeline" / f"scene_{scene_id}" / "patch_directive.applied.yaml"
    )
    if not state_path.exists() and not applied_path.exists():
        return True, ""
    if not state_path.exists():
        return False, "protected_integrity_sidecar_missing_for_applied_patch"

    proof_path = (
        work_dir
        / "pipeline"
        / "review"
        / f"{scene_id}.protected_integrity.post_revision.yaml"
    )
    from protected_integrity import (
        ProtectedIntegrityError,
        validate_post_revision_proof,
    )

    try:
        proof = _load_mapping(proof_path)
        validate_post_revision_proof(work_dir, scene_id, proof)
    except (
        FileNotFoundError,
        OSError,
        ProtectedIntegrityError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        return False, f"protected_integrity_proof_missing_or_invalid:{exc}"

    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    try:
        scene_text = scene_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"protected_integrity_scene_invalid:{exc}"

    from protected_integrity import audit_scene_revision_integrity

    live = audit_scene_revision_integrity(
        work_dir,
        scene_id,
        scene_text,
        scene_text,
    )
    if live.get("verdict") != "PASS":
        return False, f"protected_integrity_live_failed:{live.get('reason', 'unknown')}"
    return True, ""


def _post_revision_closed(work_dir: Path, scene_id: str) -> tuple[bool, str]:
    review_dir = work_dir / "pipeline" / "review"
    path = review_dir / f"scene_{scene_id}.post_revision.yaml"
    try:
        report = _load_mapping(path)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        return False, f"post_revision_missing_or_invalid:{exc}"
    if (report.get("review_incomplete") or report.get("missing_inputs")
            or report.get("written_by") in {"orchestrator_input_gate", "orchestrator_fastpath_gate"}):
        return False, "post_revision_semantic_review_incomplete"
    if str(report.get("verdict") or "").upper() != "PASS":
        return False, f"post_revision_verdict:{report.get('verdict')!r}"
    current_machine_channel = all(
        (review_dir / f"{scene_id}.{name}.yaml").exists()
        for name in ("machine_directive", "machine_ledger")
    )
    gate_closed, reason = _ai_pattern_gate_closed(report, current_machine_channel)
    if not gate_closed:
        return False, reason or "ai_pattern_gate_unclosed"

    if report.get("scene_id") not in {None, scene_id}:
        return False, "post_revision_scene_mismatch"
    for name in ("targeted_span_gate", "scene_residual_gate", "pattern_migration_gate"):
        gate = report.get(name)
        if isinstance(gate, dict) and gate.get("gate_pass") is False:
            return False, f"{name}_fail"
    targeted = report.get("targeted_span_gate") or {}
    patches = targeted.get("per_patch", []) if isinstance(targeted, dict) else []
    if not isinstance(patches, list) or any(
        isinstance(patch, dict) and (
            patch.get("semantic_function_preserved") is False
            or patch.get("contract_conflict_observed") is True
        ) for patch in patches
    ):
        return False, "post_revision_semantic_conflict"

    # Preserve the existing reviewer PASS schema gate when its inputs exist.
    from scene_review_schema_validator import validate_post_revision_pass

    ledger_path = review_dir / f"scene_{scene_id}.lint_resolution_ledger.yaml"
    lint_v2_path = review_dir / "lint" / f"{scene_id}.ai_filler.v2.yaml"
    phase5_path = work_dir / "pipeline" / "phase5_scenes.yaml"
    # Current runs close lint findings through the machine ledger in
    # `_scan_machine_scene`.  The reviewer ledger is a legacy compatibility
    # artifact: validate it when present, without requiring current runs to
    # manufacture a second lifecycle ledger.
    if not ledger_path.exists():
        return True, ""
    try:
        ledger = _load_mapping(ledger_path)
        lint_v2 = _load_mapping(lint_v2_path) if lint_v2_path.exists() else {}
        phase5 = _load_mapping(phase5_path) if phase5_path.exists() else {}
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return False, f"post_revision_inputs_invalid:{exc}"
    scene_card = next(
        (
            scene for scene in phase5.get("scenes", []) or []
            if isinstance(scene, dict)
            and (scene.get("id") or scene.get("scene_id")) == scene_id
        ),
        {},
    )
    result = validate_post_revision_pass(report, ledger, lint_v2, scene_card=scene_card)
    if not result.valid:
        return False, result.reason
    return True, ""


def _scan_human_scene(work_dir: Path, scene_id: str) -> dict:
    review_path = work_dir / "pipeline" / "review" / f"scene_{scene_id}.yaml"
    failures: list[dict] = []
    try:
        review = _load_mapping(review_path)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        failures.append({"check": "scene_review", "reason": f"missing_or_invalid:{exc}"})
        review = {}

    verdict = str(review.get("verdict") or "").upper()
    if (verdict == "ESCALATED" or review.get("review_incomplete")
            or review.get("missing_inputs")
            or review.get("written_by") in {"orchestrator_input_gate", "orchestrator_fastpath_gate"}):
        failures.append({
            "check": "scene_review",
            "reason": "ESCALATED 未闭合 (review_escalated_or_incomplete)",
        })
    elif verdict not in VALID_VERDICTS:
        failures.append({"check": "scene_review", "reason": f"invalid_verdict:{verdict or '<empty>'}"})

    legacy_ledger = work_dir / "pipeline" / "review" / f"scene_{scene_id}.lint_resolution_ledger.yaml"
    if legacy_ledger.exists():
        try:
            _load_mapping(legacy_ledger)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            failures.append({"check": "scene_review", "reason": f"ledger_yaml_invalid:{exc}"})

    scene_state_dir = work_dir / "pipeline" / f"scene_{scene_id}"
    pending = scene_state_dir / "patch_directive.yaml"
    applied = scene_state_dir / "patch_directive.applied.yaml"
    if pending.exists():
        failures.append({
            "check": "patch_application",
            "reason": "patch_directive.yaml still pending (pending_patch_unclosed)",
        })
    if verdict == "PATCH":
        if not applied.exists():
            failures.append({
                "check": "patch_application",
                "reason": "patch_directive.applied missing (applied_patch_missing)",
            })
    if verdict in {"PATCH", "ROLLBACK", "REWRITE"}:
        closed, reason = _post_revision_closed(work_dir, scene_id)
        if not closed:
            failures.append({"check": "post_revision_review", "reason": reason})

    # Protected application batches are machine-owned and therefore checked
    # independently of the human verdict.  This also closes the emergency
    # per-scene path and cannot be waived through skip_review.
    protected_closed, protected_reason = _protected_integrity_closed(
        work_dir, scene_id
    )
    if not protected_closed:
        failures.append({
            "check": "protected_integrity",
            "reason": protected_reason,
        })

    return {"closed": not failures, "verdict": verdict or "UNKNOWN", "failures": failures}


def _latest_lint_path(work_dir: Path, scene_id: str, directive: dict | None) -> Path:
    lint_dir = work_dir / "pipeline" / "review" / "lint"
    if directive:
        revision = directive.get("lint_revision")
        relative = revision.get("artifact") if isinstance(revision, dict) else None
        if not relative:
            relative = directive.get("lint_artifact")
        if isinstance(relative, str) and relative:
            path = Path(relative)
            return path if path.is_absolute() else work_dir / path
    dist = []
    for path in lint_dir.glob(f"{scene_id}.ai_filler.dist*.yaml"):
        suffix = path.stem.rsplit("dist", 1)[-1]
        if suffix.isdigit():
            dist.append((int(suffix), path))
    if dist:
        return max(dist)[1]
    for name in (f"{scene_id}.ai_filler.v2.yaml", f"{scene_id}.ai_filler.yaml"):
        path = lint_dir / name
        if path.exists():
            return path
    return lint_dir / f"{scene_id}.ai_filler.yaml"


def _unknown_machine(reason: str, lint_artifact: str | None = None) -> dict:
    result = {
        "closed": False,
        "entry_states": ["unknown"],
        "closure_modes": [],
        "reason": reason,
    }
    if lint_artifact:
        result["lint_artifact"] = lint_artifact
    return result


def _normalize_pair(directive_status: object, ledger_status: object) -> str:
    directive_value = str(directive_status or "unknown")
    ledger_value = str(ledger_status or "unknown")
    if directive_value == "pending" and ledger_value == "issued":
        return "pending"
    if directive_value == ledger_value and directive_value in OPEN_MACHINE_STATES | CLOSED_MACHINE_STATES:
        return directive_value
    return "unknown"


def _valid_hit_partition(entry: dict) -> bool:
    all_ids = entry.get("all_hit_ids")
    exempted = entry.get("exempted_hit_ids")
    remaining = entry.get("remaining_hit_ids")
    if not all(isinstance(value, list) for value in (all_ids, exempted, remaining)):
        return False
    if any(not isinstance(hit_id, str) or not hit_id for hit_id in all_ids + exempted + remaining):
        return False
    if len(all_ids) != len(set(all_ids)):
        return False
    if len(exempted) != len(set(exempted)) or len(remaining) != len(set(remaining)):
        return False
    return not (set(exempted) & set(remaining)) and set(all_ids) == set(exempted) | set(remaining)


def _active_projection_error(
    work_dir: Path,
    scene_id: str,
    directive: dict,
    ledger: dict,
    lint_path: Path,
) -> str | None:
    if directive.get("scene_id") != scene_id or ledger.get("scene_id") != scene_id:
        return "active_revision_scene_mismatch"

    directive_id = directive.get("active_revision_id")
    ledger_id = ledger.get("active_revision_id")
    directive_revision = directive.get("lint_revision")
    ledger_revision = ledger.get("lint_revision")
    if (
        not isinstance(directive_id, str)
        or not directive_id
        or directive_id != ledger_id
        or not isinstance(directive_revision, dict)
        or directive_revision != ledger_revision
    ):
        return "active_revision_mismatch"
    if directive_revision.get("artifact_sha256") != directive_id:
        return "active_revision_mismatch"

    artifact = directive_revision.get("artifact")
    if not isinstance(artifact, str) or not artifact:
        return "active_revision_artifact_missing"
    artifact_path = Path(artifact)
    if not artifact_path.is_absolute():
        artifact_path = work_dir / artifact_path
    artifact_path = artifact_path.resolve()
    try:
        artifact_path.relative_to(work_dir.resolve())
    except ValueError:
        return "active_revision_artifact_outside_work_dir"
    if artifact_path != lint_path.resolve():
        return "active_revision_artifact_mismatch"
    if not artifact_path.exists() or _sha256(artifact_path) != directive_id:
        return "active_revision_artifact_hash_mismatch"

    directive_entries = {
        entry.get("id"): entry
        for entry in directive.get("entries", []) or []
        if isinstance(entry, dict) and entry.get("level") in {"S", "M"} and entry.get("id")
    }
    ledger_entries = {
        entry.get("id"): entry
        for entry in ledger.get("entries", []) or []
        if isinstance(entry, dict) and entry.get("level") in {"S", "M"} and entry.get("id")
    }
    if set(directive_entries) != set(ledger_entries):
        return "active_entry_set_mismatch"
    for entry_id, directive_entry in directive_entries.items():
        ledger_entry = ledger_entries[entry_id]
        if not _valid_hit_partition(directive_entry) or not _valid_hit_partition(ledger_entry):
            return f"active_hit_partition_invalid:{entry_id}"
        for field in ("all_hit_ids", "exempted_hit_ids", "remaining_hit_ids"):
            if directive_entry[field] != ledger_entry[field]:
                return f"active_hit_partition_mismatch:{entry_id}"
        resolutions = ledger_entry.get("hit_resolutions")
        if not isinstance(resolutions, list):
            return f"active_hit_resolutions_invalid:{entry_id}"
        resolution_ids = [
            resolution.get("hit_id")
            for resolution in resolutions
            if isinstance(resolution, dict)
        ]
        if resolution_ids != ledger_entry["all_hit_ids"]:
            return f"active_hit_resolutions_invalid:{entry_id}"
    return None




def _scan_machine_scene(work_dir: Path, scene_id: str) -> dict:
    review_dir = work_dir / "pipeline" / "review"
    directive_path = review_dir / f"{scene_id}.machine_directive.yaml"
    directive: dict | None = None
    if directive_path.exists():
        try:
            directive = _load_mapping(directive_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return _unknown_machine(f"directive_invalid:{exc}")

    lint_path = _latest_lint_path(work_dir, scene_id, directive)
    relative_lint = str(lint_path.relative_to(work_dir)) if lint_path.is_relative_to(work_dir) else str(lint_path)
    try:
        lint = _load_mapping(lint_path)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        return _unknown_machine(f"lint_missing_or_invalid:{exc}", relative_lint)

    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    if not scene_path.exists() or lint.get("input_text_sha256") != _sha256(scene_path):
        return _unknown_machine("lint_story_hash_mismatch", relative_lint)

    # Derive the required entries through the same pure projection used by the
    # dispatcher. Density contracts can require an entry below old cluster
    # thresholds; ordinary diagnostic alerts do not create machine obligations.
    from machine_directive import build_directive

    try:
        expected, _ = build_directive(work_dir, scene_id, lint_artifact=lint_path)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        return _unknown_machine(f"machine_projection_invalid:{exc}", relative_lint)
    enforced_alerts = [
        {"family": entry["family"], "hit_ids": entry["all_hit_ids"]}
        for entry in expected["entries"]
    ]
    if directive is None:
        if enforced_alerts:
            return _unknown_machine("enforced_alert_without_directive", relative_lint)
        return {
            "closed": True,
            "entry_states": [],
            "closure_modes": [],
            "lint_artifact": relative_lint,
        }

    ledger_path = review_dir / f"{scene_id}.machine_ledger.yaml"
    try:
        ledger = _load_mapping(ledger_path)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        return _unknown_machine(f"ledger_missing_or_invalid:{exc}", relative_lint)
    projection_error = _active_projection_error(
        work_dir, scene_id, directive, ledger, lint_path
    )
    if projection_error:
        return _unknown_machine(projection_error, relative_lint)

    entries = [
        entry for entry in directive.get("entries", []) or []
        if isinstance(entry, dict) and entry.get("level") in {"S", "M"}
    ]
    expected_by_family: dict[str, set[str]] = {}
    for item in enforced_alerts:
        expected_by_family.setdefault(item["family"], set()).update(item["hit_ids"])
    active_by_family: dict[str, set[str]] = {}
    active_seen_ids: set[str] = set()
    duplicate_active_id = False
    for entry in entries:
        family = str(entry.get("family") or "")
        ids = list(entry.get("all_hit_ids") or [])
        if active_seen_ids & set(ids):
            duplicate_active_id = True
        active_seen_ids.update(ids)
        active_by_family.setdefault(family, set()).update(ids)
    expected_projection = sorted(
        (family, tuple(sorted(ids))) for family, ids in expected_by_family.items()
    )
    active_projection = sorted(
        (family, tuple(sorted(ids))) for family, ids in active_by_family.items()
    )
    if duplicate_active_id or active_projection != expected_projection:
        return _unknown_machine(
            "enforced_alert_hit_ids_projection_mismatch",
            relative_lint,
        )
    if enforced_alerts and not entries:
        return _unknown_machine("enforced_alert_without_active_entry", relative_lint)
    if not entries:
        return {
            "closed": True,
            "entry_states": [],
            "closure_modes": [],
            "lint_artifact": relative_lint,
        }

    ledger_by_id = {
        entry.get("id"): entry
        for entry in ledger.get("entries", []) or []
        if isinstance(entry, dict) and entry.get("id")
    }
    states: list[str] = []
    details: list[dict] = []
    for entry in entries:
        entry_id = entry.get("id")
        ledger_entry = ledger_by_id.get(entry_id, {})
        state = _normalize_pair(entry.get("status"), ledger_entry.get("status"))
        states.append(state)
        details.append({"id": entry_id, "family": entry.get("family"), "state": state})
    closed = not any(state in OPEN_MACHINE_STATES for state in states)
    return {
        "closed": closed,
        "entry_states": states,
        "closure_modes": sorted(set(states) & CLOSED_MACHINE_STATES),
        "entries": details,
        "lint_artifact": relative_lint,
    }


def _scene_specs(work_dir: Path) -> tuple[list[dict], str | None]:
    try:
        return strict_phase6_scenes(work_dir), None
    except ValueError as exc:
        return [], str(exc)


def check(work_dir: Path) -> int:
    work_dir = work_dir.resolve()
    if not work_dir.is_dir():
        _warn(f"work_dir 不存在或不是目录: {work_dir}")
        return 2

    scene_specs, phase6_error = _scene_specs(work_dir)
    intent, intent_error = _run_intent(work_dir)
    skipped_checks, skip_errors = _skip_config(work_dir)
    reasons = [reason for reason in (phase6_error, intent_error) if reason]
    reasons.extend(skip_errors)
    try:
        protected_artifacts = protected_artifact_manifest(work_dir)
        protected_manifest_error = None
    except OSError as exc:
        protected_artifacts = None
        protected_manifest_error = f"protected_artifacts_invalid:{exc}"
        reasons.append(protected_manifest_error)
    scenes: list[dict] = []

    for scene_spec in scene_specs:
        scene_id = scene_spec["scene_id"]
        human = _scan_human_scene(work_dir, scene_id)
        machine = _scan_machine_scene(work_dir, scene_id)
        uncovered = [
            failure for failure in human["failures"]
            if failure["check"] not in skipped_checks
        ]
        human["skipped_failures"] = [
            failure for failure in human["failures"]
            if failure["check"] in skipped_checks
        ]
        human["closed"] = not uncovered
        human["uncovered_failures"] = uncovered
        if uncovered:
            reasons.extend(
                f"{scene_id}:human:{failure['check']}:{failure['reason']}"
                for failure in uncovered
            )
        if not machine["closed"]:
            reasons.append(
                f"{scene_id}:machine:{machine.get('reason') or machine.get('entry_states')}"
            )
        scenes.append({
            "scene_id": scene_id,
            "scene_path": scene_spec["scene_path"],
            "human": human,
            "machine": machine,
        })

    try:
        input_fingerprints = admission_input_manifest(work_dir, scenes)
        input_manifest_error = None
    except (OSError, ValueError) as exc:
        input_fingerprints = None
        input_manifest_error = f"admission_input_manifest_invalid:{exc}"
        reasons.append(input_manifest_error)

    phase7_admitted = (
        phase6_error is None
        and intent in VALID_RUN_INTENTS
        and not skip_errors
        and protected_manifest_error is None
        and input_manifest_error is None
        and all(scene["human"]["closed"] and scene["machine"]["closed"] for scene in scenes)
    )
    release_candidate = (
        phase7_admitted and intent == "release" and not skipped_checks
    )
    admission = {
        "schema_version": "release-eligibility-v1",
        "run_intent": intent,
        "phase7_admitted": phase7_admitted,
        "release_candidate": release_candidate,
        "skipped_checks": skipped_checks,
        "protected_artifacts": protected_artifacts,
        "input_fingerprints": input_fingerprints,
        "scenes": scenes,
        "reasons": reasons,
    }
    write_admission(work_dir, admission)

    if phase7_admitted:
        print(
            f"[verify_review_complete] admission PASS · intent={intent} "
            f"release_candidate={str(release_candidate).lower()}",
            file=sys.stderr,
        )
        return 0
    print("[verify_review_complete] admission FAIL", file=sys.stderr)
    for reason in reasons:
        print(f"  {reason}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        _warn("用法: verify_review_complete.py <work_dir>")
        return 2
    return check(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main())
