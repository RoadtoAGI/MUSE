import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "revision_quality.py"


def _lint(text: str, hits: list[dict], *, declared_hash: str | None = None) -> dict:
    return {
        "input_text_sha256": declared_hash or hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "hits": hits,
    }


def test_text_shape_counts_chars_sentences_and_paragraphs():
    import revision_quality as quality

    text = "甲。乙！\n\n丙？"

    assert quality.count_text_shape(text) == {
        "chars": len(text),
        "sentences": 3,
        "paragraphs": 2,
    }


def test_distribution_shrinkage_below_threshold_is_audit_only():
    import revision_quality as quality

    before = "甲" * 100
    after = "乙" * 84
    report = quality.build_revision_quality(
        before,
        after,
        _lint(before, [{"family": "f"}, {"family": "f"}]),
        _lint(after, [{"family": "f"}]),
        lane="distribution",
    )

    assert report["before"]["raw_hits"] == 2
    assert report["before"]["density_per_1k"] == 20.0
    assert report["after"]["raw_hits"] == 1
    assert report["after"]["density_per_1k"] == pytest.approx(11.9048)
    assert report["delta"] == {
        "chars": -16,
        "sentences": 0,
        "paragraphs": 0,
        "raw_hits": -1,
        "density_per_1k": pytest.approx(-8.0952),
    }
    assert report["retention"]["chars"] == 0.84
    assert report["provenance"]["state"] == "fresh"
    assert report["audit_only"] is True
    assert "verdict" not in report
    assert "exit_code" not in report

    assert len(report["observations"]) == 1
    observation = report["observations"][0]
    assert observation["kind"] == "retention_below_threshold"
    assert observation["level"] == "OBSERVE"
    assert observation["audit_only"] is True
    assert observation["blocking"] is False
    assert observation["value"] == 0.84
    assert observation["threshold"] == 0.85


@pytest.mark.parametrize("lane", ["distribution", "manuscript"])
def test_exactly_point_eight_five_does_not_trigger(lane):
    import revision_quality as quality

    before = "甲" * 100
    after = "乙" * 85

    report = quality.build_revision_quality(
        before,
        after,
        _lint(before, []),
        _lint(after, []),
        lane=lane,
    )

    assert report["retention"]["chars"] == 0.85
    assert report["observations"] == []


def test_value_just_below_threshold_triggers_even_if_display_rounds_to_point_eight_five():
    import revision_quality as quality

    before = "甲" * 100_000
    after = "乙" * 84_999

    report = quality.build_revision_quality(
        before,
        after,
        _lint(before, []),
        _lint(after, []),
        lane="distribution",
    )

    assert report["retention"]["chars"] == 0.85
    assert len(report["observations"]) == 1


def test_scene_lane_never_emits_shrinkage_observation():
    import revision_quality as quality

    before = "甲" * 100
    after = "乙" * 10

    report = quality.build_revision_quality(
        before,
        after,
        _lint(before, []),
        _lint(after, []),
        lane="scene",
    )

    assert report["retention"]["chars"] == 0.1
    assert report["observations"] == []


def test_provenance_reports_stale_and_missing_without_hiding_metrics():
    import revision_quality as quality

    before = "甲" * 100
    after = "乙" * 84
    stale_hash = hashlib.sha256(b"old").hexdigest()

    stale = quality.build_revision_quality(
        before,
        after,
        _lint(before, []),
        _lint(after, [{"family": "f"}], declared_hash=stale_hash),
        lane="manuscript",
    )
    assert stale["provenance"]["state"] == "stale"
    assert stale["provenance"]["after"]["state"] == "stale"
    assert stale["after"]["raw_hits"] == 1

    missing = quality.build_revision_quality(
        before,
        after,
        _lint(before, []),
        {"hits": []},
        lane="manuscript",
    )
    assert missing["provenance"]["state"] == "missing"
    assert missing["provenance"]["after"]["state"] == "missing"


def test_attaching_audit_observations_preserves_verdict_and_exit_code():
    import revision_quality as quality

    base = {"verdict": "FAIL", "exit_code": 1, "triggers": ["hard_gate"]}
    observation = {
        "kind": "retention_below_threshold",
        "level": "OBSERVE",
        "audit_only": True,
        "blocking": False,
    }

    attached = quality.attach_audit_observations(base, [observation])

    assert attached["verdict"] == "FAIL"
    assert attached["exit_code"] == 1
    assert attached["triggers"] == ["hard_gate"]
    assert attached["audit_observations"] == [observation]
    assert "audit_observations" not in base


def test_family_scene_low_dose_matrix_is_deterministic_and_audit_only():
    import revision_quality as quality

    scenes = {
        "S02": {
            "text": "乙" * 1000,
            "lint": _lint("乙" * 1000, [{"family": "f1"}, {"family": "f2"}]),
        },
        "S01": {
            "text": "甲" * 1000,
            "lint": _lint("甲" * 1000, [{"family": "f1"}]),
        },
    }

    matrix = quality.build_family_scene_low_dose_matrix(
        scenes,
        {"f2": 2.0, "f1": 2.0},
    )

    assert matrix["scene_ids"] == ["S01", "S02"]
    assert list(matrix["families"]) == ["f1", "f2"]
    assert matrix["provenance_state"] == "fresh"

    f1 = matrix["families"]["f1"]
    assert f1["cells"]["S01"]["raw_hits"] == 1
    assert f1["cells"]["S01"]["density_per_1k"] == 1.0
    assert f1["cells"]["S01"]["low_dose"] is True
    assert f1["candidate_uniform_low_dose"] is True
    assert f1["auditable"] is True
    assert f1["uniform_low_dose"] is True
    assert f1["observation"]["level"] == "OBSERVE"
    assert f1["observation"]["audit_only"] is True
    assert f1["observation"]["blocking"] is False

    f2 = matrix["families"]["f2"]
    assert f2["cells"]["S01"]["present"] is False
    assert f2["candidate_uniform_low_dose"] is False
    assert f2["uniform_low_dose"] is False
    assert f2["observation"] is None


