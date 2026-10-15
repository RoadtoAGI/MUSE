"""kb_query 的写作范文检索：原作 / 人称 / 语域过滤、清空原因、预算窗口与 exemplar 渲染（设计 §4）。"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest


kq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_query")

HEADER = "# 场景 S01：雪夜\n**出处**：《书甲》第2章\n**角色**：甲、乙\n---\n\n"


def _para(seed: str, n: int) -> str:
    return (seed + "。") * n


ROWS = [
    # novel, scene, lang, original_lang, person, register, 正文
    ("书甲", "S01", "zh", "zh", "first", "colloquial", HEADER + _para("我推门进去", 60) + "\n\n" + _para("我坐下了", 60)),
    ("书甲", "S02", "zh", "zh", "first", "literary", _para("我看着远山", 80)),
    ("书乙", "S01", "zh", "zh", "third", "colloquial", _para("他推门进去", 80)),
    ("译本", "S01", "zh", "en", "first", "colloquial", _para("我是译本里的人", 80)),
    ("英文", "S01", "en", "en", "first", None, "I walked in. " * 200),
]


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path / "kb"
    (root / "embeddings").mkdir(parents=True)
    index = []
    for i, (novel, sid, lang, original, person, register, text) in enumerate(ROWS):
        rel = f"novels/{novel}/scenes/scene_{sid}.md"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
        index.append({"idx": i, "novel": novel, "scene_id": sid, "file": rel, "lang": lang,
                      "original_lang": original, "narrative_person": person, "register": register,
                      "author": f"{novel}作者", "source_chapter": "第1章", "description": f"{novel}{sid}"})
    (root / "embeddings" / "scene_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    vectors = np.array([[1.0, 0.0], [0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.6, 0.4]], dtype=np.float32)
    np.save(root / "embeddings" / "scene_embeddings.npy", vectors)
    monkeypatch.setattr(kq, "KB_ROOT", root)
    monkeypatch.setattr(kq, "EMBEDDINGS_DIR", root / "embeddings")
    monkeypatch.setattr(kq, "INDEX_PATH", root / "embeddings" / "scene_index.json")
    monkeypatch.setattr(kq, "EMBEDDINGS_PATH", root / "embeddings" / "scene_embeddings.npy")
    monkeypatch.setattr(kq, "STYLE_EMBEDDINGS_PATH", root / "embeddings" / "style_embeddings.npy")
    monkeypatch.setattr(kq, "API_KEY", "test")

    class _Embeddings:
        def create(self, model, input):
            item = type("Item", (), {"embedding": [1.0, 0.0]})
            return type("Resp", (), {"data": [item()]})

    class _OpenAI:
        def __init__(self, *args, **kwargs):
            self.embeddings = _Embeddings()

    monkeypatch.setattr(kq, "OpenAI", _OpenAI)
    kq._EMBED_CACHE.clear()
    return root


def _ids(results):
    return [(r["novel"], r["scene_id"]) for r in results]


def test_original_person_register_filters_before_scoring(kb):
    report: dict = {}
    results = kq.query("推门", lang="zh", original_only=True, person="first", register="colloquial",
                       top_k=5, filter_report=report)
    assert _ids(results) == [("书甲", "S01")]
    assert [label for label, _ in report["filters"]] == [
        "source_medium=novel", "lang=zh", "original-only", "person=first", "register=colloquial"]
    assert "cleared_by" not in report


def test_cleared_filter_is_named(kb, capsys):
    report: dict = {}
    assert kq.query("推门", lang="zh", original_only=True, person="third", register="literary",
                    top_k=5, filter_report=report) == []
    assert report["cleared_by"] == "register=literary"
    assert "register=literary 清空候选" in capsys.readouterr().err


def test_register_not_applied_to_uncalibrated_language(kb):
    report: dict = {}
    results = kq.query("walk", lang="en", original_only=True, person="first", register="colloquial",
                       top_k=5, filter_report=report)
    assert _ids(results) == [("英文", "S01")]
    assert report["ignored"] and "register=colloquial" in report["ignored"][0]


def test_original_only_requires_lang(kb):
    with pytest.raises(ValueError):
        kq.query("推门", original_only=True)


def test_novel_filter_accepts_several_works(kb):
    results = kq.query("推门", novel=["书甲", "书乙"], top_k=5)
    assert {r["novel"] for r in results} == {"书甲", "书乙"}
    assert {r["novel"] for r in kq.query("推门", novel="书乙", top_k=5)} == {"书乙"}


def test_misaligned_embeddings_fail_loudly(kb):
    np.save(kb / "embeddings" / "scene_embeddings.npy", np.zeros((3, 2), dtype=np.float32))
    with pytest.raises(kq.KBInfraError):
        kq.query("推门", top_k=2)


def test_exemplar_excerpt_skips_scene_header():
    text = HEADER + "夜里落了一场大雪。" * 100
    excerpt, _ = kq._exemplar_excerpt(text, None, 600)
    assert excerpt.startswith("夜里落了一场大雪")
    assert "# 场景" not in excerpt and "**出处**" not in excerpt and "---" not in excerpt


def _result(kb_root, novel, sid):
    index = json.loads((kb_root / "embeddings" / "scene_index.json").read_text(encoding="utf-8"))
    return next(dict(e) for e in index if e["novel"] == novel and e["scene_id"] == sid)


def test_windows_accumulate_by_rank_until_budget(kb):
    results = [_result(kb, "书甲", "S02"), _result(kb, "书乙", "S01"), _result(kb, "书甲", "S01")]
    windows, notes = kq.exemplar_windows(results, 700)
    assert [w["scene_id"] for w in windows] == ["S02", "S01"]  # 第一场 480 字不足，接下一名
    assert windows[0]["window_chars"] == 480
    total = sum(w["window_chars"] for w in windows)
    assert 700 <= total <= 1050
    assert not notes


def test_window_starts_at_body_and_cuts_at_sentence_end(kb):
    windows, _ = kq.exemplar_windows([_result(kb, "书甲", "S01")], 200)
    text = windows[0]["window_text"]
    assert text.startswith("我推门进去")
    assert "# 场景" not in text and "**出处**" not in text and "---" not in text
    assert text.endswith("。")
    assert 200 <= windows[0]["window_chars"] <= 300


def test_duplicate_source_text_is_skipped(kb, tmp_path):
    dup = kb / "novels" / "合集" / "scenes" / "scene_S09.md"
    dup.parent.mkdir(parents=True)
    dup.write_text(_para("我看着远山", 80), encoding="utf-8")
    results = [_result(kb, "书甲", "S02"),
               {"novel": "合集", "scene_id": "S09", "file": "novels/合集/scenes/scene_S09.md", "lang": "zh"},
               _result(kb, "书乙", "S01")]
    windows, notes = kq.exemplar_windows(results, 900)
    assert [w["novel"] for w in windows] == ["书甲", "书乙"]
    assert any("同一段原文" in n for n in notes)


def test_english_budget_counts_words(kb):
    windows, _ = kq.exemplar_windows([_result(kb, "英文", "S01")], 300)
    words = len(windows[0]["window_text"].split())
    assert 300 * 0.6 <= words <= 300 * 0.6 * 1.5


def test_exemplar_file_has_four_header_lines_and_source_lines(kb, tmp_path):
    results = [_result(kb, "书甲", "S02"), _result(kb, "书乙", "S01")]
    path, windows = kq.save_exemplar_file(results, "推门", str(tmp_path / "refs"), "S01",
                                          budget=700, filters="lang=zh")
    text = Path(path).read_text(encoding="utf-8")
    head = text.split("\n")[:5]
    assert head[0] == 'query: "推门"'
    assert head[1] == "filters: lang=zh"
    assert head[2] == "results: 2 — 书甲 S02；书乙 S01"
    assert head[3].startswith("chars: ") and "预算 700" in head[3]
    assert head[4] == ""
    assert text.count("<exemplar_window ") == 2
    assert 'source="书甲作者《书甲》第1章"' in text
    for banned in ("usage_protocol", "文风画像", "手艺拆解", "段落密度", "本场可以怎样用"):
        assert banned not in text


def test_exemplar_file_states_why_empty_and_shortfall(kb, tmp_path):
    path, _ = kq.save_exemplar_file([], "推门", str(tmp_path / "refs"), "S02", budget=4000,
                                    filters="lang=zh", empty_reason="register=colloquial 清空候选")
    assert "results: 0 — register=colloquial 清空候选" in Path(path).read_text(encoding="utf-8")
    path, _ = kq.save_exemplar_file([_result(kb, "书甲", "S02")], "推门", str(tmp_path / "refs"), "S03",
                                    budget=4000)
    assert "不足：可用候选只有 1 场" in Path(path).read_text(encoding="utf-8")


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["kb_query.py", *argv])
    kq.main()


def test_cli_render_exemplar_end_to_end(kb, tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "out"
    _run_main(monkeypatch, ["--query", "推门", "--lang", "zh", "--original-only", "--person", "first",
                            "--budget-chars", "300", "--render", "exemplar",
                            "--output-dir", str(out_dir), "--scene-id", "S01"])
    text = (out_dir / "S01_ref.md").read_text(encoding="utf-8")
    assert "filters: 全库 5 → source_medium=novel 5 → lang=zh 4 → original-only 3 → person=first 2" in text
    assert "译本" not in text.split("\n")[2]
    assert "已保存范文窗口" in capsys.readouterr().out


def test_cli_cleared_filter_writes_results_zero(kb, tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "out"
    _run_main(monkeypatch, ["--query", "推门", "--lang", "zh", "--original-only", "--person", "third",
                            "--register", "literary", "--render", "exemplar",
                            "--output-dir", str(out_dir), "--scene-id", "S01"])
    text = (out_dir / "S01_ref.md").read_text(encoding="utf-8")
    assert "results: 0 — register=literary 清空候选" in text
    assert "本场无范文" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    ["--query", "推门", "--budget-chars", "4000", "--output-dir", "x"],
    ["--query", "推门", "--render", "exemplar"],
    ["--query", "推门", "--original-only", "--render", "exemplar", "--output-dir", "x"],
])
def test_cli_rejects_inconsistent_flags(kb, monkeypatch, argv):
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, argv)
