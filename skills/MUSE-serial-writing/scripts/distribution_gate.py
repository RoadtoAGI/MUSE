#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from family_gate import _families


# Historical reference density helps locate candidates; it does not establish a defect.
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
    new_families = sorted(_families(post) - _families(pre))
    protected_ok = _protected_regions_declared(directive, summary_text, summary_status)

    checks = [
        {"name": "high_cluster_observation", "ok": not blocking_alerts, "blocking": False},
        {
            "name": "density_observation",
            "blocking": False,
            "ok": hits_per_1k <= ABS_CAPS["hits_per_1k"],
            "value": hits_per_1k,
            "cap": ABS_CAPS["hits_per_1k"],
        },
        {"name": "family_observation", "ok": not new_families, "blocking": False, "new_families": new_families},
        {
            "name": "protected_regions_declared",
            "blocking": True,
            "ok": protected_ok,
            "summary_status": summary_status,
        },
    ]
    verdict = "PASS" if all(check["ok"] for check in checks if check.get("blocking")) and summary_status == "complete" else "FAIL"
    report = {"scene_id": scene_id, "attempt": attempt, "verdict": verdict,
              "assessment": "execution_contract", "checks": checks}

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
