#!/usr/bin/env python3
"""Phase 5 r10 validation helpers."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = ("abstract_function", "physical_carrier", "reader_yield", "rendering")
PLACEHOLDER_VALUES = {"", "TODO", "待定", "-"}

PATTERN_A_ACTION_SUFFIX = re.compile(
    r"(装置|系统|边界|机制|模式)[^，。；;、\n]{0,10}"
    r"(完成|呈现|显形|落地|到位|形成|进入临界|出现裂缝)"
)
PATTERN_A_GENERAL = re.compile(r"^(物理化抵达|呈现|显形|完成|落地|形成)$")
PATTERN_B_PHASE_FIELD = re.compile(
    r"(language_boundaries|converts_into|dramatic_function|内驱力|节拍组|转场|母题级|第N层)"
)
PATTERN_C_PSYCHIC_DEVICE_SUBJECT = re.compile(
    r"(^|[\s，。；;、])[^，。；;、\n]{0,6}"
    r"(装置|系统|边界|机制|模式)[^，。；;、\n]{0,10}"
    r"(呈现|进入临界|出现裂缝|形成|完成|显形|落地|到位)"
)
EVALUATIVE_ADJECTIVES = re.compile(r"(反应得体|措辞含糊|姿态稳定|表情合理)")

def _is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return text in PLACEHOLDER_VALUES or text.upper() == "TODO"


def _as_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _scan_for_abstract_patterns(text: str, field_label: str) -> list[str]:
    errors: list[str] = []
    if PATTERN_C_PSYCHIC_DEVICE_SUBJECT.search(text):
        errors.append(f"{field_label} pattern C 心理装置名独立主语")
    if PATTERN_B_PHASE_FIELD.search(text):
        errors.append(f"{field_label} pattern B phase 字段名")
    if PATTERN_A_ACTION_SUFFIX.search(text) or PATTERN_A_GENERAL.search(text.strip()):
        errors.append(f"{field_label} pattern A 抽象名词+动作后缀")
    return errors


def scan_scene_task_concreteness(task: Any) -> dict[str, Any]:
    """Validate one Phase 5 scene_task object.

    Returns a small report instead of raising so hooks/tests can aggregate all
    scene-level errors into one actionable message.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if isinstance(task, str) and task.strip():
        return {"status": "pass", "errors": [], "warnings": ["旧字符串任务按原有含义消费；新任务使用对象结构"], "reason": ""}

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
        errors.append("physical_carrier 必须是 list，可为空")
    if "reader_yield" in task and not _as_non_empty_list(reader_yield):
        errors.append("reader_yield 空 list")
    if "rendering" in task:
        if not isinstance(rendering, dict):
            errors.append("rendering 必须是 object")
        else:
            if rendering.get("default") not in ("summary", "expand"):
                errors.append("rendering.default 必须为 summary 或 expand")
            if not isinstance(rendering.get("expand_only_if"), str) or _is_placeholder(rendering.get("expand_only_if")):
                errors.append("rendering.expand_only_if 必须为非空文本")

    abstract_function = str(task.get("abstract_function") or "")
    if not isinstance(task.get("abstract_function"), str) or _is_placeholder(task.get("abstract_function")):
        errors.append("abstract_function 必须为说明本场作用的非空文本")
    if EVALUATIVE_ADJECTIVES.search(abstract_function):
        warnings.append("abstract_function 含笼统评价，需按场景判断是否表达实际作用")

    if isinstance(physical_carrier, list):
        for index, carrier in enumerate(physical_carrier):
            if not isinstance(carrier, dict):
                errors.append(f"physical_carrier[{index}] 必须是 object")
                continue
            text = str(carrier.get("text") or "")
            if not isinstance(carrier.get("text"), str) or _is_placeholder(carrier.get("text")):
                errors.append(f"physical_carrier[{index}].text 必须为非空文本")
            warnings.extend(_scan_for_abstract_patterns(text, f"physical_carrier[{index}].text"))
            if not isinstance(carrier.get("function_link"), str) or _is_placeholder(carrier.get("function_link")):
                errors.append(f"physical_carrier[{index}].function_link 必须为非空文本")

    if isinstance(reader_yield, list):
        for index, item in enumerate(reader_yield):
            if not isinstance(item, str) or _is_placeholder(item):
                errors.append(f"reader_yield[{index}] 必须为非空文本")

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


def verify_inspiration_refs(phase5: dict, ledger: dict, chapter_id: str | None = None) -> list[dict[str, str]]:
    """校验 phase5 各 scene 的 inspiration_refs[] 字段。"""
    findings: list[dict[str, str]] = []
    if not isinstance(ledger, dict):
        return [{"code": "inspiration_ledger_invalid", "message": "ledger 必须为 mapping"}]
    cards = ledger.get("inspirations") or ledger.get("inspiration_ledger") or []
    if not isinstance(cards, list):
        return [{"code": "inspiration_ledger_invalid", "message": "ledger 条目必须为 list"}]
    ledger_index = {}
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get("id"), str):
            return [{"code": "inspiration_ledger_invalid", "message": "每条灵感须有字符串 id"}]
        if card["id"] in ledger_index:
            return [{"code": "inspiration_ledger_duplicate_id", "message": f"重复 id: {card['id']}"}]
        ledger_index[card["id"]] = card

    for scene in _iter_scenes(phase5):
        scene_id = scene.get("scene_id")
        refs = scene.get("inspiration_refs")
        if not refs:
            continue

        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            findings.append({"code": "inspiration_refs_invalid", "message": f"scene {scene_id} refs 必须为字符串列表"})
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
            encodings = card.get("project_encoding") or []
            if not isinstance(encodings, list):
                encodings = []
            for encoding in encodings:
                if not isinstance(encoding, dict):
                    continue
                if encoding.get("phase") != 5:
                    continue
                if encoding.get("scene_id") != scene_id:
                    continue
                if chapter_id is not None and encoding.get("chapter_id") != chapter_id:
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
                        f"(phase=5, chapter_id={chapter_id}, scene_id={scene_id}, adoption_kind in "
                        f"{sorted(VALID_ADOPTION_KINDS)}) 匹配项"
                    ),
                    "scene_id": str(scene_id),
                })

    return findings


def verify_chapter_inspiration_refs(phase5: dict, chapter_dir: Path) -> list[dict]:
    """Use the existing chapter identity and ledger; selected refs cannot cross chapters."""
    chapter = yaml.safe_load((chapter_dir / "chapter_card.yaml").read_text(encoding="utf-8"))
    cid = chapter.get("chapter_id") if isinstance(chapter, dict) else None
    if not isinstance(cid, str) or not cid.strip():
        raise ValueError("chapter_card.chapter_id 缺失，无法确定灵感采用范围")
    ledger = yaml.safe_load((chapter_dir / "pipeline/inspiration_ledger.yaml").read_text(encoding="utf-8"))
    return verify_inspiration_refs(phase5, ledger, chapter_id=cid)


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
        refs_present = any(scene.get("inspiration_refs") for scene in _iter_scenes(data))
        if refs_present:
            try:
                findings = verify_chapter_inspiration_refs(data, yaml_path.parent.parent)
                errors.extend(f"inspiration_refs: [{f['code']}] {f['message']}" for f in findings)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                errors.append(f"inspiration_refs: {exc}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
