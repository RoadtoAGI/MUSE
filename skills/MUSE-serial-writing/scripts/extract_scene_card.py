#!/usr/bin/env python3
"""
extract_scene_card.py — 从 phase5_scenes.yaml 机械提取单 scene 的 r10 字段，
渲染为 Markdown 切片写入 pipeline/scene_{scene_id}/scene_card.md。

供 Phase 6 writer subagent 消费，避免 writer 读全量 phase5_scenes.yaml。

用法：
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_scene_card.py --scene-id S02 --work-dir <含 pipeline/ 的章工作区根目录>

输入：
    {work_dir}/pipeline/phase5_scenes.yaml（r10 schema，MUSE-writing sequence_expansions 或 open-muse 平铺 scenes）

输出：
    {work_dir}/pipeline/scene_{scene_id}/scene_card.md

失败语义（fail-fast）：
    - scene_id 找不到 → stderr + exit 1
    - YAML schema 非 r10（缺 required 字段 / 含 forbidden alias）→ stderr 列出缺项 + exit 1，不写 scene_card.md

本脚本不调 LLM（纯机械字段提取 + Markdown 渲染）。
"""

import argparse
import sys
import tempfile
from pathlib import Path

import yaml

from yaml_resilient import load_yaml_resilient


# 对齐 evaluate/validators/validate_phase5_r10.py 的 required local set
# 不 import validator（避免 pub/private 耦合）；validator 改动时同步维护此清单
# 注：extract_scene_card 比 validator 更宽松——validator 在新产物验收时强制 reader_track，
# extract 渲染层保留 legacy 兼容（旧 yaml 缺 reader_track 仍可切片，writer 走 fallback 路径）
SCENE_REQUIRED_FIELDS = {
    "scene_id", "arc_id", "title",
    "pov", "narration_style", "participants", "location_time",
    "conflict", "value_start", "value_end", "scene_tasks", "handoff",
}
SCENE_FORBIDDEN_ALIASES = {
    "must_include", "characters", "setting", "core_conflict", "value_shift",
    "time_place", "purpose", "value_change", "tension_level",
}


class SchemaError(Exception):
    pass


def load_scenes(phase5_path: Path) -> list[dict]:
    """返回扁平 scene 列表，兼容 MUSE-writing(sequence_expansions) / open-muse(平铺 scenes)。

    对 LLM 产 yaml 常见的双引号 scalar 内嵌未转义 `"` 错误（如 S05 `value_start: "...裴自以为已"妥善"处理..."`），
    通过 yaml_resilient 自动升级为 block scalar 后再解析；recovery 命中时在 stderr 打 WARN 标线号。
    """
    if not phase5_path.exists():
        raise SchemaError(f"{phase5_path} not found")

    doc, report = load_yaml_resilient(phase5_path.read_text(encoding="utf-8"))
    if report.recovered_lines:
        sys.stderr.write(
            f"[WARN] {phase5_path}: auto-recovered broken double-quoted scalars "
            f"at line(s) {report.recovered_lines} (promoted to block scalar). "
            f"Consider fixing source yaml to use `|-` for prose fields.\n"
        )
    if not isinstance(doc, dict):
        raise SchemaError(f"{phase5_path} top level must be a mapping")

    if isinstance(doc.get("scenes"), list) and doc["scenes"]:
        scenes = doc["scenes"]
    elif isinstance(doc.get("sequence_expansions"), list):
        scenes = []
        for seq in doc["sequence_expansions"]:
            if not isinstance(seq, dict):
                continue
            seq_scenes = seq.get("scenes") or seq.get("scenes_in_sequence") or []
            if seq_scenes and all(isinstance(s, dict) for s in seq_scenes):
                scenes.extend(seq_scenes)
            elif seq_scenes and all(isinstance(s, str) for s in seq_scenes):
                continue
    else:
        raise SchemaError(f"{phase5_path}: neither 'sequence_expansions' nor 'scenes' found")

    if not scenes:
        raise SchemaError(f"{phase5_path}: no scenes found")
    return scenes


def find_scene(scenes: list[dict], scene_id: str) -> dict:
    matches = [s for s in scenes if s.get("scene_id") == scene_id]
    if not matches:
        raise SchemaError(f"scene_id {scene_id!r} not found in phase5_scenes.yaml")
    if len(matches) > 1:
        raise SchemaError(f"scene_id {scene_id!r} appears {len(matches)} times; must be unique")
    return matches[0]


