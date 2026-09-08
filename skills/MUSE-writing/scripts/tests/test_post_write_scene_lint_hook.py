"""post-write-scene-lint.sh hook 行为测试（F2 测试态小 fix）。

R 轮测试态发现 F2：reviser 改完 scene 后 v2 lint 是 v1 拷贝（同一份文件覆盖），
导致 superficial_patch_failed 检测失效。Hook 修复：
- 首次写（writer 首版）`S0N.ai_filler.yaml` 不存在 → 跑 lint 产 v1（默认输出）
- 二次写（reviser 改后）`S0N.ai_filler.yaml` 已存在 → 加 --output-suffix v2 → 产 v2

测试通过 subprocess 调用真 shell hook，模拟 Edit/Write 触发场景。
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPO_ROOT / "skills/MUSE-writing/hooks/post-write-scene-lint.sh"
MIN_SCENE = "他将笔提起来。\n他写了'还'字，又写了'反'字。\n墨色极浓。\n"


def _make_work(tmp_path: Path, scene_text: str) -> Path:
    work = tmp_path / "work"
    (work / "pipeline/scenes").mkdir(parents=True)
    (work / "pipeline/scene_S01").mkdir(parents=True)
    (work / "pipeline/scene_S01/scene_card.md").write_text(
        "# Scene Card: S01\n**arc_id**: arc_01\n", encoding="utf-8"
    )
    (work / "pipeline/scenes/scene_S01.md").write_text(scene_text, encoding="utf-8")
    return work


def _trigger(work: Path) -> subprocess.CompletedProcess:
    scene_path = work / "pipeline/scenes/scene_S01.md"
    payload = json.dumps({"tool_input": {"file_path": str(scene_path)}})
    env = {"PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT / "skills/MUSE-writing")}
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload, capture_output=True, text=True, env=env,
    )


def test_first_write_produces_v1_default_output(tmp_path):
    """v1 不存在 → 跑 lint 输出到 S01.ai_filler.yaml（无 suffix）。"""
    work = _make_work(tmp_path, MIN_SCENE)
    proc = _trigger(work)
    assert proc.returncode == 0
    lint_dir = work / "pipeline/review/lint"
    assert (lint_dir / "S01.ai_filler.yaml").exists()
    assert not (lint_dir / "S01.ai_filler.v2.yaml").exists()


def test_second_write_produces_v2_with_suffix(tmp_path):
    """v1 已存在 → 跑 lint 加 --output-suffix v2 → 产 S01.ai_filler.v2.yaml，不覆盖 v1。"""
    work = _make_work(tmp_path, MIN_SCENE)
    proc = _trigger(work)  # pass 1：产 v1
    v1_md5_before = (work / "pipeline/review/lint/S01.ai_filler.yaml").read_bytes()

    # 模拟 reviser 改了 scene 内容
    (work / "pipeline/scenes/scene_S01.md").write_text(
        MIN_SCENE.replace("他将笔提起来。\n", ""), encoding="utf-8"
    )
    proc = _trigger(work)  # pass 2：v1 在 → 应产 v2

    assert proc.returncode == 0
    lint_dir = work / "pipeline/review/lint"
    assert (lint_dir / "S01.ai_filler.yaml").exists(), "v1 不应被覆盖"
    assert (lint_dir / "S01.ai_filler.v2.yaml").exists(), "v2 应被新建"
    v1_md5_after = (lint_dir / "S01.ai_filler.yaml").read_bytes()
    assert v1_md5_before == v1_md5_after, "v1 字节级保持不变"


def test_v2_reflects_revised_scene_content_not_v1_copy(tmp_path):
    """关键检测：v2 内容反映 revised scene，不是 v1 拷贝。"""
    work = _make_work(tmp_path, MIN_SCENE)
    _trigger(work)
    # 改 scene：删一行短段
    (work / "pipeline/scenes/scene_S01.md").write_text(
        MIN_SCENE.replace("墨色极浓。\n", ""), encoding="utf-8"
    )
    _trigger(work)
    v1 = (work / "pipeline/review/lint/S01.ai_filler.yaml").read_bytes()
    v2 = (work / "pipeline/review/lint/S01.ai_filler.v2.yaml").read_bytes()
    # v2 必须跟 v1 字节不同（因为 lint 在不同的 scene 内容上跑）
    # 注：v1/v2 各自有 meta.total_chars 字段会反映字数差
    assert v1 != v2


def test_non_scene_file_write_skipped(tmp_path):
    """写非 pipeline/scenes/scene_*.md 的文件不触发 lint。"""
    other = tmp_path / "random.md"
    other.write_text("not a scene", encoding="utf-8")
    payload = json.dumps({"tool_input": {"file_path": str(other)}})
    env = {"PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT / "skills/MUSE-writing")}
    proc = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True, text=True, env=env)
    assert proc.returncode == 0
    # 没有 lint 目录生成
    assert not list(tmp_path.glob("**/lint/*.yaml"))
