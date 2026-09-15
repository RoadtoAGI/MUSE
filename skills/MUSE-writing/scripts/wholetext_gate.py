#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

import re

from ai_filler_lint import _en_words, _mask_quoted_spans, analyze, detect_lang
from ai_policy import RULE_TO_FAMILY, calibration_value, density_contract_max_count, effective_policy
from revision_quality import build_family_scene_low_dose_matrix


DEFAULT_THRESHOLDS = {
    "max_hits_per_1k": 12.0,
    "max_dash_per_1k": 5.0,
}
DEFAULT_LOW_DOSE_THRESHOLD_PER_1K = 1.0


def _dash_hits(text: str, lang: str) -> list[dict]:
    """叙述层破折号命中（含原文偏移与上下文）。

    对白引号内豁免——与 scene 层 `detect_dash_density` 同语义：破折号在对白里
    承担话语中断 / 人物结巴，是合法戏剧手法，不是叙述层的解释性连接病灶。
    机器只统计叙述层密度；每一处的手艺功能由 reviser 按 locator 逐处判。
    """
    masked = _mask_quoted_spans(text)
    pattern = "—" if lang == "en" else "——"
    hits = []
    for m in re.finditer(re.escape(pattern), masked):
        hits.append({
            "start": m.start(),
            "end": m.end(),
            "context": text[max(0, m.start() - 24):m.end() + 24].replace("\n", " "),
        })
    return hits


def _dash_per_1k(text: str, lang: str, hits: list[dict] | None = None) -> float:
    dash_hits = _dash_hits(text, lang) if hits is None else hits
    if lang == "en":
        denom = max(len(_en_words(text)), 1)
    else:
        denom = max(len(text), 1)
    return round(len(dash_hits) / denom * 1000, 2)


def build_report(story_text: str, lang: str) -> dict:
    selected_lang = detect_lang(story_text) if lang == "auto" else lang
    result = analyze(story_text, scene_id="WHOLE", lang=selected_lang)
    # Lifecycle is resolved per family×language×rule. Observe findings remain
    # visible without contributing to a release-blocking trigger.
    char_k = max(len(story_text) / 1000, 0.001)
    enforced_hits = [
        h for h in result["hits"]
        if effective_policy(h.get("family", ""), selected_lang, h.get("rule"))["lifecycle"]
        == "enforced"
    ]
    observed_hits = [h for h in result["hits"] if h not in enforced_hits]
    observed_alerts = list(result.get("observed_alerts", []))
    hits_per_1k = round(len(enforced_hits) / char_k, 2)
    dash_hits = _dash_hits(story_text, selected_lang)
    dash_per_1k = _dash_per_1k(story_text, selected_lang, dash_hits)
    triggers = []
    observations = []

    if hits_per_1k > DEFAULT_THRESHOLDS["max_hits_per_1k"]:
        observations.append({
            "type": "hits_per_1k",
            "value": hits_per_1k,
            "threshold": DEFAULT_THRESHOLDS["max_hits_per_1k"],
        })

    blocking_alerts = [
        alert
        for alert in result["cluster_alerts"]
        if alert.get("severity") in {"high", "catastrophic"}
        and effective_policy(alert.get("family", ""), selected_lang)["lifecycle"] == "enforced"
    ]
    if blocking_alerts:
        observations.append({
            "type": "blocking_cluster",
            "alert_ids": [alert.get("alert_id") for alert in blocking_alerts],
            # Pass locators through for contextual review, not mandatory edits.
            "alerts": [
                {
                    "alert_id": alert.get("alert_id"),
                    "family": alert.get("family"),
                    "severity": alert.get("severity"),
                    "total_count": alert.get("total_count"),
                    "density_per_1k": alert.get("density_per_1k"),
                    "escalation_threshold": alert.get("escalation_threshold"),
                    "hit_records": alert.get("hit_records", []),
                }
                for alert in blocking_alerts
            ],
        })

    # Compatibility for explicitly configured contracts only. Current ordinary
    # expression families remain observations and never enter this branch.
    if selected_lang == "en":
        density_denom = max(len(_en_words(story_text)), 1)
    else:
        density_denom = max(len(story_text), 1)
    for family in sorted({h.get("family") for h in enforced_hits}):
        policy = effective_policy(family, selected_lang)
        if not policy.get("density_contract"):
            continue
        baseline = calibration_value(policy)
        if not baseline:
            continue
        family_hits = [h for h in enforced_hits if h.get("family") == family]
        max_count = density_contract_max_count(policy, density_denom)
        count = len(family_hits)
        if count <= max_count:
            continue
        triggers.append({
            "type": "density_contract",
            "family": family,
            "count": count,
            "max_count": max_count,
            "required_reduction": count - max_count,
            "baseline_per_1k": baseline,
            "density_per_1k": round(count / density_denom * 1000, 2),
            "decision_ref": policy.get("decision_ref"),
            "repair": policy.get("repair"),
            "hit_records": [
                {
                    "lint_id": h.get("lint_id"),
                    "family": family,
                    "rule": h.get("rule"),
                    "locator": h.get("locator"),
                    "evidence_quote": h.get("evidence_quote"),
                }
                for h in family_hits
            ],
        })

    dash_policy = effective_policy("dash_overuse", selected_lang)
    if (
        dash_policy["lifecycle"] == "enforced"
        and dash_per_1k > DEFAULT_THRESHOLDS["max_dash_per_1k"]
    ):
        observations.append({
            "type": "dash_per_1k",
            "value": dash_per_1k,
            "threshold": DEFAULT_THRESHOLDS["max_dash_per_1k"],
            # 分布型超限：单段往往都不到 scene 立案线，定位由全文层提供，
            # 否则 de-AI reviser 只知道超标数值、不知道改哪。
            "locators": dash_hits,
        })

    if observed_hits:
        observations.append({
            "type": "observe_hits",
            "count": len(observed_hits),
            "families": sorted({h.get("family") for h in observed_hits if h.get("family")}),
            "hit_records": observed_hits,
        })
    if dash_policy["lifecycle"] == "observe" and dash_per_1k > DEFAULT_THRESHOLDS["max_dash_per_1k"]:
        observations.append({
            "type": "dash_per_1k_observe",
            "value": dash_per_1k,
            "threshold": DEFAULT_THRESHOLDS["max_dash_per_1k"],
            "locators": dash_hits,
        })

    return {
        "verdict": "FAIL" if triggers else "REVIEW" if observations or observed_alerts else "PASS",
        "review_required": bool(observations or observed_alerts),
        "surface_lint": "completed",
        "semantic_review": "not_run",
        "overall_review": "incomplete",
        "language": selected_lang,
        "input_story_sha256": hashlib.sha256(story_text.encode("utf-8")).hexdigest(),
        "whole_text": {
            "total_chars": len(story_text),
            "hits": len(result["hits"]),
            "cluster_alerts": len(result["cluster_alerts"]),
            "observed_alerts": len(observed_alerts),
            "hits_per_1k": hits_per_1k,
            "dash_per_1k": dash_per_1k,
        },
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "triggers": triggers,
        "observed_alerts": observed_alerts,
        "observations": observations,
    }