def validate_scene(scene: dict) -> None:
    missing = SCENE_REQUIRED_FIELDS - scene.keys()
    if missing:
        raise SchemaError(
            f"scene {scene.get('scene_id', '?')} missing required fields: "
            f"{sorted(missing)}"
        )
    forbidden = SCENE_FORBIDDEN_ALIASES & scene.keys()
    if forbidden:
        raise SchemaError(
            f"scene {scene.get('scene_id', '?')} contains forbidden pre-r10 aliases: "
            f"{sorted(forbidden)}（请先跑 validate_phase5_r10.py 升级到 r10 schema）"
        )
    if not scene.get("scene_tasks"):
        raise SchemaError(f"scene {scene.get('scene_id')} scene_tasks empty")
    from muse_hook_check import _scan_phase5_missing_prose_risk_contract
    if _scan_phase5_missing_prose_risk_contract({"scenes": [scene]}):
        raise SchemaError(
            f"scene {scene.get('scene_id')} prose_risk_contract 格式无效："
            "对象可缺省；已提供的 used 须为 bool，策略字段须为非空字符串列表"
        )


def render_scene_task(task) -> str:
    """把 scene_task 投影成 writer 可读语义；保留 legacy string task。"""
    if isinstance(task, str):
        return f"- {task}"
    if not isinstance(task, dict):
        return f"- {task}"

    lines: list[str] = []
    abstract_function = task.get("abstract_function")
    if abstract_function:
        lines.append(f"- **本场作用**: {abstract_function}")

    physical_carrier = task.get("physical_carrier") or []
    if physical_carrier:
        lines.append("- **候选动作与物件**:")
        for carrier in physical_carrier:
            if isinstance(carrier, dict):
                text = carrier.get("text", "")
                lines.append(f"  - {text}")
                if carrier.get("function_link"):
                    lines.append(f"    - 作用依据：{carrier['function_link']}")
            else:
                lines.append(f"  - {carrier}")

    reader_yield = task.get("reader_yield") or []
    if reader_yield:
        lines.append(f"- **读者所得**: {' / '.join(str(item) for item in reader_yield)}")

    rendering = task.get("rendering") or {}
    if rendering:
        default_mode = rendering.get("default", "summary")
        mode_label = {"summary": "简写结果", "expand": "展开过程"}.get(default_mode, str(default_mode))
        expand_condition = rendering.get("expand_only_if", "")
        if expand_condition:
            lines.append(f"- **展开尺度**: {mode_label}；仅在{expand_condition}时展开")
        else:
            lines.append(f"- **展开尺度**: {mode_label}")

    return "\n".join(lines) if lines else f"- {task}"


def render_scene_card_markdown(scene: dict) -> str:
    """把 r10 场景设计渲染成 writer-facing 投影。"""
    lines: list[str] = []
    lines.append(f"# Scene Card: {scene['scene_id']}")
    lines.append("")
    lines.append(f"**所属故事段**: {scene['arc_id']}")
    lines.append(f"**场景标题**: {scene['title']}")
    lines.append(f"**视角角色**: {scene['pov']}")
    lines.append(f"**叙述方式**: {scene['narration_style']}")
    participants = scene.get("participants") or []
    lines.append(f"**在场人物**: {', '.join(participants) if participants else '(none)'}")
    lines.append(f"**时空位置**: {scene['location_time']}")
    lines.append("")

    lines.append("## 场景约束")
    lines.append("")
    lines.append(f"**冲突或组织关系**: {scene['conflict']}")
    lines.append(f"**入场处境**: {scene['value_start']}")
    lines.append(f"**离场结果**: {scene['value_end']}")
    if scene.get("beat_direction"):
        lines.append(f"**关键转折**: {scene['beat_direction']}")
        lines.append("保留关键变化及其触发原因；动作、对白和叙述次序由正文实现。")
    # reader_track: 本场读者跟随的单一阅读问题/行动线（writer 主线锚点）。
    # 字段缺位 → 不渲染（writer 走 reader_track=null 路径，不阻断生成）。
    reader_track = scene.get("reader_track")
    if reader_track:
        lines.append(f"**阅读焦点**: {reader_track}")
    lines.append("")

    lines.append("## 可用创作材料")
    lines.append("")
    for task in scene["scene_tasks"]:
        lines.append(render_scene_task(task))
    lines.append("")

    lines.append("## 衔接")
    lines.append("")
    lines.append(f"**下场压力**: {scene['handoff']}")
    lines.append("")

    inspiration_refs = scene.get("inspiration_refs") or []
    if inspiration_refs:
        lines.append("## 灵感引用 (inspiration_refs)")
        lines.append("")
        lines.append("本场采用 `pipeline/inspiration_ledger.yaml` 中以下 INS-* 机制；只消费匹配本 chapter_id + scene_id 的 project_encoding，实际设有 disclosure_ladder 时再取当前披露层：")
        lines.append("")
        for ins_id in inspiration_refs:
            lines.append(f"- {ins_id}")
        lines.append("")

    # 扩展字段各自保留事实边界或候选性质，不能由字段出现推导强制写法。
    _render_v3_fields(scene, lines)

    return "\n".join(lines)


