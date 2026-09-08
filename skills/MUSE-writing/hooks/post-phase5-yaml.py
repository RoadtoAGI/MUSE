#!/usr/bin/env python3
"""PostToolUse hook: validate Phase 5 scene_tasks after phase5_scenes.yaml writes."""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path


PHASE5_YAML_PATTERN = "*/pipeline/phase5_scenes.yaml"
CANON_DISTILL_PATH_MARKER = "knowledge-base/novels/"
# novel-analysis (MUSE-canon-distill) 产物布局：{novel_dir}/pipeline/phase5_scenes.yaml
# 与 {novel_dir}/full_text.md or navigation.md or scene_index.json 同 novel_dir
# 任一存在即判定为逆向分析产物（scene_tasks 是字符串而非 r10 structured list）
NOVEL_ANALYSIS_SIBLINGS = ("full_text.md", "navigation.md", "scene_index.json")


def _is_novel_analysis_artifact(file_path: str) -> bool:
    """判定该 phase5_scenes.yaml 是否为 novel-analysis 逆向产物。

    三层识别（任一命中即跳过 r10 校验）：
    1. 路径含 canon-distill knowledge-base 标记（plugin 内布局）
    2. phase5 yaml 父目录的兄弟有 full_text.md / navigation.md / scene_index.json
       （novel-analysis 在任何 workspace 跑出来的标准布局）
    3. yaml 顶部含 analysis_meta 字段（semantic 标记，未来 novel-analysis 默认产出）
    """
    if CANON_DISTILL_PATH_MARKER in file_path:
        return True

    path = Path(file_path)
    novel_dir = path.parent.parent  # phase5_scenes.yaml -> pipeline/ -> novel_dir
    if any((novel_dir / name).exists() for name in NOVEL_ANALYSIS_SIBLINGS):
        return True

    try:
        with path.open(encoding="utf-8") as handle:
            head = handle.read(2048)
        if "analysis_meta:" in head:
            return True
    except OSError:
        pass

    return False


def main() -> int:
    payload_text = sys.stdin.read()
    payload = json.loads(payload_text or "{}")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool_name not in {"Write", "Edit"}:
        return 0

    file_path = tool_input.get("file_path") or ""
    if not fnmatch.fnmatch(file_path, PHASE5_YAML_PATTERN):
        return 0
    if _is_novel_analysis_artifact(file_path):
        return 0

    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
    validator = plugin_root / "scripts" / "validate_phase5_r10.py"
    result = subprocess.run(
        ["python3", str(validator), file_path, "--scan-scene-tasks", "--scan-inspiration-refs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 2
    if result.stdout:
        sys.stderr.write(result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
