#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from family_gate import evaluate_regression
from protected_integrity import (
    ProtectedIntegrityError,
    append_token_verifications,
    audit_scene_revision_integrity,
)
from revision_quality import attach_audit_observations, build_revision_quality


# KB 名著基线校准：场景全量 hits 密度 P90 ≈ 10.5/1k（P80 7.9 / P95 13.3）——
# 分布修复后的场景至少要达到名著 P90 水位。
ABS_CAPS = {"hits_per_1k": 10.5}
BLOCKING_SEVERITIES = {"high", "catastrophic", "major"}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp_path, path)


def _lint_path(work_dir: Path, scene_id: str, suffix: str) -> Path:
    return work_dir / "pipeline" / "review" / "lint" / f"{scene_id}.ai_filler.{suffix}.yaml"


def _post_dist_path(work_dir: Path, scene_id: str, attempt: int) -> Path:
    return _lint_path(work_dir, scene_id, f"dist{attempt}")


def _summary_status(summary_text: str) -> str | None:
    for line in summary_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**status**:"):
            return stripped.split(":", 1)[1].strip()
    return None


def _pending_ids(directive: dict) -> set[str]:
    return {
        entry.get("id")
        for entry in directive.get("entries", []) or []
        if isinstance(entry, dict) and entry.get("status") == "pending" and entry.get("id")
    }


def _target_families(directive: dict) -> set[str]:
    """Return active enforced repair targets from the current directive."""
    targets: set[str] = set()
    for entry in directive.get("entries", []) or []:
        if not isinstance(entry, dict) or entry.get("status") != "pending":
            continue
        remaining = entry.get("remaining_hit_ids")
        if isinstance(remaining, list) and not remaining:
            continue
        family = entry.get("family")
        if family:
            targets.add(str(family))
    return targets


def _set_entry_status(directive: dict, ledger: dict, status: str) -> None:
    ids = _pending_ids(directive)
    if not ids:
        return
    for entry in directive.get("entries", []) or []:
        if isinstance(entry, dict) and entry.get("id") in ids:
            entry["status"] = status
    for entry in ledger.get("entries", []) or []:
        if isinstance(entry, dict) and entry.get("id") in ids:
            entry["status"] = status


def _protected_regions_declared(directive: dict, summary_text: str, status: str | None) -> bool:
    if status not in {"complete", "partial"}:
        return False
    for region in directive.get("protected_regions", []) or []:
        if not isinstance(region, dict):
            continue
        patch_id = region.get("patch_id")
        if patch_id and str(patch_id) not in summary_text:
            return False
    return True


