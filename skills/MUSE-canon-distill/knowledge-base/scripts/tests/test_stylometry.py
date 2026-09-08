from __future__ import annotations

import importlib
from pathlib import Path


sm = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.stylometry")


def test_punctuation_and_pronoun_density_known_text():
    text = "他——她：你；它这个那种。"  # len=13
    stats = sm.analyze_text(text)

    assert stats.dash_per_1k == 76.92        # "——" 计 1，非拆成两个"—"
    assert stats.colon_per_1k == 76.92
    assert stats.semicolon_per_1k == 76.92
    assert stats.ta_per_1k == 76.92
    assert stats.dem_classifier_per_1k == 153.85  # "这个"+"那种" 两处限定式


def test_dash_double_char_counts_as_one_not_two():
    text = "起风了——雨也停了。"
    stats = sm.analyze_text(text)

    # 若误拆成两个"—"，dash count 会是 2；正确实现应为 1
    expected = round(1 / len(text) * 1000, 2)
    assert stats.dash_per_1k == expected


def test_pro_drop_ratio_verb_first_vs_subject_first():
    text = "走进门。他坐下来。"
    stats = sm.analyze_text(text)

    assert stats.pro_drop_ratio == 0.5


def test_top_noun_repetition_picks_highest_frequency_bigram():
    text = "帝国帝国帝国"
    stats = sm.analyze_text(text)

    assert stats.top_noun_repetition_per_1k == 500.0


def test_empty_text_zero_division_protected():
    stats = sm.analyze_text("")

    assert stats.dash_per_1k == 0.0
    assert stats.colon_per_1k == 0.0
    assert stats.semicolon_per_1k == 0.0
    assert stats.ta_per_1k == 0.0
    assert stats.dem_classifier_per_1k == 0.0
    assert stats.pro_drop_ratio == 0.0
    assert stats.top_noun_repetition_per_1k == 0.0


def test_analyze_file_matches_analyze_text(tmp_path):
    text = "他——她：你；它这个那种。"
    p = tmp_path / "scene.md"
    p.write_text(text, encoding="utf-8")

    assert sm.analyze_file(p) == sm.analyze_text(text)


def test_analyze_file_missing_returns_none(tmp_path, capsys):
    result = sm.analyze_file(tmp_path / "missing.md")

    assert result is None
    assert "读取文件失败" in capsys.readouterr().err


def test_signature_per_1k_counts_lexicon_hits():
    text = "他给废墟建了个索引。索引没用，变量太多。" * 10
    v = sm.signature_per_1k(text, ["索引", "变量"])
    assert v > 0
    n = len(text)
    assert abs(v - (30 / n * 1000)) < 1e-6   # 每份 3 次命中 × 10


def test_signature_per_1k_empty_lexicon_is_zero():
    assert sm.signature_per_1k("随便什么文本", []) == 0.0


def test_signature_distribution_by_gear():
    segs = [("dense", "索引索引变量" * 5), ("absent", "他跑了。" * 5), ("default", "变量在这。" * 5)]
    d = sm.signature_distribution(segs, ["索引", "变量"])
    assert set(d) == {"dense", "absent", "default"}
    assert d["dense"] > d["default"] > 0 and d["absent"] == 0.0


def test_signature_distribution_no_cross_segment_match():
    # R1-Codex：同档多个 segment 若直接拼接计数，会在段落边界处造出原文中不存在的词面
    segs = [("dense", "变"), ("dense", "量")]
    d = sm.signature_distribution(segs, ["变量"])
    assert d["dense"] == 0.0
