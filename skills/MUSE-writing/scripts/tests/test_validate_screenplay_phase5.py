from pathlib import Path

import yaml

from validate_screenplay_phase5 import validate


def _sequence(refs=None):
    sequence = {
        "seq_id": "SEQ01",
        "act": 1,
        "scene": 1,
        "location": "INT. 书房 - 夜",
        "time": "当晚",
        "characters_in_scene": ["甲"],
        "dramatic_purpose": "迫使甲作出选择",
        "arc_position": "rising",
    }
    if refs is not None:
        sequence["inspiration_refs"] = refs
    return sequence


def _write_yaml(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def test_sequence_without_refs_does_not_require_ledger(tmp_path):
    sequence_path = _write_yaml(
        tmp_path / "pipeline/screenplay/sequence_list.yaml",
        {"sequences": [_sequence()]},
    )
    assert validate(sequence_path) == []


def test_referenceable_ledger_ids_pass(tmp_path):
    sequence_path = _write_yaml(
        tmp_path / "pipeline/screenplay/sequence_list.yaml",
        {"sequences": [_sequence(["INS-001", "INS-A01"])]},
    )
    _write_yaml(
        tmp_path / "pipeline/inspiration_ledger.yaml",
        {"inspirations": [
            {"id": "INS-001", "status": "accepted"},
            {"id": "INS-A01", "status": "bound"},
        ]},
    )
    assert validate(sequence_path) == []


def test_refs_require_existing_ledger_and_ids(tmp_path):
    sequence_path = _write_yaml(
        tmp_path / "pipeline/screenplay/sequence_list.yaml",
        {"sequences": [_sequence(["INS-404"])]},
    )
    errors = validate(sequence_path)
    assert any("ledger.yaml 不存在" in error for error in errors)

    _write_yaml(tmp_path / "pipeline/inspiration_ledger.yaml", {"inspirations": []})
    errors = validate(sequence_path)
    assert any("INS-404 在 ledger 中不存在" in error for error in errors)


def test_refs_reject_non_referenceable_status_and_invalid_shape(tmp_path):
    sequence_path = _write_yaml(
        tmp_path / "pipeline/screenplay/sequence_list.yaml",
        {"sequences": [_sequence(["INS-001"]), _sequence("INS-002")]},
    )
    _write_yaml(
        tmp_path / "pipeline/inspiration_ledger.yaml",
        {"inspirations": [{"id": "INS-001", "status": "candidate"}]},
    )
    errors = validate(sequence_path)
    assert any("status='candidate'" in error for error in errors)
    assert any("inspiration_refs 须为列表" in error for error in errors)


def test_stage_scene_allows_empty_cast_and_optional_structural_labels(tmp_path):
    sequence = _sequence()
    sequence.pop("act")
    sequence.pop("scene")
    sequence.pop("arc_position")
    sequence.update(location="空台", characters_in_scene=[])
    path = _write_yaml(tmp_path / "pipeline/screenplay/sequence_list.yaml", {"sequences": [sequence]})
    assert validate(path) == []


def test_malformed_scene_fields_return_errors_without_crashing(tmp_path):
    sequence = _sequence()
    sequence.update(seq_id=["bad"], characters_in_scene="甲", act=False)
    path = _write_yaml(tmp_path / "pipeline/screenplay/sequence_list.yaml", {"sequences": [sequence]})
    errors = validate(path)
    assert any("seq_id" in error for error in errors)
    assert any("characters_in_scene" in error for error in errors)
    assert any("act" in error for error in errors)
    sequence.update(seq_id="../outside", act=1)
    _write_yaml(path, {"sequences": [sequence]})
    assert any("文件键" in error for error in validate(path))
