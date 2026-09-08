"""Protect consumed fields and real anchors while permitting unfinished planning."""
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from consumer_contract import load_chapter_anchors, validate_milestones, validate_tentpoles
import serial_lint


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def workspace(root):
    put(root, "series/volumes/V01.yaml", dict(volume_id="V01", tentpoles=[], chapters=[
        dict(chapter_id="C0001", status="published"),
        dict(chapter_id="C0002", status="drafted"),
        dict(chapter_id="C0003", status="outline"),
    ]))
    put(root, "series/volumes/V02.yaml", dict(volume_id="V02", chapters=[dict(chapter_id="C0004", status="outline")]))
    put(root, "published/manifest.yaml", dict(entries=[dict(chapter_id="C0001", file="V01C0001.md", published_seq=1)]))
    (root / "published/V01C0001.md").write_text("第1章\n值班员接过钥匙。", encoding="utf-8")
    put(root, "chapters/V01/C0002/chapter_card.yaml", dict(chapter_id="C0002", scene_plan=dict(scenes=["S01", "S02"])))
    return load_chapter_anchors(root)


def milestone(**changes):
    return dict(at="C0001", kind="关系变化", before="陌生", after="互相信任", evidence="她递来钥匙。", **changes)


def test_required_fields_reject_aliases_that_render_as_empty(tmp_path):
    anchors = workspace(tmp_path)
    old_row = dict(at="C0001", type="关系变化", change="信任加深", evidence="她递来钥匙。")
    errors = validate_milestones([old_row], anchors)
    assert any("kind, before, after" in message for message in errors)
    assert validate_milestones([milestone()], anchors) == []
    errors = validate_tentpoles([dict(description="拿到钥匙", value_shift="受阻到获准", anchor="C0001")], anchors, "V01")
    assert any("beat" in message for message in errors)


def test_anchor_resolution_uses_published_source_or_actual_card(tmp_path):
    anchors = workspace(tmp_path)
    # Imported history has no scene index; its chapter source remains usable.
    for at in ("C0001", "C0001S03", "C0002S02"):
        row = milestone()
        row["at"] = at
        assert validate_milestones([row], anchors) == []
    for at in ("C9999", "C0003", "C0002S09", "第1章"):
        row = milestone()
        row["at"] = at
        assert validate_milestones([row], anchors), at
    (tmp_path / "published/V01C0001.md").unlink()
    assert validate_milestones([milestone()], load_chapter_anchors(tmp_path))


def test_tentpole_planning_and_empty_collections_are_valid(tmp_path):
    anchors = workspace(tmp_path)
    row = dict(beat="交接钥匙", value_shift="拒绝到接纳", anchor="unresolved")
    assert validate_tentpoles([row], anchors, "V01") == []
    for rows in (None, []):
        assert validate_milestones(rows, anchors) == []
        assert validate_tentpoles(rows, anchors, "V01") == []
    # An existing workspace with no character directory does not acquire a new requirement.
    assert serial_lint.check_consumer_fields(tmp_path) == ([], [])


@pytest.mark.parametrize("anchor", ["C0003", "C0004", "C9999", "C0002S01"])
def test_concrete_tentpole_anchor_must_be_real_and_in_volume(tmp_path, anchor):
    anchors = workspace(tmp_path)
    row = dict(beat="交接钥匙", value_shift="拒绝到接纳", anchor=anchor)
    assert validate_tentpoles([row], anchors, "V01")
    row["anchor"] = "C0002"
    assert validate_tentpoles([row], anchors, "V01") == []


@pytest.mark.parametrize("rows", ["变化", {"at": "C0001"}, ["变化"]])
def test_wrong_record_shape_fails_clearly(tmp_path, rows):
    anchors = workspace(tmp_path)
    assert validate_milestones(rows, anchors)
    assert validate_tentpoles(rows, anchors, "V01")


def test_custom_milestone_kind_remains_warning_only(tmp_path):
    workspace(tmp_path)
    row = milestone()
    row["kind"] = "信赖建立"
    put(tmp_path, "series/ledgers/characters/keeper/biography.yaml", dict(milestones=[row]))
    put(tmp_path, "series/genre_profile.yaml", dict(substrate="generic", engine=dict(primary="人际信任")))
    failures, _ = serial_lint.check_consumer_fields(tmp_path)
    assert not failures
    failures, warnings = serial_lint.check_genre_profile(tmp_path)
    assert not failures
    assert any("信赖建立" in warning for warning in warnings)
    row["kind"] = ["关系变化"]
    put(tmp_path, "series/ledgers/characters/keeper/biography.yaml", dict(milestones=[row]))
    assert serial_lint.check_consumer_fields(tmp_path)[0]
    # The earlier vocabulary check must leave invalid types for the format failure.
    assert not serial_lint.check_genre_profile(tmp_path)[0]


def test_existing_lint_entry_rejects_bad_consumed_fields(tmp_path):
    workspace(tmp_path)
    row = milestone()
    del row["before"]
    bio = put(tmp_path, "series/ledgers/characters/keeper/biography.yaml", dict(milestones=[row]))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "serial_lint.py"), "--work-dir", str(tmp_path),
         "--check", "consumer-fields", "--file", str(bio)], capture_output=True, text=True,
    )
    assert result.returncode == 2, result.stderr
    payload = yaml.safe_load(result.stdout)
    assert payload["status"] == "FAIL"
    assert payload["failures"][0]["check"] == "consumer-fields"
    assert "before" in payload["failures"][0]["message"]
    assert "consumer-fields" in serial_lint.parse_checks(["all"])
