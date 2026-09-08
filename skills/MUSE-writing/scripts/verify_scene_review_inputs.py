#!/usr/bin/env python3
"""Check physical scene-review inputs before dispatch.

Exit 0 means the default required files exist; exit 1 lists missing_inputs.
optional_present lists existing B/C paths for discovery only. The caller selects
current reports explicitly; existence does not make an old report active.
"""
import argparse
import sys
from pathlib import Path

import yaml


def _base_required_paths(scene_id):
    """required input：正文 + scene_card + A + 3 lint。"""
    return [
        f"pipeline/scenes/scene_{scene_id}.md",
        f"pipeline/scene_{scene_id}/scene_card.md",
        "pipeline/review/A_aesthetic.yaml",
        f"pipeline/review/lint/{scene_id}.ai_filler.yaml",
        f"pipeline/review/lint/{scene_id}.lexical_stats.yaml",
        f"pipeline/review/lint/{scene_id}.dialogue.yaml",
    ]


def _optional_paths():
    """optional inputs：B/C 文件存在则列入 optional_present。"""
    return [
        "pipeline/review/B_narrative_consistency.yaml",
        "pipeline/review/C_structural_consistency.yaml",
    ]


def verify(pipeline_root, scene_id):
    """返回 (missing_inputs: list[str], optional_present: list[str])。"""
    root = Path(pipeline_root)
    missing = []
    optional_present = []

    for rel in _optional_paths():
        if (root / rel).exists():
            optional_present.append(rel)

    for rel in _base_required_paths(scene_id):
        if not (root / rel).exists():
            missing.append(rel)

    return missing, optional_present


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--pipeline-root", required=True)
    args = parser.parse_args()

    missing, optional_present = verify(args.pipeline_root, args.scene_id)
    payload = {
        "status": "ok" if not missing else "failed",
        "scene_id": args.scene_id,
        "missing_inputs": missing,
    }
    if optional_present:
        payload["optional_present"] = optional_present
    yaml.safe_dump(payload, sys.stdout, allow_unicode=True, sort_keys=False)
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
