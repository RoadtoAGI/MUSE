"""Tests for Phase Pipeline."""
import pytest
from pathlib import Path
from open_muse.pipeline.runner import PhasePipeline, PhaseResult


@pytest.fixture
def skills_dir(tmp_path):
    """Create minimal skills for testing pipeline sequencing."""
    for i, (name, tools, deliverables) in enumerate([
        ("phase0-story-conception", "load_skill write_deliverable", "premise"),
        ("phase1-world-building", "load_skill read_deliverable write_deliverable", "world_setting"),
    ]):
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Phase {i}\ncontext: inline\n"
            f"allowed-tools: {tools}\nrequired-deliverables: {deliverables}\n---\n"
            f"Do phase {i} work.",
            encoding="utf-8"
        )
    return tmp_path / "skills"


def test_pipeline_loads_phases(skills_dir, tmp_path):
    pipeline = PhasePipeline(skills_dir=skills_dir, output_dir=tmp_path / "output")
    assert len(pipeline.phases) == 2
    assert pipeline.phases[0].name == "phase0-story-conception"


def test_pipeline_phase_order(skills_dir, tmp_path):
    pipeline = PhasePipeline(skills_dir=skills_dir, output_dir=tmp_path / "output")
    names = [p.name for p in pipeline.phases]
    assert names == ["phase0-story-conception", "phase1-world-building"]


def test_pipeline_get_stage():
    assert PhasePipeline.get_stage("phase0-story-conception") == "design"
    assert PhasePipeline.get_stage("phase5-scene-arrangement") == "design"
    assert PhasePipeline.get_stage("phase6-scene-development") == "generation"
    assert PhasePipeline.get_stage("phase7-integration-revision") == "revision"
