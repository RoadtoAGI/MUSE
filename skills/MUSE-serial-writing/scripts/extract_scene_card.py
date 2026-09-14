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

    # v3 新增字段（全 optional，缺/空整段省略）
    _render_v3_fields(scene, lines)

    return "\n".join(lines)


def _render_v3_fields(scene: dict, lines: list[str]) -> None:
    """渲染 v3 schema 的扩展字段（craft_carrier / counter_prior_scene 等）。

    所有字段 optional：missing / None / 空容器 / used=false → 整段 section 省略。
    """
    # craft_carrier（object）
    craft_carrier = scene.get("craft_carrier")
    if craft_carrier:
        lines.append("## Carrier 设计")
        lines.append("")
        if craft_carrier.get("type"):
            lines.append(f"- **Type**: {craft_carrier['type']}")
        if craft_carrier.get("concrete_anchor"):
            lines.append(f"- **Concrete anchor**: {craft_carrier['concrete_anchor']}")
        if craft_carrier.get("replaces"):
            lines.append(f"- **Replaces**: {craft_carrier['replaces']}")
        lines.append("")

    _render_world_disclosure_plan(scene, lines)

    # pov_constraint（object）— 对齐 phase5 output-schema.md L35-37：
    # can_perceive: list[str] / cannot_perceive: list[str] / intentional_blind_spot: str
    pov_constraint = scene.get("pov_constraint")
    if pov_constraint:
        lines.append("## POV 约束")
        lines.append("")
        can_perceive = pov_constraint.get("can_perceive")
        if can_perceive:
            can_str = ", ".join(can_perceive) if isinstance(can_perceive, list) else can_perceive
            lines.append(f"- **可感知**: {can_str}")
        cannot_perceive = pov_constraint.get("cannot_perceive")
        if cannot_perceive:
            cannot_str = ", ".join(cannot_perceive) if isinstance(cannot_perceive, list) else cannot_perceive
            lines.append(f"- **不可感知**: {cannot_str}")
        if pov_constraint.get("intentional_blind_spot"):
            lines.append(f"- **故意遮蔽**: {pov_constraint['intentional_blind_spot']}")
        lines.append("")

    # omission_plan（list）
    omission_plan = scene.get("omission_plan")
    if omission_plan:
        lines.append("## 故意省略")
        lines.append("")
        for item in omission_plan:
            lines.append(f"- {item}")
        lines.append("")

    # irreversible_action（list）
    irreversible_action = scene.get("irreversible_action")
    if irreversible_action:
        lines.append("## 不可逆动作")
        lines.append("")
        for item in irreversible_action:
            lines.append(f"- {item}")
        lines.append("")

    # reveal_method（object）— schema 只有 type 一个子键
    reveal_method = scene.get("reveal_method")
    if reveal_method:
        lines.append("## 揭示方式")
        lines.append("")
        if reveal_method.get("type"):
            lines.append(f"- **Type**: {reveal_method['type']}")
        lines.append("")

    # narrator_distance（object）
    narrator_distance = scene.get("narrator_distance")
    if narrator_distance:
        lines.append("## 叙述距离")
        lines.append("")
        if narrator_distance.get("mode"):
            lines.append(f"- **Mode**: {narrator_distance['mode']}")
        if narrator_distance.get("reason"):
            lines.append(f"- **Reason**: {narrator_distance['reason']}")
        lines.append("")

    # scale_inversion（object，used=true 时渲染）— schema 仅 used / bridge
    scale_inversion = scene.get("scale_inversion")
    if scale_inversion and scale_inversion.get("used") is True:
        lines.append("## 尺度反转")
        lines.append("")
        lines.append("- **Used**: true")
        if scale_inversion.get("bridge"):
            lines.append(f"- **Bridge**: {scale_inversion['bridge']}")
        lines.append("")

    # precedent_mirror（object）
    precedent_mirror = scene.get("precedent_mirror")
    if precedent_mirror:
        lines.append("## 先例镜像")
        lines.append("")
        if precedent_mirror.get("mirrors_scene"):
            lines.append(f"- **Mirrors scene**: {precedent_mirror['mirrors_scene']}")
        if precedent_mirror.get("mirror_kind"):
            lines.append(f"- **Mirror kind**: {precedent_mirror['mirror_kind']}")
        preserved = precedent_mirror.get("preserved_anchors")
        if preserved:
            anchors_str = ", ".join(preserved) if isinstance(preserved, list) else str(preserved)
            lines.append(f"- **Preserved anchors**: {anchors_str}")
        removed = precedent_mirror.get("removed_premises")
        if removed:
            removed_str = ", ".join(removed) if isinstance(removed, list) else str(removed)
            lines.append(f"- **Removed premises**: {removed_str}")
        lines.append("")

    # climax_pattern（object，primary != null 时渲染）
    climax_pattern = scene.get("climax_pattern")
    if climax_pattern:
        primary = climax_pattern.get("primary")
        if primary and primary != "null":
            lines.append("## Climax Pattern")
            lines.append("")
            lines.append(f"- **Primary**: {primary}")
            secondary = climax_pattern.get("secondary")
            if secondary:
                sec_str = ", ".join(secondary) if isinstance(secondary, list) else str(secondary)
                lines.append(f"- **Secondary**: {sec_str}")
            forbidden = climax_pattern.get("forbidden_moves")
            if forbidden:
                forb_str = ", ".join(forbidden) if isinstance(forbidden, list) else str(forbidden)
                lines.append(f"- **Forbidden moves**: {forb_str}")
            lines.append("")

    # dialogue_hints（list of dict，按 speaker 块渲染）
    dialogue_hints = scene.get("dialogue_hints")
    if dialogue_hints:
        lines.append("## 对白偏好")
        lines.append("")
        for hint in dialogue_hints:
            if not isinstance(hint, dict):
                continue
            speaker = hint.get("speaker", "(unspecified)")
            lines.append(f"### Speaker: {speaker}")
            lines.append("")
            if hint.get("attribution_strategy"):
                lines.append(f"- **Attribution**: {hint['attribution_strategy']}")
            if hint.get("dialogue_form"):
                lines.append(f"- **Form**: {hint['dialogue_form']}")
            if hint.get("reason"):
                lines.append(f"- **Reason**: {hint['reason']}")
            lines.append("")

    # counter_prior_scene（object，used=true 时渲染）
    counter_prior_scene = scene.get("counter_prior_scene")
    if counter_prior_scene and counter_prior_scene.get("used") is True:
        lines.append("## 反先例场景 (counter_prior_scene)")
        lines.append("")
        lines.append("- **Used**: true")
        if counter_prior_scene.get("kind"):
            lines.append(f"- **Kind**: {counter_prior_scene['kind']}")
        if counter_prior_scene.get("mundane_action"):
            lines.append(f"- **Mundane action**: {counter_prior_scene['mundane_action']}")
        if counter_prior_scene.get("emotional_context"):
            lines.append(f"- **Emotional context**: {counter_prior_scene['emotional_context']}")
        forbidden = counter_prior_scene.get("forbidden_moves")
        if forbidden:
            forb_str = ", ".join(forbidden) if isinstance(forbidden, list) else str(forbidden)
            lines.append(f"- **Forbidden moves**: {forb_str}")
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
        lines.append("**风险族（主动规避；锚 ai-cliche-patterns.md 现有条目）**：")
        lines.append("")
        for item in risk_families:
            lines.append(f"- {item}")
        lines.append("")

    if positive_strategy:
        lines.append("**正向策略（本场特化）**：")
        lines.append("")
        for item in positive_strategy:
            lines.append(f"- {item}")
        lines.append("")

    if bad_shape_examples:
        lines.append("**结构形态示例（避同构，非字面禁词）**：")
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
