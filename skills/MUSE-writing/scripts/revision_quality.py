#!/usr/bin/env python3
"""Deterministic audit measurements for revision quality.

The report covers text shape, raw lint density, before/after retention, and
uniform low-dose family distribution. Manuscript reports also carry the live
protected-integrity result; retention and texture observations remain audit-only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_RETENTION_THRESHOLD = 0.85
SHRINKAGE_AUDIT_LANES = frozenset({"distribution", "manuscript"})

_SENTENCE_BREAK_RE = re.compile(r"(?:[。！？!?]+|[.]+(?=\s|$))")
_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n+")
_LINT_HASH_KEYS = ("input_text_sha256", "input_story_sha256")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ratio(after: int | float, before: int | float) -> float | None:
    if before == 0:
        return None
    return round(after / before, 4)


def _exact_ratio(after: int | float, before: int | float) -> float | None:
    if before == 0:
        return None
    return after / before


def count_text_shape(text: str) -> dict[str, int]:
    """Count code-point characters, sentence units, and paragraph blocks."""
    stripped = text.strip()
    if not stripped:
        return {"chars": len(text), "sentences": 0, "paragraphs": 0}

    sentence_chunks = [
        chunk for chunk in _SENTENCE_BREAK_RE.split(stripped) if chunk.strip()
    ]
    paragraph_chunks = [
        chunk for chunk in _PARAGRAPH_BREAK_RE.split(stripped) if chunk.strip()
    ]
    return {
        "chars": len(text),
        "sentences": len(sentence_chunks),
        "paragraphs": len(paragraph_chunks),
    }


def _raw_hits(lint: Mapping[str, Any]) -> list[Any]:
    hits = lint.get("hits")
    if isinstance(hits, list):
        return hits
    lint_hits = lint.get("lint_hits")
    return lint_hits if isinstance(lint_hits, list) else []


def raw_hit_metrics(lint: Mapping[str, Any], *, chars: int) -> dict[str, int | float | None]:
    """Return unfiltered hit count and its density per 1,000 characters."""
    raw_hits = len(_raw_hits(lint))
    density = round(raw_hits / chars * 1000, 4) if chars else None
    return {"raw_hits": raw_hits, "density_per_1k": density}


def _declared_input_hash(lint: Mapping[str, Any]) -> str | None:
    for key in _LINT_HASH_KEYS:
        value = lint.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def lint_provenance(text: str, lint: Mapping[str, Any]) -> dict[str, str | None]:
    """Compare a lint artifact's declared input hash with the supplied text."""
    actual = _sha256(text)
    declared = _declared_input_hash(lint)
    if declared is None:
        state = "missing"
    elif declared == actual:
        state = "fresh"
    else:
        state = "stale"
    return {
        "state": state,
        "actual_text_sha256": actual,
        "declared_input_sha256": declared,
    }


def _combined_provenance_state(states: Sequence[str]) -> str:
    if any(state == "stale" for state in states):
        return "stale"
    if any(state == "missing" for state in states):
        return "missing"
    return "fresh"


def _retention(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, float | None]:
    return {
        key: _ratio(after[key], before[key])
        for key in ("chars", "sentences", "paragraphs")
    }


def _delta(
    before: Mapping[str, int | float | None],
    after: Mapping[str, int | float | None],
) -> dict[str, int | float | None]:
    result: dict[str, int | float | None] = {}
    for key in ("chars", "sentences", "paragraphs", "raw_hits", "density_per_1k"):
        before_value = before[key]
        after_value = after[key]
        if before_value is None or after_value is None:
            result[key] = None
        elif isinstance(before_value, int) and isinstance(after_value, int):
            result[key] = after_value - before_value
        else:
            result[key] = round(float(after_value) - float(before_value), 4)
    return result


