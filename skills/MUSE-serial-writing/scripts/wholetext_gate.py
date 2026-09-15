#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from ai_filler_lint import _en_words, analyze, detect_lang


DEFAULT_THRESHOLDS = {
    "max_hits_per_1k": 12.0,
    "max_dash_per_1k": 5.0,
}


def _dash_per_1k(text: str, lang: str) -> float:
    if lang == "en":
        denom = max(len(_en_words(text)), 1)
        return round(text.count("—") / denom * 1000, 2)
    denom = max(len(text), 1)
    return round(text.count("——") / denom * 1000, 2)


def build_report(story_text: str, lang: str) -> dict:
    selected_lang = detect_lang(story_text) if lang == "auto" else lang
    result = analyze(story_text, scene_id="WHOLE", lang=selected_lang)
    hits_per_1k = result["density"]["hits_per_1k"]
    dash_per_1k = _dash_per_1k(story_text, selected_lang)
    triggers = []

    if hits_per_1k > DEFAULT_THRESHOLDS["max_hits_per_1k"]:
        triggers.append({
            "type": "hits_per_1k",
            "value": hits_per_1k,
            "threshold": DEFAULT_THRESHOLDS["max_hits_per_1k"],
        })

    blocking_alerts = [
        alert
        for alert in result["cluster_alerts"]
        if alert.get("severity") in {"high", "catastrophic"}
    ]
    if blocking_alerts:
        triggers.append({
            "type": "blocking_cluster",
            "alert_ids": [alert.get("alert_id") for alert in blocking_alerts],
        })

    if dash_per_1k > DEFAULT_THRESHOLDS["max_dash_per_1k"]:
        triggers.append({
            "type": "dash_per_1k",
            "value": dash_per_1k,
            "threshold": DEFAULT_THRESHOLDS["max_dash_per_1k"],
        })

    observations = [{"type": "pattern_candidates", "hit_records": result["hits"]}] if result["hits"] else []
    observations.extend(triggers)
    return {
        "verdict": "REVIEW" if observations else "PASS",
        "review_required": bool(observations),
        "assessment": "diagnostic",
        "surface_lint": "completed",
        "semantic_review": "not_run",
        "overall_review": "incomplete",
        "observations": observations,
        "cluster_alerts": result["cluster_alerts"],
        "language": selected_lang,
        "whole_text": {
            "total_chars": len(story_text),
            "hits": len(result["hits"]),
            "cluster_alerts": len(result["cluster_alerts"]),
            "hits_per_1k": hits_per_1k,
            "density_unit": "characters",
            "dash_per_1k": dash_per_1k,
            "dash_density_unit": "words" if selected_lang == "en" else "characters",
        },
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "triggers": [],
    }


def _write_report(report: dict, work_dir: Path | None, story_path: Path) -> Path:
    if work_dir is None:
        out_path = story_path.with_name("wholetext_gate.yaml")
    else:
        out_path = work_dir / "pipeline" / "review" / "wholetext_gate.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Chapter-level expression diagnostics")
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
        out_path = _write_report(report, args.work_dir.resolve() if args.work_dir else None, args.story)
    except Exception as exc:
        print(f"[wholetext_gate] ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"{report['verdict']} {out_path}")
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
