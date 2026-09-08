#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from ai_filler_lint import RULE_TO_FAMILY


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _families(data: dict) -> set[str]:
    families: set[str] = set()
    for alert in data.get("cluster_alerts", []) or []:
        if not isinstance(alert, dict):
            continue
        family = alert.get("family") or alert.get("cluster")
        if family:
            families.add(str(family))
    for hit in data.get("hits", []) or data.get("lint_hits", []) or []:
        if not isinstance(hit, dict):
            continue
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if family:
            families.add(str(family))
    return families


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe family changes after distribution rewrite")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()

    try:
        before = _load_yaml(args.before)
        after = _load_yaml(args.after)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[family_gate] ERROR: {exc}", file=sys.stderr)
        return 2

    before_families = _families(before)
    after_families = _families(after)
    new_families = sorted(after_families - before_families)
    if new_families:
        print("REVIEW new_families: " + ", ".join(new_families))
        return 0

    print("PASS family_set_not_expanded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
