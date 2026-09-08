# src/open_muse/tools/skill_tools.py
"""Tool handlers for skill loading."""
from __future__ import annotations

from pathlib import Path
from open_muse.skills.loader import SkillDef


def make_load_skill_handler(skills: list[SkillDef]):
    """Factory: returns a load_skill handler bound to discovered skills."""
    skill_map = {s.name: s for s in skills}

    def handler(params: dict) -> str:
        name = params.get("name", "")
        skill = skill_map.get(name)
        if skill is None:
            available = ", ".join(skill_map.keys())
            return f"Skill '{name}' not found. Available: {available}"
        return skill.prompt

    return handler


def make_load_reference_handler(skills_dir: Path):
    """Factory: returns a load_reference handler bound to skills directory."""
    root = Path(skills_dir).resolve()

    def handler(params: dict) -> str:
        skill_name = params.get("skill", "")
        ref_path = params.get("path", "")
        ref_base = (root / skill_name / "references").resolve()
        full_path = (ref_base / ref_path).resolve()
        # Path traversal guard: must stay within this skill's references/
        if not str(full_path).startswith(str(ref_base)):
            return f"Error: path traversal rejected: {ref_path}"
        if not full_path.exists():
            return f"Reference not found: {skill_name}/references/{ref_path}"
        return full_path.read_text(encoding="utf-8")

    return handler