# 已知枚举仅作自然语言投影；自由描述与未知值原样保留。
CRAFT_LABELS = {
    "object": "物件", "bodily_action": "身体行动", "silence": "沉默",
    "procedural_form": "程序或文书形式", "second_hand_story": "转述故事",
    "sensory_shock": "感官冲击", "scale_shift": "尺度转换",
    "expectation_reversal": "期待反转",
}
REVEAL_LABELS = {
    "direct_action": "由当场行动显露", "indirect_evidence": "由间接证据推知",
    "witness_chain": "由见证者的转述逐步揭示", "object_trace": "由物件痕迹揭示",
    "official_record": "由正式记录揭示", "overheard_fragment": "由听到的话语片段揭示",
    "bodily_reaction": "由身体反应显露", "delayed_revelation": "延后揭示",
}
DISTANCE_LABELS = {
    "intimate_first": "贴近当下体验的第一人称", "reminiscing_first": "回顾式第一人称",
    "reporter_third_close": "贴近人物的第三人称", "reporter_third_distant": "外部观察式第三人称",
    "archival_zero": "档案式外部叙述", "omniscient_satirist": "全知讽刺叙述",
    "bilingual_drifter": "游移的双语叙述", "unreliable_first": "不可靠的第一人称叙述",
}
MIRROR_LABELS = {"failure": "失败呼应", "success": "成功呼应", "irony": "反讽呼应"}
CLIMAX_LABELS = {
    "layered_revelation": "新证据逐步改写既有理解",
    "ineffable_realization": "难以概括为命题的认知或感受转折",
    "passive_death": "通过肉身与物质变化呈现死亡",
    "mask_hard_cut": "情绪收回时显出恢复的社会面具",
    "unfinished_action": "未完成的表达或行动承担后果",
    "anti_epic_failure": "主角失败后由已铺设的他者或世界因果完成结果",
    "scale_shrink": "宏大后果落到具体的人类尺度",
}
ATTRIBUTION_LABELS = {
    "neutral_tag": "中性说话标记", "action_bridge": "通过动作衔接说话者",
    "object_bridge": "通过物件衔接说话者", "listener_reaction": "通过听者反应承接",
    "omitted_tag": "省略说话标记",
}
DIALOGUE_LABELS = {
    "diagnostic_verdict": "诊断或裁决式表达", "single_word_winner": "以单个词改变交锋",
    "caretaker_tone_violence": "照料口吻中的暴力", "monosyllable_confession": "极短的坦白",
    "co_creation_as_confession": "通过共同创作表露心意",
}
COUNTER_PRIOR_LABELS = {
    "ritual_with_food": "仪式中的饮食", "hospital_with_lecture": "医院处境中的讲授",
    "death_with_chore": "死亡处境中的日常事务", "farewell_with_chess": "告别中的对弈",
    "custom": "本场自定的日常行为与处境组合",
}


def _label(value, labels: dict[str, str]) -> str:
    """翻译已有含义；未知枚举不猜测、不丢弃。"""
    if isinstance(value, list):
        return " / ".join(_label(item, labels) for item in value)
    return labels.get(str(value), str(value))


