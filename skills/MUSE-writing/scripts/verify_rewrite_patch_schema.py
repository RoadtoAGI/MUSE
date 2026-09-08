#!/usr/bin/env python3
"""Validate rewrite patch schema before reviser dispatch."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from protected_integrity import (
    ProtectedIntegrityError,
    collect_patch_declarations,
    snapshot_patch_documents,
)

REWRITE_KINDS = {"rewrite_sentence", "rewrite_span"}
REWRITE_DIRECTIVE_FIELDS = {
    "semantic_function",
    "preserve",
    "remove_patterns",
    "target_style",
}


def _scene_id_from_patch_path(path: Path) -> str:
    return path.parent.name.replace("scene_", "")


def _valid_line_range(location: object) -> bool:
    if not isinstance(location, dict):
        return False
    line_range = location.get("line_range")
    return (
        isinstance(line_range, list)
        and len(line_range) == 2
        and all(isinstance(n, int) and n >= 1 for n in line_range)
        and line_range[0] <= line_range[1]
    )


def check(work_dir: Path, scene_id: str | None = None) -> int:
    errors: list[str] = []
    protected_documents: list[tuple[str, dict]] = []
    pipeline_dir = work_dir / "pipeline"
    if scene_id is not None:
        if Path(scene_id).name != scene_id or scene_id in {".", ".."}:
            print("scene_id invalid", file=sys.stderr)
            return 2
        patch_files = [pipeline_dir / f"scene_{scene_id}" / "patch_directive.yaml"]
        if not patch_files[0].is_file():
            print(f"missing patch_directive: {patch_files[0]}", file=sys.stderr)
            return 2
    else:
        patch_files = sorted(pipeline_dir.glob("scene_*/patch_directive.yaml"))

    for patch_path in patch_files:
        scene_id = _scene_id_from_patch_path(patch_path)
        scene_md = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
        if not scene_md.exists():
            errors.append(f"{patch_path}: missing scene body {scene_md}")
            continue
        scene_text = scene_md.read_text(encoding="utf-8")

        try:
            patch_doc = yaml.safe_load(patch_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{patch_path}: YAML parse failed: {exc}")
            continue
        if not isinstance(patch_doc, dict):
            errors.append(f"{patch_path}: top level must be mapping")
            continue

        application_id = patch_doc.get("application_id") or patch_doc.get("review_round")
        if not isinstance(application_id, str) or not application_id.strip():
            errors.append(
                f"{patch_path}: application_id required "
                "(review_round accepted for legacy producers)"
            )

        patches = patch_doc.get("patches")
        if not isinstance(patches, list):
            errors.append(f"{patch_path}: patches must be list")
            patches = []
        seen_patch_ids: set[str] = set()
        for idx, patch in enumerate(patches):
            if not isinstance(patch, dict):
                errors.append(f"{patch_path}#{idx}: patch must be mapping")
                continue
            patch_id = patch.get("patch_id")
            if not isinstance(patch_id, str) or not patch_id.strip():
                errors.append(f"{patch_path}#{idx}: patch_id required")
            elif patch_id in seen_patch_ids:
                errors.append(f"{patch_path}#{idx}: duplicate patch_id {patch_id!r}")
            else:
                seen_patch_ids.add(patch_id)

        try:
            collect_patch_declarations(patch_doc)
        except ProtectedIntegrityError as exc:
            errors.append(f"{patch_path}: protected_integrity: {exc}")
        else:
            protected_documents.append((scene_id, patch_doc))

        for idx, patch in enumerate(patches):
            if not isinstance(patch, dict):
                continue
            patch_kind = patch.get("patch_kind")
            if patch_kind not in REWRITE_KINDS:
                continue

            rewrite_directive = patch.get("rewrite_directive") or {}
            if not isinstance(rewrite_directive, dict):
                errors.append(f"{patch_path}#{idx}: rewrite_directive must be mapping")
                rewrite_directive = {}
            missing = REWRITE_DIRECTIVE_FIELDS - set(rewrite_directive)
            if missing:
                errors.append(f"{patch_path}#{idx}: rewrite_directive missing {sorted(missing)}")

            if patch.get("location") is not None and not _valid_line_range(patch["location"]):
                errors.append(f"{patch_path}#{idx}: location.line_range invalid")

            if patch_kind == "rewrite_sentence":
                anchor_quote = patch.get("anchor_quote") or ""
                if not anchor_quote.strip():
                    errors.append(f"{patch_path}#{idx}: anchor_quote required")
                if anchor_quote and anchor_quote not in scene_text:
                    errors.append(f"{patch_path}#{idx}: anchor_quote not found in scene_{scene_id}.md")
                if anchor_quote and scene_text.count(anchor_quote) > 1 and not _valid_line_range(patch.get("location")):
                    errors.append(f"{patch_path}#{idx}: repeated anchor_quote requires location.line_range")
                continue

            anchor_start = patch.get("anchor_quote_start") or ""
            anchor_end = patch.get("anchor_quote_end") or ""
            old_span = patch.get("old_span") or ""

            if not anchor_start.strip() or not anchor_end.strip():
                errors.append(f"{patch_path}#{idx}: anchor_quote_start/end required")
            if not old_span:
                errors.append(f"{patch_path}#{idx}: old_span required")
                continue
            if anchor_start not in old_span or anchor_end not in old_span:
                errors.append(f"{patch_path}#{idx}: old_span must contain anchor_quote_start and anchor_quote_end")
            stripped = old_span.strip()
            if not stripped.startswith(anchor_start) or not stripped.endswith(anchor_end):
                errors.append(f"{patch_path}#{idx}: old_span boundary inconsistent with anchors")
            if old_span not in scene_text:
                errors.append(f"{patch_path}#{idx}: old_span not found in scene_{scene_id}.md")
            if scene_text.count(old_span) > 1 and not _valid_line_range(patch.get("location")):
                errors.append(f"{patch_path}#{idx}: repeated old_span requires location.line_range")

    if not errors:
        try:
            snapshot_patch_documents(work_dir, protected_documents)
        except ProtectedIntegrityError as exc:
            errors.append(f"protected_integrity: {exc}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--scene-id", help="Validate only the dispatched scene")
    args = parser.parse_args(argv[1:])
    return check(args.work_dir, args.scene_id)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
