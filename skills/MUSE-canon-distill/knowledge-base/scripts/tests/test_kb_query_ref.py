from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml


kq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_query")


STYLE_PROFILE = {
    "narration_voice": "全知说书",
    "diction": "半文半白",
    "rhetoric_density": "medium",
    "dialogue_mode": "对白点睛",
    "pacing": "短句连动",
}


def _scene_text() -> str:
    return "\n\n".join(
        [
            "第一段。第二句。",
            "第二段。第二句。",
            "第三段。第二句。",
            "第四段。第二句。",
            "第五段。第二句。",
        ]
    )


def _make_kb(tmp_path: Path, *, sidecar: bool = True, raw_md: bool = False, style_card: bool = True) -> Path:
    kb = tmp_path / "knowledge-base"
    work = kb / "novels" / "书A"
    (work / "scenes").mkdir(parents=True)
    (work / "craft_notes").mkdir()
    (work / "scenes" / "scene_S01.md").write_text(_scene_text(), encoding="utf-8")
    (work / "scenes" / "scene_S02.md").write_text(_scene_text(), encoding="utf-8")
    (work / "scene_index.json").write_text(
        json.dumps(
            [
                {
                    "scene_id": "S01",
                    "novel": "书A",
                    "file": "scenes/scene_S01.md",
                    "style_profile": STYLE_PROFILE,
                },
                {
                    "scene_id": "S02",
                    "novel": "书A",
                    "file": "scenes/scene_S02.md",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if style_card:
        (work / "style_card.yaml").write_text(
            yaml.safe_dump(
                {
                    "novel": "书A",
                    "author": "作者A",
                    "narration_voice": "全知",
                    "diction": "旧式话本腔",
                    "rhetoric_density": "medium",
                    "dialogue_mode": "归属用「某某道」",
                    "pacing": "快慢相间",
                    "signature_moves": ["短句连动"],
                    "anti_signature": ["不要现代口语"],
                    "author_cross_ref": "",
                    "style_card_by": "test",
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    if sidecar:
        (work / "craft_notes" / "scene_S01_beats.yaml").write_text(
            yaml.safe_dump(
                {
                    "scene_id": "S01",
                    "source_notes": "scene_S01_beats.md",
                    "patterns": [
                        {
                            "pattern_id": "S01-p1",
                            "beat": "拔剑对峙",
                            "dimension": "verb",
                            "original_move": "用动作链推进，不写心理",
                            "ai_default_failure": "为每个动作补情绪解释",
                            "transfer_rule": "高压节拍里动词可替代心理陈述",
                            "quote": "拔剑、转身",
                        }
                    ],
                    "overall_traits": ["动作承担情绪"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    if raw_md:
        (work / "craft_notes" / "scene_S01_beats.md").write_text("## 手艺\n原始手艺标注", encoding="utf-8")
    return kb


def _result(rank: int = 1, scene_id: str = "S01", style_profile: dict | None = None) -> dict:
    r = {
        "rank": rank,
        "score": 0.9,
        "match": "high",
        "novel": "书A",
        "author": "作者A",
        "scene_id": scene_id,
        "file": f"novels/书A/scenes/scene_{scene_id}.md",
        "description": "描述",
    }
    if style_profile is not None:
        r["style_profile"] = style_profile
    return r


def _render(tmp_path: Path, kb: Path, results: list[dict], **kwargs) -> str:
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb
    out = kq.save_reference_file(
        results, "query", None, str(tmp_path / "refs"), "T", max_chars=0, **kwargs
    )
    return Path(out).read_text(encoding="utf-8")


def _add_inspiration(kb: Path) -> None:
    insp = kb / "inspiration"
    insp.mkdir()
    (insp / "_backlinks.json").write_text(
        json.dumps({"书A|S01": ["mentor-death"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (insp / "mentor-death.yaml").write_text(
        yaml.safe_dump(
            {
                "card_id": "mentor-death",
                "pattern_name": "导师之死范式",
                "dramatic_function": "以不可逆失去迫使主角承担使命",
                "reuse_candidates": ["具体死法"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _add_rhetoric_index(kb: Path) -> None:
    rhetoric = kb / "rhetoric"
    rhetoric.mkdir(exist_ok=True)
    (rhetoric / "occurrence_index.json").write_text(
        json.dumps(
            {
                "schema_version": "rhetoric-occurrence-index/v1",
                "scope_status": "complete",
                "occurrences": [
                    {
                        "occurrence_id": "rh-test",
                        "work_id": "novels:书A",
                        "occurrence_file": "novels/书A/rhetoric/occurrences/rh-test.yaml",
                        "source_locator": "full_text.md:L10",
                        "figure_type": "simile",
                        "quote": "拔剑像骤然裂开的闪电",
                        "image_mechanism": "把拔剑速度转成闪电的突发亮线",
                        "property_alignment": "都突然出现；都沿单一路径切开视野",
                        "context_alignment": "对峙现场已有雷雨",
                        "narrative_function": "让攻击先于解释抵达读者",
                        "transfer_rule": "用现场已有物象呈现同构动作",
                        "failure_boundary": "缓慢动作缺少闪电的突发性",
                        "quality_assessment": "exemplary",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_exemplar_is_last_block(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result()])

    assert "不设字符或段落长度上限" in text
    assert "跨语言 reference 可翻译、转写或保留原文，由交付语言决定" in text
    assert "具体句子不得复制" not in text
    assert "勿抄表层元素" not in text
    assert "只迁移戏剧功能" not in text
    markers = ["文风画像", "作品文风卡", "**手艺拆解**", "段落密度观测", "<style_exemplar"]
    positions = [text.index(m) for m in markers]
    assert positions == sorted(positions)
    assert "</style_exemplar>" in text
    assert "<craft_notes" not in text[text.index("<style_exemplar"):]
    assert "3-5 条" not in text
    assert "覆盖五维" not in text
    assert "不设数量和维度覆盖配额" in text


def test_paired_function_bridge_is_opt_in_and_preserves_tier_boundaries(tmp_path):
    kb = _make_kb(tmp_path)
    result = _result()
    result["description"] = "追逐者封死出口，迫使人物改走危险捷径"
    result["fit"] = 0.9

    plain = _render(tmp_path, kb, [result], function_hint="退路收窄 战术改道")
    paired = _render(
        tmp_path,
        kb,
        [result],
        function_hint="退路收窄 战术改道",
        paired_function_bridge=True,
    )

    assert "<function_bridge" not in plain
    assert '<function_bridge experimental="true" tier="full">' in paired
    assert "目标场景职责：退路收窄 战术改道" in paired
    assert "源场景职责线索：追逐者封死出口，迫使人物改走危险捷径" in paired
    assert "按 full 档复用契约接入当前故事" in paired
    assert paired.index("</function_bridge>") < paired.index("<style_exemplar")
    assert paired.rstrip().endswith("</style_exemplar>")


def test_paired_function_bridge_does_not_overclaim_low_fit_or_style_only(tmp_path):
    kb = _make_kb(tmp_path)
    material = _result()
    material["fit"] = 0.0
    style = _result(scene_id="S02")
    style["match"] = "style_only"

    material_text = _render(
        tmp_path, kb, [material], function_hint="守阵", paired_function_bridge=True
    )
    style_text = _render(
        tmp_path, kb, [style], function_hint="守阵", paired_function_bridge=True
    )

    assert 'tier="material"' in material_text
    assert 'tier="style"' in style_text


def test_reuse_mandate_header_reflects_match_tiers(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result()])
    assert "reuse_mandate: true" in text
    assert "reuse_tier: full" in text

    low = _result()
    low["match"] = "low"
    text_low = _render(tmp_path, kb, [low])
    assert "reuse_mandate: false" in text_low


def test_reuse_tier_header_three_way(tmp_path):
    kb = _make_kb(tmp_path)

    selected = _result()
    selected["match"] = "selected"
    text = _render(tmp_path, kb, [selected])
    assert "reuse_tier: full" in text
    assert "reuse_mandate: true" in text

    high_good_fit = _result()
    high_good_fit["fit"] = 0.9
    text = _render(tmp_path, kb, [high_good_fit])
    assert "reuse_tier: full" in text
    assert "reuse_mandate: true" in text

    high_low_fit = _result()
    high_low_fit["fit"] = 0.0
    text = _render(tmp_path, kb, [high_low_fit])
    assert "reuse_tier: material" in text
    assert "reuse_mandate: true" in text

    style_only = _result()
    style_only["match"] = "style_only"
    text = _render(tmp_path, kb, [style_only])
    assert "reuse_tier: style" in text
    assert "reuse_mandate: false" in text
    assert "本场只作文风参考" in text


def test_tier_mandate_invariant(tmp_path):
    kb = _make_kb(tmp_path)
    cases = []
    for match, fit in [("selected", None), ("high", 0.9), ("high", 0.0), ("style_only", None)]:
        r = _result()
        r["match"] = match
        if fit is not None:
            r["fit"] = fit
        cases.append(r)

    for r in cases:
        text = _render(tmp_path, kb, [r])
        tier = next(l for l in text.splitlines() if l.startswith("reuse_tier:")).split(": ", 1)[1]
        mandate = next(l for l in text.splitlines() if l.startswith("reuse_mandate:")).split(": ", 1)[1]
        assert mandate == ("false" if tier == "style" else "true")


def test_function_hint_missing_fields_tolerated():
    hint = "战前蓄势 守阵"
    entry_full = {"tags": ["战前蓄势", "守阵"], "conflict_type": "军事冲突", "description": "两军对峙"}
    entry_bare = {"description": "两军战前对峙"}
    entry_empty = {}

    assert kq._fit_score(hint, entry_full) > 0
    assert kq._fit_score(hint, entry_bare) >= 0
    assert kq._fit_score(hint, entry_empty) == 0.0


def test_reuse_shortlist_block_renders_from_three_sources(tmp_path):
    kb = _make_kb(tmp_path, sidecar=True, style_card=True)
    _add_inspiration(kb)

    text = _render(tmp_path, kb, [_result()])

    assert "## 复用候选（脚本聚合——第一优先素材）" in text
    assert "[书A S01·手艺拆解] 「拔剑、转身」" in text
    assert "[书A S01·灵感卡] 具体死法" in text
    assert "[书A·文风卡] 短句连动" in text
    assert text.index("## 复用候选") < text.index("<style_exemplar")


def test_rhetoric_cards_render_once_after_usage_protocol(tmp_path):
    kb = _make_kb(tmp_path)
    _add_rhetoric_index(kb)
    result = _result()
    result["description"] = "雨夜拔剑对峙"

    text = _render(tmp_path, kb, [result, _result(rank=2, scene_id="S02")])

    assert text.count("<rhetoric_cards") == 1
    assert "拔剑像骤然裂开的闪电" in text
    assert text.index("</usage_protocol>") < text.index("<rhetoric_cards")
    assert text.index("</rhetoric_cards>") < text.index("<style_exemplar")


def test_reuse_shortlist_omitted_when_no_assets(tmp_path):
    kb = _make_kb(tmp_path, sidecar=False, style_card=False)

    text = _render(tmp_path, kb, [_result()])

    assert "## 复用候选" not in text


@pytest.mark.parametrize("match", ["high", "selected"])
@pytest.mark.parametrize("shortform", [False, True])
def test_explicit_style_use_caps_selected_and_high_references(tmp_path, match, shortform):
    kb = _make_kb(tmp_path)
    _add_inspiration(kb)
    _add_lore(kb)
    result = dict(_result(), match=match)
    text = _render(tmp_path, kb, [result], reuse_mode="style_only",
                   intended_domains=["prose_style_imitation"], worldview="书A",
                   shortform_pack=shortform, function_hint="对峙", paired_function_bridge=True)

    assert "reuse_mode: style_only" in text
    assert 'intended_domains: ["prose_style_imitation"]' in text
    assert "reuse_tier: style" in text and "reuse_mandate: false" in text
    assert 'tier="full"' not in text
    assert '<worldview_lore' not in text
    assert '## 复用候选' not in text
    assert '可直接复用的表层元素' not in text
    assert _scene_text() in text


def test_world_only_scope_is_material_and_explicit_scene_reuse_remains_full(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb)
    selected = dict(_result(), match="selected")
    material = _render(tmp_path, kb, [selected], reuse_mode="maximize_apt_reuse",
                       intended_domains=["world_rule"], worldview="书A")
    assert "reuse_tier: material" in material and "reuse_mandate: true" in material
    assert '<worldview_lore' in material
    full = _render(tmp_path, kb, [selected], reuse_mode="maximize_apt_reuse",
                   intended_domains=["scene_carrier", "prose_style_imitation"])
    assert "reuse_tier: full" in full and "reuse_mandate: true" in full


def test_mixed_manual_sources_keep_per_work_scope_and_global_caps(tmp_path):
    kb = _make_kb(tmp_path)
    second = kb / "novels" / "书B" / "scenes"
    second.mkdir(parents=True)
    (second / "scene_S01.md").write_text(_scene_text(), encoding="utf-8")
    profile = tmp_path / "phase0.yaml"
    profile.write_text(yaml.safe_dump({"canon_reference_profile": {
        "user_reference_materials": [
            {"work": "书A", "stance": "prefer", "reuse_mode": "style_only",
             "intended_domains": ["prose_style_imitation"]},
            {"work": "书B", "stance": "prefer", "reuse_mode": "maximize_apt_reuse",
             "intended_domains": ["scene_carrier", "prose_style_imitation"]},
        ]}}, allow_unicode=True))
    selected = [dict(_result(), match="selected"),
                dict(_result(rank=2), novel="书B", file="novels/书B/scenes/scene_S01.md", match="selected")]
    results = kq.bind_reference_profile(selected, str(profile))
    for shortform in (False, True):
        text = _render(tmp_path, kb, results, reuse_mode="maximize_apt_reuse", shortform_pack=shortform)
        scopes = [part.split("</reference_scope>", 1)[0] for part in text.split("<reference_scope ")[1:]]
        assert "reuse_tier: style" in scopes[0] and "reuse_mode: style_only" in scopes[0]
        assert "reuse_tier: full" in scopes[1] and "reuse_mandate: true" in scopes[1]
        text = _render(tmp_path, kb, results, intended_domains=["prose_style_imitation"], shortform_pack=shortform)
        assert "reuse_tier: full" not in text
        assert "reuse_mandate: true" not in text
    unbound = dict(_result(), novel="书A续篇")
    assert "reuse_mode" not in kq.bind_reference_profile([unbound], str(profile))[0]


@pytest.mark.parametrize("source_scope", [
    {"reuse_mode": "style_only"},
    {"stance": "avoid"},
])
@pytest.mark.parametrize("worldview_name", ["书A", " 书 Ａ "])
def test_worldview_profile_applies_without_same_work_scene(tmp_path, source_scope, worldview_name):
    kb = _make_kb(tmp_path)
    _add_lore(kb)
    profile = tmp_path / "phase0.yaml"
    profile.write_text(yaml.safe_dump({"canon_reference_profile": {
        "user_reference_materials": [{"work": "书A", **source_scope}]
    }}, allow_unicode=True), encoding="utf-8")
    other = dict(_result(), novel="书B", match="selected")
    text = _render(tmp_path, kb, [other], worldview=worldview_name,
                   canon_reference_profile=str(profile))
    assert "<worldview_lore" not in text
    assert "worldview_reuse:" not in text
    assert "reuse_tier: full" in text


def test_worldview_disjoint_domains_does_not_load_lore(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb)
    scoped = dict(_result(), intended_domains=["prose_style_imitation"])
    text = _render(tmp_path, kb, [scoped], worldview="书A",
                   intended_domains=["world_rule"])
    assert "<worldview_lore" not in text
    assert "worldview_reuse:" not in text


def test_authoritative_craft_path_and_sibling_sidecar_reach_reference(tmp_path):
    kb = _make_kb(tmp_path, sidecar=False, style_card=False)
    work = kb / "novels" / "书A"
    index_path = work / "scene_index.json"
    index = json.loads(index_path.read_text())
    index[0]["craft_notes_file"] = "scenes/scene_S01_craft.md"
    index_path.write_text(json.dumps(index))
    notes = work / index[0]["craft_notes_file"]
    notes.write_text("来自显式路径的手艺解释", encoding="utf-8")
    text = _render(tmp_path, kb, [_result()])
    assert "来自显式路径的手艺解释" in text
    notes.with_suffix(".yaml").write_text(yaml.safe_dump({
        "patterns": [{"pattern_id": "S01-p1", "original_move": "显式来源的结构化解释"}]
    }, allow_unicode=True))
    text = _render(tmp_path, kb, [_result()])
    assert "显式来源的结构化解释" in text
    assert "来自显式路径的手艺解释" not in text
    notes.unlink()
    notes.with_suffix(".yaml").unlink()
    text = _render(tmp_path, kb, [_result()])
    assert "来自显式路径的手艺解释" not in text


def _add_lore(kb: Path, novel: str = "书A") -> None:
    pipeline = kb / "novels" / novel / "pipeline"
    pipeline.mkdir(parents=True, exist_ok=True)
    (pipeline / "phase1_world.yaml").write_text(
        yaml.safe_dump(
            {
                "setting": {"era": "架空古代"},
                "world_rules": {"physical": ["无魔法"]},
                "genre_conventions": ["江湖恩怨"],
                "daily_life": [{"dimension": "饮食", "findings": [{"detail": "粗茶淡饭"}]}],
                "creative_constraints": [{"constraint": "无枪械", "narrative_function": "近战冲突"}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (pipeline / "phase0_conception.yaml").write_text(
        yaml.safe_dump(
            {
                "premise": "一个复仇者的旅程",
                "genre": {"primary": "武侠", "conventions": [{"characters": "侠客道义"}]},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_worldview_flag_renders_lore_block_and_header(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb, novel="书A")
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb
    text = Path(
        kq.save_reference_file(
            [_result()], "query", None, str(tmp_path / "refs"), "T",
            max_chars=0, worldview="书A",
        )
    ).read_text(encoding="utf-8")

    assert "worldview_reuse: 书A" in text
    assert '<worldview_lore novel="书A">' in text
    assert "一个复仇者的旅程" in text
    assert "架空古代" in text
    assert "侠客道义" in text
    assert text.index("<worldview_lore") < text.index("<style_exemplar")


def test_worldview_lore_renders_once_for_multiple_exemplars(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb, novel="书A")
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb

    text = Path(
        kq.save_reference_file(
            [_result(rank=1), _result(rank=2, scene_id="S02")],
            "query", None, str(tmp_path / "refs"), "T",
            max_chars=0, worldview="书A",
        )
    ).read_text(encoding="utf-8")

    assert text.count('<worldview_lore novel="书A">') == 1
    assert text.rstrip().endswith("</style_exemplar>")


def test_shortform_pack_keeps_raw_reference_and_omits_design_analysis(tmp_path):
    kb = _make_kb(tmp_path, sidecar=True, style_card=True)
    _add_inspiration(kb)
    _add_lore(kb)
    _add_rhetoric_index(kb)
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb

    out = kq.save_reference_file(
        [_result()], "query", "末世", str(tmp_path / "pipeline" / "shortform"), None,
        max_chars=0, worldview="书A", shortform_pack=True,
    )
    text = Path(out).read_text(encoding="utf-8")

    assert Path(out).name == "reference_pack.md"
    assert text.startswith("# 短篇名著参考包")
    assert "reuse_tier: full" in text
    assert '<worldview_lore novel="书A">' in text
    assert "文风画像" in text
    assert "作品文风卡" in text
    assert "段落密度观测" in text
    assert "第一段。第二句。" in text
    assert "## 复用候选" not in text
    assert "**手艺拆解**" not in text
    assert "原始手艺标注" not in text
    assert "灵感卡·" not in text
    assert "<rhetoric_cards" not in text
    assert "具体死法" not in text
    assert text.rstrip().endswith("</style_exemplar>")


def test_filter_normalization_handles_fullwidth_and_separator_spacing():
    assert kq._genre_matches("末日 ／ 病毒灾难", "末日/病毒灾难")
    assert kq._normalized_contains(" 狂 病 ", "狂病")


def test_worldview_lookup_uses_same_title_normalization(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb, novel="书A")

    assert kq._load_lore(kb, " 书 Ａ ") is not None


def test_worldview_absent_keeps_ref_byte_identical(tmp_path):
    kb = _make_kb(tmp_path)
    _add_lore(kb, novel="书A")

    with_none = _render(tmp_path, kb, [_result()])
    (tmp_path / "refs").rename(tmp_path / "refs_noarg")
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb
    explicit_none = Path(
        kq.save_reference_file(
            [_result()], "query", None, str(tmp_path / "refs_explicit"), "T",
            max_chars=0, worldview=None,
        )
    ).read_text(encoding="utf-8")

    assert with_none == explicit_none
    assert "worldview_reuse" not in with_none
    assert "<worldview_lore" not in with_none


def test_worldview_missing_pipeline_degrades(tmp_path, capsys):
    kb = _make_kb(tmp_path)  # 无 pipeline/ 目录

    text = _render(tmp_path, kb, [_result()])

    assert "worldview_reuse" not in text
    assert "<worldview_lore" not in text
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb
    kq.save_reference_file(
        [_result()], "query", None, str(tmp_path / "refs2"), "T",
        max_chars=0, worldview="书A",
    )
    assert "worldview lore 装载失败" in capsys.readouterr().err


def test_stylometry_block_renders_for_rank1_only(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result(rank=1), _result(rank=2, scene_id="S02")])

    assert text.count("**量化文风诊断**") == 1
    assert "dash_per_1k:" in text
    assert "pro_drop_ratio:" in text
    assert "数值偏离不自动要求改写" in text
    assert text.index("**量化文风诊断**") < text.index("<style_exemplar")


def test_sidecar_table_replaces_raw_md(tmp_path):
    kb = _make_kb(tmp_path, sidecar=True, raw_md=True)

    text = _render(tmp_path, kb, [_result()])

    assert "| S01-p1 | 拔剑对峙 | 用动作链推进，不写心理 |" in text
    assert "整体手艺特征：动作承担情绪" in text
    assert "原始手艺标注" not in text


def test_sidecar_table_renders_quote_column(tmp_path):
    kb = _make_kb(tmp_path, sidecar=True)

    text = _render(tmp_path, kb, [_result()])

    assert "| id | 节拍 | 原作怎么做 | 对照说明 | 迁移规则 | 原句锚 |" in text
    assert "AI 默认怎么写坏" not in text
    assert "为每个动作补情绪解释" in text
    assert "拔剑、转身" in text


def test_sidecar_without_contrast_preserves_transfer_conditions_in_both_outputs(tmp_path):
    kb = _make_kb(tmp_path)
    sidecar = kb / "novels/书A/craft_notes/scene_S01_beats.yaml"
    data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    pattern = data["patterns"][0]
    del pattern["ai_default_failure"]
    pattern["transfer_rule"] = "物件已与失去建立联系时可重现。\n用途改变|含义也随之改变。"
    sidecar.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    reference = _render(tmp_path, kb, [_result()])
    terminal = kq.format_results([_result()], include_text=True)

    assert "| id | 节拍 | 原作怎么做 | 迁移规则 | 原句锚 |" in reference
    assert "物件已与失去建立联系时可重现。<br>用途改变\\|含义也随之改变。" in reference
    assert pattern["transfer_rule"] in terminal
    assert "对照说明" not in reference and "对照说明" not in terminal


def test_inspiration_reference_keeps_applicability_when_present(tmp_path):
    kb = _make_kb(tmp_path)
    _add_inspiration(kb)
    card_path = kb / "inspiration/mentor-death.yaml"
    card = yaml.safe_load(card_path.read_text(encoding="utf-8"))
    card["applicability"] = "导师此前承担了主角依赖的判断职责，失去后留下具体待决事项。"
    card_path.write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")

    text = _render(tmp_path, kb, [_result()])

    assert f"适用条件：{card['applicability']}" in text


def test_raw_md_fallback_before_exemplar(tmp_path):
    kb = _make_kb(tmp_path, sidecar=False, raw_md=True)

    text = _render(tmp_path, kb, [_result()])

    assert "原始手艺标注" in text
    assert text.index("原始手艺标注") < text.index("<style_exemplar")


def test_style_profile_read_from_per_novel_index(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result(style_profile=None)])

    assert "narration_voice: 全知说书" in text


def test_style_card_only_rank1(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result(rank=1), _result(rank=2, scene_id="S02")])

    assert text.count("作品文风卡") == 1


def test_missing_annotations_degrade_silently(tmp_path):
    kb = _make_kb(tmp_path, sidecar=False, raw_md=False, style_card=False)
    (kb / "novels" / "书A" / "scene_index.json").unlink()

    text = _render(tmp_path, kb, [_result()])

    assert "<style_exemplar" in text
    assert "文风画像" not in text
    assert "作品文风卡" not in text
    assert "手艺拆解" not in text


def test_inspiration_lite_block_before_exemplar(tmp_path):
    kb = _make_kb(tmp_path)
    _add_inspiration(kb)

    text = _render(tmp_path, kb, [_result()])

    assert "灵感卡·导师之死范式" in text
    assert "可直接复用的表层元素：具体死法" in text
    assert "只迁移戏剧功能" not in text
    assert "不抄表层元素" not in text
    assert text.index("灵感卡·导师之死范式") < text.index("<style_exemplar")


def test_no_inspiration_dir_degrades(tmp_path):
    kb = _make_kb(tmp_path)

    text = _render(tmp_path, kb, [_result()])

    assert "<style_exemplar" in text
    assert "灵感卡·" not in text


DRAMA_PROFILE = {
    "dialogue_voice": "身份化口语分层",
    "diction": "白话夹文言",
    "rhetoric_density": "medium",
    "stage_direction_style": "小说化工笔",
    "pacing": "对白回合密集",
}


def test_annotations_load_from_drama_jsonl(tmp_path):
    kb = tmp_path / "knowledge-base"
    work = kb / "dramas" / "剧A"
    work.mkdir(parents=True)
    entry = {"scene_id": "A1", "style_profile": DRAMA_PROFILE}
    (work / "dramatic_scene_index.jsonl").write_text(
        json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
    # 并存 legacy JSON（无标注）——JSONL 优先
    (work / "scene_index.json").write_text(
        json.dumps([{"scene_id": "A1"}], ensure_ascii=False), encoding="utf-8")

    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    kq.KB_ROOT = kb
    annotations = kq.load_novel_annotations("dramas/剧A/scenes/scene_A1.md")

    assert annotations["style_profiles"]["A1"] == DRAMA_PROFILE


def _make_query_kb(tmp_path: Path, *, style_rows: int = 3) -> Path:
    kb = tmp_path / "query-kb"
    emb = kb / "embeddings"
    emb.mkdir(parents=True)
    index = [
        {"scene_id": "S01", "novel": "书A", "file": "novels/书A/scene_S01.md", "description": "一"},
        {"scene_id": "S02", "novel": "书A", "file": "novels/书A/scene_S02.md", "description": "二"},
        {"scene_id": "S03", "novel": "书A", "file": "novels/书A/scene_S03.md", "description": "三"},
    ]
    (emb / "scene_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    np.save(emb / "scene_embeddings.npy", np.array([[1.0, 0.0], [0.97, 0.24], [0.35, 0.94]], dtype=np.float32))
    style = np.array([[0.0, 1.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32)[:style_rows]
    np.save(emb / "style_embeddings.npy", style)
    return kb


class _FakeEmbeddings:
    def create(self, model, input):
        text = input[0]
        vec = [0.0, 1.0] if text == "贴身冷感" else [1.0, 0.0]
        item = type("EmbeddingItem", (), {"embedding": vec})
        return type("EmbeddingResponse", (), {"data": [item()]})


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.embeddings = _FakeEmbeddings()


@pytest.fixture
def query_env(tmp_path, monkeypatch):
    kb = _make_query_kb(tmp_path)
    monkeypatch.setattr(kq, "KB_ROOT", kb)
    monkeypatch.setattr(kq, "EMBEDDINGS_DIR", kb / "embeddings")
    monkeypatch.setattr(kq, "INDEX_PATH", kb / "embeddings" / "scene_index.json")
    monkeypatch.setattr(kq, "EMBEDDINGS_PATH", kb / "embeddings" / "scene_embeddings.npy")
    monkeypatch.setattr(kq, "STYLE_EMBEDDINGS_PATH", kb / "embeddings" / "style_embeddings.npy", raising=False)
    monkeypatch.setattr(kq, "API_KEY", "test")
    monkeypatch.setattr(kq, "OpenAI", _FakeOpenAI)
    return kb


def test_descriptive_genre_stays_in_query_and_explicit_limit_stays_hard(query_env):
    assert kq.query("反乌托邦悬疑惊险小说中的父子对峙", top_k=2)
    assert kq.query("父子对峙", genre="反乌托邦悬疑惊险小说", top_k=2) == []


def test_style_channel_requires_hint_and_valid_npy(query_env, capsys):
    no_hint = kq.query("内容", top_k=2, style_mode="vector")
    assert [r["scene_id"] for r in no_hint] == ["S01", "S02"]
    assert all("style_match" not in r for r in no_hint)

    with_hint = kq.query("内容", top_k=2, threshold=0.4, style_hint="贴身冷感", style_mode="vector")
    assert with_hint[0]["scene_id"] == "S01"
    assert "style_match" in with_hint[0]

    np.save(query_env / "embeddings" / "style_embeddings.npy", np.ones((2, 2), dtype=np.float32))
    degraded = kq.query("内容", top_k=2, style_hint="贴身冷感", style_mode="vector")
    assert "降级" in capsys.readouterr().err
    assert [r["scene_id"] for r in degraded] == ["S01", "S02"]


def test_match_tier_immune_to_style_boost(query_env):
    results = kq.query("内容", top_k=3, threshold=0.4, style_hint="贴身冷感", style_mode="vector")

    s03 = next(r for r in results if r["scene_id"] == "S03")

    assert s03["style_match"] == pytest.approx(1.0)
    assert s03["match"] == "style_only"


def test_style_mode_bigram_forces_legacy_rerank(query_env, monkeypatch):
    calls = []

    def fake_rerank(candidates, style_hint, weight=kq.STYLE_HINT_WEIGHT):
        calls.append(style_hint)
        candidates[0]["style_match"] = 0.123
        return candidates

    monkeypatch.setattr(kq, "rerank_by_style_hint", fake_rerank)

    results = kq.query("内容", top_k=2, style_hint="贴身冷感", style_mode="bigram")

    assert calls == ["贴身冷感"]
    assert results[0]["style_match"] == 0.123


def test_bm25_rrf_expands_pool_membership():
    entries = [{"description": "普通"}, {"description": "玄铁剑法 独有招式"}, {"description": "普通二"}]
    sparse_order = kq._bm25_rank("玄铁剑法", entries, [e["description"] for e in entries])

    pool = kq._rrf_pool([0, 2], sparse_order, pool_k=3)

    assert sparse_order[0] == 1
    assert 1 in pool


def test_rrf_does_not_change_match_tier(query_env):
    results = kq.query("玄铁剑法", top_k=3, threshold=0.4, hybrid=True)

    s03 = next(r for r in results if r["scene_id"] == "S03")

    assert s03["match"] == "style_only"
    assert s03["sparse_rank"] is None


def test_bm25_zero_hit_degrades_to_dense(query_env):
    dense = kq.query("内容", top_k=2, hybrid=False)
    hybrid = kq.query("内容", top_k=2, hybrid=True)

    assert [r["scene_id"] for r in hybrid] == [r["scene_id"] for r in dense]


def test_mmr_select_diversifies_near_duplicates():
    vecs = np.array([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]], dtype=np.float32)

    selected = kq._mmr_select([0, 1, 2], vecs, [1.0, 0.99, 0.8], top_k=2, lam=0.7)

    assert selected == [0, 2]


def test_mmr_off_and_small_pool_keep_order(query_env):
    off = kq.query("内容", top_k=2, mmr_lambda=0)
    small = kq._mmr_select([0, 1], np.eye(2, dtype=np.float32), [1.0, 0.9], top_k=2, lam=0.7)

    assert [r["scene_id"] for r in off] == ["S01", "S02"]
    assert small == [0, 1]


def test_select_mode_query_optional_and_medium_hard(query_env, capsys):
    index = json.loads((query_env / "embeddings" / "scene_index.json").read_text(encoding="utf-8"))
    index[0]["source_medium"] = "drama"
    (query_env / "embeddings" / "scene_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    selected = kq.select_results("书A:S01", source_medium="novel")

    assert selected == []
    assert "source_medium" in capsys.readouterr().err


def test_select_render_no_score_crash(tmp_path):
    kb = _make_kb(tmp_path)
    selected = [_result()]
    selected[0]["score"] = None
    selected[0]["match"] = "selected"

    text = _render(tmp_path, kb, selected)

    assert "手动指定参考" in text
    assert "人物、设定、情节与原句" in text
    assert "score=None" not in text


def test_select_invalid_scene_skip_and_exit2(query_env, capsys):
    selected = kq.select_results("书A:S99", source_medium="novel")

    assert selected == []
    assert "跳过" in capsys.readouterr().err


def test_list_pool_overrides_candidate_count(query_env):
    results = kq.query("内容", top_k=3, pool=3)
    table = kq.format_candidate_table(results)

    assert table.count("\n") >= 3
    assert "rank" in table and "dense" in table


def test_cjk_bigrams_strip_punct():
    grams = kq._cjk_bigrams("限知、内聚；心理戏")
    assert "限知" in grams and "心理" in grams and "理戏" in grams
    assert not any("、" in g or "；" in g for g in grams)


def test_rerank_by_style_hint_demotes_voice_mismatch(monkeypatch):
    texts = {
        "S_action": "全知说书 招式调度 动作链连贯 热闹群战",
        "S_inner": "限知贴身 心理停顿 沉默留白 对白稀少 内聚",
    }
    monkeypatch.setattr(kq, "_style_text_for", lambda c: texts[c["scene_id"]])
    candidates = [
        {"scene_id": "S_action", "score": 0.50, "match": "high"},
        {"scene_id": "S_inner", "score": 0.45, "match": "high"},
    ]

    ranked = kq.rerank_by_style_hint(candidates, "限知贴身 心理戏 对白稀少 留白")

    assert [c["scene_id"] for c in ranked] == ["S_inner", "S_action"]
    assert ranked[0]["style_match"] > ranked[1]["style_match"]


def test_rerank_no_annotation_keeps_embedding_order(monkeypatch):
    monkeypatch.setattr(kq, "_style_text_for", lambda c: "")
    candidates = [
        {"scene_id": "A", "score": 0.50, "match": "high"},
        {"scene_id": "B", "score": 0.45, "match": "high"},
    ]

    ranked = kq.rerank_by_style_hint(candidates, "限知 心理")

    assert [c["scene_id"] for c in ranked] == ["A", "B"]
    assert all(c["style_match"] == 0 for c in ranked)


def test_apply_fit_rank_promotes_functional_match():
    candidates = [
        {"scene_id": "A", "score": 0.50, "match": "high", "tags": ["守阵"], "description": "守阵蓄势"},
        {"scene_id": "B", "score": 0.49, "match": "high", "tags": ["宫斗"], "description": "宫斗算计"},
    ]

    ranked = kq._apply_fit_rank(candidates, "守阵 蓄势")

    assert [c["scene_id"] for c in ranked] == ["A", "B"]
    assert ranked[0]["fit"] > ranked[1]["fit"]


def test_query_with_function_hint_sets_fit_field(query_env):
    results = kq.query("内容", top_k=2, function_hint="内容")
    assert all("fit" in r for r in results)


def test_query_without_function_hint_omits_fit_field(query_env):
    results = kq.query("内容", top_k=2)
    assert all("fit" not in r for r in results)


def test_embed_text_cached_single_api_call():
    kq._EMBED_CACHE.clear()
    calls = []

    class _Resp:
        data = [type("D", (), {"embedding": [0.1, 0.2]})()]

    class _Embeddings:
        @staticmethod
        def create(model, input):
            calls.append(input[0])
            return _Resp()

    class _Client:
        embeddings = _Embeddings()

    v1 = kq._embed_text_cached(_Client(), "m", "同一文本", label="t")
    v2 = kq._embed_text_cached(_Client(), "m", "同一文本", label="t")

    assert v1 == v2 == [0.1, 0.2]
    assert len(calls) == 1