def _render_v3_fields(scene: dict, lines: list[str]) -> None:
    """投影场景材料的作用、候选性质与已确认边界。"""
    craft_carrier = scene.get("craft_carrier")
    if craft_carrier:
        lines.extend(["## 承载候选", ""])
        if craft_carrier.get("type"):
            lines.append(f"- **承载方式**: {_label(craft_carrier['type'], CRAFT_LABELS)}")
        if craft_carrier.get("concrete_anchor"):
            lines.append(f"- **具体材料**: {craft_carrier['concrete_anchor']}")
        if craft_carrier.get("function"):
            lines.append(f"- **叙事作用**: {craft_carrier['function']}")
        if craft_carrier.get("replaces"):
            lines.append(f"- **既有候选说明**: {craft_carrier['replaces']}")
            lines.append("  按本场作用判断替代关系；这条说明不要求删除有独立作用的解释、心理或背景。")
        lines.append("")

    _render_world_disclosure_plan(scene, lines)

    pov_constraint = scene.get("pov_constraint")
    if pov_constraint:
        lines.extend(["## POV 约束", ""])
        for key, label in (("can_perceive", "可感知"), ("cannot_perceive", "不可感知"),
                           ("intentional_blind_spot", "故意遮蔽")):
            if pov_constraint.get(key):
                lines.append(f"- **{label}**: {_label(pov_constraint[key], {})}")
        lines.append("")

    omission_plan = scene.get("omission_plan")
    if omission_plan:
        lines.extend(["## 故意省略", ""])
        lines.extend(f"- {item}" for item in omission_plan)
        lines.append("")

    irreversible_action = scene.get("irreversible_action")
    if irreversible_action:
        lines.extend(["## 不可逆变化", "",
                      "保持已确认的事实、核心因果与必要结果；动作的具体实现按其作用选择。", ""])
        lines.extend(f"- {item}" for item in irreversible_action)
        lines.append("")

    reveal_method = scene.get("reveal_method")
    if reveal_method:
        lines.extend(["## 揭示方式候选", ""])
        if reveal_method.get("type"):
            lines.append(f"- **信息怎样显露**: {_label(reveal_method['type'], REVEAL_LABELS)}")
        lines.append("")

    narrator_distance = scene.get("narrator_distance")
    if narrator_distance:
        lines.extend(["## 叙述距离建议", ""])
        if narrator_distance.get("mode"):
            lines.append(f"- **叙述位置**: {_label(narrator_distance['mode'], DISTANCE_LABELS)}")
        if narrator_distance.get("reason"):
            lines.append(f"- **选择依据**: {narrator_distance['reason']}")
        lines.append("")

    scale_inversion = scene.get("scale_inversion")
    if scale_inversion and scale_inversion.get("used") is True:
        lines.extend(["## 尺度转换候选", ""])
        if scale_inversion.get("bridge"):
            lines.append(f"- **大命题与具体事物的联系**: {scale_inversion['bridge']}")
        lines.append("")

    precedent_mirror = scene.get("precedent_mirror")
    if precedent_mirror:
        lines.extend(["## 先例呼应候选", ""])
        for key, label, labels in (
            ("mirrors_scene", "呼应场景", {}), ("mirror_kind", "呼应关系", MIRROR_LABELS),
            ("preserved_anchors", "沿用的锚点", {}), ("removed_premises", "本场已失去的前提", {}),
        ):
            if precedent_mirror.get(key):
                lines.append(f"- **{label}**: {_label(precedent_mirror[key], labels)}")
        lines.append("")

    climax_pattern = scene.get("climax_pattern")
    if climax_pattern and climax_pattern.get("primary") not in (None, "", "null"):
        lines.extend(["## 高潮机制候选", ""])
        lines.append(f"- **主要参考**: {_label(climax_pattern['primary'], CLIMAX_LABELS)}")
        if climax_pattern.get("secondary") not in (None, "", "null", []):
            lines.append(f"- **辅助参考**: {_label(climax_pattern['secondary'], CLIMAX_LABELS)}")
        forbidden = climax_pattern.get("forbidden_moves")
        if forbidden:
            lines.append(f"- **适用限制**: {_label(forbidden, {})}")
            lines.append("  保留明确的作者禁界、事实、人物知识、核心因果与衔接要求；手法偏好按本场效果取舍。")
        lines.append("")

    dialogue_hints = scene.get("dialogue_hints")
    if dialogue_hints:
        lines.extend(["## 对白偏好", ""])
        for hint in dialogue_hints:
            if not isinstance(hint, dict):
                continue
            lines.extend([f"### {hint.get('speaker') or '全场对白'}", ""])
            if hint.get("attribution_strategy"):
                lines.append(f"- **说话归属**: {_label(hint['attribution_strategy'], ATTRIBUTION_LABELS)}")
            if hint.get("dialogue_form") not in (None, "", "null"):
                lines.append(f"- **表达形态候选**: {_label(hint['dialogue_form'], DIALOGUE_LABELS)}")
            if hint.get("reason"):
                lines.append(f"- **选择依据**: {hint['reason']}")
            lines.append("")

    counter_prior_scene = scene.get("counter_prior_scene")
    if counter_prior_scene and counter_prior_scene.get("used") is True:
        lines.extend(["## 反先验场景候选", ""])
        for key, label, labels in (
            ("kind", "行为与处境的组合", COUNTER_PRIOR_LABELS),
            ("mundane_action", "日常行为候选", {}),
            ("emotional_context", "情感处境", {}),
        ):
            if counter_prior_scene.get(key):
                lines.append(f"- **{label}**: {_label(counter_prior_scene[key], labels)}")
        forbidden = counter_prior_scene.get("forbidden_moves")
        if forbidden:
            lines.append(f"- **适用限制**: {_label(forbidden, {})}")
            lines.append("  保留明确的作者禁界与故事约束；仅由模式带出的写法偏好按本场作用判断。")
        lines.append("")

    _render_prose_risk_contract(scene, lines)


