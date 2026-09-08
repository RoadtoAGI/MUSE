from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml


dws = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.distill_work_style")


STYLE_PROFILE = {
    "narration_voice": "全知说书",
    "diction": "半文半白",
    "rhetoric_density": "medium",
    "dialogue_mode": "对白点睛",
    "pacing": "短句连动",
}


def _make_kb(tmp_path: Path, n_annotated: int = 2) -> Path:
    kb = tmp_path / "knowledge-base"
    work = kb / "novels" / "书A"
    (work / "scenes").mkdir(parents=True)
    entries = []
    for i in range(1, 4):
        sid = f"S{i:02d}"
        (work / "scenes" / f"scene_{sid}.md").write_text(f"{sid} 原文。", encoding="utf-8")
        entry = {
            "scene_id": sid,
            "novel": "书A",
            "author": "作者A",
            "lang": "zh",
            "file": f"scenes/scene_{sid}.md",
            "description": f"{sid} 描述",
        }
        if i <= n_annotated:
            entry["style_profile"] = STYLE_PROFILE
        entries.append(entry)
    (work / "scene_index.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    peer = kb / "novels" / "书B"
    peer.mkdir(parents=True)
    (peer / "scene_index.json").write_text(
        json.dumps([{"scene_id": "S01", "novel": "书B", "author": "作者A", "lang": "zh"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (peer / "style_card.yaml").write_text("novel: 书B\nnarration_voice: 全知\n", encoding="utf-8")
    return kb


def _valid_card() -> dict:
    return {
        "narration_voice": "全知说书",
        "diction": "半文半白",
        "rhetoric_density": "medium",
        "dialogue_mode": "对白点睛，归属用「某某道」",
        "pacing": "短句连动，快慢相间",
        "signature_moves": ["短句连动写打斗"],
        "anti_signature": ["不要现代口语"],
        "author_cross_ref": "",
    }


def test_collect_inputs_raises_coverage_error(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, n_annotated=2)
    monkeypatch.setattr(dws, "KB_ROOT", kb)

    with pytest.raises(dws.CoverageError, match="annotate_style_profile"):
        dws.collect_inputs("书A", min_count=3)


def test_collect_inputs_includes_peer_cards(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, n_annotated=3)
    monkeypatch.setattr(dws, "KB_ROOT", kb)

    inputs = dws.collect_inputs("书A", min_count=3)

    assert len(inputs["profiles"]) == 3
    assert "novel: 书B" in inputs["peer_cards"][0]


def test_parse_card_validates_fields_and_required_lists():
    card = dws.parse_card(json.dumps(_valid_card(), ensure_ascii=False))

    assert card["rhetoric_density"] == "medium"

    bad = _valid_card()
    bad["signature_moves"] = "not a list"
    with pytest.raises(ValueError, match="signature_moves"):
        dws.parse_card(json.dumps(bad, ensure_ascii=False))


def test_main_converts_coverage_error_to_exit2(tmp_path, monkeypatch, capsys):
    kb = _make_kb(tmp_path, n_annotated=2)
    monkeypatch.setattr(dws, "KB_ROOT", kb)
    monkeypatch.setattr(sys, "argv", [
        "distill_work_style.py", "--prepare", "--novel", "书A",
        "--min-style-profile-count", "3",
        "--out", str(tmp_path / "task.json"),
    ])

    assert dws.main() == 2
    assert "annotate_style_profile" in capsys.readouterr().err


def test_prepare_then_ingest_roundtrip(tmp_path, monkeypatch):
    import json

    kb = _make_kb(tmp_path, n_annotated=3)
    monkeypatch.setattr(dws, "KB_ROOT", kb)
    task_path = tmp_path / "task.json"
    monkeypatch.setattr(sys, "argv", [
        "distill_work_style.py", "--prepare", "--novel", "书A",
        "--min-style-profile-count", "3", "--out", str(task_path),
    ])
    assert dws.main() == 0
    task = json.loads(task_path.read_text(encoding="utf-8"))
    assert task["novel"] == "书A" and len(task["profiles"]) == 3
    assert "novel: 书B" in task["peer_cards"][0]

    out_path = tmp_path / "card.out.json"
    out_path.write_text(json.dumps(
        {"annotated_by": "test-model", "novel": "书A", "card": _valid_card()},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["distill_work_style.py", "--ingest", str(out_path)])
    assert dws.main() == 0
    card = yaml.safe_load((kb / "novels" / "书A" / "style_card.yaml").read_text(encoding="utf-8"))
    assert card["style_card_by"] == "test-model" and card["novel"] == "书A"


def test_assemble_card_yaml_includes_metadata(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, n_annotated=3)
    monkeypatch.setattr(dws, "KB_ROOT", kb)
    inputs = dws.collect_inputs("书A", min_count=3)

    text = dws.assemble_card_yaml(inputs, _valid_card(), "model-x")
    data = yaml.safe_load(text)

    assert data["novel"] == "书A"
    assert data["author"] == "作者A"
    assert "translator" in data
    assert data["style_card_by"] == "model-x"


def _make_drama_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    work = kb / "dramas" / "剧B"
    (work / "scenes").mkdir(parents=True)
    lines = []
    for i in range(1, 4):
        sid = f"A{i}"
        (work / "scenes" / f"scene_{sid}.md").write_text(f"{sid} 台词。", encoding="utf-8")
        lines.append({
            "scene_id": sid,
            "work_id": "jub",
            "author": "剧作者",
            "language": "zh",
            "file": f"scenes/scene_{sid}.md",
            "dramatic_purpose": f"{sid} 目的",
            "style_profile": {
                "dialogue_voice": "身份化口语",
                "diction": "白话",
                "rhetoric_density": "low",
                "stage_direction_style": "极简标记",
                "pacing": "回合密集",
            },
        })
    (work / "dramatic_scene_index.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in lines) + "\n", encoding="utf-8")
    (work / "work-meta.yaml").write_text("translator: 译者乙\n", encoding="utf-8")
    return kb


def test_drama_collect_inputs_and_card_roundtrip(tmp_path, monkeypatch):
    kb = _make_drama_kb(tmp_path)
    monkeypatch.setattr(dws, "KB_ROOT", kb)

    inputs = dws.collect_inputs("剧B", min_count=3)
    assert inputs["medium"] == "drama"
    assert inputs["lang"] == "zh"
    assert inputs["translator"] == "译者乙"
    assert inputs["profiles"][0]["description"] == "A1 目的"

    drama_card = {
        "dialogue_voice": "身份化口语分层",
        "diction": "白话夹文言",
        "rhetoric_density": "low",
        "stage_direction_style": "极简标记",
        "pacing": "回合密集",
        "signature_moves": ["上场即冲突"],
        "anti_signature": ["不要旁白解释"],
        "author_cross_ref": "",
    }
    card = dws.parse_card(json.dumps(drama_card, ensure_ascii=False), "drama")
    assert card["dialogue_voice"] == "身份化口语分层"

    with pytest.raises(ValueError, match="dialogue_voice"):
        dws.parse_card(json.dumps(_valid_card(), ensure_ascii=False), "drama")


def test_small_work_and_empty_style_boundaries_are_valid(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, n_annotated=1)
    monkeypatch.setattr(dws, "KB_ROOT", kb)
    inputs = dws.collect_inputs("书A")
    assert len(inputs["profiles"]) == 1
    card = _valid_card()
    card["signature_moves"] = []
    card["anti_signature"] = []
    assert dws.parse_card(json.dumps(card))["anti_signature"] == []


def test_work_style_preview_exposes_actual_source(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, n_annotated=1)
    monkeypatch.setattr(dws, "KB_ROOT", kb)
    source = kb / "novels/书A/scenes/scene_S01.md"
    source.write_text("前" * (dws.SAMPLE_CHARS + 1) + "后段改成第一人称。")
    sample = dws.collect_inputs("书A")["samples"][0]
    assert sample["text_truncated"] is True
    assert "第一人称" not in sample["text"]
    assert "第一人称" in Path(sample["source_path"]).read_text()
