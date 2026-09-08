"""Tests for SKILL.md parsing and discovery."""
import pytest
from pathlib import Path
from open_muse.skills.loader import SkillDef, parse_skill_file, discover_skills


SAMPLE_SKILL = """\
---
name: phase0-story-conception
description: >
  故事构想阶段：从用户需求提取前提、主控思想、核心价值。
context: inline
allowed-tools: load_skill read_deliverable write_deliverable
required-deliverables: premise, controlling_idea, core_value
---

## 任务指令
1. 分析用户需求
2. 提取前提
"""


def test_parse_skill_basic(tmp_path):
    skill_dir = tmp_path / "phase0-story-conception"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE_SKILL, encoding="utf-8")

    skill = parse_skill_file(skill_dir / "SKILL.md")

    assert skill is not None
    assert skill.name == "phase0-story-conception"
    assert "故事构想" in skill.description
    assert skill.context == "inline"
    assert skill.allowed_tools == ["load_skill", "read_deliverable", "write_deliverable"]
    assert skill.required_deliverables == ["premise", "controlling_idea", "core_value"]
    assert "分析用户需求" in skill.prompt


def test_parse_skill_fork_context(tmp_path):
    content = """\
---
name: actors
description: 角色隔离表演
context: fork
allowed-tools: write_dialogue write_action
required-deliverables: dialogue
---
表演指令
"""
    skill_dir = tmp_path / "actors"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    skill = parse_skill_file(skill_dir / "SKILL.md")
    assert skill.context == "fork"
    assert skill.allowed_tools == ["write_dialogue", "write_action"]


def test_parse_skill_no_frontmatter(tmp_path):
    (tmp_path / "SKILL.md").write_text("No frontmatter here")
    assert parse_skill_file(tmp_path / "SKILL.md") is None


def test_discover_skills(tmp_path):
    for name in ["phase0-story-conception", "phase1-world-building"]:
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\nPrompt", encoding="utf-8")

    skills = discover_skills(tmp_path)
    assert len(skills) == 2
    assert {s.name for s in skills} == {"phase0-story-conception", "phase1-world-building"}


def test_discover_skills_skips_invalid(tmp_path):
    d = tmp_path / "valid-skill"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: valid-skill\ndescription: ok\n---\nPrompt", encoding="utf-8")
    d2 = tmp_path / "broken"
    d2.mkdir()
    (d2 / "SKILL.md").write_text("no frontmatter")

    skills = discover_skills(tmp_path)
    assert len(skills) == 1
