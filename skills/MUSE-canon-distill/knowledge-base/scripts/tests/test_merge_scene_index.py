from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


msi = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.merge_scene_index")


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    (kb / "embeddings").mkdir(parents=True)

    # 小说甲：per-novel index 的 novel 字段用"·"旧写法（目录名用"-"）——验证目录名为准
    a = kb / "novels" / "书甲Ⅰ-上部"
    a.mkdir(parents=True)
    (a / "scene_index.json").write_text(
        json.dumps(
            [
                {"scene_id": "S02", "novel": "书甲Ⅰ·上部", "file": "novels/书甲Ⅰ-上部/scenes/scene_S02.md",
                 "description": "乙场", "style_profile": {"diction": "冷"}},
                {"scene_id": "S01", "novel": "书甲Ⅰ·上部", "file": "novels/书甲Ⅰ-上部/scenes/scene_S01.md",
                 "description": "甲场", "style_profile": {"diction": "热"},
                 "craft_notes": "craft_notes/scene_S01_beats.md"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 小说乙：用 participants 旧字段名
    b = kb / "novels" / "书乙"
    b.mkdir(parents=True)
    (b / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "S01", "novel": "书乙", "file": "novels/书乙/scenes/scene_S01.md",
              "description": "丙场", "participants": ["张三", "李四"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 戏剧丙：整文件 JSON array
    c = kb / "dramas" / "剧丙"
    c.mkdir(parents=True)
    (c / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "A1S1", "novel": "剧丙", "file": "dramas/剧丙/scenes/scene_A1S1.md",
              "dramatic_purpose": "开场"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 戏剧丁：JSONL 逐行格式
    d = kb / "dramas" / "剧丁"
    d.mkdir(parents=True)
    (d / "dramatic_scene_index.jsonl").write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False)
            for row in [
                {"scene_id": "A1S1", "novel": "剧丁", "file": "dramas/剧丁/scenes/scene_A1S1.md",
                 "dramatic_purpose": "序幕"},
                {"scene_id": "A2S1", "novel": "剧丁", "file": "dramas/剧丁/scenes/scene_A2S1.md",
                 "dramatic_purpose": "转折"},
            ]
        ),
        encoding="utf-8",
    )
    return kb


def _agg(kb: Path) -> list[dict]:
    return json.loads((kb / "embeddings/scene_index.json").read_text(encoding="utf-8"))


def test_merge_counts_and_sources(tmp_kb):
    assert msi.merge(tmp_kb) == 0
    agg = _agg(tmp_kb)
    assert len(agg) == 6  # 2+1+1+2（含 jsonl 两行）
    novels = {e["novel"] for e in agg}
    assert "书甲Ⅰ-上部" in novels  # 目录名为准，"·"写法被归一
    assert "书甲Ⅰ·上部" not in novels


def test_field_normalization(tmp_kb):
    msi.merge(tmp_kb)
    agg = _agg(tmp_kb)
    b_row = next(e for e in agg if e["novel"] == "书乙")
    assert b_row["characters"] == ["张三", "李四"]  # participants → characters
    assert b_row["participants"] == ["张三", "李四"]  # 原字段保留
    a1 = next(e for e in agg if e["novel"] == "书甲Ⅰ-上部" and e["scene_id"] == "S01")
    assert a1["has_craft_notes"] is True
    assert a1["craft_notes_file"] == "craft_notes/scene_S01_beats.md"
    assert a1["style_profile"] == {"diction": "热"}  # style_profile 透传
    drama = next(e for e in agg if e["novel"] == "剧丁")
    assert drama["source_medium"] == "stage_play"
    novel = next(e for e in agg if e["novel"] == "书乙")
    assert novel["source_medium"] == "novel"


def test_deterministic_sort_and_idx(tmp_kb):
    msi.merge(tmp_kb)
    agg = _agg(tmp_kb)
    keys = [(e["novel"], e["scene_id"]) for e in agg]
    assert keys == sorted(keys)  # 确定性排序
    assert [e["idx"] for e in agg] == list(range(len(agg)))


def test_idempotent(tmp_kb):
    msi.merge(tmp_kb)
    first = (tmp_kb / "embeddings/scene_index.json").read_bytes()
    msi.merge(tmp_kb)
    second = (tmp_kb / "embeddings/scene_index.json").read_bytes()
    assert first == second


def test_dry_run_does_not_write(tmp_kb, capsys):
    rc = msi.merge(tmp_kb, dry_run=True)
    assert rc == 0
    assert not (tmp_kb / "embeddings/scene_index.json").exists()
    out = capsys.readouterr().out
    assert "6" in out  # 报告应含合并行数


def test_file_field_normalized_from_work_relative_source(tmp_path):
    # per-novel 源常见约定：file 相对作品目录（如 "scenes/scene_S01.md"），不含
    # "novels/<dir>/" 前缀——消费方（read_scene_text 等）按 KB_ROOT 相对路径解析，
    # 聚合层必须补前缀，否则全库读原文/密度/文风指标静默失败。
    kb = tmp_path / "knowledge-base"
    (kb / "embeddings").mkdir(parents=True)
    work = kb / "novels" / "书戊"
    work.mkdir(parents=True)
    (work / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "S01", "novel": "书戊", "file": "scenes/scene_S01.md",
              "description": "戊场"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert msi.merge(kb) == 0
    agg = _agg(kb)
    row = next(e for e in agg if e["novel"] == "书戊")
    assert row["file"] == "novels/书戊/scenes/scene_S01.md"


def test_file_field_already_kb_root_relative_not_double_prefixed(tmp_path):
    kb = tmp_path / "knowledge-base"
    (kb / "embeddings").mkdir(parents=True)
    work = kb / "novels" / "书己"
    work.mkdir(parents=True)
    (work / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "S01", "novel": "书己", "file": "novels/书己/scenes/scene_S01.md",
              "description": "己场"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert msi.merge(kb) == 0
    agg = _agg(kb)
    row = next(e for e in agg if e["novel"] == "书己")
    assert row["file"] == "novels/书己/scenes/scene_S01.md"


def test_json_preferred_over_jsonl_when_both(tmp_kb):
    # 剧丁补一个 .json（内容 1 行），应优先于 .jsonl（2 行）
    (tmp_kb / "dramas" / "剧丁" / "scene_index.json").write_text(
        json.dumps(
            [{"scene_id": "A1S1", "novel": "剧丁", "file": "dramas/剧丁/scenes/scene_A1S1.md"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    msi.merge(tmp_kb)
    assert len([e for e in _agg(tmp_kb) if e["novel"] == "剧丁"]) == 1


def test_drama_authority_and_query_fields_survive_aggregation(tmp_path):
    kb = tmp_path / "knowledge-base"
    work = kb / "dramas" / "广播剧"
    (work / "pipeline").mkdir(parents=True)
    (work / "scene_index.json").write_text(json.dumps([{"scene_id": "old"}]))
    row = {"scene_id": "new", "language": "zh", "characters_on_stage": ["甲"], "file": "scenes/scene_new.md"}
    (work / "dramatic_scene_index.jsonl").write_text(json.dumps(row))
    (work / "work-meta.yaml").write_text("source_medium: radio_play\n")
    (work / "pipeline/phase0_conception.yaml").write_text("genre:\n  primary: mystery\n")
    rows = msi.collect(kb)
    assert len(rows) == 1
    assert rows[0]["scene_id"] == "new"
    assert rows[0]["source_medium"] == "radio_play"
    assert rows[0]["lang"] == "zh"
    assert rows[0]["genre"] == "mystery"
    assert rows[0]["characters"] == ["甲"]
