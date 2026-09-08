#!/usr/bin/env python3
"""Admission/terminal release eligibility state for the full writing pipeline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from protected_integrity import audit_terminal_integrity

STATE_RELATIVE_PATH = Path("pipeline/audit/release_eligibility.yaml")
HUMAN_SKIPPABLE_CHECKS = frozenset({
    "scene_review",
    "patch_application",
    "post_revision_review",
})
CLOSED_MACHINE_STATES = frozenset({"resolved", "objection_granted"})
GLOBAL_ADMISSION_INPUTS = frozenset({
    "pipeline/phase6_development.yaml",
    "pipeline/run_state.yaml",
    "pipeline/audit/skip_review.yaml",
    "pipeline/phase5_scenes.yaml",
})
SEMANTIC_REVIEW_REPORTS = (
    (
        Path("pipeline/review/A_aesthetic.manuscript.post_revision.yaml"),
        2,
        "pipeline/review/snapshots/story.semantic.round2.md",
    ),
    (
        Path("pipeline/review/A_aesthetic.manuscript.yaml"),
        1,
        "pipeline/review/snapshots/story.semantic.round1.md",
    ),
)


def canonical_digest(value: dict) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _story_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_artifact_manifest(work_dir: Path) -> list[dict]:
    """Fingerprint every authoritative protected declaration sidecar."""
    root = work_dir.resolve()
    artifacts: list[dict] = []
    for path in sorted((root / "pipeline").glob("scene_*/protected_integrity.yaml")):
        scene_id = path.parent.name.removeprefix("scene_")
        artifacts.append({
            "scene_id": scene_id,
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return artifacts


def strict_phase6_scenes(work_dir: Path) -> list[dict]:
    """Load the canonical Phase 6 scene index without dropping bad entries."""
    root = work_dir.resolve()
    path = root / "pipeline" / "phase6_development.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError) as exc:
        raise ValueError(f"phase6_development_missing_or_invalid:{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("phase6_development_top_level_must_be_mapping")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("phase6_development_missing_scenes")

    scenes: list[dict] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, raw in enumerate(raw_scenes):
        if not isinstance(raw, dict):
            raise ValueError(f"phase6_development_scene_not_mapping:{index}")
        legacy_id = raw.get("id")
        current_id = raw.get("scene_id")
        if legacy_id is not None and current_id is not None and legacy_id != current_id:
            raise ValueError(f"phase6_development_scene_id_conflict:{index}")
        scene_id = current_id if current_id is not None else legacy_id
        if (
            not isinstance(scene_id, str)
            or not scene_id
            or scene_id != scene_id.strip()
        ):
            raise ValueError(f"phase6_development_scene_id_invalid:{index}")
        expected_path = f"pipeline/scenes/scene_{scene_id}.md"
        file_path = raw.get("file_path")
        if file_path != expected_path:
            raise ValueError(
                f"phase6_development_scene_path_invalid:{scene_id}:{file_path!r}"
            )
        resolved = (root / expected_path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"phase6_development_scene_path_outside_work_dir:{scene_id}"
            ) from exc
        if scene_id in seen_ids:
            raise ValueError(f"phase6_development_duplicate_scene_id:{scene_id}")
        if expected_path in seen_paths:
            raise ValueError(f"phase6_development_duplicate_scene_path:{expected_path}")
        if not resolved.is_file():
            raise ValueError(f"phase6_development_scene_missing:{expected_path}")
        seen_ids.add(scene_id)
        seen_paths.add(expected_path)
        scenes.append({"scene_id": scene_id, "scene_path": expected_path})
    return scenes


def _safe_relative_input_path(work_dir: Path, raw_path: str) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("admission_input_path_invalid")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise ValueError(f"admission_input_path_absolute:{raw_path}")
    normalized = relative.as_posix()
    if (
        normalized in {"", "."}
        or ".." in relative.parts
        or normalized != raw_path
    ):
        raise ValueError(f"admission_input_path_invalid:{raw_path}")
    return normalized


def _admission_input_paths(work_dir: Path, scenes: list[dict]) -> list[str]:
    paths = set(GLOBAL_ADMISSION_INPUTS)
    seen_scene_ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("admission_scene_shape")
        scene_id = scene.get("scene_id")
        expected_scene_path = f"pipeline/scenes/scene_{scene_id}.md"
        if (
            not isinstance(scene_id, str)
            or not scene_id
            or scene_id in seen_scene_ids
            or scene.get("scene_path") != expected_scene_path
        ):
            raise ValueError("admission_scene_shape")
        seen_scene_ids.add(scene_id)
        paths.update({
            expected_scene_path,
            f"pipeline/review/scene_{scene_id}.yaml",
            f"pipeline/review/scene_{scene_id}.post_revision.yaml",
            f"pipeline/scene_{scene_id}/patch_directive.yaml",
            f"pipeline/scene_{scene_id}/patch_directive.applied.yaml",
            f"pipeline/scene_{scene_id}/revision_summary.md",
            f"pipeline/review/scene_{scene_id}.lint_resolution_ledger.yaml",
            f"pipeline/review/lint/{scene_id}.ai_filler.yaml",
            f"pipeline/review/lint/{scene_id}.ai_filler.v2.yaml",
            f"pipeline/review/{scene_id}.machine_directive.yaml",
            f"pipeline/review/{scene_id}.machine_ledger.yaml",
            f"pipeline/review/{scene_id}.protected_integrity.post_revision.yaml",
        })
        machine = scene.get("machine")
        lint_artifact = machine.get("lint_artifact") if isinstance(machine, dict) else None
        if lint_artifact is not None:
            paths.add(_safe_relative_input_path(work_dir, lint_artifact))
    return sorted(paths)


def admission_input_manifest(work_dir: Path, scenes: list[dict]) -> list[dict]:
    """Fingerprint the complete static admission input set, including absences."""
    root = work_dir.resolve()
    manifest: list[dict] = []
    for relative in _admission_input_paths(root, scenes):
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"admission_input_path_outside_work_dir:{relative}") from exc
        if path.exists() and not path.is_file():
            raise ValueError(f"admission_input_not_file:{relative}")
        present = path.is_file()
        manifest.append({
            "path": relative,
            "present": present,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if present else None,
        })
    return manifest


def _input_manifest_error(admission: dict) -> str | None:
    fingerprints = admission.get("input_fingerprints")
    scenes = admission.get("scenes")
    if not isinstance(fingerprints, list) or not isinstance(scenes, list):
        return "input_fingerprints_shape"
    paths: list[str] = []
    for item in fingerprints:
        if not isinstance(item, dict):
            return "input_fingerprints_shape"
        path = item.get("path")
        present = item.get("present")
        digest = item.get("sha256")
        if not isinstance(path, str) or not path:
            return "input_fingerprints_shape"
        if not isinstance(present, bool):
            return "input_fingerprints_shape"
        if present:
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                return "input_fingerprints_shape"
        elif digest is not None:
            return "input_fingerprints_shape"
        paths.append(path)
    if len(paths) != len(set(paths)):
        return "input_fingerprints_duplicate"
    if fingerprints != sorted(fingerprints, key=lambda item: item["path"]):
        return "input_fingerprints_order"
    try:
        expected_paths = _admission_input_paths(Path("."), scenes)
    except ValueError:
        return "input_fingerprints_scene_contract"
    if paths != expected_paths:
        return "input_fingerprints_path_set"
    return None


def state_path(work_dir: Path) -> Path:
    return work_dir / STATE_RELATIVE_PATH


def load_state(work_dir: Path) -> dict:
    path = state_path(work_dir)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def atomic_write_state(work_dir: Path, state: dict) -> None:
    path = state_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    os.replace(tmp_path, path)


def write_admission(work_dir: Path, admission: dict) -> None:
    """Keep the terminal when its admission input is unchanged."""
    if not isinstance(admission, dict):
        raise ValueError("admission must be a mapping")
    current = load_state(work_dir) if state_path(work_dir).exists() else {}
    if current.get("admission") == admission:
        return
    atomic_write_state(work_dir, {"admission": admission})


def _read_run_intent(work_dir: Path) -> str | None:
    path = work_dir / "pipeline" / "run_state.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    value = data.get("run_intent")
    return str(value) if value in {"smoke", "evaluation", "release"} else None


def _reader_skip_info(work_dir: Path) -> dict | None:
    path = work_dir / "pipeline" / "audit" / "reader_review_skip.yaml"
    if not path.exists():
        return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"present": True, "valid_yaml": False}
    return {"present": True, "valid_yaml": isinstance(value, dict), "record": value}


def _reader_review_state(work_dir: Path, story_sha256: str) -> dict:
    """Bind the existing reader-review/revision loop to the current manuscript."""
    review_path = work_dir / "pipeline" / "review" / "reader_review.yaml"
    skip_path = work_dir / "pipeline" / "audit" / "reader_review_skip.yaml"

    if not review_path.exists():
        if not skip_path.exists():
            return {"status": "incomplete", "reason": "reader_review_missing"}
        try:
            skip = yaml.safe_load(skip_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {"status": "incomplete", "reason": "reader_review_skip_invalid"}
        reason = skip.get("reason") if isinstance(skip, dict) else None
        if not isinstance(reason, str) or not reason.strip():
            return {"status": "incomplete", "reason": "reader_review_skip_reason_missing"}
        return {
            "status": "skipped",
            "skip_path": "pipeline/audit/reader_review_skip.yaml",
            "skip_sha256": hashlib.sha256(skip_path.read_bytes()).hexdigest(),
        }

    try:
        review = yaml.safe_load(review_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"status": "incomplete", "reason": "reader_review_invalid"}
    findings = review.get("reader_findings") if isinstance(review, dict) else None
    if not isinstance(findings, list):
        return {"status": "incomplete", "reason": "reader_findings_invalid"}

    base = {
        "review_path": "pipeline/review/reader_review.yaml",
        "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "finding_count": len(findings),
    }
    snapshot_relative = "pipeline/review/snapshots/story.semantic.round1.md"
    if review.get("input_snapshot") != snapshot_relative:
        return {"status": "incomplete", "reason": "reader_input_snapshot_missing", **base}
    snapshot_path = work_dir / snapshot_relative
    try:
        snapshot_sha = _story_hash(snapshot_path)
    except OSError:
        return {"status": "incomplete", "reason": "reader_snapshot_missing", **base}
    base["input_snapshot"] = snapshot_relative
    base["input_story_sha256"] = snapshot_sha
    if not findings and snapshot_sha == story_sha256:
        return {"status": "clean", **base}

    summary_path = work_dir / "pipeline" / "revision_summary.md"
    quality_path = work_dir / "pipeline" / "review" / "manuscript_quality.reader.round1.yaml"
    try:
        summary = summary_path.read_text(encoding="utf-8")
        quality = yaml.safe_load(quality_path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return {"status": "incomplete", "reason": "reader_revision_artifact_missing", **base}

    first_line = summary.splitlines()[0].strip() if summary.splitlines() else ""
    if first_line not in {"status: complete", "**status**: complete"}:
        return {"status": "incomplete", "reason": "reader_revision_not_complete", **base}
    if not isinstance(quality, dict):
        return {"status": "incomplete", "reason": "reader_revision_invalid", **base}
    provenance = quality.get("provenance") or {}
    provenance = provenance if isinstance(provenance, dict) else {}
    before = provenance.get("before") or {}
    after = provenance.get("after") or {}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {"status": "incomplete", "reason": "reader_revision_invalid", **base}
    if (
        quality.get("reader_review_sha256") != base["review_sha256"]
        or before.get("state") != "fresh"
        or before.get("actual_text_sha256") != snapshot_sha
        or quality.get("schema_version") != "revision-quality-v1"
        or quality.get("lane") != "manuscript"
        or after.get("state") != "fresh"
        or after.get("actual_text_sha256") != story_sha256
        or (quality.get("protected_results") or {}).get("verdict") != "PASS"
    ):
        return {"status": "incomplete", "reason": "reader_revision_not_bound_to_story", **base}
    return {
        "status": "revised",
        **base,
        "revision_summary_path": "pipeline/revision_summary.md",
        "revision_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "quality_path": "pipeline/review/manuscript_quality.reader.round1.yaml",
        "quality_sha256": hashlib.sha256(quality_path.read_bytes()).hexdigest(),
        "story_sha256": story_sha256,
    }


def _semantic_review_state(work_dir: Path) -> dict:
    """Resolve a current, bounded A-group manuscript review without trusting revision state."""
    story_path = work_dir / "story.md"
    try:
        story_bytes = story_path.read_bytes()
    except OSError:
        return {"status": "incomplete", "reason": "story_missing"}

    current: list[dict] = []
    stale: list[dict] = []
    invalid: list[str] = []
    valid_rounds: dict[int, tuple[dict, bytes, bool]] = {}
    seen_report = False
    for report_relative, expected_round, expected_snapshot in SEMANTIC_REVIEW_REPORTS:
        report_path = work_dir / report_relative
        if not report_path.exists():
            continue
        seen_report = True
        try:
            report = yaml.safe_load(report_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            invalid.append(f"{report_relative.as_posix()}:invalid_yaml")
            continue
        if not isinstance(report, dict):
            invalid.append(f"{report_relative.as_posix()}:top_level")
            continue

        findings = report.get("review_findings")
        coverage = report.get("coverage")
        summary = report.get("summary")
        semantic_status = report.get("semantic_review")
        planning_findings = [
            item for item in (findings or [])
            if isinstance(item, dict)
            and item.get("dimension") == "ai_pattern"
            and item.get("subkind") == "planning_trace_leakage"
        ]
        findings_valid = isinstance(findings, list) and all(
            isinstance(item, dict)
            and isinstance(item.get("dimension"), str)
            and (
                item.get("scene_id") is None
                or (isinstance(item.get("scene_id"), str) and item["scene_id"].strip())
            )
            and item.get("source") == "story"
            and all(
                isinstance(item.get(field), str) and item[field].strip()
                for field in ("location", "evidence_quote", "issue", "suggestion")
            )
            for item in (findings or [])
        )
        if (
            report.get("review_scope") != "manuscript"
            or report.get("review_round") != expected_round
            or report.get("input_snapshot") != expected_snapshot
            or not findings_valid
            or not isinstance(coverage, dict)
            or coverage.get("planning_trace_leakage") not in {"clear", "findings"}
            or (
                coverage.get("planning_trace_leakage") == "findings"
                and not planning_findings
            )
            or (
                planning_findings
                and coverage.get("planning_trace_leakage") != "findings"
            )
            or not isinstance(summary, dict)
            or summary.get("total_issues") != len(findings or [])
            or not isinstance(summary.get("by_dimension"), dict)
            or semantic_status not in {"clear", "findings"}
            or (
                semantic_status == "clear"
                and (findings or coverage.get("planning_trace_leakage") != "clear")
            )
            or (
                semantic_status == "findings"
                and not findings
            )
        ):
            invalid.append(f"{report_relative.as_posix()}:schema")
            continue

        snapshot_path = work_dir / expected_snapshot
        try:
            snapshot_bytes = snapshot_path.read_bytes()
        except OSError:
            invalid.append(f"{report_relative.as_posix()}:snapshot_missing")
            continue
        state = {
            "status": semantic_status,
            "report_path": report_relative.as_posix(),
            "review_round": expected_round,
            "input_snapshot": expected_snapshot,
            "finding_count": len(findings),
            "coverage": {"planning_trace_leakage": coverage["planning_trace_leakage"]},
        }
        is_current = snapshot_bytes == story_bytes
        valid_rounds[expected_round] = (state, snapshot_bytes, is_current)
        if is_current:
            current.append(state)
        else:
            stale.append(state)

    post_review = valid_rounds.get(2)
    if post_review and post_review[2]:
        initial_review = valid_rounds.get(1)
        if initial_review is None:
            return {
                "status": "incomplete",
                "reason": "semantic_post_review_without_valid_initial",
            }
        if post_review[1] == initial_review[1]:
            same_text_states = (post_review[0], initial_review[0])
            findings_state = next(
                (item for item in same_text_states if item["status"] == "findings"),
                None,
            )
            return findings_state or initial_review[0]

    if current:
        return current[0]
    if invalid:
        return {
            "status": "incomplete",
            "reason": "semantic_review_invalid",
            "details": invalid,
        }
    if stale:
        return {
            "status": "stale",
            "reason": "semantic_review_snapshot_not_current",
            "reports": [item["report_path"] for item in stale],
        }
    if seen_report:
        return {"status": "incomplete", "reason": "semantic_review_unusable"}
    return {"status": "not_run", "reason": "semantic_review_missing"}


def _overall_aigc_state(wholetext: dict, semantic_review: dict) -> str:
    if wholetext.get("verdict") == "FAIL" or semantic_review.get("status") == "findings":
        return "findings"
    if wholetext.get("verdict") in {"PASS", "REVIEW"} and semantic_review.get("status") == "clear":
        return "clear"
    return "incomplete"


def _admission_error(admission: dict, run_intent: str) -> str | None:
    """Recompute admission invariants instead of trusting summary booleans."""
    if admission.get("schema_version") != "release-eligibility-v1":
        return "schema_version"
    if admission.get("run_intent") != run_intent:
        return "run_intent"
    skipped = admission.get("skipped_checks")
    if (
        not isinstance(skipped, list)
        or any(not isinstance(item, str) for item in skipped)
        or not set(skipped).issubset(HUMAN_SKIPPABLE_CHECKS)
    ):
        return "skipped_checks"
    protected_artifacts = admission.get("protected_artifacts")
    if not isinstance(protected_artifacts, list):
        return "protected_artifacts_shape"
    seen_paths: set[str] = set()
    seen_scenes: set[str] = set()
    for item in protected_artifacts:
        if not isinstance(item, dict):
            return "protected_artifacts_shape"
        scene_id = item.get("scene_id")
        path = item.get("path")
        digest = item.get("sha256")
        if (
            not isinstance(scene_id, str)
            or not scene_id
            or path != f"pipeline/scene_{scene_id}/protected_integrity.yaml"
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            return "protected_artifacts_shape"
        if path in seen_paths or scene_id in seen_scenes:
            return "protected_artifacts_duplicate"
        seen_paths.add(path)
        seen_scenes.add(scene_id)
    if protected_artifacts != sorted(
        protected_artifacts,
        key=lambda item: (item["scene_id"], item["path"]),
    ):
        return "protected_artifacts_order"
    scenes = admission.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return "scenes"
    input_manifest_error = _input_manifest_error(admission)
    if input_manifest_error:
        return input_manifest_error
    derived_closed = True
    seen_scene_ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict) or not scene.get("scene_id"):
            return "scene_shape"
        scene_id = scene["scene_id"]
        if (
            not isinstance(scene_id, str)
            or scene_id in seen_scene_ids
            or scene.get("scene_path") != f"pipeline/scenes/scene_{scene_id}.md"
        ):
            return "scene_shape"
        seen_scene_ids.add(scene_id)
        human = scene.get("human")
        machine = scene.get("machine")
        if not isinstance(human, dict) or not isinstance(machine, dict):
            return "check_shape"
        human_closed = human.get("closed") is True
        machine_closed = machine.get("closed") is True
        states = machine.get("entry_states", [])
        if not isinstance(states, list) or any(not isinstance(value, str) for value in states):
            return "machine_states_shape"
        if machine_closed and any(value not in CLOSED_MACHINE_STATES for value in states):
            return "machine_closed_state_mismatch"
        derived_closed = derived_closed and human_closed and machine_closed
    if admission.get("phase7_admitted") is not derived_closed:
        return "phase7_admitted_mismatch"
    expected_candidate = derived_closed and run_intent == "release" and not skipped
    if admission.get("release_candidate") is not expected_candidate:
        return "release_candidate_mismatch"
    return None


def _terminal(
    *,
    outcome: str,
    eligible: bool,
    reason: str,
    story_sha256: str,
    admission_sha256: str,
    wholetext: dict,
    reader_skip: dict | None,
    reader_review: dict | None = None,
    semantic_review: dict | None = None,
    protected_integrity: dict | None = None,
) -> dict:
    semantic_review = semantic_review or {
        "status": "not_run",
        "reason": "semantic_review_not_evaluated",
    }
    result = {
        "outcome": outcome,
        "release_eligible": eligible,
        "reason": reason,
        "story_sha256": story_sha256,
        "admission_sha256": admission_sha256,
        "wholetext": wholetext,
        "semantic_review": semantic_review,
        "overall_aigc": _overall_aigc_state(wholetext, semantic_review),
    }
    if protected_integrity is not None:
        result["protected_integrity"] = protected_integrity
    if reader_skip is not None:
        result["reader_review_skip"] = reader_skip
    if reader_review is not None:
        result["reader_review"] = reader_review
    return result


def finalize(work_dir: Path, *, lang: str = "auto") -> int:
    """Run the live whole-text gate and bind its result to the current story/admission."""
    work_dir = work_dir.resolve()
    try:
        state = load_state(work_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError):
        return 2
    admission = state.get("admission")
    if not isinstance(admission, dict):
        return 2
    admission_sha = canonical_digest(admission)
    story = work_dir / "story.md"
    if not story.exists():
        return 2
    story_sha = _story_hash(story)

    run_intent = _read_run_intent(work_dir)
    if run_intent is None or run_intent != admission.get("run_intent"):
        terminal = _terminal(
            outcome="escalated",
            eligible=False,
            reason="run_intent_missing_or_changed",
            story_sha256=story_sha,
            admission_sha256=admission_sha,
            wholetext={"verdict": "NOT_RUN"},
            reader_skip=_reader_skip_info(work_dir),
            protected_integrity={"verdict": "NOT_RUN"},
        )
        atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
        return 2

    admission_error = _admission_error(admission, run_intent)
    if admission_error:
        terminal = _terminal(
            outcome="escalated",
            eligible=False,
            reason="admission_invalid",
            story_sha256=story_sha,
            admission_sha256=admission_sha,
            wholetext={"verdict": "NOT_RUN", "admission_error": admission_error},
            reader_skip=_reader_skip_info(work_dir),
            protected_integrity={"verdict": "NOT_RUN"},
        )
        atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
        return 2

    try:
        current_inputs = admission_input_manifest(work_dir, admission["scenes"])
    except (OSError, ValueError):
        current_inputs = None
    if current_inputs != admission.get("input_fingerprints"):
        terminal = _terminal(
            outcome="escalated",
            eligible=False,
            reason="admission_inputs_changed",
            story_sha256=story_sha,
            admission_sha256=admission_sha,
            wholetext={"verdict": "NOT_RUN"},
            reader_skip=_reader_skip_info(work_dir),
            protected_integrity={"verdict": "NOT_RUN"},
        )
        atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
        return 2

    try:
        current_protected_artifacts = protected_artifact_manifest(work_dir)
    except OSError:
        current_protected_artifacts = None
    if current_protected_artifacts != admission.get("protected_artifacts"):
        terminal = _terminal(
            outcome="escalated",
            eligible=False,
            reason="protected_artifacts_changed",
            story_sha256=story_sha,
            admission_sha256=admission_sha,
            wholetext={"verdict": "NOT_RUN"},
            reader_skip=_reader_skip_info(work_dir),
            protected_integrity={"verdict": "NOT_RUN"},
        )
        atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
        return 2

    protected_integrity = audit_terminal_integrity(
        work_dir,
        story.read_text(encoding="utf-8"),
    )
    if protected_integrity.get("verdict") != "PASS":
        terminal = _terminal(
            outcome="escalated",
            eligible=False,
            reason="protected_integrity_failed",
            story_sha256=story_sha,
            admission_sha256=admission_sha,
            wholetext={"verdict": "NOT_RUN"},
            reader_skip=_reader_skip_info(work_dir),
            protected_integrity=protected_integrity,
        )
        atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
        return 2

    gate = Path(__file__).resolve().parent / "wholetext_gate.py"
    result = subprocess.run(
        [
            sys.executable,
            str(gate),
            "--story",
            str(story),
            "--lang",
            lang,
            "--work-dir",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report_path = work_dir / "pipeline" / "review" / "wholetext_gate.yaml"
    try:
        report = yaml.safe_load(report_path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError, OSError):
        report = {}
    current_story_sha = _story_hash(story)
    wholetext = {
        "verdict": report.get("verdict", "ERROR"),
        "input_story_sha256": report.get("input_story_sha256"),
        "triggers": report.get("triggers", []),
        "observations": report.get("observations", []),
        "report_path": "pipeline/review/wholetext_gate.yaml",
    }

    reader_review = _reader_review_state(work_dir, current_story_sha)
    semantic_review = _semantic_review_state(work_dir)
    environment_error = (
        result.returncode not in {0, 1}
        or story_sha != current_story_sha
        or report.get("input_story_sha256") != current_story_sha
    )
    if environment_error:
        outcome, eligible, reason, rc = "escalated", False, "wholetext_execution_error", 2
    elif result.returncode == 1 or report.get("verdict") not in {"PASS", "REVIEW"}:
        outcome, eligible, reason, rc = "quality_failed", False, "live_wholetext_failed", 1
    elif admission.get("phase7_admitted") is not True:
        outcome, eligible, reason, rc = "escalated", False, "admission_not_closed", 2
    elif semantic_review.get("status") == "findings":
        outcome, eligible, reason, rc = "quality_failed", False, "live_semantic_review_findings", 1
    elif semantic_review.get("status") != "clear":
        outcome, eligible, reason, rc = "escalated", False, "semantic_review_incomplete", 2
    elif reader_review.get("status") == "incomplete":
        outcome, eligible, reason, rc = "escalated", False, "reader_review_incomplete", 2
    elif admission.get("release_candidate") is True and run_intent == "release":
        outcome, eligible, reason, rc = "released", True, "all_release_checks_passed", 0
    else:
        if admission.get("skipped_checks"):
            reason = "human_review_skipped"
        else:
            reason = f"run_intent_{run_intent}"
        outcome, eligible, rc = "completed_not_releasable", False, 1

    terminal = _terminal(
        outcome=outcome,
        eligible=eligible,
        reason=reason,
        story_sha256=current_story_sha,
        admission_sha256=admission_sha,
        wholetext=wholetext,
        reader_skip=_reader_skip_info(work_dir),
        reader_review=reader_review,
        semantic_review=semantic_review,
        protected_integrity=protected_integrity,
    )
    atomic_write_state(work_dir, {"admission": admission, "terminal": terminal})
    return rc


def validate_release(work_dir: Path) -> tuple[bool, str]:
    """Consumer-side three-condition validation plus terminal consistency."""
    try:
        state = load_state(work_dir.resolve())
    except (FileNotFoundError, ValueError, yaml.YAMLError):
        return False, "release_state_missing_or_invalid"
    admission = state.get("admission")
    terminal = state.get("terminal")
    if not isinstance(admission, dict) or not isinstance(terminal, dict):
        return False, "terminal_missing"
    if terminal.get("admission_sha256") != canonical_digest(admission):
        return False, "admission_digest_mismatch"
    story = work_dir.resolve() / "story.md"
    if not story.exists() or terminal.get("story_sha256") != _story_hash(story):
        return False, "story_hash_mismatch"
    if terminal.get("outcome") != "released" or terminal.get("release_eligible") is not True:
        return False, "terminal_not_released"
    wholetext = terminal.get("wholetext") or {}
    if wholetext.get("verdict") not in {"PASS", "REVIEW"} or wholetext.get("input_story_sha256") != terminal.get("story_sha256"):
        return False, "wholetext_binding_invalid"
    protected_integrity = terminal.get("protected_integrity") or {}
    if protected_integrity.get("verdict") != "PASS":
        return False, "protected_integrity_invalid"
    terminal_reader = terminal.get("reader_review")
    if not isinstance(terminal_reader, dict):
        return False, "reader_review_binding_missing"
    live_reader = _reader_review_state(work_dir.resolve(), terminal.get("story_sha256"))
    if (
        live_reader.get("status") == "incomplete"
        or canonical_digest(live_reader) != canonical_digest(terminal_reader)
    ):
        return False, "reader_review_binding_invalid"
    terminal_semantic = terminal.get("semantic_review")
    if not isinstance(terminal_semantic, dict):
        return False, "semantic_review_binding_missing"
    live_semantic = _semantic_review_state(work_dir.resolve())
    if (
        live_semantic.get("status") != "clear"
        or canonical_digest(live_semantic) != canonical_digest(terminal_semantic)
        or terminal.get("overall_aigc") != "clear"
    ):
        return False, "semantic_review_binding_invalid"
    try:
        current_inputs = admission_input_manifest(work_dir.resolve(), admission["scenes"])
    except (KeyError, OSError, ValueError):
        return False, "admission_input_manifest_invalid"
    if current_inputs != admission.get("input_fingerprints"):
        return False, "admission_input_manifest_mismatch"
    try:
        current_protected_artifacts = protected_artifact_manifest(work_dir.resolve())
    except OSError:
        return False, "protected_artifact_manifest_invalid"
    if current_protected_artifacts != admission.get("protected_artifacts"):
        return False, "protected_artifact_manifest_mismatch"
    live_protected = audit_terminal_integrity(
        work_dir.resolve(),
        story.read_text(encoding="utf-8"),
    )
    if (
        live_protected.get("verdict") != "PASS"
        or canonical_digest(live_protected) != canonical_digest(protected_integrity)
    ):
        return False, "protected_integrity_binding_invalid"
    if admission.get("run_intent") != "release" or admission.get("release_candidate") is not True:
        return False, "admission_not_release_candidate"
    if _admission_error(admission, "release") is not None:
        return False, "admission_invalid"
    return True, "released"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--work-dir", required=True, type=Path)
    finalize_parser.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "finalize":
        return finalize(args.work_dir, lang=args.lang)
    ok, reason = validate_release(args.work_dir)
    print(("PASS " if ok else "FAIL ") + reason)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
