"""Tests for tool handler implementations."""
import pytest
from pathlib import Path
from open_muse.tools.skill_tools import make_load_skill_handler, make_load_reference_handler
from open_muse.tools.deliverable_tools import make_write_deliverable_handler, make_read_deliverable_handler
from open_muse.skills.loader import discover_skills
from open_muse.deliverables.storage import DeliverableStore


@pytest.fixture
def skill_dir(tmp_path):
    d = tmp_path / "skills" / "phase0-story-conception"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: phase0-story-conception\ndescription: test\n---\n## Instructions\nDo stuff", encoding="utf-8")
    ref_dir = d / "references"
    ref_dir.mkdir()
    (ref_dir / "mckee.md").write_text("McKee says...", encoding="utf-8")
    return tmp_path / "skills"


def test_load_skill(skill_dir):
    skills = discover_skills(skill_dir)
    handler = make_load_skill_handler(skills)
    result = handler({"name": "phase0-story-conception"})
    assert "## Instructions" in result
    assert "Do stuff" in result


def test_load_skill_not_found(skill_dir):
    skills = discover_skills(skill_dir)
    handler = make_load_skill_handler(skills)
    result = handler({"name": "nonexistent"})
    assert "not found" in result.lower()


def test_load_reference(skill_dir):
    handler = make_load_reference_handler(skill_dir)
    result = handler({"skill": "phase0-story-conception", "path": "mckee.md"})
    assert "McKee says" in result


def test_load_reference_path_traversal(skill_dir):
    handler = make_load_reference_handler(skill_dir)
    result = handler({"skill": "phase0-story-conception", "path": "../../etc/passwd"})
    assert "traversal" in result.lower() or "error" in result.lower()


def test_write_and_read_deliverable(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    write_handler = make_write_deliverable_handler(store)
    read_handler = make_read_deliverable_handler(store)

    write_handler({"name": "phase0_story_conception", "content": "premise: test story\ncontrolling_idea: justice", "format": "yaml"})
    result = read_handler({"name": "phase0_story_conception"})
    assert "test story" in result
