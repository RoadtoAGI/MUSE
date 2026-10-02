from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_phase5_r10 import verify_commitments, verify_inspiration_refs  # noqa: E402


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


def _p5_with_commitments(commitments):
    return {
        "sequence_expansions": [{"seq_id": "Q1", "scenes": [{"scene_id": "S01"}, {"scene_id": "S02"}]}],
        "commitments": commitments,
    }


def test_commitments_absent_or_valid_passes():
    """缺字段合法；每项恰有 payoff_in 或 deliberate_omission 且场景存在 -> 不报错。"""
    assert verify_commitments({"scenes": [{"scene_id": "S01"}]}) == []
    p5 = _p5_with_commitments([
        {"name": "只剩一术", "kind": "device", "introduced_in": "S01", "payoff_in": "S02"},
        {"name": "玄照", "kind": "character_line", "introduced_in": "S01",
         "deliberate_omission": "离场后由转述交代去向"},
    ])
    assert verify_commitments(p5) == []


def test_commitments_structure_errors_reported():
    """kind 非法、场景不存在、payoff 与 omission 同填或皆空 -> 逐项报错。"""
    p5 = _p5_with_commitments([
        {"name": "A", "kind": "prop", "introduced_in": "S01", "payoff_in": "S02"},
        {"name": "B", "kind": "motif", "introduced_in": "S09", "payoff_in": "S02"},
        {"name": "C", "kind": "question", "introduced_in": "S01",
         "payoff_in": "S02", "deliberate_omission": "x"},
        {"name": "D", "kind": "question", "introduced_in": "S01"},
        {"kind": "device", "introduced_in": "S01", "payoff_in": "S07"},
    ])
    errors = verify_commitments(p5)
    joined = "\n".join(errors)
    assert "A: kind" in joined
    assert "B: introduced_in 指向不存在的场景 S09" in joined
    assert "C: payoff_in 与 deliberate_omission 须恰填一项" in joined
    assert "D: payoff_in 与 deliberate_omission 须恰填一项" in joined
    assert "name 缺失" in joined and "指向不存在的场景 S07" in joined


def test_cli_reports_commitments_without_flags(tmp_path):
    """CLI 无需额外 flag 即检查 commitments 结构。"""
    p5 = _p5_with_commitments([{"name": "A", "kind": "device", "introduced_in": "S01"}])
    path = tmp_path / "phase5_scenes.yaml"
    path.write_text(yaml.safe_dump(p5, allow_unicode=True), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "恰填一项" in result.stderr


def test_commitments_require_resolvable_scene_set_and_string_kind():
    """场景集合为空时报错而非静默通过；顶层空 scenes 不遮蔽序列形态；kind 非字符串按枚举错误报。"""
    empty = {"scenes": [], "commitments": [{"name": "线索", "kind": "device", "introduced_in": "S01", "payoff_in": "S99"}]}
    errors = verify_commitments(empty)
    assert errors and "场景集合为空或不可解析" in errors[0]

    both = {
        "scenes": [],
        "sequence_expansions": [{"seq_id": "Q1", "scenes": [{"scene_id": "S01"}, {"scene_id": "S02"}]}],
        "commitments": [{"name": "线索", "kind": "device", "introduced_in": "S01", "payoff_in": "S02"}],
    }
    assert verify_commitments(both) == []

    listed_kind = _p5_with_commitments([{"name": "A", "kind": ["device"], "introduced_in": "S01", "payoff_in": "S02"}])
    errors = verify_commitments(listed_kind)
    assert any("A: kind" in e for e in errors)