def test_stale_scene_suppresses_uniform_low_dose_observation():
    import revision_quality as quality

    text = "甲" * 1000
    scenes = {
        "S01": {"text": text, "lint": _lint(text, [{"family": "f"}])},
        "S02": {
            "text": text,
            "lint": _lint(
                text,
                [{"family": "f"}],
                declared_hash=hashlib.sha256(b"stale").hexdigest(),
            ),
        },
    }

    matrix = quality.build_family_scene_low_dose_matrix(scenes, {"f": 2.0})

    family = matrix["families"]["f"]
    assert matrix["provenance_state"] == "stale"
    assert family["candidate_uniform_low_dose"] is True
    assert family["auditable"] is False
    assert family["uniform_low_dose"] is False
    assert family["observation"] is None


def test_snapshot_cli_is_immutable_and_audit_cli_never_blocks(tmp_path):
    source = tmp_path / "story.md"
    snapshot = tmp_path / "story.pre.md"
    source.write_text("甲。" * 100, encoding="utf-8")

    first = subprocess.run(
        [sys.executable, str(SCRIPT), "snapshot", "--source", str(source), "--out", str(snapshot)],
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    assert snapshot.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    source.write_text("乙。" * 80, encoding="utf-8")
    conflict = subprocess.run(
        [sys.executable, str(SCRIPT), "snapshot", "--source", str(source), "--out", str(snapshot)],
        capture_output=True,
        text=True,
    )
    assert conflict.returncode == 2
    assert snapshot.read_text(encoding="utf-8") == "甲。" * 100

    report_path = tmp_path / "quality.yaml"
    audit = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "audit",
            "--before-text",
            str(snapshot),
            "--after-text",
            str(source),
            "--lane",
            "manuscript",
            "--work-dir",
            str(tmp_path),
            "--lang",
            "zh",
            "--out",
            str(report_path),
        ],
        capture_output=True,
        text=True,
    )
    assert audit.returncode == 0, audit.stderr
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["retention"]["chars"] == 0.8
    assert report["observations"][0]["blocking"] is False
    assert report["protected_results"]["verdict"] == "PASS"


def test_manuscript_quality_report_carries_blocking_protected_result(tmp_path):
    from protected_integrity import (
        append_declaration_snapshot,
        append_relation_verifications,
        scene_sha256,
    )

    before = "甲没有下令。"
    after = "据说甲没有下令。"
    scene_dir = tmp_path / "pipeline" / "scenes"
    scene_dir.mkdir(parents=True)
    (scene_dir / "scene_S01.md").write_text(before, encoding="utf-8")
    (tmp_path / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump({
            "scenes": [{
                "scene_id": "S01",
                "file_path": "pipeline/scenes/scene_S01.md",
            }],
        }),
        encoding="utf-8",
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[{
            "relation_id": "R1",
            "patch_id": "patch_01",
            "type": "modality",
            "expected": "事实陈述保持确定",
            "before_quote": before,
        }],
        _register_application_batch=False,
    )
    append_relation_verifications(tmp_path, "S01", before, [{
        "relation_id": "R1",
        "patch_id": "patch_01",
        "preserved": True,
        "after_quote": before,
        "reason": "认识模态保持",
        "current_span": {"start": 0, "end": len(before)},
        "scene_sha": scene_sha256(before),
    }])
    before_path = tmp_path / "story.pre.md"
    after_path = tmp_path / "story.md"
    before_path.write_text(before + "\n", encoding="utf-8")
    after_path.write_text(after + "\n", encoding="utf-8")
    report_path = tmp_path / "pipeline" / "review" / "manuscript_quality.yaml"

    audit = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "audit",
            "--before-text",
            str(before_path),
            "--after-text",
            str(after_path),
            "--lane",
            "manuscript",
            "--work-dir",
            str(tmp_path),
            "--lang",
            "zh",
            "--out",
            str(report_path),
        ],
        capture_output=True,
        text=True,
    )

    assert audit.returncode == 2
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    assert report["audit_only"] is True
    assert report["protected_results"]["verdict"] == "FAIL"
    assert "manuscript_relation_span_overlap" in report["protected_results"]["reason"]


def test_reader_audit_binds_report_to_revision_input(tmp_path):
    import revision_quality as quality

    relative = "pipeline/review/snapshots/story.semantic.round1.md"
    snapshot = tmp_path / relative
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("原稿。", encoding="utf-8")
    story = tmp_path / "story.md"
    story.write_text("修订稿。", encoding="utf-8")
    reader = tmp_path / "pipeline/review/reader_review.yaml"
    reader.write_text(yaml.safe_dump({"input_snapshot": relative, "reader_findings": []}))
    out = tmp_path / "quality.yaml"
    args = ["audit", "--before-text", str(snapshot), "--after-text", str(story),
            "--lane", "manuscript", "--work-dir", str(tmp_path), "--lang", "zh",
            "--reader-report", str(reader), "--out", str(out)]
    assert quality.main(args) == 0
    report = yaml.safe_load(out.read_text())
    assert report["reader_review_sha256"] == hashlib.sha256(reader.read_bytes()).hexdigest()
    reader.write_text(yaml.safe_dump({"input_snapshot": "story.md", "reader_findings": []}))
    assert quality.main(args) == 2
