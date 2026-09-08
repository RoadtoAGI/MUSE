"""Skill loading: parse SKILL.md files with YAML frontmatter."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SkillDef:
    """Parsed skill definition from a SKILL.md file."""
    name: str
    description: str
    prompt: str
    file_path: str
    context: str = "inline"
    allowed_tools: list[str] = field(default_factory=list)
    required_deliverables: list[str] = field(default_factory=list)


def _parse_list_field(value: str) -> list[str]:
    """Parse list field: supports comma-separated, space-separated, or YAML-like [a, b, c]."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    # If commas present, split by comma; otherwise split by whitespace
    if "," in value:
        items = value.split(",")
    else:
        items = value.split()
    return [item.strip().strip('"').strip("'") for item in items if item.strip()]


def parse_skill_file(path: Path) -> Optional[SkillDef]:
    """Parse a SKILL.md file with --- frontmatter into a SkillDef."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_raw = parts[1].strip()
    prompt = parts[2].strip()

    fields: dict[str, str] = {}
    current_key: Optional[str] = None
    current_val_lines: list[str] = []

    for line in frontmatter_raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped and not stripped.startswith("-"):
            if current_key is not None:
                fields[current_key] = " ".join(current_val_lines).strip()
            key, _, val = stripped.partition(":")
            current_key = key.strip().lower()
            current_val_lines = [val.strip()] if val.strip() else []
        elif current_key is not None:
            current_val_lines.append(stripped)

    if current_key is not None:
        fields[current_key] = " ".join(current_val_lines).strip()

    name = fields.get("name", "")
    if not name:
        return None

    context = fields.get("context", "inline").lower()
    if context not in ("inline", "fork"):
        context = "inline"

    tools_raw = fields.get("allowed-tools", "")
    req_raw = fields.get("required-deliverables", "")

    return SkillDef(
        name=name,
        description=fields.get("description", ""),
        prompt=prompt,
        file_path=str(path),
        context=context,
        allowed_tools=_parse_list_field(tools_raw) if tools_raw else [],
        required_deliverables=_parse_list_field(req_raw) if req_raw else [],
    )


def discover_skills(skills_dir: Path) -> list[SkillDef]:
    """Discover all valid SKILL.md files under a directory."""
    skills = []
    if not skills_dir.is_dir():
        return skills

    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if skill_file.exists():
            skill = parse_skill_file(skill_file)
            if skill is not None:
                skills.append(skill)

    return skills
