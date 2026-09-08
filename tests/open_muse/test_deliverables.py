"""Tests for deliverable storage and validation."""
import pytest
import yaml
from pathlib import Path
from open_muse.deliverables.storage import DeliverableStore
from open_muse.deliverables.validator import validate_deliverable


def test_write_and_read_yaml(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    data = {"premise": "A story about...", "controlling_idea": "Justice prevails"}
    store.write("phase0_story_conception", data, fmt="yaml")
    result = store.read("phase0_story_conception")
    assert result["premise"] == "A story about..."
    assert (tmp_path / "pipeline" / "phase0_story_conception.yaml").exists()


def test_write_and_read_markdown(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    store.write("scenes/scene_01", "# Scene 1\nThe rain fell...", fmt="md")
    result = store.read("scenes/scene_01")
    assert "The rain fell" in result
    assert (tmp_path / "pipeline" / "scenes" / "scene_01.md").exists()


def test_read_nonexistent(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    assert store.read("nonexistent") is None


def test_list_deliverables(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    store.write("phase0_story_conception", {"a": 1}, fmt="yaml")
    store.write("phase1_world_building", {"b": 2}, fmt="yaml")
    available = store.list_available()
    assert "phase0_story_conception" in available
    assert "phase1_world_building" in available


def test_validate_success():
    data = {"premise": "x", "controlling_idea": "y", "core_value": "z"}
    errors = validate_deliverable(data, required_fields=["premise", "controlling_idea", "core_value"])
    assert errors == []


def test_validate_missing_fields():
    data = {"premise": "x"}
    errors = validate_deliverable(data, required_fields=["premise", "controlling_idea", "core_value"])
    assert len(errors) == 2
    assert "controlling_idea" in errors[0]


def test_validate_empty_field():
    data = {"premise": "", "controlling_idea": "y", "core_value": "z"}
    errors = validate_deliverable(data, required_fields=["premise", "controlling_idea", "core_value"])
    assert len(errors) == 1
    assert "premise" in errors[0]


def test_path_traversal_rejected(tmp_path):
    store = DeliverableStore(output_dir=tmp_path)
    with pytest.raises(ValueError, match="traversal"):
        store.write("../../etc/passwd", "evil", fmt="md")
