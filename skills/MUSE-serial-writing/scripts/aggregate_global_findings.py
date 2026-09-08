#!/usr/bin/env python3
"""aggregate_global_findings.py — 把 B/C yaml 中 scene_id=null 的全文级 finding 聚合到 global_findings.yaml

orchestrator 在 Step 5 L2 dispatch consistency-review A/B/C 后调用。adaptive 路径下 B/C 可能未跑——
脚本会写空 global_findings.yaml，下游 orchestrator 读到空 list 直接跳过全局路由。

接口：
    python3 aggregate_global_findings.py --work-dir <pipeline_dir>

输入（任一缺失视为 B/C 该组未跑，不报错）：
    {work_dir}/pipeline/review/B_narrative_consistency.yaml
    {work_dir}/pipeline/review/C_structural_consistency.yaml

输出：
    {work_dir}/pipeline/review/global_findings.yaml

退出码：0（脚本不阻断；B/C 缺失为合法 adaptive 状态）。
"""
import argparse
import sys
from pathlib import Path

import yaml


SOURCES = [
    ("B", "pipeline/review/B_narrative_consistency.yaml"),
    ("C", "pipeline/review/C_structural_consistency.yaml"),
]


def collect(yaml_path: Path):
    if not yaml_path.exists():
        return []
    try:
        data = yaml.safe_load(yaml_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    findings = data.get("review_findings") or data.get("findings") or []
    return [f for f in findings if isinstance(f, dict) and f.get("scene_id") is None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", required=True, type=Path)
    args = ap.parse_args()

    out_path = args.work_dir / "pipeline" / "review" / "global_findings.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    aggregated = []
    sources_present = []
    for label, rel in SOURCES:
        path = args.work_dir / rel
        if path.exists():
            sources_present.append(label)
            for f in collect(path):
                f.setdefault("source_group", label)
                aggregated.append(f)

    payload = {
        "global_findings": aggregated,
        "sources_present": sources_present,
        "total": len(aggregated),
    }
    out_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    print(f"wrote {out_path} (sources={sources_present}, total={len(aggregated)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
