#!/usr/bin/env python3
"""muse_hook_check.py — hook 用机械检查脚本，子命令分发。

设计文档：docs/Level_3_implementation/pipeline/2026-05-16-hooks-治理设计.md §2 H4

用法：
  python3 muse_hook_check.py yaml-contract --file <path>

(phase-complete subcommand v6 已删——H5 validate-phase-complete hook 取消，参见 design doc v6)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# 按各 phase output-schema.md 真实顶层 key
# 来源：skills/MUSE-writing/skills/phase{N}-*/references/output-schema.md
# 仅取"产物未生成必失败"的稳态顶层字段；漏列优于误判（warning only）
PHASE_REQUIRED_KEYS = {
    0: ["premise", "core_value", "controlling_idea", "genre"],
    1: ["setting", "genre_conventions", "world_rules"],
    2: ["protagonist"],
    3: ["inciting_incident", "spine_mode", "arcs", "spine_statement", "dramatic_question", "story_climax_design"],
    4: ["arc_expansions"],
    5: ["sequence_expansions"],
    6: ["scenes"],
}

# status 字段在多个语义不重叠的产物中复用（如 mode_alignment.yaml / pipeline-state.yaml），
# 各自值集不同；全局 enum 会误报。verdict / spine_mode 闭合集保留校验。
ENUM_FIELDS = {
    "verdict": {"PASS", "PATCH", "ROLLBACK", "REWRITE", "ESCALATED"},
    "spine_mode": {"desire", "information", "motif"},
}


def _scan_phase5_missing_prose_risk_contract(data: dict) -> list[str]:
    """返回已有 prose_risk_contract 格式无效的 scene_id；对象缺省合法。

    兼容 MUSE-writing (sequence_expansions[].scenes) 与 open-muse (顶层 scenes[]) 两种 schema。
    """
    scenes: list = []
    for seq in (data.get("sequence_expansions") or []):
        if isinstance(seq, dict):
            scenes.extend(seq.get("scenes") or [])
    scenes.extend(data.get("scenes") or [])

    missing: list[str] = []
    for sc in scenes:
        if not isinstance(sc, dict):
            continue
        sid = sc.get("scene_id") or "<no-id>"
        prc = sc.get("prose_risk_contract")
        if prc is None:
            continue
        if not isinstance(prc, dict) or not isinstance(prc.get("used"), bool):
            missing.append(sid)
            continue
        for field in ("risk_families", "positive_strategy", "bad_shape_examples"):
            if field not in prc:
                continue
            value = prc[field]
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                missing.append(sid)
                break
    return missing


def cmd_yaml_contract(args) -> int:
    """H4: YAML 语法 + 最小 schema 校验。warning only（return 0 + stderr WARN）。"""
    try:
        import yaml
    except ImportError:
        print("[muse-hook-check] INFO: PyYAML 不可用，跳过", file=sys.stderr)
        return 0

    path = Path(args.file)
    if not path.exists():
        return 0  # 新建文件场景下文件可能尚未落盘，hook 不报错

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"[muse-hook-check] WARN: {path}: YAML 解析失败：{e}", file=sys.stderr)
        return 0

    if not isinstance(data, dict):
        print(f"[muse-hook-check] WARN: {path}: 顶层应为 dict，实为 {type(data).__name__}", file=sys.stderr)
        return 0

    # phase{N}_*.yaml 必填顶层 key 检查
    m = re.search(r"phase(\d)_", path.name)
    if m:
        phase_n = int(m.group(1))
        required = PHASE_REQUIRED_KEYS.get(phase_n, [])
        for k in required:
            if k not in data:
                print(f"[muse-hook-check] WARN: {path}: phase{phase_n} 必填顶层 key 缺：`{k}`", file=sys.stderr)

        # 只诊断已提供的风险提示格式；缺省使用通用写作指导。
        if phase_n == 5:
            for sid in _scan_phase5_missing_prose_risk_contract(data):
                print(
                    f"[muse-hook-check] WARN: {path}: scene `{sid}` prose_risk_contract 格式无效"
                    "（used 须为 bool，已提供的策略字段须为非空字符串列表）",
                    file=sys.stderr,
                )

    # enum 字段值检查（递归扫一层）
    def scan_enum(obj, depth=0):
        if depth > 5 or not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if k in ENUM_FIELDS and isinstance(v, str) and v not in ENUM_FIELDS[k]:
                print(f"[muse-hook-check] WARN: {path}: `{k}=\"{v}\"` 不在 enum {sorted(ENUM_FIELDS[k])}", file=sys.stderr)
            if isinstance(v, dict):
                scan_enum(v, depth + 1)
            elif isinstance(v, list):
                for item in v:
                    scan_enum(item, depth + 1)

    scan_enum(data)
    return 0


# ── scene-card-compliance ──
# 由 hooks/check-scene-card-compliance.sh 调用
# 校验：narration_style / pov 与 scene_text 兑现关系（v3 收敛后两字段）
# participants 仅 parse-only（Phase 2 扩展位，见附录 A2）
# 设计依据：2026-05-18 单路径协议 plan T15 + 183 run POV 漏检事故

_PRONOUN_FIRST = ["我", "我的", "我们", "咱", "咱们"]
_PRONOUN_THIRD = ["他", "她", "它", "他们", "她们", "它们", "他的", "她的", "它的"]


def _count_substrings(text: str, words: list[str]) -> int:
    total = 0
    for w in words:
        total += text.count(w)
    return total


def _parse_scene_card_fields(card_text: str) -> dict:
    """从 scene_card.md 提取硬字段。支持两种格式：
    - markdown bold: **narration_style**: first
    - YAML-like: narration_style: first
    返回 dict（可能为空）。"""
    fields = {}
    aliases = {
        "narration_style": ("narration_style", "叙述方式"),
        "pov": ("pov", "视角角色"),
        "participants": ("participants", "在场人物"),
    }
    for line in card_text.splitlines():
        line = line.strip()
        for key, labels in aliases.items():
            for label in labels:
                for prefix in (f"**{label}**:", f"{label}:"):
                    if not line.startswith(prefix):
                        continue
                    val = line[len(prefix):].strip()
                    if key == "participants":
                        fields[key] = [p.strip() for p in val.split(",") if p.strip()]
                    else:
                        fields[key] = val
                    break
                if key in fields:
                    break
    return fields


def cmd_scene_card_compliance(args) -> int:
    """校验 scene_text 是否兑现 scene_card 的硬字段。统一 WARN + exit 0。"""
    card_path = Path(args.scene_card)
    text_path = Path(args.scene_text)

    if not card_path.exists():
        print(f"[scene-card-compliance WARN] scene_card 不存在：{card_path}", file=sys.stderr)
        return 0

    if not text_path.exists():
        print(f"[scene-card-compliance WARN] scene 正文不存在：{text_path}", file=sys.stderr)
        return 0

    card_text = card_path.read_text(encoding="utf-8")
    scene_text = text_path.read_text(encoding="utf-8")

    fields = _parse_scene_card_fields(card_text)
    if not fields:
        print(f"[scene-card-compliance WARN] scene_card 未解析到 narration_style / pov 字段：{card_path}", file=sys.stderr)
        return 0

    violations = []

    # narration_style 校验
    # v5 修法（StoryStudio smoke 报告 §B）：补中文枚举别名——
    # 原 `.lower()` 不影响中文，"第一人称" 会绕过下方 if 静默跳过；
    # 同时归一 1st/3rd 与全角冒号清洗，所有形态收敛到 first/third。
    raw_style = fields.get("narration_style", "").strip().lower()
    _STYLE_ALIASES = {
        "first": "first", "1st": "first", "第一人称": "first", "我": "first",
        "third": "third", "3rd": "third", "第三人称": "third", "他": "third", "她": "third",
    }
    style = _STYLE_ALIASES.get(raw_style, raw_style)
    if style in ("first", "third"):
        n_first = _count_substrings(scene_text, _PRONOUN_FIRST)
        n_third = _count_substrings(scene_text, _PRONOUN_THIRD)
        if style == "first":
            if n_first == 0 and n_third > 0:
                violations.append(
                    f"narration_style=first 但正文 0 个第一人称代词、{n_third} 个第三人称代词；典型 POV 违反（如 183 run）"
                )
            elif n_third > 0 and n_first > 0 and (n_first / max(n_third, 1)) < 1.0:
                violations.append(
                    f"narration_style=first 但第三人称代词占比偏高：{n_first} 个第一人称 vs {n_third} 个第三人称（比值 {n_first/max(n_third,1):.2f} < 1.0）"
                )
        elif style == "third":
            if n_third == 0 and n_first > 0:
                violations.append(
                    f"narration_style=third 但正文 0 个第三人称代词、{n_first} 个第一人称代词"
                )
            elif n_first > 0 and n_third > 0 and (n_third / max(n_first, 1)) < 1.0:
                # v4 收敛（codex R3-F1）：补 ratio 分支，对齐 first 分支的"两侧都存在但比值偏低"语义
                violations.append(
                    f"narration_style=third 但第一人称代词占比偏高：{n_third} 个第三人称 vs {n_first} 个第一人称（比值 {n_third/max(n_first,1):.2f} < 1.0）"
                )
    # mixed → 不校验

    # pov 校验（仅 first 时要求非空）
    if style == "first":
        pov = fields.get("pov", "").strip()
        if not pov:
            violations.append("narration_style=first 但 scene_card.pov 字段为空（应填写承担第一人称视角的角色 slug）")

    # participants 字段：v2 第一版不输出 WARN，仅 parse 不报错（接口位留给 Phase 2）。
    # 原因（codex R1 F3）：scene_card.participants 存 slug（"lu-yuan"），正文中
    # 出现的是中文名 / 别名 / 绰号；slug↔name 映射需要 character builder 提供 alias
    # 字段，本 plan 尚未配套。Phase 2 扩展时可在此处加入：
    #   - 读 character build-meta.yaml 的 aliases 字段构造名字白名单
    #   - 检查"列表非空 + 白名单内的名字一个都没在正文出现" → WARN
    _ = fields.get("participants") or []  # parse-only，不报错也不输出

    if not violations:
        return 0

    print("[scene-card-compliance] 正文与 scene_card 硬字段不一致：", file=sys.stderr)
    for v in violations:
        print(f"  - {v}", file=sys.stderr)
    print(f"  scene_card: {card_path}", file=sys.stderr)
    print(f"  正文: {text_path}", file=sys.stderr)

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_yaml = sub.add_parser("yaml-contract")
    p_yaml.add_argument("--file", required=True)
    p_yaml.set_defaults(func=cmd_yaml_contract)

    p_sc = sub.add_parser("scene-card-compliance")
    p_sc.add_argument("--scene-card", required=True, help="scene_card.md 路径")
    p_sc.add_argument("--scene-text", required=True, help="正文 scene_*.md 路径")
    p_sc.set_defaults(func=cmd_scene_card_compliance)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
