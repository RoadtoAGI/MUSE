from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import yaml


bic = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.build_inspiration_cards")


IDX_MAP = {"书A": {"scene_01", "scene_02", "scene_14"}, "书B": {"S01", "S02"}}


def _card(card_id: str = "mentor-death") -> dict:
    return {
        "card_id": card_id,
        "pattern_name": "导师之死范式",
        "dramatic_function": "以不可逆失去迫使主角承担使命",
        "applicability": "Phase 3/4 的转折或代价节点",
        "reuse_candidates": ["具体死法"],
        "tags": ["师徒", "丧失"],
        "phase_affinity": [3, 4],
        "source_scenes": [{"novel": "书A", "scene_id": "scene_14", "note": "导师死亡后主角承诺"}],
    }


def test_contract_fields_use_reuse_candidates():
    legacy_field = "do_" + "not_copy"

    assert "reuse_candidates" in bic.CARD_FIELDS
    assert "reuse_candidates" in bic.NOMINATION_FIELDS
    assert legacy_field not in bic.CARD_FIELDS
    assert legacy_field not in bic.NOMINATION_FIELDS
    assert "- reuse_candidates:" in bic.NOMINATE_INSTRUCTIONS
    assert "reuse_candidates" in bic.CLUSTER_INSTRUCTIONS


def test_validate_card_rejects_legacy_field():
    card = _card()
    legacy_field = "do_" + "not_copy"
    card[legacy_field] = ["不要复制具体死法"]

    with pytest.raises(ValueError, match=legacy_field):
        bic.validate_card(card, IDX_MAP)


@pytest.mark.parametrize(
    ("candidates", "message"),
    [
        ([], "reuse_candidates 必须是非空列表"),
        ("具体死法", "reuse_candidates 必须是非空列表"),
        ([""], "reuse_candidates 元素必须是非空字符串"),
        (["具体死法", "   "], "reuse_candidates 元素必须是非空字符串"),
        (["具体死法", 1], "reuse_candidates 元素必须是非空字符串"),
    ],
)
def test_validate_card_requires_nonempty_string_candidates(candidates, message):
    card = _card()
    card["reuse_candidates"] = candidates

    with pytest.raises(ValueError, match=message):
        bic.validate_card(card, IDX_MAP)


@pytest.mark.parametrize(
    "candidate",
    [
        "  不要照抄具体死法",
        "\t不要照搬: 具体死法",
        "不要复制：具体死法",
        "不要把仪式写成治愈完成",
    ],
)
def test_validate_card_rejects_legacy_negative_prefix_candidates(candidate):
    card = _card()
    card["reuse_candidates"] = [candidate]

    with pytest.raises(ValueError, match="废弃否定前缀"):
        bic.validate_card(card, IDX_MAP)


def test_validate_card_allows_quoted_negative_phrase_reference():
    card = _card()
    card["reuse_candidates"] = ["「不要回答」三连警告原文"]

    clean = bic.validate_card(card, IDX_MAP)

    assert clean["reuse_candidates"] == ["「不要回答」三连警告原文"]


def test_validate_card_rejects_bad_id_and_missing_fields():
    with pytest.raises(ValueError, match="card_id"):
        bic.validate_card(_card("导师之死"), IDX_MAP)

    with pytest.raises(ValueError, match="顺序编号"):
        bic.validate_card(_card("ins-001"), IDX_MAP)

    bad = _card()
    bad.pop("tags")
    with pytest.raises(ValueError, match="缺字段"):
        bic.validate_card(bad, IDX_MAP)


def test_validate_card_requires_exact_scene_id_and_drops_nonexact_sources(capsys):
    card = _card()
    card["source_scenes"] = [
        {"novel": "书A", "scene_id": "scene_14", "note": "exact source"},
        {"novel": "书A", "scene_id": "S14", "note": "形态不同，不做猜配"},
        {"novel": "书A", "scene_id": "phase1-creative_constraints", "note": "幻觉佐证,应剔除"},
    ]
    clean = bic.validate_card(card, IDX_MAP)
    assert clean["source_scenes"] == [
        {"novel": "书A", "scene_id": "scene_14", "note": "exact source"}
    ]
    assert "佐证不存在已剔除" in capsys.readouterr().err


