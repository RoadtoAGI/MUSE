#!/usr/bin/env python3
"""Phase 5 r10 validation helpers."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = ("abstract_function", "reader_yield", "rendering")
PATTERN_A_ACTION_SUFFIX = re.compile(
    r"(装置|系统|边界|机制|模式)[^，。；;、\n]{0,10}"
    r"(完成|呈现|显形|落地|到位|形成|进入临界|出现裂缝)"
)
PATTERN_A_GENERAL = re.compile(r"^(物理化抵达|呈现|显形|完成|落地|形成)$")
EVALUATIVE_ADJECTIVES = re.compile(r"(反应得体|措辞含糊|姿态稳定|表情合理)")


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def scan_scene_task_concreteness(task: Any) -> dict[str, Any]:
    """Validate one Phase 5 scene_task object.

    Returns a small report instead of raising so hooks/tests can aggregate all
    scene-level errors into one actionable message.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(task, dict):
        return {
            "status": "error",
            "errors": ["scene_task 必须是 object"],
            "reason": "scene_task 必须是 object",
        }

    for field in REQUIRED_FIELDS:
        if field not in task:
            errors.append(f"缺字段 {field}")

    physical_carrier = task.get("physical_carrier")
    reader_yield = task.get("reader_yield")
    rendering = task.get("rendering")

    if "physical_carrier" in task and not isinstance(physical_carrier, list):
        errors.append("physical_carrier 必须是 list")
    if "reader_yield" in task and not _as_non_empty_list(reader_yield):
        errors.append("reader_yield 空 list")
    if "rendering" in task:
        if not isinstance(rendering, dict):
            errors.append("rendering 必须是 object")
        else:
            if not rendering.get("default"):
                errors.append("rendering 缺 default")
            if not rendering.get("expand_only_if"):
                errors.append("rendering 缺 expand_only_if")

    abstract_function = str(task.get("abstract_function") or "")
    if EVALUATIVE_ADJECTIVES.search(abstract_function):
        errors.append("评估性形容词作 task")
    if PATTERN_A_ACTION_SUFFIX.search(abstract_function) or PATTERN_A_GENERAL.search(abstract_function.strip()):
        errors.append("abstract_function pattern A 抽象名词+动作后缀")

    if isinstance(physical_carrier, list):
        for index, carrier in enumerate(physical_carrier):
            if not isinstance(carrier, dict):
                errors.append(f"physical_carrier[{index}] 必须是 object")
                continue
            if not _is_non_empty_text(carrier.get("text")):
                errors.append(f"physical_carrier[{index}].text 必须是非空 str")
            if not _is_non_empty_text(carrier.get("function_link")):
                errors.append(f"physical_carrier[{index}].function_link 必须是非空 str")

    status = "error" if errors else "pass"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "reason": errors[0] if errors else "",
    }


def _iter_scenes(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("scenes"), list):
        return [scene for scene in data["scenes"] if isinstance(scene, dict)]
    scenes: list[dict[str, Any]] = []
    for seq in data.get("sequence_expansions") or []:
        if not isinstance(seq, dict):
            continue
        seq_scenes = seq.get("scenes") or seq.get("scenes_in_sequence") or []
        scenes.extend(scene for scene in seq_scenes if isinstance(scene, dict))
    return scenes


def scan_phase5_scene_tasks(data: Any) -> list[str]:
    errors: list[str] = []
    for scene_index, scene in enumerate(_iter_scenes(data)):
        scene_id = scene.get("scene_id") or f"#{scene_index}"
        scene_tasks = scene.get("scene_tasks")
        if not isinstance(scene_tasks, list) or not scene_tasks:
            errors.append(f"scene {scene_id}: scene_tasks 缺失或为空")
            continue
        for task_index, task in enumerate(scene_tasks):
            result = scan_scene_task_concreteness(task)
            for reason in result.get("errors", []):
                errors.append(f"scene {scene_id} task[{task_index}]: {reason}")
    return errors


