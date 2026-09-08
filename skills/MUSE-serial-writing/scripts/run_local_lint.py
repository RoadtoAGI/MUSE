#!/usr/bin/env python3
"""Run ai_filler_lint on a patch's old and new span."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from ai_filler_lint import analyze  # noqa: E402


def _load_patch(work_dir: Path, scene_id: str, patch_id: str) -> dict:
    scene_dir = work_dir / "pipeline" / f"scene_{scene_id}"
    for name in ("patch_directive.applied.yaml", "patch_directive.yaml"):
        path = scene_dir / name
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for patch in doc.get("patches", []):
            if patch.get("patch_id") == patch_id:
                return patch
            if str(patch.get("issue_id", "")).startswith(patch_id):
                return patch
    raise ValueError(f"patch {patch_id} not found for scene {scene_id}")


def _extract_new_span(work_dir: Path, scene_id: str, patch: dict) -> str:
    scene_md = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    lines = scene_md.read_text(encoding="utf-8").splitlines()
    line_range = patch.get("location", {}).get("line_range")
    if not (
        isinstance(line_range, list)
        and len(line_range) == 2
        and all(isinstance(n, int) for n in line_range)
    ):
        raise ValueError("patch location.line_range is required")
    start, end = line_range
    return "\n".join(lines[start - 1 : end])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--patch-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--output-v2", required=True, type=Path)
    args = parser.parse_args()

    work_dir = args.work_dir.resolve()
    try:
        patch = _load_patch(work_dir, args.scene_id, args.patch_id)
        old_span = patch.get("old_span") or patch.get("anchor_quote") or ""
        if not old_span:
            raise ValueError("patch old_span or anchor_quote is required")
        new_span = _extract_new_span(work_dir, args.scene_id, patch)
    except (OSError, ValueError) as exc:
        print(f"[run_local_lint] ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output_v2.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(analyze(old_span), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    args.output_v2.write_text(
        yaml.safe_dump(analyze(new_span), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
