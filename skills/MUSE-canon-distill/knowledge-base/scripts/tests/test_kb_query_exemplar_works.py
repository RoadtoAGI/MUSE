"""写作范文的两段式选择（设计 §4.2）：范文池准入、先按文风选作品、按作品排序依次取窗口、窗口人称起点与头部描述。"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest


kq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_query")


def _para(seed: str, n: int) -> str:
    return (seed + "。") * n


LETTER = "\n\n".join([_para("他推开门", 20), _para("她没有回头", 20), _para("他坐下读信", 20),
                      _para("我写这封信时天已经黑了", 20), _para("我想你会明白", 20)])

# novel, scene, plot 向量, style 向量, exemplar_pool, 正文
ROWS = [
    ("甲作", "S01", [1.0, 0.0], [0.0, 1.0], None, "\n\n".join([_para("我推门进去", 30)] * 4)),
    ("甲作", "S02", [0.9, 0.1], [0.0, 1.0], None, "\n\n".join([_para("我看着远山", 30)] * 4)),
    ("乙作", "S01", [0.5, 0.5], [1.0, 0.0], None, "\n\n".join([_para("我饿得发慌", 30)] * 4)),
    ("乙作", "S02", [0.4, 0.6], [1.0, 0.0], None, "\n\n".join([_para("我数着心跳", 30)] * 4)),
    ("口播", "S01", [1.0, 0.0], [1.0, 0.0], "on_request", "\n\n".join([_para("我们这块随后", 30)] * 4)),
    ("书信", "S01", [0.8, 0.2], [0.5, 0.5], None, LETTER),
]


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path / "kb"
    (root / "embeddings").mkdir(parents=True)
    index = []
    for i, (novel, sid, _, _, pool, text) in enumerate(ROWS):
        rel = f"novels/{novel}/scenes/scene_{sid}.md"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
        row = {"idx": i, "novel": novel, "scene_id": sid, "file": rel, "lang": "zh", "original_lang": "zh",
               "narrative_person": "first", "register": "colloquial", "dialogue_ratio": 0.1}
        if pool:
            row["exemplar_pool"] = pool
        index.append(row)
    (root / "novels" / "乙作" / "style_card.yaml").write_text(
        "narration_voice: 第一人称口语独白，跟熟人说话的口气，句子短\ndialogue_mode: 对白加引号，归属放句后\n",
        encoding="utf-8")
    (root / "embeddings" / "scene_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    np.save(root / "embeddings" / "scene_embeddings.npy", np.array([r[2] for r in ROWS], dtype=np.float32))
    np.save(root / "embeddings" / "style_embeddings.npy", np.array([r[3] for r in ROWS], dtype=np.float32))
    for name, value in (("KB_ROOT", root), ("EMBEDDINGS_DIR", root / "embeddings"),
                        ("INDEX_PATH", root / "embeddings" / "scene_index.json"),
                        ("EMBEDDINGS_PATH", root / "embeddings" / "scene_embeddings.npy"),
                        ("STYLE_EMBEDDINGS_PATH", root / "embeddings" / "style_embeddings.npy"),
                        ("API_KEY", "test")):
        monkeypatch.setattr(kq, name, value)

    class _Embeddings:
        def create(self, model, input):
            item = type("Item", (), {"embedding": [1.0, 0.0]})
            return type("Resp", (), {"data": [item()]})

    class _OpenAI:
        def __init__(self, *args, **kwargs):
            self.embeddings = _Embeddings()

    monkeypatch.setattr(kq, "OpenAI", _OpenAI)
    kq._EMBED_CACHE.clear()
    kq._CARD_CACHE.clear()
    return root


def test_style_hint_picks_works_before_plot(kb):
    report: dict = {}
    works = kq.select_exemplar_works("搜写字楼", lang="zh", original_only=True, person="first",
                                     style_hint="第一人称口语独白", filter_report=report)
    # 情节上甲作最近，文风上乙作最近：作品先按文风选
    assert [w["novel"] for w in works][:2] == ["乙作", "书信"]
    assert "口播" not in {w["novel"] for w in works}
    assert ("exemplar_pool", 5) in report["filters"]
    assert report["pool"] == {"scenes": 5, "works": 3, "largest": "甲作", "largest_share": 0.4}
    assert [r["scene_id"] for r in works[0]["rows"]] == ["S01", "S02"]  # 作品内按情节排


def test_without_style_hint_works_follow_plot(kb):
    works = kq.select_exemplar_works("搜写字楼", lang="zh", person="first")
    assert works[0]["novel"] == "甲作" and works[0]["style"] is None


def test_on_request_work_only_when_named(kb):
    works = kq.select_exemplar_works("搜写字楼", lang="zh", novel=["口播"], style_hint="口语")
    assert [w["novel"] for w in works] == ["口播"]


def test_exclude_novel_drops_the_work(kb):
    report: dict = {}
    works = kq.select_exemplar_works("搜写字楼", lang="zh", exclude=["乙作"], style_hint="口语",
                                     filter_report=report)
    assert "乙作" not in {w["novel"] for w in works}
    assert report["filters"][2][0] == "exclude=乙作"


def test_top_work_fills_the_budget_before_the_next(kb):
    works = kq.select_exemplar_works("搜写字楼", lang="zh", exclude=["书信"], style_hint="口语")
    windows, _ = kq.exemplar_windows_by_work(works, 1000)
    # 不设单部作品的配额：排第一的乙作场景够用，就全部取自乙作
    assert {w["novel"] for w in windows} == {"乙作"}
    assert sum(w["window_chars"] for w in windows) >= 1000
    windows, _ = kq.exemplar_windows_by_work(works, 2000)
    # 乙作两场取完仍不足预算，再取下一部
    novels = [w["novel"] for w in windows]
    assert novels[:2] == ["乙作", "乙作"] and novels[-1] == "甲作"
    assert sum(w["window_chars"] for w in windows) >= 2000


def test_single_work_gets_the_whole_budget(kb):
    works = kq.select_exemplar_works("搜写字楼", lang="zh", novel=["乙作"], style_hint="口语")
    windows, _ = kq.exemplar_windows_by_work(works, 1000)
    assert {w["novel"] for w in windows} == {"乙作"}
    assert sum(w["window_chars"] for w in windows) >= 1000


def test_first_person_window_starts_at_first_person_paragraph(kb):
    row = next(r for w in kq.select_exemplar_works("信", lang="zh", novel=["书信"]) for r in w["rows"])
    windows, _ = kq.exemplar_windows([row], 200, person="first")
    assert windows[0]["window_text"].startswith("我写这封信时")
    third, _ = kq.exemplar_windows([row], 200, person="third")
    assert third[0]["window_text"].startswith("他推开门")


def test_header_shows_pool_hint_and_window_descriptions(kb, tmp_path):
    report: dict = {}
    works = kq.select_exemplar_works("搜写字楼", lang="zh", person="first", style_hint="第一人称口语独白",
                                     filter_report=report)
    path, windows = kq.save_exemplar_file([], "搜写字楼", str(tmp_path / "refs"), "S01", budget=800,
                                          filters="lang=zh", works=works, person="first",
                                          pool=report["pool"], style_hint="第一人称口语独白")
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    assert lines[2] == "pool: 5 场、3 部；最大一部 甲作 占 40%"
    assert lines[3] == 'style_hint: "第一人称口语独白"'
    assert lines[4].startswith("results: ")
    assert lines[6] == "windows:"
    assert lines[7].startswith("- 乙作 S01｜人称 first｜语域 colloquial｜对白 0.10｜口吻：第一人称口语独白")
    assert "对白写法：对白加引号" in lines[7]
    body = "\n".join(lines[lines.index("", 7):])
    assert "口吻：" not in body  # 描述只在头部，窗口里只有原文


def test_cli_exclude_requires_exemplar(kb, monkeypatch):
    import sys
    monkeypatch.setattr(sys, "argv", ["kb_query.py", "--query", "q", "--exclude-novel", "乙作"])
    with pytest.raises(SystemExit):
        kq.main()
