"""L1 lint 三件套全文输入模式测试——whole.* 报告 = per-scene 同构体（scene_id=WHOLE）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[1]

STORY = (
    "溪水从石缝里流过。阿禾蹲在岸边把手放进水里。\n\n"
    "「水凉了。」她说。\n\n"
    "守渡人没有回头。他把船篙插进泥里，看着对岸的灯一盏一盏灭掉。\n"
)


def _run(script: str, work_dir: Path, story: Path, extra=()):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script),
         "--story", str(story), "--work-dir", str(work_dir), *extra],
        capture_output=True, text=True,
    )


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    work = tmp_path / "run"
    (work / "pipeline" / "review" / "lint").mkdir(parents=True)
    story = work / "story.md"
    story.write_text(STORY, encoding="utf-8")
    return work, story


def test_ai_filler_whole_mode(tmp_path):
    work, story = _setup(tmp_path)
    r = _run("ai_filler_lint.py", work, story)
    assert r.returncode == 0, r.stderr
    out = work / "pipeline" / "review" / "lint" / "whole.ai_filler.yaml"
    assert out.exists()
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["scene_id"] == "WHOLE"
    assert "hits" in data          # R3 F4：固定 hits 键，非散装入口的 lint_hits
    assert "lint_hits" not in data


def test_lexical_stats_whole_mode(tmp_path):
    work, story = _setup(tmp_path)
    r = _run("lexical_stats.py", work, story)
    assert r.returncode == 0, r.stderr
    out = work / "pipeline" / "review" / "lint" / "whole.lexical_stats.yaml"
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["scene_id"] == "WHOLE"
    assert "density" in data


def test_dialogue_lint_whole_mode(tmp_path):
    work, story = _setup(tmp_path)
    r = _run("dialogue_lint.py", work, story)
    assert r.returncode == 0, r.stderr
    out = work / "pipeline" / "review" / "lint" / "whole.dialogue.yaml"
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["scene_id"] == "WHOLE"
    assert "hits" in data


def test_scene_id_and_story_mutually_exclusive(tmp_path):
    work, story = _setup(tmp_path)
    for script in ("lexical_stats.py", "dialogue_lint.py", "ai_filler_lint.py"):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / script), "--scene-id", "S01",
             "--story", str(story), "--work-dir", str(work)],
            capture_output=True, text=True,
        )
        assert r.returncode != 0, script


def test_per_scene_mode_unchanged(tmp_path):
    """既有 per-scene 契约零回归：--scene-id 路径与输出名不变。"""
    work, _ = _setup(tmp_path)
    scenes = work / "pipeline" / "scenes"
    scenes.mkdir(parents=True)
    (scenes / "scene_S01.md").write_text(STORY, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "dialogue_lint.py"),
         "--scene-id", "S01", "--work-dir", str(work)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    out = work / "pipeline" / "review" / "lint" / "S01.dialogue.yaml"
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["scene_id"] == "S01"