def _shrinkage_observation(
    lane: str,
    value: float | None,
    threshold: float,
) -> dict[str, Any] | None:
    if lane not in SHRINKAGE_AUDIT_LANES or value is None or value >= threshold:
        return None
    return {
        "kind": "retention_below_threshold",
        "lane": lane,
        "level": "OBSERVE",
        "audit_only": True,
        "blocking": False,
        "value": value,
        "threshold": threshold,
    }


def build_revision_quality(
    before_text: str,
    after_text: str,
    before_lint: Mapping[str, Any],
    after_lint: Mapping[str, Any],
    *,
    lane: str,
    retention_threshold: float = DEFAULT_RETENTION_THRESHOLD,
) -> dict[str, Any]:
    """Build a deterministic before/after measurement report.

    The result is audit-only and intentionally has no ``verdict`` or
    ``exit_code`` field.
    """
    before_shape = count_text_shape(before_text)
    after_shape = count_text_shape(after_text)
    before = {**before_shape, **raw_hit_metrics(before_lint, chars=before_shape["chars"])}
    after = {**after_shape, **raw_hit_metrics(after_lint, chars=after_shape["chars"])}
    retention = _retention(before_shape, after_shape)

    before_provenance = lint_provenance(before_text, before_lint)
    after_provenance = lint_provenance(after_text, after_lint)
    provenance = {
        "state": _combined_provenance_state(
            [str(before_provenance["state"]), str(after_provenance["state"])]
        ),
        "before": before_provenance,
        "after": after_provenance,
    }

    observation = _shrinkage_observation(
        lane,
        _exact_ratio(after_shape["chars"], before_shape["chars"]),
        retention_threshold,
    )
    return {
        "schema_version": "revision-quality-v1",
        "lane": lane,
        "audit_only": True,
        "before": before,
        "after": after,
        "delta": _delta(before, after),
        "retention": retention,
        "provenance": provenance,
        "observations": [observation] if observation else [],
    }


