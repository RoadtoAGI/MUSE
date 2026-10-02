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

# status 字段在多个语义不重叠的产物中复用（如 pipeline-state.yaml），
# 各自值集不同；全局 enum 会误报。verdict / spine_mode 闭合集保留校验。
ENUM_FIELDS = {
    "verdict": {"PASS", "PATCH", "ROLLBACK", "REWRITE", "ESCALATED"},
    "spine_mode": {"desire", "information", "motif"},
}


def _scan_phase5_missing_prose_risk_contract(data: dict) -> list[str]:
    """扫 phase5_scenes.yaml，返回 prose_risk_contract 格式无效的 scene_id。

    整个对象缺失合法。对象存在时 `used` 必须为 bool；三个既有
    列表字段若存在，必须是由去空白后非空字符串组成的 list。
    兼容 MUSE-writing (sequence_expansions[].scenes) 与 open-muse
    (顶层 scenes[]) 两种 schema。
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

        # phase5_scenes.yaml 中 prose_risk_contract 为 optional；对象存在时只校验格式。
        if phase_n == 5:
            for sid in _scan_phase5_missing_prose_risk_contract(data):
                print(
                    f"[muse-hook-check] WARN: {path}: scene `{sid}` 的 prose_risk_contract "
                    f"格式无效：used 应为 bool，既有列表字段应只含非空字符串",
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_yaml = sub.add_parser("yaml-contract")
    p_yaml.add_argument("--file", required=True)
    p_yaml.set_defaults(func=cmd_yaml_contract)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
