from __future__ import annotations

import importlib
import json
from pathlib import Path

import yaml


iq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.inspiration_query")


def _card(card_id: str, phase: list[int], text: str, applicability: str = None, tags: list[str] = None) -> dict:
    return {
        "card_id": card_id,
        "pattern_name": text,
        "dramatic_function": f"{text} 功能",
        "applicability": applicability or f"{text} 适用",
        "tags": tags or [],
        "phase_affinity": phase,
        "source_scenes": [{"novel": "书A", "scene_id": "S01", "note": "note"}],
        "reuse_candidates": [f"{text}的表层元素"],
    }


def _write_cards(tmp_path: Path, cards: list[dict]) -> Path:
    kb = tmp_path / "knowledge-base"
    insp = kb / "inspiration"
    insp.mkdir(parents=True)
    for card in cards:
        (insp / f"{card['card_id']}.yaml").write_text(
            yaml.safe_dump(card, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return kb


def _make_kb(tmp_path: Path) -> Path:
    return _write_cards(tmp_path, [
        _card("revenge-cost", [3], "复仇代价"),
        _card("mentor-death", [3], "导师之死"),
    ])


def test_signals_tokens_bigrams_and_ascii_words():
    tokens = iq.signals_tokens({"genre": "武侠", "tags": ["复仇代价", {"x": "mentor-death"}]})

    assert {"武侠", "复仇", "仇代", "代价", "mentor-death"} <= tokens


def test_signal_weight_families():
    assert iq.signal_weight("genre") == 2.0
    assert iq.signal_weight("题材") == 2.0
    assert iq.signal_weight("crisis_type") == 1.8
    assert iq.signal_weight("conflict_layer") == 1.8
    assert iq.signal_weight("motif") == 1.0


def test_score_rank_prefers_phase_and_signal_coverage(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(iq, "KB_ROOT", kb)
    cards = iq.load_cards(kb)

    selected, rejected = iq.rank_cards(cards, 3, {"motif": "复仇代价"}, limit=2)

    assert len(selected) == 1
    assert selected[0]["card_id"] == "revenge-cost"
    assert [card["card_id"] for card in rejected] == ["mentor-death"]


def test_genre_signal_differentiates_same_phase_pool(tmp_path, monkeypatch):
    kb = _write_cards(tmp_path, [
        _card("scifi-pattern", [3], "技术失控", applicability="适用于科幻与硬科技题材"),
        _card("mystery-pattern", [3], "证词反转", applicability="适用于悬疑与罪案题材"),
    ])
    monkeypatch.setattr(iq, "KB_ROOT", kb)
    cards = iq.load_cards(kb)

    scifi_top, _ = iq.rank_cards(cards, 3, {"genre": "科幻"}, limit=1)
    mystery_top, _ = iq.rank_cards(cards, 3, {"genre": "悬疑"}, limit=1)

    assert scifi_top[0]["card_id"] == "scifi-pattern"
    assert mystery_top[0]["card_id"] == "mystery-pattern"


def test_tags_participate_in_matching(tmp_path, monkeypatch):
    kb = _write_cards(tmp_path, [
        _card("mirror-card", [3], "镜像章节", tags=["镜像结构", "双线叙事"]),
        _card("plain-card", [3], "平铺直叙"),
    ])
    monkeypatch.setattr(iq, "KB_ROOT", kb)
    cards = iq.load_cards(kb)

    selected, rejected = iq.rank_cards(cards, 3, {"structure": "镜像结构"}, limit=2)

    assert len(selected) == 1
    assert selected[0]["card_id"] == "mirror-card"
    assert [card["card_id"] for card in rejected] == ["plain-card"]


def test_reuse_candidates_participate_in_matching(tmp_path, monkeypatch):
    matching = _card("matching-card", [3], "共同范式")
    matching["reuse_candidates"] = ["反物质钥匙"]
    other = _card("other-card", [3], "共同范式")
    other["reuse_candidates"] = ["青铜罗盘"]
    kb = _write_cards(tmp_path, [matching, other])
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    selected, rejected = iq.rank_cards(
        iq.load_cards(kb), 3, {"motif": "反物质钥匙"}, limit=2
    )

    assert len(selected) == 1
    assert selected[0]["card_id"] == "matching-card"
    assert [card["card_id"] for card in rejected] == ["other-card"]


def test_source_scene_notes_participate_in_matching(tmp_path, monkeypatch):
    matching = _card("matching-card", [4], "共同范式")
    matching["source_scenes"][0]["note"] = "政治线截断军事资源"
    other = _card("other-card", [4], "共同范式")
    other["source_scenes"][0]["note"] = "人物独处"
    kb = _write_cards(tmp_path, [matching, other])
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    selected, _ = iq.rank_cards(
        iq.load_cards(kb), 4, {"narrative_problem": "军事资源被政治线截断"}, limit=2
    )

    assert selected[0]["card_id"] == "matching-card"


def test_preferred_work_boosts_semantically_relevant_card(tmp_path, monkeypatch):
    preferred = _card("preferred-card", [4], "延迟揭示")
    preferred["source_scenes"][0]["novel"] = "手选书"
    other = _card("other-card", [4], "延迟揭示")
    other["source_scenes"][0]["novel"] = "其他书"
    kb = _write_cards(tmp_path, [preferred, other])
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    selected, _ = iq.rank_cards(
        iq.load_cards(kb),
        4,
        {"narrative_problem": "延迟揭示"},
        limit=2,
        preferred_works=["手选书"],
    )

    assert selected[0]["card_id"] == "preferred-card"
    assert "preferred=手选书" in selected[0]["_reasons"]


def test_preferred_work_does_not_rescue_semantically_irrelevant_card(tmp_path, monkeypatch):
    preferred = _card("preferred-card", [4], "宴会礼仪")
    preferred["source_scenes"][0]["novel"] = "手选书"
    matching = _card("matching-card", [4], "延迟揭示")
    matching["source_scenes"][0]["novel"] = "其他书"
    kb = _write_cards(tmp_path, [preferred, matching])
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    selected, rejected = iq.rank_cards(
        iq.load_cards(kb),
        4,
        {"narrative_problem": "延迟揭示"},
        limit=2,
        preferred_works=["手选书"],
    )

    assert [card["card_id"] for card in selected] == ["matching-card"]
    assert [card["card_id"] for card in rejected] == ["preferred-card"]


def test_cli_writes_selected_and_rejected(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    code = iq.run(3, json.dumps({"motif": "复仇代价"}, ensure_ascii=False), str(tmp_path / "refs"), top_k=1)

    out = tmp_path / "refs" / "inspiration" / "phase3_cards.md"
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "revenge-cost" in text
    assert "- reuse_candidates: 复仇代价的表层元素" in text
    assert ("do_" + "not_copy") not in text
    assert "落选" in text
    assert "mentor-death" in text


def test_missing_kb_exit2(tmp_path, monkeypatch):
    monkeypatch.setattr(iq, "KB_ROOT", tmp_path / "missing")

    assert iq.run(3, "{}", str(tmp_path / "refs")) == 2


def test_no_match_exit2_and_no_file(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path)
    monkeypatch.setattr(iq, "KB_ROOT", kb)

    code = iq.run(1, json.dumps({"motif": "无关"}, ensure_ascii=False), str(tmp_path / "refs"))

    assert code == 2
    assert not (tmp_path / "refs" / "inspiration" / "phase1_cards.md").exists()