def _render_prose_risk_contract(scene: dict, lines: list[str]) -> None:
    """渲染 prose_risk_contract 字段为 markdown 段。

    契约：
    - 段标题精确字面量：## 写作层 AI pattern 预防 (prose_risk_contract)
    - 字段缺失 OR used != True → 整段不输出
    - used=True 但 risk_families / positive_strategy / bad_shape_examples 同时为空 → 整段不输出
    - 任一非空 → 输出段标题 + 该非空子列表（空那一侧不输出子标题）
    """
    contract = scene.get("prose_risk_contract")
    if not contract or contract.get("used") is not True:
        return
    risk_families = contract.get("risk_families") or []
    positive_strategy = contract.get("positive_strategy") or []
    bad_shape_examples = contract.get("bad_shape_examples") or []
    if not (risk_families or positive_strategy or bad_shape_examples):
        return

    lines.append("## 写作层 AI pattern 预防 (prose_risk_contract)")
    lines.append("")

    if risk_families:
        lines.append("**风险关注（可参考 ai-cliche-patterns.md 现有条目）**：")
        lines.append("")
        for item in risk_families:
            lines.append(f"- {item}")
        lines.append("")

    if positive_strategy:
        lines.append("**候选策略（本场提示）**：")
        lines.append("")
        for item in positive_strategy:
            lines.append(f"- {item}")
        lines.append("")

    if bad_shape_examples:
        lines.append("**问题形态线索（用于定位）**：")
        lines.append("")
        for item in bad_shape_examples:
            lines.append(f"- {item}")
        lines.append("")


def _render_world_disclosure_plan(scene: dict, lines: list[str]) -> None:
    """渲染 world_disclosure_plan 字段为 markdown 段（D-2026-05-19-8/14 契约）。

    契约：
    - 段标题精确字面量：## 世界观披露 (world_disclosure_plan)
    - forbid + allow 同时为空 OR 字段缺失 → 整段不输出
    - 任一非空 → 输出段标题 + 该非空子列表（空那一侧不输出子标题）
    """
    plan = scene.get("world_disclosure_plan")
    if not plan:
        return
    forbid = plan.get("forbid") or []
    allow = plan.get("allow") or []
    if not forbid and not allow:
        return

    lines.append("")
    lines.append("## 世界观披露 (world_disclosure_plan)")
    lines.append("")

    if forbid:
        lines.append("**暂缓披露**（按当前知识边界与已确认披露安排）：")
        lines.append("")
        for item in forbid:
            lines.append(f"- {item}")
        lines.append("")

    if allow:
        lines.append("**本场可披露**（按人物知情与叙述权限选择表达）：")
        lines.append("")
        for item in allow:
            lines.append(f"- {item}")
        lines.append("")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--scene-id", required=True, help="e.g. S02")
    parser.add_argument("--work-dir", required=True, type=Path, help="章工作区根目录（其下含 pipeline/）")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    phase5_path = work_dir / "pipeline" / "phase5_scenes.yaml"
    output_path = work_dir / "pipeline" / f"scene_{args.scene_id}" / "scene_card.md"

    try:
        scenes = load_scenes(phase5_path)
        scene = find_scene(scenes, args.scene_id)
        validate_scene(scene)
        if scene.get("inspiration_refs"):
            from validate_phase5_r10 import verify_chapter_inspiration_refs
            try:
                findings = verify_chapter_inspiration_refs({"scenes": [scene]}, work_dir)
            except (OSError, ValueError) as exc:
                raise SchemaError(str(exc)) from exc
            if findings:
                raise SchemaError("; ".join(f["message"] for f in findings))
    except SchemaError as e:
        print(f"[extract_scene_card] ERROR: {e}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(f"[extract_scene_card] YAML parse error in {phase5_path}: {e}", file=sys.stderr)
        return 1

    markdown = render_scene_card_markdown(scene)
    atomic_write(output_path, markdown)
    print(f"✅ scene_card written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