def evaluate(work_dir: Path, scene_id: str, attempt: int, max_attempts: int) -> tuple[int, dict]:
    review_dir = work_dir / "pipeline" / "review"
    pre = _load_yaml(_lint_path(work_dir, scene_id, "pre_dist"))
    post = _load_yaml(_post_dist_path(work_dir, scene_id, attempt))
    directive = _load_yaml(review_dir / f"{scene_id}.machine_directive.yaml")
    ledger = _load_yaml(review_dir / f"{scene_id}.machine_ledger.yaml")

    scene_text = (work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md").read_text(
        encoding="utf-8"
    )
    snapshot_path = review_dir / "snapshots" / f"{scene_id}.pre_dist.md"
    protected_path = work_dir / "pipeline" / f"scene_{scene_id}" / "protected_integrity.yaml"
    if snapshot_path.exists():
        before_text = snapshot_path.read_text(encoding="utf-8")
        protected_results = audit_scene_revision_integrity(
            work_dir,
            scene_id,
            before_text,
            scene_text,
        )
        snapshot_source = str(snapshot_path.relative_to(work_dir))
        if (
            protected_results["verdict"] == "PASS"
            and protected_results.get("active_tokens_after")
        ):
            try:
                append_token_verifications(
                    work_dir,
                    scene_id,
                    scene_text,
                    protected_results["active_tokens_after"],
                )
            except ProtectedIntegrityError as exc:
                protected_results["verdict"] = "FAIL"
                protected_results["reason"] = f"token_anchor_advance_failed:{exc}"
    else:
        before_text = scene_text
        snapshot_source = "compat_current_text"
        if protected_path.exists():
            protected_results = {
                "verdict": "FAIL",
                "reason": f"pre_dist_snapshot_missing:{snapshot_path}",
                "literal_results": [],
                "active_relations_before": [],
                "active_relations_after": [],
                "relation_overlaps": [],
            }
        else:
            protected_results = audit_scene_revision_integrity(
                work_dir,
                scene_id,
                before_text,
                scene_text,
            )
    revision_quality = build_revision_quality(
        before_text,
        scene_text,
        pre,
        post,
        lane="distribution",
    )
    revision_quality["before_snapshot"] = snapshot_source
    summary_path = work_dir / "pipeline" / f"scene_{scene_id}" / "distribution_summary.md"
    summary_text = summary_path.read_text(encoding="utf-8")
    summary_status = _summary_status(summary_text)

    blocking_alerts = [
        alert
        for alert in post.get("cluster_alerts", []) or []
        if isinstance(alert, dict)
        and str(alert.get("severity") or "").lower() in BLOCKING_SEVERITIES
    ]
    hit_count = len(post.get("hits", []) or [])
    hits_per_1k = round(hit_count / max(len(scene_text), 1) * 1000, 2)
    language = str(post.get("language") or pre.get("language") or "zh")
    targets = _target_families(directive)
    family_regression = evaluate_regression(pre, post, targets, lang=language)
    protected_ok = _protected_regions_declared(directive, summary_text, summary_status)

    checks = [
        {
            "name": "high_cluster_observation",
            "ok": not blocking_alerts,
            "blocking": False,
            "alerts": blocking_alerts,
        },
        {
            "name": "density_observation",
            "ok": hits_per_1k <= ABS_CAPS["hits_per_1k"],
            "blocking": False,
            "value": hits_per_1k,
            "cap": ABS_CAPS["hits_per_1k"],
        },
        {
            "name": "family_non_regression",
            "ok": family_regression["verdict"] == "PASS",
            "blocking": True,
            "blocking_families": family_regression["blocking_families"],
        },
        {
            "name": "protected_regions_declared",
            "ok": protected_ok,
            "blocking": True,
            "summary_status": summary_status,
        },
        {
            "name": "protected_integrity",
            "ok": protected_results["verdict"] == "PASS",
            "blocking": True,
            "reason": protected_results.get("reason"),
        },
    ]
    hard_checks_pass = all(check["ok"] for check in checks if check.get("blocking"))
    verdict = "PASS" if hard_checks_pass and summary_status == "complete" else "FAIL"
    report = {
        "scene_id": scene_id,
        "attempt": attempt,
        "verdict": verdict,
        "checks": checks,
        "family_regression": family_regression,
        "revision_quality": revision_quality,
        "protected_results": protected_results,
    }
    report = attach_audit_observations(report, revision_quality["observations"])

    if verdict == "PASS":
        _set_entry_status(directive, ledger, "resolved")
    elif attempt >= max_attempts:
        _set_entry_status(directive, ledger, "escalated")

    _atomic_write_yaml(review_dir / f"{scene_id}.distribution_gate.yaml", report)
    _atomic_write_yaml(review_dir / f"{scene_id}.machine_directive.yaml", directive)
    _atomic_write_yaml(review_dir / f"{scene_id}.machine_ledger.yaml", ledger)

    return (0 if verdict == "PASS" else 1), report


def main() -> int:
    parser = argparse.ArgumentParser(description="Composite acceptance gate for distribution revision")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args()

    try:
        rc, report = evaluate(
            args.work_dir.resolve(), args.scene_id, args.attempt, args.max_attempts
        )
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[distribution_gate] ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"{report['verdict']} distribution_gate scene={args.scene_id} attempt={args.attempt}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
