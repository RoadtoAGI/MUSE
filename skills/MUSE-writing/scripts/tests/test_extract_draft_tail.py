"""tests for extract_draft_tail.py — 尾部抽取 + 幂等写入

幂等性核心断言（G0 round 2026-05-04）：
  内容相同时不刷 mtime——184 实战 PATCH 后重抽 tail 只换 mtime 会让前序场景
  audit 物理校验 fail；幂等写入避免该副作用。
"""
import os, subprocess, time
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "extract_draft_tail.py"


def make_draft(pipeline_dir: Path, scene_id: str, content: str) -> Path:
    """fixture：单路径协议下 writer 直产 pipeline/scenes/scene_{id}.md。"""
    sd = pipeline_dir / "pipeline" / f"scene_{scene_id}"
    sd.mkdir(parents=True, exist_ok=True)
    scenes_dir = pipeline_dir / "pipeline" / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    scene_path = scenes_dir / f"scene_{scene_id}.md"
    scene_path.write_text(content, encoding="utf-8")
    return scene_path


def run(pipeline_dir: Path, scene_id: str):
    return subprocess.run(
        ["python3", str(SCRIPT), "--scene-id", scene_id, "--work-dir", str(pipeline_dir)],
        capture_output=True, text=True,
    )


def test_basic_tail_extraction(tmp_path):
    content = "前段。" * 50 + "末句压力收束。"
    make_draft(tmp_path, "S01", content)
    r = run(tmp_path, "S01")
    assert r.returncode == 0, r.stderr
    tail = (tmp_path / "pipeline" / "scene_S01" / "draft_tail.md").read_text(encoding="utf-8")
    assert "末句压力收束。" in tail
    assert len(tail) <= 250  # HARD_CAP


def test_idempotent_write_preserves_mtime(tmp_path):
    """同一 draft 重抽 tail 内容一致 → 第二次 mtime 不变（G0 修复）"""
    content = "前段。" * 50 + "末句压力收束。"
    make_draft(tmp_path, "S01", content)

    r1 = run(tmp_path, "S01")
    assert r1.returncode == 0
    tail_path = tmp_path / "pipeline" / "scene_S01" / "draft_tail.md"
    mtime_first = tail_path.stat().st_mtime

    time.sleep(1.1)  # 确保系统时钟前进至少一秒
    r2 = run(tmp_path, "S01")
    assert r2.returncode == 0
    mtime_second = tail_path.stat().st_mtime

    assert mtime_first == mtime_second, (
        f"内容不变时 tail mtime 应保持；first={mtime_first} second={mtime_second}"
    )


def test_changed_content_refreshes_mtime(tmp_path):
    """draft 内容变化 → tail 内容变化 → mtime 应刷新"""
    content_v1 = "前段。" * 50 + "原版末句。"
    content_v2 = "前段。" * 50 + "修订版末句完全不同。"

    make_draft(tmp_path, "S01", content_v1)
    r1 = run(tmp_path, "S01")
    assert r1.returncode == 0
    tail_path = tmp_path / "pipeline" / "scene_S01" / "draft_tail.md"
    mtime_first = tail_path.stat().st_mtime
    tail_v1 = tail_path.read_text(encoding="utf-8")

    time.sleep(1.1)
    make_draft(tmp_path, "S01", content_v2)
    r2 = run(tmp_path, "S01")
    assert r2.returncode == 0
    mtime_second = tail_path.stat().st_mtime
    tail_v2 = tail_path.read_text(encoding="utf-8")

    assert tail_v1 != tail_v2
    assert mtime_second > mtime_first


def test_missing_draft_fails(tmp_path):
    sd = tmp_path / "pipeline" / "scene_S01"
    sd.mkdir(parents=True, exist_ok=True)
    r = run(tmp_path, "S01")
    assert r.returncode != 0
    assert "not found" in r.stderr.lower() or "draft" in r.stderr.lower()
