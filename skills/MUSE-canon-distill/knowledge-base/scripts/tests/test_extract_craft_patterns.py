from __future__ import annotations

import importlib
import json
from pathlib import Path

import yaml


ecp = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.extract_craft_patterns")


def _make_kb(tmp_path: Path, *, sidecar: bool = False) -> Path:
    kb = tmp_path / "knowledge-base"
    notes = kb / "novels" / "书A" / "craft_notes"
    notes.mkdir(parents=True)
    (notes / "scene_S01_beats.md").write_text("## 手艺\n- 动词连缀", encoding="utf-8")
    if sidecar:
        (notes / "scene_S01_beats.yaml").write_text("scene_id: S01\npatterns: []\n", encoding="utf-8")
    return kb


def _raw_patterns() -> str:
    return json.dumps(
        {
            "patterns": [
                {
                    "beat": "拔剑对峙",
                    "dimension": "verb",
                    "original_move": "用动作链推进，不写心理",
                    "ai_default_failure": "为每个动作补情绪解释",
                    "transfer_rule": "高压节拍里动词可替代心理陈述",
                    "quote": "拔剑、转身",
                },
                {
                    "beat": "门外沉默",
                    "dimension": "omission",
                    "original_move": "只写手势省略心理",
                    "ai_default_failure": "直说害怕",
                    "transfer_rule": "可见动作能承载情绪时省略直陈",
                    "quote": "只写手势",
                },
            ],
            "overall_traits": ["动作承担情绪"],
            "narrative_organization": {
                "presentation": "先给远处火光，再进入现场",
                "transition_anchor": "同一声钟响",
                "knowledge_change": "读者确认两线发生于同夜",
                "effect": "延迟确认灾难规模",
                "source_anchor": "第三章末",
            },
        },
        ensure_ascii=False,
    )


def test_collect_todo_skips_existing_sidecar_unless_force(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, sidecar=True)
    monkeypatch.setattr(ecp, "KB_ROOT", kb)

    assert ecp.collect_todo("书A", force=False, limit=10) == []
    todo = ecp.collect_todo("书A", force=True, limit=10)

    assert len(todo) == 1
    assert todo[0].name == "scene_S01_beats.md"


def test_parse_extraction_validates_dimension_and_assigns_ids():
    data = ecp.parse_extraction(_raw_patterns(), "S01")

    assert [p["pattern_id"] for p in data["patterns"]] == ["S01-p1", "S01-p2"]

    bad = json.loads(_raw_patterns())
    bad["patterns"][0]["dimension"] = "bad"
    try:
        ecp.parse_extraction(json.dumps(bad, ensure_ascii=False), "S01")
    except ValueError as e:
        assert "dimension" in str(e)
    else:
        raise AssertionError("expected invalid dimension")


def test_write_sidecar_yaml_roundtrip(tmp_path):
    out = tmp_path / "scene_S01_beats.yaml"
    data = ecp.parse_extraction(_raw_patterns(), "S01")

    ecp.write_sidecar(out, "S01", "scene_S01_beats.md", data)

    loaded = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert loaded["scene_id"] == "S01"
    assert loaded["source_notes"] == "scene_S01_beats.md"
    assert loaded["patterns"][0]["pattern_id"] == "S01-p1"
    assert loaded["patterns"][0]["original_move"] == "用动作链推进，不写心理"
    assert loaded["overall_traits"] == ["动作承担情绪"]
    assert loaded["narrative_organization"]["knowledge_change"] == "读者确认两线发生于同夜"


def test_parse_extraction_rejects_unknown_narrative_organization_field():
    raw = json.loads(_raw_patterns())
    raw["narrative_organization"]["beat_count"] = 3

    try:
        ecp.parse_extraction(json.dumps(raw, ensure_ascii=False), "S01")
    except ValueError as e:
        assert "未知字段" in str(e)
    else:
        raise AssertionError("expected unknown narrative organization field rejection")


def test_parse_extraction_drama_dimension_enum():
    raw = json.loads(_raw_patterns())
    raw["patterns"] = raw["patterns"][:1]
    raw["patterns"][0]["dimension"] = "blocking"

    data = ecp.parse_extraction(json.dumps(raw, ensure_ascii=False), "A1", "drama")
    assert data["patterns"][0]["dimension"] == "blocking"

    raw["patterns"][0]["dimension"] = "camera"  # prose 专属维度，对 drama 拒收
    try:
        ecp.parse_extraction(json.dumps(raw, ensure_ascii=False), "A1", "drama")
    except ValueError as e:
        assert "medium=drama" in str(e)
    else:
        raise AssertionError("expected drama enum rejection")


def test_craft_counterexample_is_optional_and_keeps_existing_evidence():
    data = json.loads(_raw_patterns())
    data["patterns"][0].pop("ai_default_failure")
    result = ecp.parse_extraction(json.dumps(data), "S01")
    assert "ai_default_failure" not in result["patterns"][0]
    assert result["patterns"][1]["ai_default_failure"] == "直说害怕"
    assert result["patterns"][0]["transfer_rule"] == data["patterns"][0]["transfer_rule"]
