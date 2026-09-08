from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import yaml


dk = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.dialogue_kb")


def _write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _make_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge-base"
    work = kb / "novels" / "测试作品"
    scene = work / "scenes" / "scene_S01.md"
    scene.parent.mkdir(parents=True)
    scene.write_text("甲说：‘你还走？’\n乙说：‘走。现在。’\n", encoding="utf-8")
    (work / "scene_index.json").write_text(
        json.dumps(
            [
                {
                    "scene_id": "S01",
                    "file": "scenes/scene_S01.md",
                    "author": "测试作者",
                    "language": "zh",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    role = work / "characters" / "role-a"
    role.mkdir(parents=True)
    (role / "SKILL.md").write_text(
        "# 角色甲\n\n## 声音框架\n\n短答，不解释。证据：scenes/scene_S01.md:L1-L2\n",
        encoding="utf-8",
    )
    nested_role = work / "characters" / "单篇" / "role-c"
    nested_role.mkdir(parents=True)
    (nested_role / "SKILL.md").write_text(
        "# 角色丙\n\n## 声音框架\n\n只在单篇中出现。证据：scenes/scene_S01.md:L1-L2\n",
        encoding="utf-8",
    )
    _write_yaml(
        work / "dialogue" / "events" / "scene_S01.yaml",
        {
            "schema_version": "dialogue-scene-events/v1",
            "work_id": "novel:测试作品",
            "scene_id": "S01",
            "scene_file": "scenes/scene_S01.md",
            "events": [
                {
                    "event_id": "novel:测试作品:S01:e01",
                    "event_type": "interaction",
                    "context": {"relationship": "peer", "pressure": "departure"},
                    "participants": [
                        {"character_id": "novel:测试作品:role-a", "display_name": "甲"},
                        {"character_id": "novel:测试作品:role-b", "display_name": "乙"},
                    ],
                    "turns": [
                        {
                            "turn_id": "t01",
                            "speaker_id": "novel:测试作品:role-a",
                            "speaker_label": "甲",
                            "response_to": None,
                            "source_locator": "scenes/scene_S01.md:L1",
                            "text": "你还走？",
                        },
                        {
                            "turn_id": "t02",
                            "speaker_id": "novel:测试作品:role-b",
                            "speaker_label": "乙",
                            "response_to": "t01",
                            "source_locator": "scenes/scene_S01.md:L2",
                            "text": "走。现在。",
                        },
                    ],
                    "annotation": {
                        "source_file": "scenes/scene_S01.md",
                        "source_sha256": hashlib.sha256(scene.read_bytes()).hexdigest(),
                        "review_status": "source_checked",
                    },
                }
            ],
        },
    )
    return kb


def test_refresh_builds_source_backed_indexes_and_profiles(tmp_path):
    kb = _make_kb(tmp_path)

    assert dk.bootstrap_profiles(kb, write=True) == 2
    catalog = dk.build_catalog(kb, write=True)
    report = dk.build_indexes(kb, write=True)

    assert dk.verify(kb) == []
    assert catalog["works"][0]["processing_status"] == "complete"
    assert catalog["works"][0]["counts"]["dialogue_profiles"] == 2
    assert report["summary"] == {
        "works": 1,
        "complete_works": 1,
        "dialogue_events": 1,
        "dialogue_profiles": 2,
    }
    event_index = json.loads((kb / "dialogue" / "event_index.json").read_text(encoding="utf-8"))
    assert event_index["events"][0]["scene_id"] == "S01"
    assert event_index["events"][0]["scene_file"] == "scenes/scene_S01.md"
    profile = yaml.safe_load(
        (kb / "novels" / "测试作品" / "characters" / "role-a" / "dialogue-profile.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert profile["profile_tier"] == "compact"
    assert profile["prototype_eligible"] is False
    assert profile["baseline_voice"]["evidence_locators"] == ["scenes/scene_S01.md:L1-L2"]
    nested_profile = yaml.safe_load(
        (
            kb
            / "novels"
            / "测试作品"
            / "characters"
            / "单篇"
            / "role-c"
            / "dialogue-profile.yaml"
        ).read_text(encoding="utf-8")
    )
    assert nested_profile["character_id"] == "novel:测试作品:单篇--role-c"


def test_bootstrap_preserves_full_text_voice_evidence(tmp_path):
    kb = _make_kb(tmp_path)
    work = kb / "novels" / "测试作品"
    (work / "full_text.md").write_text(
        (work / "scenes" / "scene_S01.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    skill = work / "characters" / "role-a" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace("scenes/scene_S01.md:L1-L2", "full_text.md:L1-L2"),
        encoding="utf-8",
    )

    assert dk.bootstrap_profiles(kb, write=True) == 2
    profile = yaml.safe_load((skill.parent / "dialogue-profile.yaml").read_text(encoding="utf-8"))
    assert profile["baseline_voice"]["evidence_locators"] == ["full_text.md:L1-L2"]
    assert "full_text.md:L1-L2" in profile["baseline_voice"]["observed_summary"]


def test_verify_rejects_a_turn_not_present_at_its_locator(tmp_path):
    kb = _make_kb(tmp_path)
    event_path = kb / "novels" / "测试作品" / "dialogue" / "events" / "scene_S01.yaml"
    event = yaml.safe_load(event_path.read_text(encoding="utf-8"))
    event["events"][0]["turns"][1]["text"] = "没有出现在原文里的话"
    _write_yaml(event_path, event)

    errors = dk.verify(kb)

    assert any("turn text not found" in error for error in errors)


def test_dialogue_reader_uses_current_drama_index_and_legacy_json_container(tmp_path):
    work = tmp_path / "剧目"
    work.mkdir()
    (work / "scene_index.json").write_text(json.dumps({"entries": [{"scene_id": "old"}]}))
    assert dk.load_scene_index(work) == [{"scene_id": "old"}]
    (work / "dramatic_scene_index.jsonl").write_text(json.dumps({"scene_id": "current"}) + "\n")
    assert dk.load_scene_index(work) == [{"scene_id": "current"}]


def test_work_metadata_supplies_catalog_identity_without_per_scene_duplication(tmp_path):
    work = tmp_path / "剧目"
    work.mkdir()
    _write_yaml(work / "work-meta.yaml", {"author": "作者甲", "language": "zh"})
    (work / "dramatic_scene_index.jsonl").write_text(json.dumps({"scene_id": "A1S1", "lang": "mixed"}))
    metadata = dk.first_metadata(work)
    assert metadata["author"] == "作者甲"
    assert metadata["lang"] == "mixed"


def test_scoped_refresh_preserves_other_work_and_manual_registry_fields(tmp_path, monkeypatch):
    import copy
    import sys
    kb = _make_kb(tmp_path)
    work = kb / "novels" / "测试作品"
    dk.build_catalog(kb, write=True)
    dk.build_indexes(kb, write=True)
    registry_path = kb / "dialogue" / "corpus_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    registry["works"][0]["aliases"] = ["人工别名"]
    registry["works"][0]["editions"][0].update({"translator": "人工译者", "rights": "authorized"})
    other = copy.deepcopy(registry["works"][0])
    other.update({"work_id": "novel:其他作品", "title": "其他作品"})
    registry["works"].append(other)
    _write_yaml(registry_path, registry)
    index_path = kb / "dialogue" / "event_index.json"
    index = json.loads(index_path.read_text())
    other_event = copy.deepcopy(index["events"][0])
    other_event["work_id"] = "novel:其他作品"
    other_event["event_id"] = "novel:其他作品:S01:e01"
    index["events"].append(other_event)
    index_path.write_text(json.dumps(index, ensure_ascii=False))
    monkeypatch.setattr(sys, "argv", ["dialogue_kb.py", "--kb-root", str(kb), "--work-dir", str(work), "refresh", "--write"])
    assert dk.main() == 0
    updated = yaml.safe_load(registry_path.read_text())
    chosen = next(item for item in updated["works"] if item["work_id"] == "novel:测试作品")
    assert chosen["aliases"] == ["人工别名"]
    assert chosen["editions"][0]["translator"] == "人工译者"
    assert chosen["editions"][0]["rights"] == "authorized"
    assert next(item for item in updated["works"] if item["work_id"] == other["work_id"]) == other
    assert other_event in json.loads(index_path.read_text())["events"]
    assert not list((work / "characters").rglob("dialogue-profile.yaml"))


def test_event_requires_original_text_and_valid_addressee(tmp_path):
    kb = _make_kb(tmp_path)
    path = kb / "novels" / "测试作品" / "dialogue" / "events" / "scene_S01.yaml"
    document = yaml.safe_load(path.read_text())
    document["events"][0]["turns"][0]["text"] = ""
    document["events"][0]["turns"][1]["addressee_ids"] = ["absent"]
    _write_yaml(path, document)
    errors = dk.verify(kb)
    assert any("nonempty original text" in error for error in errors)
    assert any("addressee_ids" in error for error in errors)


def test_index_keeps_specific_drama_medium(tmp_path):
    kb = _make_kb(tmp_path)
    work = kb / "novels" / "测试作品"
    _write_yaml(work / "work-meta.yaml", {"source_medium": "radio_play"})
    dk.build_indexes(kb, write=True, work_dir=work)
    event = json.loads((kb / "dialogue" / "event_index.json").read_text())["events"][0]
    assert event["medium"] == "radio_play"
    assert event["work_id"] == "novel:测试作品"
