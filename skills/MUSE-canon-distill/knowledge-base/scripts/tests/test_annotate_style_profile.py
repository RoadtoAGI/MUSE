from __future__ import annotations

import importlib
import json
from pathlib import Path


asp = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.annotate_style_profile")


def _make_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    for container, name in [("novels", "书A"), ("dramas", "剧A")]:
        work = kb / container / name
        (work / "scenes").mkdir(parents=True)
        (work / "scenes" / "scene_S01.md").write_text("一段文字", encoding="utf-8")
        (work / "scene_index.json").write_text(
            json.dumps(
                [
                    {
                        "scene_id": "S01",
                        "novel": name,
                        "file": "scenes/scene_S01.md",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    (kb / "embeddings").mkdir()
    return kb


def test_iter_novel_indexes_covers_novels_and_dramas(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)

    paths = asp.iter_novel_indexes(None)

    assert [p.parent.name for p in paths] == ["剧A", "书A"]


def test_iter_novel_indexes_filters_by_novel(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)

    paths = asp.iter_novel_indexes("书")

    assert len(paths) == 1
    assert paths[0].parent.name == "书A"


def test_collect_todo_skips_annotated_unless_force(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    idx_path = kb / "novels" / "书A" / "scene_index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    index[0]["style_profile"] = {"narration_voice": "x"}
    idx_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    assert asp.collect_todo("书A", force=False, limit=10) == []
    todo = asp.collect_todo("书A", force=True, limit=10)

    assert len(todo) == 1
    assert todo[0][0] == idx_path
    assert todo[0][2]["scene_id"] == "S01"


def test_save_index_writes_per_novel_only(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    idx_path = kb / "novels" / "书A" / "scene_index.json"
    index = asp.load_index(idx_path)
    index[0]["style_profile"] = {"narration_voice": "贴身"}

    asp.save_index(idx_path, index)

    saved = json.loads(idx_path.read_text(encoding="utf-8"))
    assert saved[0]["style_profile"]["narration_voice"] == "贴身"
    assert not (kb / "embeddings" / "scene_index.json").exists()


_PROFILE = {
    "narration_voice": "限知贴身",
    "diction": "白话",
    "rhetoric_density": "low",
    "dialogue_mode": "对白稀少",
    "pacing": "短段留白",
}


def test_prepare_then_ingest_roundtrip(tmp_path, monkeypatch):
    import sys

    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    task_path = tmp_path / "task.json"
    monkeypatch.setattr(sys, "argv", [
        "annotate_style_profile.py", "--prepare", "--novel", "书A",
        "--out", str(task_path),
    ])
    assert asp.main() == 0
    task = json.loads(task_path.read_text(encoding="utf-8"))
    assert task["entries"] == [
        {"novel": "书A", "medium": "novel", "scene_id": "S01", "text": "一段文字",
         "source_path": str(kb / "novels/书A/scenes/scene_S01.md"), "text_truncated": False}
    ]
    assert set(task["instructions"]) == {"novel"}

    out_path = tmp_path / "profiles.out.json"
    out_path.write_text(json.dumps({
        "annotated_by": "test-model",
        "profiles": [{"novel": "书A", "scene_id": "S01", "style_profile": _PROFILE}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["annotate_style_profile.py", "--ingest", str(out_path)])
    assert asp.main() == 0
    saved = json.loads((kb / "novels" / "书A" / "scene_index.json").read_text(encoding="utf-8"))
    assert saved[0]["style_profile"] == _PROFILE
    assert saved[0]["style_profile_by"] == "test-model"


_DRAMA_PROFILE = {
    "dialogue_voice": "身份化口语分层",
    "diction": "白话夹文言",
    "rhetoric_density": "medium",
    "stage_direction_style": "小说化工笔",
    "pacing": "对白回合密集",
}


def _make_drama_kb(tmp_path):
    kb = tmp_path / "knowledge-base"
    work = kb / "dramas" / "剧B"
    (work / "scenes").mkdir(parents=True)
    (work / "scenes" / "scene_A1.md").write_text("台词与舞台指示", encoding="utf-8")
    legacy = [{"scene_id": "OLD", "file": "scenes/scene_A1.md"}]
    (work / "scene_index.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    entry = {"scene_id": "A1", "work_id": "jub", "file": "scenes/scene_A1.md", "act": 1}
    (work / "dramatic_scene_index.jsonl").write_text(
        json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
    return kb


def test_drama_jsonl_precedence_and_roundtrip(tmp_path, monkeypatch):
    import sys

    kb = _make_drama_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    task_path = tmp_path / "task.json"
    monkeypatch.setattr(sys, "argv", [
        "annotate_style_profile.py", "--prepare", "--novel", "剧B",
        "--out", str(task_path),
    ])
    assert asp.main() == 0
    task = json.loads(task_path.read_text(encoding="utf-8"))
    # JSONL 优先：装包的是 A1 而非 legacy OLD；instructions 走 drama 字段集
    assert [e["scene_id"] for e in task["entries"]] == ["A1"]
    assert task["entries"][0]["medium"] == "drama"
    assert "stage_direction_style" in task["instructions"]["drama"]

    out_path = tmp_path / "profiles.out.json"
    out_path.write_text(json.dumps({
        "annotated_by": "m",
        "profiles": [{"novel": "剧B", "scene_id": "A1", "style_profile": _DRAMA_PROFILE}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["annotate_style_profile.py", "--ingest", str(out_path)])
    assert asp.main() == 0
    lines = (kb / "dramas" / "剧B" / "dramatic_scene_index.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    saved = json.loads(lines[0])
    assert saved["style_profile"] == _DRAMA_PROFILE
    # legacy JSON 不被写回
    legacy = json.loads((kb / "dramas" / "剧B" / "scene_index.json").read_text(encoding="utf-8"))
    assert "style_profile" not in legacy[0]


def test_drama_rejects_novel_field_profile(tmp_path, monkeypatch, capsys):
    import sys

    kb = _make_drama_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    out_path = tmp_path / "profiles.out.json"
    out_path.write_text(json.dumps({
        "annotated_by": "m",
        "profiles": [{"novel": "剧B", "scene_id": "A1", "style_profile": _PROFILE}],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["annotate_style_profile.py", "--ingest", str(out_path)])
    assert asp.main() == 1
    assert "dialogue_voice" in capsys.readouterr().err


def test_ingest_rejects_bad_profile_and_unknown_scene(tmp_path, monkeypatch, capsys):
    import sys

    kb = _make_kb(tmp_path)
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    bad = dict(_PROFILE, rhetoric_density="ultra")
    out_path = tmp_path / "profiles.out.json"
    out_path.write_text(json.dumps({
        "annotated_by": "m",
        "profiles": [
            {"novel": "书A", "scene_id": "S01", "style_profile": bad},
            {"novel": "书A", "scene_id": "S99", "style_profile": _PROFILE},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["annotate_style_profile.py", "--ingest", str(out_path)])
    assert asp.main() == 1
    err = capsys.readouterr().err
    assert "rhetoric_density" in err and "无此 scene_id" in err
    saved = json.loads((kb / "novels" / "书A" / "scene_index.json").read_text(encoding="utf-8"))
    assert "style_profile" not in saved[0]


def test_preview_carries_full_source_path_and_truncation(tmp_path, monkeypatch):
    import argparse
    kb = tmp_path / "knowledge-base"
    work = kb / "novels" / "短篇"
    work.mkdir(parents=True)
    source = work / "scene.md"
    source.write_text("前" * (asp.MAX_SCENE_CHARS + 1) + "后段视角变化")
    (work / "scene_index.json").write_text(json.dumps([{"scene_id": "S1", "file": "scene.md"}]))
    monkeypatch.setattr(asp, "KB_ROOT", kb)
    output = tmp_path / "task.json"
    args = argparse.Namespace(novel="短篇", scene_id=None, force=False, limit=1, out=str(output))
    assert asp.prepare(args) == 0
    entry = json.loads(output.read_text())["entries"][0]
    assert entry["text_truncated"] is True
    assert "变化" not in entry["text"]
    assert "变化" in Path(entry["source_path"]).read_text()
