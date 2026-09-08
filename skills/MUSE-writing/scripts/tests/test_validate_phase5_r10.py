from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_phase5_r10 import verify_inspiration_refs  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "validate_phase5_r10.py"


def _ledger_card(ins_id, type_, status, project_encoding=None):
    return {
        "id": ins_id,
        "type": type_,
        "status": status,
        "project_encoding": project_encoding or [],
    }


def test_inspiration_refs_valid_passes():
    """有效引用 + 双向一致 -> 不报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
    ledger = {"inspirations": [
        _ledger_card("INS-001", "pattern", "bound", project_encoding=[
            {"phase": 5, "scene_id": "S07", "adoption_kind": "scene_carrier"}
        ])
    ]}
    findings = verify_inspiration_refs(p5, ledger)
    assert findings == []


def test_inspiration_refs_missing_in_ledger_reports():
    """引用 INS-* 在 ledger 找不到 -> 报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-999"]}]}
    ledger = {"inspirations": []}
    findings = verify_inspiration_refs(p5, ledger)
    assert any("ledger_id_missing" in f["code"] for f in findings)


def test_inspiration_refs_wrong_type_reports():
    """引用 INS-* type=archetype（不是 pattern）-> 报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-A01"]}]}
    ledger = {"inspirations": [_ledger_card("INS-A01", "archetype", "bound")]}
    findings = verify_inspiration_refs(p5, ledger)
    assert any("type" in f["code"] for f in findings)


def test_inspiration_refs_status_candidate_reports():
    """引用 INS-* status=candidate -> 报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
    ledger = {"inspirations": [_ledger_card("INS-001", "pattern", "candidate")]}
    findings = verify_inspiration_refs(p5, ledger)
    assert any("status" in f["code"] for f in findings)


def test_inspiration_refs_bidirectional_no_match_reports():
    """ledger.project_encoding[] 中找不到对应 phase=5 / scene_id 的项 -> 报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
    ledger = {"inspirations": [
        _ledger_card("INS-001", "pattern", "bound", project_encoding=[
            {"phase": 5, "scene_id": "S99", "adoption_kind": "scene_carrier"}
        ])
    ]}
    findings = verify_inspiration_refs(p5, ledger)
    assert any("bidirectional" in f["code"] or "project_encoding" in f["code"] for f in findings)


def test_inspiration_refs_invalid_adoption_kind_reports():
    """ledger.project_encoding[] 的 adoption_kind 不在 enum 内 -> 报错。"""
    p5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
    ledger = {"inspirations": [
        _ledger_card("INS-001", "pattern", "bound", project_encoding=[
            {"phase": 5, "scene_id": "S07", "adoption_kind": "weird_kind"}
        ])
    ]}
    findings = verify_inspiration_refs(p5, ledger)
    assert any("adoption_kind" in f["code"] for f in findings)


def test_inspiration_refs_field_absent_passes():
    """字段不存在 / 空数组 -> 不报错。"""
    p5 = {"scenes": [
        {"scene_id": "S08", "inspiration_refs": []},
        {"scene_id": "S09"},
    ]}
    ledger = {}
    findings = verify_inspiration_refs(p5, ledger)
    assert findings == []


def test_cli_scan_inspiration_refs_returns_nonzero_when_bidirectional_missing():
    """CLI：phase5 inspiration_refs 引用 INS-* 但 ledger.project_encoding 不匹配 -> 非 0。"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        phase5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
        ledger = {"inspirations": [_ledger_card(
            "INS-001", "pattern", "bound",
            project_encoding=[{"phase": 5, "scene_id": "S99", "adoption_kind": "scene_carrier"}],
        )]}
        phase5_path = tmp / "phase5_scenes.yaml"
        ledger_path = tmp / "inspiration_ledger.yaml"
        phase5_path.write_text(yaml.safe_dump(phase5), encoding="utf-8")
        ledger_path.write_text(yaml.safe_dump(ledger), encoding="utf-8")
        result = subprocess.run(
            ["python3", str(SCRIPT), str(phase5_path), "--scan-inspiration-refs"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "inspiration_refs_bidirectional_missing" in result.stderr


def test_cli_scan_inspiration_refs_ledger_absent_returns_zero():
    """CLI：ledger 文件不存在 -> graceful skip 返回 0。"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        phase5 = {"scenes": [{"scene_id": "S07", "inspiration_refs": ["INS-001"]}]}
        phase5_path = tmp / "phase5_scenes.yaml"
        phase5_path.write_text(yaml.safe_dump(phase5), encoding="utf-8")
        result = subprocess.run(
            ["python3", str(SCRIPT), str(phase5_path), "--scan-inspiration-refs"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


def test_hook_passes_scan_inspiration_refs_flag():
    """hook 协议：post-phase5-yaml.py 必须传 --scan-inspiration-refs。"""
    hook_path = Path(__file__).resolve().parents[2] / "hooks" / "post-phase5-yaml.py"
    content = hook_path.read_text(encoding="utf-8")
    assert "--scan-inspiration-refs" in content