def _load_mapping(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _latest_scene_lint(work_dir: Path, scene_id: str) -> Path | None:
    review_dir = work_dir / "pipeline" / "review"
    lint_dir = review_dir / "lint"
    directive = _load_mapping(review_dir / f"{scene_id}.machine_directive.yaml")
    revision = directive.get("lint_revision")
    relative = revision.get("artifact") if isinstance(revision, dict) else None
    if not relative:
        relative = directive.get("lint_artifact")
    if isinstance(relative, str) and relative:
        candidate = Path(relative)
        path = candidate if candidate.is_absolute() else work_dir / candidate
        if path.exists():
            return path
    dist: list[tuple[int, Path]] = []
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
    return None


def _build_family_scene_matrix(work_dir: Path, lang: str) -> dict:
    scenes: dict[str, dict] = {}
    families: set[str] = set()
    scene_dir = work_dir / "pipeline" / "scenes"
    for scene_path in sorted(scene_dir.glob("scene_*.md")):
        scene_id = scene_path.stem.removeprefix("scene_")
        lint_path = _latest_scene_lint(work_dir, scene_id)
        lint = _load_mapping(lint_path) if lint_path else {}
        scenes[scene_id] = {
            "text": scene_path.read_text(encoding="utf-8"),
            "lint": lint,
        }
        for hit in lint.get("hits", []) or lint.get("lint_hits", []) or []:
            if not isinstance(hit, dict):
                continue
            family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
            if family:
                families.add(str(family))

    thresholds: dict[str, float] = {}
    for family in sorted(families):
        policy = effective_policy(family, lang)
        if not policy.get("registered"):
            continue
        baseline = calibration_value(policy)
        thresholds[family] = baseline if baseline > 0 else DEFAULT_LOW_DOSE_THRESHOLD_PER_1K
    return build_family_scene_low_dose_matrix(scenes, thresholds)


def _write_report(report: dict, work_dir: Path | None, story_path: Path) -> Path:
    if work_dir is None:
        out_path = story_path.with_name("wholetext_gate.yaml")
    else:
        out_path = work_dir / "pipeline" / "review" / "wholetext_gate.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Whole-text diagnostics and explicit density contracts")
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")
    parser.add_argument("--work-dir", type=Path, default=None)
    args = parser.parse_args()

    if not args.story.exists():
        print(f"[wholetext_gate] ERROR: story not found: {args.story}", file=sys.stderr)
        return 2

    try:
        story_text = args.story.read_text(encoding="utf-8")
        report = build_report(story_text, args.lang)
        if args.work_dir:
            matrix = _build_family_scene_matrix(args.work_dir.resolve(), report["language"])
            report["family_scene_matrix"] = matrix
            report["observations"].extend(
                family["observation"]
                for family in matrix["families"].values()
                if family.get("observation")
            )
        if report["observations"]:
            report["review_required"] = True
            if report["verdict"] == "PASS":
                report["verdict"] = "REVIEW"
        out_path = _write_report(report, args.work_dir.resolve() if args.work_dir else None, args.story)
    except Exception as exc:
        print(f"[wholetext_gate] ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"{report['verdict']} {out_path}")
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