def attach_audit_observations(
    report: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Attach audit observations without mutating or re-deciding a report."""
    attached = deepcopy(dict(report))
    existing = attached.get("audit_observations")
    merged = list(existing) if isinstance(existing, list) else []
    merged.extend(deepcopy(list(observations)))
    attached["audit_observations"] = merged
    return attached


def build_family_scene_low_dose_matrix(
    scenes: Mapping[str, Mapping[str, Any]],
    family_density_thresholds: Mapping[str, float],
) -> dict[str, Any]:
    """Build a deterministic family-by-scene low-dose observation matrix.

    A family is uniformly low-dose only when it is present below its density
    threshold in every scene and every lint artifact is fresh.  Stale or
    missing provenance remains visible and suppresses the observation.
    """
    scene_ids = sorted(str(scene_id) for scene_id in scenes)
    scene_provenance: dict[str, dict[str, str | None]] = {}
    scene_shapes: dict[str, dict[str, int]] = {}
    scene_hits: dict[str, list[Any]] = {}

    for scene_id in scene_ids:
        record = scenes[scene_id]
        text = str(record.get("text") or "")
        lint = record.get("lint")
        lint_mapping = lint if isinstance(lint, Mapping) else {}
        scene_shapes[scene_id] = count_text_shape(text)
        scene_hits[scene_id] = _raw_hits(lint_mapping)
        scene_provenance[scene_id] = lint_provenance(text, lint_mapping)

    provenance_state = _combined_provenance_state(
        [str(item["state"]) for item in scene_provenance.values()]
    )
    families: dict[str, Any] = {}
    for family in sorted(str(name) for name in family_density_thresholds):
        threshold = float(family_density_thresholds[family])
        cells: dict[str, Any] = {}
        for scene_id in scene_ids:
            family_hits = [
                hit
                for hit in scene_hits[scene_id]
                if isinstance(hit, Mapping) and hit.get("family") == family
            ]
            raw_hits = len(family_hits)
            chars = scene_shapes[scene_id]["chars"]
            density = round(raw_hits / chars * 1000, 4) if chars else None
            present = raw_hits > 0
            low_dose = present and density is not None and density < threshold
            cells[scene_id] = {
                "raw_hits": raw_hits,
                "density_per_1k": density,
                "present": present,
                "low_dose": low_dose,
                "provenance_state": scene_provenance[scene_id]["state"],
            }

        candidate = bool(scene_ids) and all(cell["low_dose"] for cell in cells.values())
        auditable = bool(scene_ids) and all(
            cell["provenance_state"] == "fresh" for cell in cells.values()
        )
        uniform = candidate and auditable
        observation = None
        if uniform:
            observation = {
                "kind": "uniform_low_dose_distribution",
                "family": family,
                "scene_ids": list(scene_ids),
                "threshold_density_per_1k": threshold,
                "level": "OBSERVE",
                "audit_only": True,
                "blocking": False,
            }
        families[family] = {
            "threshold_density_per_1k": threshold,
            "cells": cells,
            "candidate_uniform_low_dose": candidate,
            "auditable": auditable,
            "uniform_low_dose": uniform,
            "observation": observation,
        }

    return {
        "schema_version": "family-scene-low-dose-v1",
        "audit_only": True,
        "scene_ids": scene_ids,
        "provenance_state": provenance_state,
        "provenance": scene_provenance,
        "families": families,
    }


def snapshot_text(source: Path, out: Path) -> None:
    """Create an immutable, idempotent text snapshot."""
    payload = source.read_bytes()
    if out.exists():
        if out.read_bytes() != payload:
            raise ValueError(f"snapshot already exists with different content: {out}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    try:
        tmp.write_bytes(payload)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)


def _atomic_write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            yaml.safe_dump(dict(value), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _analyze_text(text: str, lang: str, scene_id: str) -> dict[str, Any]:
    from ai_filler_lint import analyze, detect_lang

    selected = detect_lang(text) if lang == "auto" else lang
    return analyze(text, scene_id=scene_id, lang=selected)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--source", type=Path, required=True)
    snapshot_parser.add_argument("--out", type=Path, required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--before-text", type=Path, required=True)
    audit_parser.add_argument("--after-text", type=Path, required=True)
    audit_parser.add_argument(
        "--lane", choices=["scene", "distribution", "manuscript"], required=True
    )
    audit_parser.add_argument("--work-dir", type=Path)
    audit_parser.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")
    audit_parser.add_argument("--out", type=Path, required=True)
    audit_parser.add_argument("--reader-report", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "snapshot":
            snapshot_text(args.source, args.out)
            return 0
        before_text = args.before_text.read_text(encoding="utf-8")
        after_text = args.after_text.read_text(encoding="utf-8")
        before_lint = _analyze_text(before_text, args.lang, "REVISION_BEFORE")
        after_lint = _analyze_text(after_text, args.lang, "REVISION_AFTER")
        report = build_revision_quality(
            before_text,
            after_text,
            before_lint,
            after_lint,
            lane=args.lane,
        )
        rc = 0
        if args.lane == "manuscript":
            if args.work_dir is None:
                raise ValueError("--work-dir is required for manuscript audit")
            from protected_integrity import audit_terminal_integrity

            protected_results = audit_terminal_integrity(
                args.work_dir.resolve(),
                after_text,
            )
            report["protected_results"] = protected_results
            if args.reader_report is not None:
                reader_bytes = args.reader_report.read_bytes()
                reader = yaml.safe_load(reader_bytes)
                if not isinstance(reader, dict) or not isinstance(reader.get("reader_findings"), list):
                    raise ValueError("reader report is invalid")
                snapshot = args.work_dir / "pipeline/review/snapshots/story.semantic.round1.md"
                if reader.get("input_snapshot") != "pipeline/review/snapshots/story.semantic.round1.md" or snapshot.read_text(encoding="utf-8") != before_text:
                    raise ValueError("reader report does not refer to the revision input")
                report["reader_review_sha256"] = hashlib.sha256(reader_bytes).hexdigest()
            if protected_results.get("verdict") != "PASS":
                rc = 2
        _atomic_write_yaml(args.out, report)
        return rc
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"[revision_quality] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
