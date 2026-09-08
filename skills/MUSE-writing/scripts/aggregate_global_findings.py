#!/usr/bin/env python3
"""Aggregate explicitly selected, current review reports for the active task."""
import argparse
import sys
from pathlib import Path

import yaml

from release_eligibility import _semantic_review_state

SOURCES = {
    "A": "pipeline/review/A_aesthetic.yaml",
    "B": "pipeline/review/B_narrative_consistency.yaml",
    "C": "pipeline/review/C_structural_consistency.yaml",
}


def collect(yaml_path: Path, *, manuscript_scope: bool = False):
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"选中报告不可读：{yaml_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"报告须为 mapping：{yaml_path}")
    findings = data.get("review_findings", data.get("findings"))
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise ValueError(f"报告 findings 须为对象列表：{yaml_path}")
    return [dict(f) for f in findings if manuscript_scope or f.get("scene_id") is None]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work-dir", required=True, type=Path)
    ap.add_argument("--source", choices=[*SOURCES, "A-manuscript"], action="append", required=True)
    args = ap.parse_args(argv)
    work_dir = args.work_dir.resolve()
    aggregated = []
    sources_present = list(dict.fromkeys(args.source))
    source_reports = {}
    try:
        for label in sources_present:
            manuscript = label == "A-manuscript"
            if manuscript:
                state = _semantic_review_state(work_dir)
                if state.get("status") not in {"clear", "findings"}:
                    raise ValueError(f"当前全稿语义报告不可用：{state.get('reason', state.get('status'))}")
                relative = state["report_path"]
            else:
                relative = SOURCES[label]
            source_reports[label] = relative
            for finding in collect(work_dir / relative, manuscript_scope=manuscript):
                aggregated.append({**finding, "source_group": label})
        out_path = work_dir / "pipeline/review/global_findings.yaml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"global_findings": aggregated, "sources_present": sources_present,
                   "source_reports": source_reports, "total": len(aggregated)}
        temporary = out_path.with_suffix(".yaml.tmp")
        temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        temporary.replace(out_path)
    except (OSError, ValueError) as exc:
        print(f"[aggregate_global_findings] {exc}", file=sys.stderr)
        return 2
    print(f"wrote {out_path} (sources={sources_present}, total={len(aggregated)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
