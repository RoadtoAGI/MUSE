#!/usr/bin/env python3
"""检查显式构建清单中的人物兼容包；不要求连载人物全部有包。

传入 series/character-skills，或包含 pipeline/ 的单篇工作目录。
校验清单映射、四件完整性、元数据和模板章节；已引用的原型检查来源。
历史报告额外列与元数据额外字段保留。退出 0 仅说明这些结构检查通过。
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

CORE_META_FIELDS = [
    "generated_by", "character_slug", "character_display_name",
    "input_sources", "adapter_path",
]
DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills/character-persona/references/skill-template.md"
)
LAYOUT: dict = {}


def resolve_layout(root: Path) -> dict:
    root = root.resolve()
    if (root / "pipeline").is_dir():
        return {
            "work_dir": root,
            "skills_home": root / "pipeline" / "story-character-skills",
            "adapters": root / "pipeline" / "characters",
            "phase2": root / "pipeline" / "phase2_character.yaml",
            "ledger": root / "pipeline" / "inspiration_ledger.yaml",
        }
    work_dir = root.parent.parent if root.parent.name == "series" else root
    return {
        "work_dir": work_dir,
        "skills_home": root,
        "adapters": root / "characters",
        "phase2": root / "phase2_character.yaml",
        "ledger": root / "inspiration_ledger.yaml",
    }


def parse_template_sections(template_path: Path):
    required, allowed = set(), set()
    lines = template_path.read_text().splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        head, _, tail = line.partition("<!--")
        name = head.removeprefix("## ").strip()
        marker = tail.split("-->")[0].strip().lower()
        if not marker and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line.startswith("<!--") and next_line.endswith("-->"):
                marker = next_line[4:-3].strip().lower()
        if marker == "required":
            required.add(name)
            allowed.add(name)
        elif marker == "optional":
            allowed.add(name)
    if not required:
        raise ValueError(f"template has no required sections: {template_path}")
    return required, allowed


def read_mapping(path: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return data


def verify_canon_archetype(phase2: dict, ledger: dict) -> list:
    findings = []
    cards = ledger.get("inspirations") or ledger.get("inspiration_ledger") or []
    if not isinstance(cards, list):
        return [{"code": "canon_archetype_ledger_invalid", "message": "原型台账需为列表"}]
    ledger_index = {c.get("id"): c for c in cards if isinstance(c, dict) and c.get("id")}
    for slot in ("protagonist", "deuteragonist", "antagonist"):
        role = phase2.get(slot)
        if not isinstance(role, dict):
            continue
        archetypes = role.get("canon_archetype")
        if archetypes is None:
            continue

        def report(code, message):
            findings.append({"code": code, "message": message, "role_slug": slot})

        if not isinstance(archetypes, list):
            report("canon_archetype_invalid", f"{slot}.canon_archetype 需为列表")
            continue
        for item in archetypes:
            if not isinstance(item, dict):
                report("canon_archetype_invalid", f"{slot} 原型条目需为映射")
                continue
            ins_id = item.get("id")
            weight = item.get("weight")
            if weight not in ("dominant", "secondary"):
                report("canon_archetype_weight_invalid", f"{slot} {ins_id}: 无效 weight")
            if weight == "secondary" and not str(item.get("merge_boundary") or "").strip():
                report("canon_archetype_secondary_missing_merge_boundary", f"{slot} {ins_id}: 缺 merge_boundary")
            if not isinstance(ins_id, str) or ins_id not in ledger_index:
                report("canon_archetype_ledger_id_missing", f"{slot}: 原型引用 {ins_id!r} 不在台账")
                continue
            card = ledger_index[ins_id]
            if card.get("type") != "archetype":
                report("canon_archetype_ledger_type_mismatch", f"{slot} {ins_id}: type 应为 archetype")
            if card.get("status") not in ("accepted", "bound"):
                report("canon_archetype_ledger_status_invalid", f"{slot} {ins_id}: 尚未采纳")
            if card.get("archetype_target_slug") != slot:
                report("canon_archetype_target_slug_mismatch", f"{slot} {ins_id}: 目标角色不符")
    return findings


def parse_build_report(pipeline: Path):
    path = LAYOUT["skills_home"] / "build-report.md"
    if not path.exists():
        return None
    built, unbuilt = [], []
    section = None
    headers = []
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            headers = []
            continue
        if not line.strip().startswith("|") or not line.strip().endswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if "name" in cells:
            headers = cells
            continue
        if not headers:
            continue
        row = dict(zip(headers, cells))
        name = row.get("name", "")
        if section and section.startswith("已构建"):
            built.append((name, row.get("slug", ""), row.get("reason", "")))
        elif section and section.startswith("未构建"):
            unbuilt.append((name, row.get("skip_reason", row.get("reason", ""))))
    return {"built": built, "unbuilt": unbuilt}


def check_skill(pipeline: Path, slug: str, display_name: str,
                required_sections: set, allowed_sections: set):
    errors = []
    skill_dir = LAYOUT["skills_home"] / ".claude" / "skills" / slug
    skill_md = skill_dir / "SKILL.md"
    adapter = LAYOUT["adapters"] / f"{display_name}.md"
    for path in (skill_md, skill_dir / "state.md", skill_dir / "build-meta.yaml", adapter):
        if not path.is_file():
            errors.append(f"{slug}: missing artifact {path}")
    if errors:
        return errors
    meta = read_mapping(skill_dir / "build-meta.yaml")
    for field in CORE_META_FIELDS:
        if meta.get(field) in (None, "", []):
            errors.append(f"{slug}: build-meta missing {field}")
    if meta.get("generated_by") != "character-persona":
        errors.append(f"{slug}: generated_by must be character-persona")
    if meta.get("character_slug") != slug or meta.get("character_display_name") != display_name:
        errors.append(f"{slug}: build-meta mapping differs from build-report")
    if not isinstance(meta.get("input_sources"), list) or not all(
        isinstance(source, str) and source.strip() for source in meta.get("input_sources", [])
    ):
        errors.append(f"{slug}: input_sources must list actual source paths")
    adapter_ref = meta.get("adapter_path")
    if isinstance(adapter_ref, str):
        candidates = [LAYOUT["work_dir"] / adapter_ref, LAYOUT["skills_home"] / adapter_ref]
        if not any(path.resolve() == adapter.resolve() for path in candidates):
            errors.append(f"{slug}: adapter_path does not match the selected layout")
    else:
        errors.append(f"{slug}: adapter_path must be a path string")
    skill_text = skill_md.read_text()
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\n|$)", skill_text, re.S)
    frontmatter = yaml.safe_load(match.group(1)) if match else None
    if not isinstance(frontmatter, dict) or frontmatter.get("name") != slug:
        errors.append(f"{slug}: SKILL frontmatter name does not match directory")
    elif "version" in meta and frontmatter.get("version") != meta["version"]:
        errors.append(f"{slug}: SKILL and build-meta versions differ")
    sections = {
        line[3:].split("<!--")[0].strip()
        for line in skill_text.splitlines() if line.startswith("## ")
    }
    if missing := required_sections - sections:
        errors.append(f"{slug}: missing required sections {sorted(missing)}")
    if extra := sections - allowed_sections:
        errors.append(f"{slug}: sections absent from template {sorted(extra)}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline_dir", type=Path)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH)
    args = parser.parse_args()
    errors = []
    try:
        LAYOUT.update(resolve_layout(args.pipeline_dir))
        required, allowed = parse_template_sections(args.template)
        report = parse_build_report(args.pipeline_dir)
        if report is None:
            raise ValueError(f"missing build-report under {LAYOUT['skills_home']}")
        if not report["built"]:
            errors.append("build-report contains no built roles")
        seen_names, seen_slugs = set(), set()
        for name, slug, _ in report["built"]:
            if not name or "/" in name or "\\" in name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                errors.append(f"invalid built role mapping: {name!r} -> {slug!r}")
                continue
            if name in seen_names or slug in seen_slugs:
                errors.append(f"duplicate built role mapping: {name} -> {slug}")
                continue
            seen_names.add(name)
            seen_slugs.add(slug)
            errors.extend(check_skill(args.pipeline_dir, slug, name, required, allowed))
        for name, reason in report["unbuilt"]:
            if not name or not reason:
                errors.append("unbuilt row needs name and skip_reason")
            if name in seen_names:
                errors.append(f"role appears in both built and unbuilt: {name}")
        # 开工设计可能不存在。只检查实际构建角色所引用的原型，不扩大构建集。
        if LAYOUT["phase2"].exists():
            phase2 = read_mapping(LAYOUT["phase2"])
            selected = {
                key: value for key, value in phase2.items()
                if isinstance(value, dict) and value.get("name") in seen_names
            }
            ledger = read_mapping(LAYOUT["ledger"]) if LAYOUT["ledger"].exists() else {}
            errors.extend(item["message"] for item in verify_canon_archetype(selected, ledger))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    if errors:
        print("verify_phase2_assets FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"verify_phase2_assets PASSED (built={len(report['built'])}; structure only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