VALID_ADOPTION_KINDS = {
    "scene_carrier",
    "reveal_carrier",
    "structure_carrier",
    "craft_carrier",
}


def verify_inspiration_refs(phase5: dict, ledger: dict) -> list[dict[str, str]]:
    """校验 phase5 各 scene 的 inspiration_refs[] 字段。"""
    findings: list[dict[str, str]] = []
    cards = ledger.get("inspirations") or ledger.get("inspiration_ledger") or []
    ledger_index = {
        card.get("id"): card for card in cards
        if isinstance(card, dict) and card.get("id")
    }

    for scene in _iter_scenes(phase5):
        scene_id = scene.get("scene_id")
        refs = scene.get("inspiration_refs")
        if not refs:
            continue

        for ins_id in refs:
            if ins_id not in ledger_index:
                findings.append({
                    "code": "inspiration_refs_ledger_id_missing",
                    "message": f"scene {scene_id} inspiration_refs 引用 {ins_id} 在 ledger 中找不到",
                    "scene_id": str(scene_id),
                })
                continue
            card = ledger_index[ins_id]
            if card.get("type") != "pattern":
                findings.append({
                    "code": "inspiration_refs_ledger_type_mismatch",
                    "message": (
                        f"scene {scene_id} inspiration_refs 引用 {ins_id} 在 ledger 中 "
                        f"type={card.get('type')}，应为 pattern"
                    ),
                    "scene_id": str(scene_id),
                })
                continue
            if card.get("status") not in ("accepted", "bound"):
                findings.append({
                    "code": "inspiration_refs_ledger_status_invalid",
                    "message": (
                        f"scene {scene_id} inspiration_refs 引用 {ins_id} "
                        f"status={card.get('status')}，应为 accepted 或 bound"
                    ),
                    "scene_id": str(scene_id),
                })
                continue

            pe_match = False
            for encoding in card.get("project_encoding", []):
                if not isinstance(encoding, dict):
                    continue
                if encoding.get("phase") != 5:
                    continue
                if encoding.get("scene_id") != scene_id:
                    continue
                kind = encoding.get("adoption_kind")
                if kind not in VALID_ADOPTION_KINDS:
                    findings.append({
                        "code": "inspiration_refs_invalid_adoption_kind",
                        "message": (
                            f"scene {scene_id} inspiration_refs {ins_id} "
                            f"ledger.project_encoding adoption_kind={kind} 不在 enum "
                            f"{sorted(VALID_ADOPTION_KINDS)} 内"
                        ),
                        "scene_id": str(scene_id),
                    })
                    continue
                pe_match = True
                break
            if not pe_match:
                findings.append({
                    "code": "inspiration_refs_bidirectional_missing",
                    "message": (
                        f"scene {scene_id} inspiration_refs {ins_id} 在 "
                        "ledger.project_encoding[] 找不到 "
                        f"(phase=5, scene_id={scene_id}, adoption_kind in "
                        f"{sorted(VALID_ADOPTION_KINDS)}) 匹配项"
                    ),
                    "scene_id": str(scene_id),
                })

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 5 r10 scene_tasks.")
    parser.add_argument("file", help="phase5_scenes.yaml path")
    parser.add_argument("--scan-scene-tasks", action="store_true", help="run scene_task concreteness checks")
    parser.add_argument(
        "--scan-inspiration-refs",
        action="store_true",
        help="validate scene.inspiration_refs[] against sibling inspiration_ledger.yaml",
    )
    args = parser.parse_args(argv)

    yaml_path = Path(args.file)
    with yaml_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    errors: list[str] = []
    if args.scan_scene_tasks:
        errors.extend(scan_phase5_scene_tasks(data))

    if args.scan_inspiration_refs:
        ledger_path = yaml_path.parent / "inspiration_ledger.yaml"
        if ledger_path.exists():
            with ledger_path.open(encoding="utf-8") as handle:
                ledger_data = yaml.safe_load(handle) or {}
            for finding in verify_inspiration_refs(data, ledger_data):
                errors.append(f"inspiration_refs: [{finding['code']}] {finding['message']}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
