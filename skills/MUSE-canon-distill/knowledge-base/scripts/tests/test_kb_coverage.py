from __future__ import annotations

import importlib
import json
from pathlib import Path


cov = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_coverage")


def _row(novel, author, person, register, *, original="zh", medium="novel", words=1000):
    return {"novel": novel, "author": author, "scene_id": f"{novel}{person}{register}", "lang": "zh",
            "original_lang": original, "narrative_person": person, "register": register,
            "source_medium": medium, "word_count": words}


def test_recallable_rows_split_originals_translations_and_unannotated():
    index = [
        _row("甲", "作者甲", "first", "colloquial"),
        _row("乙", "作者乙", "third", "literary", original="en"),
        _row("丙", "作者丙", "third", "literary", medium="stage_play"),
        {"novel": "丁", "lang": "zh", "source_medium": "novel"},
    ]
    originals, translations, unannotated = cov.recallable_rows(index, "zh", "novel")
    assert [r["novel"] for r in originals] == ["甲"]
    assert [r["novel"] for r in translations] == ["乙"]
    assert unannotated == 1


def test_matrix_counts_cells_against_targets():
    rows = [_row("甲", "作者甲", "first", "colloquial", words=150_000),
            _row("乙", "作者乙", "first", "colloquial", words=60_000),
            _row("丙", "作者丙", "third", "literary")]
    lines = cov.matrix_lines(rows, "zh")
    first_col = next(line for line in lines if line.startswith("first × colloquial")).split("\t")
    assert first_col[1:4] == ["2", "210,000", "2"]
    assert first_col[5:] == ["≥ 60", "是"]
    third_lit = next(line for line in lines if line.startswith("third × literary")).split("\t")
    assert third_lit[5:] == ["不补", "否"]
    assert any(line.startswith("third × colloquial\t0\t") for line in lines)  # 目标格即使为空也列出


def test_main_prints_matrix_from_aggregate(tmp_path, capsys):
    kb = tmp_path / "kb"
    (kb / "embeddings").mkdir(parents=True)
    (kb / "embeddings" / "scene_index.json").write_text(
        json.dumps([_row("甲", "作者甲", "first", "colloquial")], ensure_ascii=False), encoding="utf-8")
    assert cov.main(["--kb", str(kb), "--no-features"]) == 0
    out = capsys.readouterr().out
    assert "可召回 1 场（1 部）" in out
    assert "first × colloquial\t1\t" in out
