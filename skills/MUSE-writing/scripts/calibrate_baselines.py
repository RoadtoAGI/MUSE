#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

import yaml

from ai_filler_lint import (
    _coefficient_of_variation,
    _sentence_lengths,
    analyze,
    detect_lang,
)
from ai_policy import FAMILY_MANIFEST, RULE_TO_FAMILY, effective_policy, registry_hash

DENOMINATOR_VERSION = "chars-per-1k-v2"


def _scene_paths(kb_root: Path, works: set[str] | None = None) -> list[Path]:
    paths = sorted(
        p for p in (kb_root / "novels").glob("*/scenes/*.md")
        if not p.stem.endswith("_craft")
    )
    if works is None:
        return paths
    return [path for path in paths if path.parents[1].name in works]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 4)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    value = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(float(value), 4)


def _denominator(text: str, lang: str) -> float:
    # 与 aggregate_cluster_alerts 的 char_k 同口径（en 同 zh 按字符），
    # 否则基线与运行时 density 分母错位，抑制 gate 失真。
    return max(len(text) / 1000, 0.001)


def collect_family_densities(
    kb_root: Path,
    scene_paths: list[Path] | None = None,
) -> dict[str, dict[str, list[float]]]:
    densities: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for scene_path in _scene_paths(kb_root) if scene_paths is None else scene_paths:
        text = scene_path.read_text(encoding="utf-8")
        lang = detect_lang(text)
        result = analyze(text, scene_id=scene_path.stem, lang=lang)
        counts: Counter[str] = Counter()
        for hit in result.get("hits", []):
            family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
            # 无条件立案 family 不出基线——名著合法用例不得回填为容忍阈值
            policy = effective_policy(str(family), lang, hit.get("rule")) if family else {}
            if policy.get("registered") and policy.get("baseline_policy") != "exempt":
                counts[str(family)] += 1
        denom = _denominator(text, lang)
        eligible_families = sorted(
            family
            for family in FAMILY_MANIFEST
            if (
                (policy := effective_policy(family, lang)).get("registered")
                and policy.get("baseline_policy") != "exempt"
            )
        )
        for family in eligible_families:
            densities[lang][family].append(round(counts.get(family, 0) / denom, 4))
    return densities


def collect_sentence_cvs(
    kb_root: Path,
    scene_paths: list[Path] | None = None,
) -> dict[str, list[float]]:
    cvs: dict[str, list[float]] = defaultdict(list)
    for scene_path in _scene_paths(kb_root) if scene_paths is None else scene_paths:
        text = scene_path.read_text(encoding="utf-8")
        lang = detect_lang(text)
        lengths = _sentence_lengths(text, lang)
        if len(lengths) < 12:
            continue
        cvs[lang].append(round(_coefficient_of_variation(lengths), 4))
    return cvs


def _corpus_hash(kb_root: Path, scene_paths: list[Path] | None = None) -> str:
    digest = hashlib.sha256()
    for path in _scene_paths(kb_root) if scene_paths is None else scene_paths:
        digest.update(path.relative_to(kb_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _build_metrics(kb_root: Path, scene_paths: list[Path]) -> dict:
    densities = collect_family_densities(kb_root, scene_paths)
    sentence_cvs = collect_sentence_cvs(kb_root, scene_paths)
    output: dict = {}
    for lang in sorted(set(densities) | set(sentence_cvs)):
        output[lang] = {}
        if lang in sentence_cvs:
            values = sentence_cvs[lang]
            output[lang]["sentence_cv"] = {
                "p10": _percentile(values, 0.10),
                "p50": _percentile(values, 0.50),
                "p90": _percentile(values, 0.90),
                "samples": len(values),
            }
        family_values = densities.get(lang, {})
        for family, values in sorted(family_values.items()):
            positive = [value for value in values if value > 0]
            output[lang][family] = {
                "n_total": len(values),
                "n_positive": len(positive),
                "prevalence": round(len(positive) / len(values), 4) if values else 0.0,
                "p80_all": _percentile(values, 0.80),
                "p90_all": _percentile(values, 0.90),
                "p80_positive": _percentile(positive, 0.80),
                "p90_positive": _percentile(positive, 0.90),
                # Back-compatible aliases: the old p80/p90 semantics were positive-only.
                "p80": _percentile(positive, 0.80),
                "p90": _percentile(positive, 0.90),
                "samples": len(positive),
            }
    return output


def _split_result(kb_root: Path, scene_paths: list[Path], metrics: dict) -> dict:
    works = sorted({path.parents[1].name for path in scene_paths})
    return {
        "works": works,
        "samples": [path.relative_to(kb_root).as_posix() for path in scene_paths],
        "scene_count": len(scene_paths),
        "corpus_sha256": _corpus_hash(kb_root, scene_paths),
        "metrics": deepcopy(metrics),
    }


def build_calibration(kb_root: Path, held_out_works: set[str] | None = None) -> dict:
    held_out_works = set(held_out_works or set())
    all_paths = _scene_paths(kb_root)
    works = sorted({path.parents[1].name for path in all_paths})
    unknown_works = held_out_works - set(works)
    if unknown_works:
        raise ValueError(f"held-out work not found: {', '.join(sorted(unknown_works))}")

    train_works = [work for work in works if work not in held_out_works]
    if held_out_works and not train_works:
        raise ValueError("held-out split leaves no training work")

    train_paths = [path for path in all_paths if path.parents[1].name in train_works]
    held_out_paths = [path for path in all_paths if path.parents[1].name in held_out_works]
    train_metrics = _build_metrics(kb_root, train_paths)
    output = {
        "_schema_version": "ai-pattern-calibration-v2",
        "_provenance": {
            "corpus_sha256": _corpus_hash(kb_root, all_paths),
            "registry_sha256": registry_hash(),
            "denominator_version": DENOMINATOR_VERSION,
            "work_split": {
                "train": train_works,
                "held_out": sorted(held_out_works),
            },
        },
    }
    if held_out_works:
        held_out_metrics = _build_metrics(kb_root, held_out_paths)
        output["_split_results"] = {
            "train": _split_result(kb_root, train_paths, train_metrics),
            "held_out": _split_result(kb_root, held_out_paths, held_out_metrics),
        }
    output.update(train_metrics)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow calibrate AI-pattern baselines over KB scenes")
    parser.add_argument("--kb-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--held-out-work", action="append", default=[])
    args = parser.parse_args()

    if not args.kb_root.exists():
        print(f"[calibrate_baselines] ERROR: kb root not found: {args.kb_root}", file=sys.stderr)
        return 2

    try:
        calibration = build_calibration(args.kb_root, held_out_works=set(args.held_out_work))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(yaml.safe_dump(calibration, allow_unicode=True, sort_keys=False), encoding="utf-8")
    except Exception as exc:
        print(f"[calibrate_baselines] ERROR: {exc}", file=sys.stderr)
        return 2

    scene_count = len(_scene_paths(args.kb_root))
    print(f"✅ {args.out} · {scene_count} scenes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
