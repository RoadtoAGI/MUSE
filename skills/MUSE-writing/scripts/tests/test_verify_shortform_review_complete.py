"""verify_shortform_review_complete.py — 短链终验 gate 五断言测试。

wholetext 闸门本体的判定逻辑归 test_cluster_alert_trigger 等既有测试；本文件对
逻辑断言模拟闸门 PASS；旧报告须重跑，匹配当前正文的报告可直接复用。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_shortform_review_complete as gate  # noqa: E402

TINY_STORY = "溪水从石缝里流过。阿禾蹲在岸边把手放进水里。水很凉，她没有缩回去。\n"


class _FakeGateResult:
    def __init__(self, rc: int):
        self.returncode = rc
        self.stdout = "FAIL fake" if rc else "PASS fake"
        self.stderr = ""


def _force_gate(monkeypatch, rc: int) -> None:
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: _FakeGateResult(rc))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_run(tmp_path: Path, *, requirements=None) -> Path:
    work = tmp_path / "run"
    (work / "pipeline" / "shortform" / "review").mkdir(parents=True)
    (work / "story.md").write_text(TINY_STORY, encoding="utf-8")
    conception = {
        "premise": "x", "core_value": "y", "genre": "z", "target_length": 3000,
    }
    if requirements:
        conception["requirements"] = requirements
    (work / "pipeline" / "shortform" / "conception.yaml").write_text(
        yaml.safe_dump(conception, allow_unicode=True), encoding="utf-8")
    return work


def _write_report(work: Path, rn: int, *, status="PASS", findings=None,
                  coverage=None, sha=None) -> Path:
    report = {
        "story_sha256": sha if sha is not None else _sha(work / "story.md"),
        "status": status,
        "findings": findings or [],
    }
    if coverage is not None:
        report["requirements_coverage"] = coverage
    p = work / "pipeline" / "shortform" / "review" / f"short_story_review.r{rn}.yaml"
    p.write_text(yaml.safe_dump(report, allow_unicode=True), encoding="utf-8")
    return p


def test_all_green_passes(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path, requirements=["至少一段对话", "结尾开放"])
    _write_report(work, 1, coverage=[
        {"requirement": "至少一段对话", "met": True, "evidence": "第二段"},
        {"requirement": "结尾开放", "met": True, "evidence": "末句"},
    ])
    assert gate.run_gate(work) == 0


def test_missing_story_fails(tmp_path):
    work = _build_run(tmp_path)
    (work / "story.md").unlink()
    assert gate.run_gate(work) == 1


def test_stale_hash_fails(tmp_path, monkeypatch):
    """修订后未复审：报告 hash 对不上当前正文 → fail。"""
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1)
    (work / "story.md").write_text(TINY_STORY + "修订后追加了一段。\n", encoding="utf-8")
    assert gate.run_gate(work) == 1


def test_blocker_fails(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1, findings=[
        {"severity": "BLOCKER", "dimension": "价值转变", "quote": "x", "note": "y"},
    ])
    assert gate.run_gate(work) == 1


def test_status_revise_fails(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1, status="REVISE", findings=[
        {"severity": "MAJOR", "dimension": "人物声音", "quote": "x", "note": "y"},
    ])
    assert gate.run_gate(work) == 1


def test_latest_rn_wins(tmp_path, monkeypatch):
    """r1 REVISE + r2 PASS → 取最新轮次判定。"""
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1, status="REVISE")
    _write_report(work, 2)
    assert gate.run_gate(work) == 0


def test_requirements_missing_item_fails(tmp_path, monkeypatch):
    """一一对应（R3 F2）：coverage 缺项静默漏核 → fail。"""
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path, requirements=["至少一段对话", "结尾开放"])
    _write_report(work, 1, coverage=[
        {"requirement": "至少一段对话", "met": True, "evidence": "第二段"},
    ])
    assert gate.run_gate(work) == 1


def test_requirements_extra_item_fails(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path, requirements=["至少一段对话"])
    _write_report(work, 1, coverage=[
        {"requirement": "至少一段对话", "met": True, "evidence": "第二段"},
        {"requirement": "编造的要求", "met": True, "evidence": "无"},
    ])
    assert gate.run_gate(work) == 1


def test_requirements_empty_evidence_fails(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path, requirements=["至少一段对话"])
    _write_report(work, 1, coverage=[
        {"requirement": "至少一段对话", "met": True, "evidence": ""},
    ])
    assert gate.run_gate(work) == 1


def test_no_requirements_no_coverage_needed(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1)
    assert gate.run_gate(work) == 0


def test_wholetext_rerun_fail_blocks(tmp_path, monkeypatch):
    """终验当场重跑 wholetext（R3 F1）：本次退出码 1 → 终验 fail。"""
    _force_gate(monkeypatch, 1)
    work = _build_run(tmp_path)
    _write_report(work, 1)
    assert gate.run_gate(work) == 1


def test_stale_disk_pass_is_refreshed_to_current_surface_review(tmp_path):
    work = _build_run(tmp_path)
    (work / "story.md").write_text(
        "门槛上卧着一条黑狗。它听见脚步便抬起头。\n", encoding="utf-8")
    _write_report(work, 1)
    review_dir = work / "pipeline" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "wholetext_gate.yaml").write_text(
        "verdict: PASS\ntriggers: []\n", encoding="utf-8")
    assert gate.run_gate(work) == 0
    fresh = yaml.safe_load((review_dir / "wholetext_gate.yaml").read_text(encoding="utf-8"))
    assert fresh["verdict"] == "REVIEW"
    assert fresh["semantic_review"] == "not_run"
    # An actual semantic finding still blocks the same surface candidate text.
    _write_report(work, 1, status="REVISE", findings=[{
        "severity": "MAJOR", "dimension": "人物声音", "quote": "它听见脚步便抬起头。",
        "note": "本例假设独立语义审阅确认当前正文与有效人物视角冲突",
    }])
    assert gate.run_gate(work) == 1


# ---------- 报告 schema 正向校验（畸形结构不得静默绕过 BLOCKER 断言） ----------

def _write_raw_report(work: Path, rn: int, content: dict) -> None:
    p = work / "pipeline" / "shortform" / "review" / f"short_story_review.r{rn}.yaml"
    p.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")


def test_scalar_findings_rejected(tmp_path, monkeypatch):
    """findings 是字符串（如 'BLOCKER: 结局悬空'）→ schema fail，不得放行。"""
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_raw_report(work, 1, {
        "story_sha256": _sha(work / "story.md"),
        "status": "PASS",
        "findings": "BLOCKER: 结局悬空",
    })
    assert gate.run_gate(work) == 1


def test_severity_enum_drift_rejected(tmp_path, monkeypatch):
    """severity 带空格漂移（'BLOCKER '）→ 枚举精确匹配 fail。"""
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_raw_report(work, 1, {
        "story_sha256": _sha(work / "story.md"),
        "status": "PASS",
        "findings": [{"severity": "BLOCKER ", "dimension": "价值转变",
                      "quote": "x", "note": "y"}],
    })
    assert gate.run_gate(work) == 1


def test_unknown_top_level_field_rejected(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_raw_report(work, 1, {
        "story_sha256": _sha(work / "story.md"),
        "status": "PASS",
        "findings": [],
        "verdict": "SHIP_IT",
    })
    assert gate.run_gate(work) == 1


def test_finding_missing_keys_rejected(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_raw_report(work, 1, {
        "story_sha256": _sha(work / "story.md"),
        "status": "PASS",
        "findings": [{"severity": "MINOR"}],
    })
    assert gate.run_gate(work) == 1


def test_illegal_dimension_rejected(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_raw_report(work, 1, {
        "story_sha256": _sha(work / "story.md"),
        "status": "PASS",
        "findings": [{"severity": "MINOR", "dimension": "INS 落点",
                      "quote": "x", "note": "y"}],
    })
    assert gate.run_gate(work) == 1


@pytest.mark.parametrize("verdict, expected", [("PASS", 0), ("FAIL", 1)])
def test_current_wholetext_result_reused(tmp_path, monkeypatch, verdict, expected):
    work = _build_run(tmp_path)
    _write_report(work, 1)
    path = work / "pipeline" / "review" / "wholetext_gate.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"verdict": verdict, "input_story_sha256": _sha(work / "story.md")}))
    def unexpected_run(*args, **kwargs):
        raise AssertionError("unchanged story should reuse current wholetext report")
    monkeypatch.setattr(gate.subprocess, "run", unexpected_run)
    assert gate.run_gate(work) == expected


@pytest.mark.parametrize("content", [None, "[]", "requirements: broken"])
def test_invalid_conception_is_input_error(tmp_path, monkeypatch, content):
    work = _build_run(tmp_path)
    _write_report(work, 1)
    path = work / "pipeline" / "shortform" / "conception.yaml"
    if content is None:
        path.unlink()
    else:
        path.write_text(content)
    def unexpected_run(*args, **kwargs):
        raise AssertionError("invalid required input should be reported before text checks")
    monkeypatch.setattr(gate.subprocess, "run", unexpected_run)
    assert gate.run_gate(work) == 2


def test_narrative_organization_is_a_supported_review_dimension(tmp_path, monkeypatch):
    _force_gate(monkeypatch, 0)
    work = _build_run(tmp_path)
    _write_report(work, 1, findings=[{
        "severity": "MINOR", "dimension": "叙事组织", "quote": "溪水从石缝里流过。", "note": "局部转场可再打磨",
    }])
    assert gate.run_gate(work) == 0
