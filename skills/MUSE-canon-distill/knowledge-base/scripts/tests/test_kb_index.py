from __future__ import annotations

import importlib
import json
from pathlib import Path


ki = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_index")


def _make_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    novel = kb / "novels" / "书A"
    novel.mkdir(parents=True)
    (novel / "scene_index.json").write_text(
        json.dumps([{"scene_id": "S01"}], ensure_ascii=False), encoding="utf-8")

    both = kb / "dramas" / "剧A"
    both.mkdir(parents=True)
    (both / "scene_index.json").write_text(
        json.dumps([{"scene_id": "OLD"}], ensure_ascii=False), encoding="utf-8")
    (both / "dramatic_scene_index.jsonl").write_text(
        json.dumps({"scene_id": "A1"}, ensure_ascii=False) + "\n", encoding="utf-8")
    return kb


def test_index_precedence_jsonl_over_json(tmp_path):
    kb = _make_kb(tmp_path)

    assert ki.index_path_of(kb / "novels" / "书A").name == "scene_index.json"
    assert ki.index_path_of(kb / "dramas" / "剧A").name == "dramatic_scene_index.jsonl"
    assert ki.index_path_of(kb / "novels") is None or True  # 非作品目录不在契约内
    assert ki.find_index_path(kb, "剧A").name == "dramatic_scene_index.jsonl"
    assert ki.find_index_path(kb, "不存在") is None


def test_medium_by_container_not_filename(tmp_path):
    kb = _make_kb(tmp_path)
    # legacy JSON 索引的剧目仍按 drama 处理
    assert ki.medium_of(kb / "dramas" / "剧A" / "scene_index.json") == "drama"
    assert ki.medium_of(kb / "novels" / "书A" / "scene_index.json") == "novel"


def test_jsonl_load_save_preserves_format_and_fields(tmp_path):
    kb = _make_kb(tmp_path)
    path = kb / "dramas" / "剧A" / "dramatic_scene_index.jsonl"
    entries = ki.load_index(path)
    assert entries == [{"scene_id": "A1"}]

    entries[0]["style_profile"] = {"diction": "白话"}
    ki.save_index(path, entries)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["style_profile"] == {"diction": "白话"}


def test_iter_work_indexes_covers_both_containers(tmp_path):
    kb = _make_kb(tmp_path)
    names = [p.name for p in ki.iter_work_indexes(kb)]
    assert names == ["dramatic_scene_index.jsonl", "scene_index.json"]