def test_validate_card_rejects_all_ghost_sources():
    card = _card()
    card["source_scenes"] = [{"novel": "书C", "scene_id": "S01", "note": "书不存在"}]
    with pytest.raises(ValueError, match="全部佐证不存在"):
        bic.validate_card(card, IDX_MAP)


def test_normalize_scene_id_is_exact_join():
    assert bic.normalize_scene_id("书A", "scene_01", IDX_MAP) == "scene_01"
    assert bic.normalize_scene_id("书A", "S01", IDX_MAP) is None
    assert bic.normalize_scene_id("书A", "01", IDX_MAP) is None
    assert bic.normalize_scene_id("书B", "scene_02", IDX_MAP) is None
    assert bic.normalize_scene_id("书A", "S99", IDX_MAP) is None


def test_read_phase_summary_projects_tail_structure_without_truncation(tmp_path):
    work = tmp_path / "书A"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    filler = "x" * 9000
    (pipeline / "phase4_structure.yaml").write_text(
        yaml.safe_dump(
            {
                "analysis_meta": {"note": filler},
                "arc_expansions": [{"arc_id": "ARC-1", "sequences": []}],
                "narrative_threads": [
                    {
                        "name": "政治线",
                        "description": "改变军事资源",
                        "evidence_scenes": [{"scene_id": "scene_14", "note": "资源被截断"}],
                    }
                ],
                "thread_intersections": [
                    {"threads": ["政治线", "军事线"], "cross_effect": "预算被取消"}
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = bic._read_phase_summary(work)

    assert "narrative_threads" in summary
    assert "thread_intersections" in summary
    assert filler not in summary


def test_read_phase_summary_preserves_collection_unit_identity(tmp_path):
    work = tmp_path / "合集A"
    pipeline = work / "pipeline"
    unit = pipeline / "短篇甲"
    unit.mkdir(parents=True)
    (pipeline / "phase0_conception.yaml").write_text(
        yaml.safe_dump({"premise": "共享世界"}, allow_unicode=True),
        encoding="utf-8",
    )
    (unit / "phase3_spine.yaml").write_text(
        yaml.safe_dump(
            {
                "reader_spine": {
                    "reader_waits_to_know": "短篇甲的问题",
                    "recognition_object": "短篇甲的确认物",
                }
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    summary = bic._read_phase_summary(work)

    assert "## phase0_conception.yaml" in summary
    assert "## 短篇甲/phase3_spine.yaml" in summary
    assert "短篇甲的问题" in summary


def test_read_phase_summary_projects_legacy_phase5_scenes(tmp_path):
    work = tmp_path / "合集A"
    unit = work / "pipeline" / "短篇甲"
    unit.mkdir(parents=True)
    (unit / "phase5_scenes.yaml").write_text(
        yaml.safe_dump(
            {
                "scenes": [
                    {
                        "scene_id": "A-S01",
                        "label": "旧结构私有字段",
                        "source_chapter": "短篇甲",
                        "beat_direction": {"function": "由观察转为追逐"},
                        "narrative_evidence": {
                            "presentation": "先给预警，再以碎裂声交代结果",
                            "effect": "安全屏障失效",
                        },
                    }
                ],
                "pacing_curve": {"shape": "缓到急"},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = bic._read_phase_summary(work)

    assert "## 短篇甲/phase5_scenes.yaml" in summary
    assert "scene_id: A-S01" in summary
    assert "narrative_evidence" in summary
    assert "先给预警，再以碎裂声交代结果" in summary
    assert "旧结构私有字段" not in summary
    assert "pacing_curve" not in summary


def test_read_phase_summary_keeps_standard_phase5_projection(tmp_path):
    work = tmp_path / "书A"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "phase5_scenes.yaml").write_text(
        yaml.safe_dump(
            {
                "sequence_expansions": [
                    {
                        "seq_id": "ARC1-SEQ1",
                        "private_note": "不进入任务包",
                        "scenes": [
                            {
                                "scene_id": "S01",
                                "private_note": "不进入任务包",
                                "narrative_evidence": {
                                    "presentation": "先展示后果，再补交原因"
                                },
                            }
                        ],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = bic._read_phase_summary(work)

    assert "sequence_expansions" in summary
    assert "seq_id: ARC1-SEQ1" in summary
    assert "scene_id: S01" in summary
    assert "先展示后果，再补交原因" in summary
    assert "private_note" not in summary


def test_read_phase_summary_omits_empty_collection_projection(tmp_path):
    work = tmp_path / "合集A"
    unit = work / "pipeline" / "短篇甲"
    unit.mkdir(parents=True)
    (unit / "phase3_spine.yaml").write_text(
        yaml.safe_dump({"legacy_only": "当前消费者不读取"}, allow_unicode=True),
        encoding="utf-8",
    )

    assert bic._read_phase_summary(work) == "(none)"


def test_read_phase_summary_omits_empty_legacy_phase5(tmp_path):
    work = tmp_path / "合集A"
    unit = work / "pipeline" / "短篇甲"
    unit.mkdir(parents=True)
    (unit / "phase5_scenes.yaml").write_text("scenes: []\n", encoding="utf-8")

    assert bic._read_phase_summary(work) == "(none)"


def test_write_card_and_rebuild_index(tmp_path):
    insp = tmp_path / "inspiration"

    out = bic.write_card(insp, bic.validate_card(_card(), IDX_MAP))
    backlinks = bic.rebuild_index(insp)

    assert out.name == "mentor-death.yaml"
    assert (insp / "index.md").exists()
    assert backlinks == {"书A|scene_14": ["mentor-death"]}
    index_md = (insp / "index.md").read_text(encoding="utf-8")
    assert "mentor-death" in index_md and "师徒" in index_md
    written = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert written["reuse_candidates"] == ["具体死法"]
    assert ("do_" + "not_copy") not in written


def test_rebuild_index_ignores_nominations(tmp_path):
    insp = tmp_path / "inspiration"
    bic.write_card(insp, bic.validate_card(_card(), IDX_MAP))
    nom = insp / "_nominations"
    nom.mkdir()
    (nom / "bad.yaml").write_text(
        yaml.safe_dump(_card("bad-card"), allow_unicode=True), encoding="utf-8")

    backlinks = bic.rebuild_index(insp)

    assert backlinks == {"书A|scene_14": ["mentor-death"]}
    assert "bad-card" not in (insp / "index.md").read_text(encoding="utf-8")


def test_ingest_cluster_replace_clears_old_cards(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    work = kb / "novels" / "书A"
    work.mkdir(parents=True)
    (work / "scene_index.json").write_text(
        json.dumps([{"scene_id": "scene_14"}], ensure_ascii=False), encoding="utf-8")
    insp = kb / "inspiration"
    monkeypatch.setattr(bic, "KB_ROOT", kb)
    monkeypatch.setattr(bic, "INSPIRATION_DIR", insp)

    stale = _card("stale-card")
    stale["source_scenes"] = [{"novel": "书A", "scene_id": "scene_14", "note": "n"}]
    bic.write_card(insp, stale)

    out_file = tmp_path / "cluster.out.json"
    out_file.write_text(json.dumps({"cards": [_card()]}, ensure_ascii=False), encoding="utf-8")
    rc = bic.ingest_cluster(str(out_file), replace=True)

    assert rc == 0
    names = {p.name for p in insp.glob("*.yaml")}
    assert names == {"mentor-death.yaml"}


def test_ingest_cluster_rejected_replacement_preserves_cards_and_indexes(tmp_path, monkeypatch):
    insp = tmp_path / "inspiration"
    monkeypatch.setattr(bic, "INSPIRATION_DIR", insp)
    monkeypatch.setattr(bic, "load_idx_map", lambda: IDX_MAP)
    bic.write_card(insp, _card("prior-card"))
    bic.rebuild_index(insp)
    before = {p.name: p.read_bytes() for p in insp.iterdir()}
    invalid = _card("invalid-card")
    invalid["source_scenes"][0]["scene_id"] = "missing"
    output = tmp_path / "cluster.json"
    output.write_text(json.dumps({"cards": [_card("new-card"), invalid]}), encoding="utf-8")

    assert bic.ingest_cluster(str(output), replace=True) == 1
    assert {p.name: p.read_bytes() for p in insp.iterdir()} == before


def test_ingest_nominate_rejects_legacy_negative_prefix_candidate(
    tmp_path, monkeypatch, capsys
):
    kb = tmp_path / "kb"
    work = kb / "novels" / "书A"
    work.mkdir(parents=True)
    (work / "scene_index.json").write_text(
        json.dumps([{"scene_id": "scene_14"}], ensure_ascii=False), encoding="utf-8"
    )
    inspiration = kb / "inspiration"
    monkeypatch.setattr(bic, "KB_ROOT", kb)
    monkeypatch.setattr(bic, "INSPIRATION_DIR", inspiration)
    payload = {
        "novel": "书A",
        "nominations": [
            {
                "pattern_name": "导师之死范式",
                "dramatic_function": "以不可逆失去迫使主角承担使命",
                "applicability": "Phase 3/4 的转折或代价节点",
                "reuse_candidates": ["不要照搬导师死法"],
                "tags": ["师徒", "丧失"],
                "evidence_scenes": [
                    {"scene_id": "scene_14", "note": "导师死亡后主角承诺"}
                ],
            }
        ],
    }
    out_file = tmp_path / "nomination.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    rc = bic.ingest_nominate(str(out_file))

    assert rc == 1
    assert "废弃否定前缀" in capsys.readouterr().err
    assert not (inspiration / "_nominations" / "书A.json").exists()


def test_drama_phase_material_reaches_nomination_with_its_conditions(tmp_path):
    work = tmp_path / "dramas" / "广播剧"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    fixtures = {
        "phase1_world_stage.yaml": {"primary_space": "隔门听声", "rules": ["甲无法看见室内"]},
        "phase2_roles.yaml": {"roles": {"jia": {"name": "甲", "desire": "确认门内人的身份"}}},
        "phase4_act_sequence.yaml": {"acts": [{"act_id": "A1", "end_state": "身份仍未揭示"}]},
        "phase5_scene_table.yaml": {"scenes": [{"scene_id": "A1S1", "stageable_actions": ["声音突然中断"], "notes": "观众也未看见门内"}]},
    }
    for name, value in fixtures.items():
        (pipeline / name).write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")
    summary = bic._read_phase_summary(work)
    for expected in ["甲无法看见室内", "确认门内人的身份", "身份仍未揭示", "声音突然中断", "观众也未看见门内"]:
        assert expected in summary


def test_drama_craft_notes_without_fixed_heading_reach_nomination(tmp_path):
    work = tmp_path / "dramas" / "测试剧"
    notes = work / "craft_notes"
    notes.mkdir(parents=True)
    (notes / "scene_A1S1_beats.md").write_text("## 上下场\n甲退场后，乙才向观众说明来意。", encoding="utf-8")
    assert "乙才向观众说明来意" in bic._read_craft_traits(work)
    (notes / "scene_A1S1_beats.yaml").write_text(yaml.safe_dump({
        "scene_id": "A1S1", "patterns": [{"original_move": "来意只向观众公开", "transfer_rule": "其他角色无法听见"}]
    }, allow_unicode=True), encoding="utf-8")
    result = bic._read_craft_traits(work)
    assert "来意只向观众公开" in result
    assert "其他角色无法听见" in result


def test_phase5_projection_preserves_source_context_and_function(tmp_path):
    """缓场的原作情境及信息作用随现有 Phase 投影进入提名上下文。"""
    scene = {"scene_id": "S1", "location": "厨房", "time": "次日", "participants": ["甲", "乙"], "pov": "甲", "scene_tasks": "等饭时让读者得知乙已把钥匙归还；人物关系未发生变化"}
    projected = bic._project_phase(tmp_path / "phase5_scenes.yaml", {"sequence_expansions": [{"seq_id": "Q1", "scenes": [scene]}]})
    assert projected["sequence_expansions"][0]["scenes"][0] == scene
