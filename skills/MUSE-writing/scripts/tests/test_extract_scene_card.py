"""场景投影的语义、作者权限与兼容边界；结构 fixture 不作文学案例。"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_scene_card import SchemaError, load_scenes, render_scene_card_markdown  # noqa: E402


BASE_SCENE = {
    "scene_id": "S02",
    "arc_id": "ARC-2",
    "title": "Section 2/3：渡口新盟",
    "pov": "小龙女",
    "narration_style": "close-third",
    "participants": ["xiao-long-nv", "lu-qing-yi"],
    "location_time": "渭水渡口 / 次日午后",
    "conflict": "小龙女判断陌生人证据是否可信。",
    "value_start": "信息状态：互相矛盾的杨过传闻。",
    "value_end": "信息状态：药粉、假渡船和暗号互相关联。",
    "scene_tasks": [
        {
            "abstract_function": "小龙女判断陌生人证据是否可信",
            "physical_carrier": [
                {"text": "药粉包在桌上摊开", "function_link": "药粉→证据链"},
            ],
            "reader_yield": ["信息判断压力"],
            "rendering": {"default": "summary"},
        },
    ],
    "handoff": "三人推定杨过被引向关中旧驿。",
}


def test_reader_track_renders_when_present():
    scene = dict(BASE_SCENE, reader_track="小龙女判断陌生人证据是否可信，并决定是否纳入寻找杨过的行动。")
    md = render_scene_card_markdown(scene)
    assert "**阅读焦点**: 小龙女判断陌生人证据是否可信" in md


def test_reader_track_absent_does_not_break_render():
    """旧 yaml 无 reader_track 字段——不阻断渲染（向后兼容）。"""
    scene = dict(BASE_SCENE)  # 无 reader_track
    md = render_scene_card_markdown(scene)
    assert "**阅读焦点**" not in md
    # 必填字段仍正确渲染
    assert "**冲突或组织关系**" in md
    assert "**入场处境**" in md


def test_scene_tasks_string_rejected():
    """full 链 scene_task 恒为 r10 object——字符串任务（含 marker 形态）硬拒。"""
    scene = dict(BASE_SCENE, scene_tasks=["[核心][main] 小龙女判断陌生人证据是否可信"])
    with pytest.raises(SchemaError, match="必须是 r10 object"):
        render_scene_card_markdown(scene)


def test_render_scene_card_markdown_scene_task_dict_renders_layered_sections():
    dict_task = {
        "abstract_function": "自欺装置首次裂缝",
        "physical_carrier": [
            {"text": "杯沿停在唇边却没喝", "function_link": "杯沿→自欺裂缝"},
            {"text": "折扇开合", "function_link": "折扇→克制"},
        ],
        "reader_yield": ["关系压力", "自欺破裂"],
        "rendering": {"default": "summary", "expand_only_if": "动作改变关系"},
    }
    scene = dict(BASE_SCENE, scene_tasks=[dict_task])
    md = render_scene_card_markdown(scene)

    assert "{'abstract_function':" not in md
    assert "abstract_function='自欺装置首次裂缝'" not in md
    assert "自欺装置首次裂缝" in md
    assert "杯沿停在唇边却没喝" in md
    assert "作用依据：杯沿→自欺裂缝" in md
    assert "作用依据：折扇→克制" in md
    assert "关系压力" in md
    assert "简写结果" in md
    assert "**需成立的叙事工作**" in md
    assert "**候选承载（可替换、合并或舍弃）**" in md
    assert "**目标叙事增量**" in md
    assert "**呈现建议（不规定正文顺序）**" in md


def test_writer_projection_hides_keys_and_preserves_turning_point():
    scene = dict(
        BASE_SCENE,
        reader_track="小龙女决定是否接受证据。",
        beat_direction="从怀疑走向结盟，鸿沟在药粉显色时裂开。",
    )
    md = render_scene_card_markdown(scene)

    for token in (
        "value_start", "value_end", "reader_track", "scene_tasks",
        "abstract_function", "physical_carrier", "function_link",
        "reader_yield", "rendering", "beat_direction",
    ):
        assert token not in md
    assert "**关键转折**: 从怀疑走向结盟" in md
    assert "药粉显色" in md
    assert "动作、对白和叙述次序由正文实现" in md
    assert "**入场处境**" in md
    assert "**离场结果**" in md
    assert "## 可用创作材料" in md
    assert "不规定正文措辞或排列" in md
    assert "输入顺序不代表正文顺序" in md
    assert "只复述同一结果的内容应合并" in md
    assert "重复本身产生新效果或承担来源复用时保留" in md


def test_render_scene_card_markdown_plain_string_scene_task_rejected():
    scene = dict(BASE_SCENE, scene_tasks=["旧版字符串 task A"])
    with pytest.raises(SchemaError, match="必须是 r10 object"):
        render_scene_card_markdown(scene)


# v3 R2 #2.6 + R3 #1 + R3 #4：renderer 渲染 11 个 v3 新字段
V3_SCENE_OVERLAY = {
    "craft_carrier": {
        "type": "object",
        "concrete_anchor": "撕碎的遗嘱",
        "replaces": "关于'国王指定继承人'的所有口头解释",
    },
    "pov_constraint": {
        "can_perceive": ["大殿内对话", "瑟曦表情", "太监反应"],
        "cannot_perceive": ["殿外动静", "其他角色心理"],
        "intentional_blind_spot": "凯瑟琳的反应（让读者后续才知道）",
    },
    "omission_plan": [
        "不写小龙女如何识破药粉",
        "不解释陆青漪为何深夜赶来",
    ],
    "irreversible_action": [
        "小龙女把假渡船的暗号告诉陆青漪",
        "陆青漪决定一同北上",
    ],
    "reveal_method": {
        "type": "delayed_implication",
    },
    "narrator_distance": {
        "mode": "intimate_first",
        "reason": "本场是小龙女判断的核心心智过程，距离贴近能让读者跟住判断",
    },
    "scale_inversion": {
        "used": True,
        "bridge": "鞋底水痕从私人警觉折入江湖局势",
    },
    "precedent_mirror": {
        "mirrors_scene": "S01",
        "mirror_kind": "spatial_inversion",
        "preserved_anchors": ["渡口意象", "陌生人证言"],
        "removed_premises": ["对杨过的全知视角"],
    },
    "climax_pattern": {
        "primary": "decision_under_uncertainty",
        "secondary": ["irreversible_alliance"],
        "forbidden_moves": ["不得让小龙女在本场获得确凿证据"],
    },
    "dialogue_hints": [
        {
            "speaker": "小龙女",
            "attribution_strategy": "action_bridge",
            "dialogue_form": "diagnostic_verdict",
            "reason": "她在判断证据真伪，动作桥能让判断过程外化",
        },
        {
            "speaker": "陆青漪",
            "attribution_strategy": "minimal_tag",
            "dialogue_form": "factual_offering",
            "reason": "她在提供药理依据，极简标签突出信息密度",
        },
    ],
    "counter_prior_scene": {
        "used": True,
        "kind": "death_with_chore",
        "mundane_action": "一边吃黄瓜一边交代后事",
        "emotional_context": "临终",
        "forbidden_moves": [
            "不得把吃黄瓜解释成象征",
            "不得在动作后追加心理解释",
        ],
    },
}


def test_render_with_v3_fields():
    """11 个 v3 新字段全部 populated → 每个 section 标题都应渲染。"""
    scene = dict(BASE_SCENE, **V3_SCENE_OVERLAY)
    md = render_scene_card_markdown(scene)

    # 11 个 section 标题全部出现
    assert "## 承载候选" in md
    assert "## POV 约束" in md
    assert "## 故意省略" in md
    assert "## 不可逆变化" in md
    assert "## 揭示方式候选" in md
    assert "## 叙述距离建议" in md
    assert "## 尺度转换候选" in md
    assert "## 先例呼应候选" in md
    assert "## 高潮机制候选" in md
    assert "## 对白偏好" in md
    assert "## 反先验场景候选" in md

    # 字段内容抽查（每段至少一个具体值）
    assert "撕碎的遗嘱" in md
    assert "凯瑟琳的反应" in md
    assert "不写小龙女如何识破药粉" in md
    assert "陆青漪决定一同北上" in md
    assert "delayed_implication" in md
    assert "贴近当下体验的第一人称" in md
    assert "鞋底水痕从私人警觉折入江湖局势" in md
    assert "spatial_inversion" in md
    assert "decision_under_uncertainty" in md
    assert "通过动作衔接说话者" in md
    assert "诊断或裁决式表达" in md
    assert "死亡处境中的日常事务" in md
    assert "一边吃黄瓜一边交代后事" in md

    # dialogue_hints 多 speaker 分别渲染
    assert "### 小龙女" in md
    assert "### 陆青漪" in md


def test_render_without_v3_fields():
    """旧 fixture 不带任何 v3 字段 → renderer 完成、新 section 标题全部不出现。"""
    scene = dict(BASE_SCENE)  # 仅 baseline 字段
    md = render_scene_card_markdown(scene)

    # baseline 仍正确渲染
    assert "**冲突或组织关系**" in md
    assert "**入场处境**" in md
    assert "## 可用创作材料" in md

    # 11 个 v3 section 标题均不出现
    assert "## 承载候选" not in md
    assert "## POV 约束" not in md
    assert "## 故意省略" not in md
    assert "## 不可逆变化" not in md
    assert "## 揭示方式候选" not in md
    assert "## 叙述距离建议" not in md
    assert "## 尺度转换候选" not in md
    assert "## 先例呼应候选" not in md
    assert "## 高潮机制候选" not in md
    assert "## 对白偏好" not in md
    assert "## 反先验场景候选" not in md


def test_render_inspiration_refs_lists_each_id():
    """inspiration_refs 字段非空时渲染独立段。"""
    scene = dict(BASE_SCENE, inspiration_refs=["INS-001", "INS-007"])
    md = render_scene_card_markdown(scene)

    assert "## 灵感引用 (inspiration_refs)" in md
    assert "INS-001" in md
    assert "INS-007" in md
    assert "实际存在 disclosure_ladder 时再消费对应层" in md


def test_render_inspiration_refs_absent_section_omitted():
    """字段缺席时不渲染 inspiration_refs 段。"""
    scene = dict(BASE_SCENE)
    md = render_scene_card_markdown(scene)

    assert "## 灵感引用" not in md
    assert "inspiration_refs" not in md


def test_render_inspiration_refs_empty_array_section_omitted():
    """字段为空数组时不渲染 inspiration_refs 段。"""
    scene = dict(BASE_SCENE, inspiration_refs=[])
    md = render_scene_card_markdown(scene)

    assert "## 灵感引用" not in md


def test_pov_constraint_uses_schema_keys():
    """正向用例：fixture 用 phase5 output-schema.md L35-37 的字段名
    (can_perceive / cannot_perceive / intentional_blind_spot) — renderer 必须读到，
    并把 list 元素拼出来（防止再次发生 perceivable / not_perceivable / deliberately_obscured 这类
    key-drift 退化）。"""
    scene = dict(
        BASE_SCENE,
        pov_constraint={
            "can_perceive": ["对方的语气", "桌上的茶杯", "门外的脚步"],
            "cannot_perceive": ["陆青漪的内心独白", "殿外暗器位置"],
            "intentional_blind_spot": "杨过此刻是否还活着 — 故意不让 POV 角色推断",
        },
    )
    md = render_scene_card_markdown(scene)

    # section header 出现
    assert "## POV 约束" in md
    # 三个 label 都出现（Chinese label 不变 — 只 yaml key 变）
    assert "**可感知**" in md
    assert "**不可感知**" in md
    assert "**故意遮蔽**" in md
    # can_perceive list 每个元素都被拼进输出
    assert "对方的语气" in md
    assert "桌上的茶杯" in md
    assert "门外的脚步" in md
    # cannot_perceive list 同上
    assert "陆青漪的内心独白" in md
    assert "殿外暗器位置" in md
    # intentional_blind_spot 字符串
    assert "杨过此刻是否还活着" in md
    # 旧 wrong-key 名一律不应出现在 renderer 输出（label 中文已覆盖）
    assert "perceivable" not in md
    assert "deliberately_obscured" not in md


def test_world_disclosure_plan_both_non_empty_renders_full_section():
    """forbid + allow 都非空 → 输出锁定标题 + 两个子标题 + 列表项"""
    scene = dict(BASE_SCENE, world_disclosure_plan={
        "forbid": ["终极成因", "救援"],
        "allow": ["主角口吻披露崩坏过程"],
    })
    md = render_scene_card_markdown(scene)
    assert "## 世界观披露 (world_disclosure_plan)" in md
    assert "终极成因" in md
    assert "救援" in md
    assert "主角口吻披露崩坏过程" in md
    assert "**暂缓披露**（当前 POV 不可知，或延迟后产生明确收益）：" in md
    assert "**本场可披露**" in md
    assert "终极成因 / 宏大总结类硬约束" not in md
    assert "极简短句即止" not in md


def test_world_disclosure_plan_missing_skips_section():
    """字段缺失 → 整段不输出（不出现锁定标题；BASE_SCENE 不含此字段）"""
    scene = dict(BASE_SCENE)  # 无 world_disclosure_plan
    md = render_scene_card_markdown(scene)
    assert "## 世界观披露" not in md


def test_world_disclosure_plan_both_empty_skips_section():
    """forbid + allow 同时为空 → 整段不输出"""
    scene = dict(BASE_SCENE, world_disclosure_plan={"forbid": [], "allow": []})
    md = render_scene_card_markdown(scene)
    assert "## 世界观披露" not in md


def test_world_disclosure_plan_only_allow_non_empty():
    """只有 allow 非空 → 输出段标题 + allow 列表项，不输出 forbid 子标题"""
    scene = dict(BASE_SCENE, world_disclosure_plan={
        "forbid": [],
        "allow": ["主角披露行动规则"],
    })
    md = render_scene_card_markdown(scene)
    assert "## 世界观披露 (world_disclosure_plan)" in md
    assert "主角披露行动规则" in md
    # 注：具体子标题文字由实现决定，test 只验段标题 + 列表内容字段


def test_extract_prefers_top_level_scenes_over_sequence_expansions(tmp_path):
    """phase5_scenes.yaml 同时有 scenes 和 sequence_expansions 时，优先 top-level scenes。"""
    doc = {
        "scenes": [dict(BASE_SCENE, scene_id="S01", scene_value_arc="+/-")],
        "sequence_expansions": [
            {"sequence_id": "seq1", "scenes_in_sequence": ["S01"]}
        ],
    }
    work = tmp_path / "work"
    (work / "pipeline").mkdir(parents=True)
    phase5 = work / "pipeline" / "phase5_scenes.yaml"
    phase5.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    scenes = load_scenes(phase5)
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "S01"
    assert scenes[0]["title"] == BASE_SCENE["title"]


def test_render_v3_partial_fields_optional():
    """部分字段缺失 / used=false → 仅渲染存在且 truthy 的 section。"""
    scene = dict(
        BASE_SCENE,
        craft_carrier={"type": "object", "concrete_anchor": "信物"},
        scale_inversion={"used": False, "bridge": "should not render"},
        climax_pattern={"primary": None, "secondary": ["should not render"]},
        counter_prior_scene={"used": False, "kind": "should not render"},
        dialogue_hints=[],
        omission_plan=[],
    )
    md = render_scene_card_markdown(scene)

    # craft_carrier 部分字段：section 渲染，缺的 replaces 不输出空行
    assert "## 承载候选" in md
    assert "信物" in md
    assert "**Replaces**" not in md

    # scale_inversion.used=false → 整段省略
    assert "## 尺度转换候选" not in md
    assert "should not render" not in md

    # climax_pattern.primary=None → 整段省略
    assert "## 高潮机制候选" not in md

    # counter_prior_scene.used=false → 整段省略
    assert "## 反先验场景候选" not in md

    # 空列表 → 整段省略
    assert "## 对白偏好" not in md
    assert "## 故意省略" not in md


# ---------------- prose_risk_contract renderer tests (R2-P2-004) ---------------- #


def test_prose_risk_contract_renders_when_used_true():
    """used=true + 三子列表都有内容 → 渲染段标题 + 三组列表；标题文字不含 R 轮未落地 protocol 关键词（D7 闭包）。"""
    scene = dict(
        BASE_SCENE,
        prose_risk_contract={
            "used": True,
            "risk_families": ["动作清单化", "psychological_overfill"],
            "positive_strategy": ["本场社交调度，动作合并必须落到关系压力变化点"],
            "bad_shape_examples": ["他停下，低头，看门缝，伸手，推开"],
        },
    )
    md = render_scene_card_markdown(scene)

    # 段标题精确字面量
    assert "## 写作层 AI pattern 预防 (prose_risk_contract)" in md
    # 三个子列表内容
    assert "动作清单化" in md
    assert "psychological_overfill" in md
    assert "本场社交调度" in md
    assert "他停下，低头" in md
    assert "风险关注" in md
    assert "候选策略" in md
    assert "问题形态线索" in md
    # D7 闭包：标题文字不含 R 轮未落地 protocol 关键词
    assert "R 轮" not in md
    assert "family taxonomy" not in md
    assert "default_repair_strategy" not in md
    assert "rewrite_directive" not in md


def test_prose_risk_contract_omitted_when_used_false_or_missing():
    """used=false / 字段缺失 / 三子列表全空 → 整段不渲染。"""
    # 1. used=false
    scene_false = dict(
        BASE_SCENE,
        prose_risk_contract={
            "used": False,
            "risk_families": ["should not render"],
            "positive_strategy": ["should not render"],
        },
    )
    md_false = render_scene_card_markdown(scene_false)
    assert "## 写作层 AI pattern 预防" not in md_false
    assert "should not render" not in md_false

    # 2. 字段缺失（不在 scene dict 里）
    scene_missing = dict(BASE_SCENE)
    md_missing = render_scene_card_markdown(scene_missing)
    assert "## 写作层 AI pattern 预防" not in md_missing

    # 3. used=true 但三子列表全空 → 仍整段不渲染
    scene_empty = dict(
        BASE_SCENE,
        prose_risk_contract={
            "used": True,
            "risk_families": [],
            "positive_strategy": [],
            "bad_shape_examples": [],
        },
    )
    md_empty = render_scene_card_markdown(scene_empty)
    assert "## 写作层 AI pattern 预防" not in md_empty


@pytest.mark.parametrize("bad_value", ["action_log", [{"id": "action_log"}]])
def test_prose_risk_contract_rejects_non_string_list_shape(bad_value):
    """直接调用 renderer 也不会逐字符遍历 str 或遍历 dict。"""
    scene = dict(
        BASE_SCENE,
        prose_risk_contract={
            "used": True,
            "risk_families": bad_value,
            "positive_strategy": ["本场策略一"],
        },
    )
    with pytest.raises(SchemaError, match="risk_families"):
        render_scene_card_markdown(scene)


@pytest.mark.parametrize("other_contract", [None, {}, {"used": True, "risk_families": "action_log"}])
def test_extract_scene_card_phase5_absent_contract_passes(tmp_path, other_contract):
    """当前场景缺省合法；其他场景的缺省或待修格式不阻断本场提取。"""
    work = tmp_path / "work"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    s01 = dict(BASE_SCENE, scene_id="S01")
    if other_contract is not None:
        s01["prose_risk_contract"] = other_contract
    s02 = dict(BASE_SCENE, scene_id="S02")
    (pipeline / "phase5_scenes.yaml").write_text(yaml.dump({
        "scenes": [
            s01,
            s02,
        ]
    }), encoding="utf-8")
    import subprocess, sys
    script = Path(__file__).resolve().parents[1] / "extract_scene_card.py"
    result = subprocess.run(
        [sys.executable, str(script), "--scene-id", "S02", "--work-dir", str(work)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (pipeline / "scene_S02" / "scene_card.md").exists()


def test_extract_scene_card_phase5_invalid_contract_list_hard_fails(tmp_path):
    """CLI 在已声明 contract 的既有 list 字段格式无效时阻断。"""
    work = tmp_path / "work"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    scene = dict(
        BASE_SCENE,
        scene_id="S02",
        prose_risk_contract={"used": True, "risk_families": "action_log"},
    )
    (pipeline / "phase5_scenes.yaml").write_text(
        yaml.dump({"scenes": [scene]}), encoding="utf-8"
    )
    current_card = pipeline / "scene_S02" / "scene_card.md"
    current_card.parent.mkdir()
    current_card.write_text("existing scene card", encoding="utf-8")
    import subprocess, sys
    script = Path(__file__).resolve().parents[1] / "extract_scene_card.py"
    result = subprocess.run(
        [sys.executable, str(script), "--scene-id", "S02", "--work-dir", str(work)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "prose_risk_contract 格式无效" in (result.stderr + result.stdout)
    assert current_card.read_text(encoding="utf-8") == "existing scene card"


@pytest.mark.parametrize("contract", [None, {"used": True, "risk_families": "pending correction"}])
def test_generate_phase6_index_phase5_absent_contract_passes(tmp_path, contract):
    """索引只消费场景身份与顺序，风险格式问题留给该字段的消费者。"""
    work = tmp_path / "work"
    pipeline = work / "pipeline"
    pipeline.mkdir(parents=True)
    scene = {"scene_id": "S01", "title": "场景一", "scene_tasks": []}
    if contract is not None:
        scene["prose_risk_contract"] = contract
    (pipeline / "phase5_scenes.yaml").write_text(yaml.dump({
        "sequence_expansions": [{
            "sequence_id": "Q1",
            "arc_id": "A1",
            "scenes": [scene]
        }]
    }), encoding="utf-8")
    import subprocess, sys
    script = Path(__file__).resolve().parents[1] / "generate_phase6_index.py"
    result = subprocess.run(
        [sys.executable, str(script), str(work)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (pipeline / "phase6_development.yaml").exists()


@pytest.fixture(params=["MUSE-writing", "MUSE-serial-writing"])
def extractor_module(request):
    """两包独立分发，代表性契约必须在各自实现上成立。"""
    import importlib.util

    script = Path(__file__).resolve().parents[3] / request.param / "scripts" / "extract_scene_card.py"
    spec = importlib.util.spec_from_file_location(f"projection_{request.param}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scene_projection_preserves_meaning_and_authority_across_packages(extractor_module):
    scene = dict(
        BASE_SCENE,
        beat_direction="起初可以撤离，资源丧失后必须继续。",
        craft_carrier={"type": "object", "concrete_anchor": "场内物件", "function": "改变可用退路"},
        irreversible_action=["退路已经关闭"],
        reveal_method={"type": "direct_action"},
        climax_pattern={"primary": "unfinished_action", "forbidden_moves": ["不能恢复已毁退路"]},
        counter_prior_scene={"used": True, "kind": "death_with_chore", "mundane_action": "现有日常动作", "forbidden_moves": ["作者要求保留沉默"]},
        pov_constraint={"cannot_perceive": ["门外是谁"]},
        omission_plan=["身份留到下一场确认"],
    )
    md = extractor_module.render_scene_card_markdown(scene)
    assert "**关键转折**: 起初可以撤离，资源丧失后必须继续。" in md
    assert "beat_direction" not in md
    assert "**叙事作用**: 改变可用退路" in md
    assert "## 承载候选" in md
    assert "## 高潮机制候选" in md
    assert "由当场行动显露" in md
    assert "direct_action" not in md
    assert "未完成的表达或行动承担后果" in md
    assert "保持已确认的事实、核心因果与必要结果" in md
    for boundary in ("退路已经关闭", "不能恢复已毁退路", "作者要求保留沉默", "门外是谁", "身份留到下一场确认"):
        assert boundary in md
    assert "手法偏好按本场效果取舍" in md
    assert "人物知识" in md


def test_projection_preserves_unknown_values_and_legacy_carrier(extractor_module):
    scene = dict(
        BASE_SCENE,
        craft_carrier={"type": "custom_carrier", "function": "形成新的认识", "replaces": "原有背景说明"},
        reveal_method={"type": "custom_revelation"},
        narrator_distance={"mode": "本作的自由叙述描述"},
        dialogue_hints=[{"speaker": None, "attribution_strategy": "custom_attribution", "dialogue_form": "custom_dialogue"}],
    )
    md = extractor_module.render_scene_card_markdown(scene)
    for original in ("custom_carrier", "custom_revelation", "本作的自由叙述描述", "custom_attribution", "custom_dialogue"):
        assert original in md
    assert "**叙事作用**: 形成新的认识" in md
    assert "**既有候选说明**: 原有背景说明" in md
    assert "不要求删除有独立作用的解释、心理或背景" in md
    assert "Replaces" not in md
    assert "### 全场对白" in md


def test_extractor_cli_delivers_turning_point_and_candidate_semantics(extractor_module, tmp_path):
    import subprocess

    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    scene = dict(
        BASE_SCENE,
        beat_direction="证据出现后，原来的判断失效。",
        craft_carrier={"type": "object", "function": "使原判断失效"},
        prose_risk_contract={"used": True, "positive_strategy": ["保留必要承接"]},
    )
    (pipeline / "phase5_scenes.yaml").write_text(yaml.safe_dump({"scenes": [scene]}, allow_unicode=True), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, extractor_module.__file__, "--scene-id", scene["scene_id"], "--work-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    md = (pipeline / "scene_S02" / "scene_card.md").read_text(encoding="utf-8")
    assert "**关键转折**: 证据出现后，原来的判断失效。" in md
    assert "## 承载候选" in md
    assert "**叙事作用**: 使原判断失效" in md
    assert "候选策略" in md
