#!/usr/bin/env python3
"""PostToolUse hook: validate pipeline/shortform/*.yaml writes（短链属主校验器,仅本包注册）。

匹配面：父目录恰为 pipeline/shortform 的 .yaml/.yml（单层——shortform/review/ 子目录
不归本 hook,审阅报告属主校验器是 verify_shortform_review_complete.py）。
校验正文在 scripts/validate_shortform_contract.py,按 basename 分派四类 schema。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _in_scope(file_path: str) -> bool:
    if not file_path.endswith((".yaml", ".yml")):
        return False
    path = Path(file_path)
    return path.parent.name == "shortform" and path.parent.parent.name == "pipeline"


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    if payload.get("tool_name") not in {"Write", "Edit"}:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not _in_scope(file_path):
        return 0

    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
    validator = plugin_root / "scripts" / "validate_shortform_contract.py"
    result = subprocess.run(
        ["python3", str(validator), file_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        return 2

    # 上游联动重验：characters/ledger 改动后，已存在的 outline 外键可能失效
    path = Path(file_path)
    if path.name in {"characters.yaml", "inspiration_ledger.yaml"}:
        outline = path.parent / "outline.yaml"
        if outline.exists():
            recheck = subprocess.run(
                ["python3", str(validator), str(outline)],
                capture_output=True,
                text=True,
                check=False,
            )
            if recheck.returncode != 0:
                sys.stderr.write(f"[上游联动] {path.name} 本次写入合法，但使既有 outline.yaml 失效：\n")
                sys.stderr.write(recheck.stdout)
                sys.stderr.write(recheck.stderr)
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
