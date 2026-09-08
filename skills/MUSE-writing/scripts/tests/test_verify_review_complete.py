"""verify_review_complete.py 单测——§1.5 完整性 gate。"""
from __future__ import annotations
import subprocess
import sys
import hashlib
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parent.parent / "verify_review_complete.py"
sys.path.insert(0, str(_SCRIPT.parent))


def _run(work_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(work_dir)],
        capture_output=True,
        text=True,
    )


def _scaffold(tmp_path: Path, scene_ids: list[str]) -> Path:
    """构造最小可用 work_dir：pipeline/phase6_development.yaml + pipeline/ 子目录。"""
    work = tmp_path / "work"
    (work / "pipeline" / "review").mkdir(parents=True)
    (work / "pipeline" / "audit").mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "review" / "lint").mkdir(parents=True)
    dev = {"scenes": [{"scene_id": sid, "file_path": f"pipeline/scenes/scene_{sid}.md"} for sid in scene_ids]}
    (work / "pipeline" / "phase6_development.yaml").write_text(yaml.safe_dump(dev), encoding="utf-8")
    (work / "pipeline" / "run_state.yaml").write_text(
        yaml.safe_dump({"run_intent": "release"}), encoding="utf-8"
    )
    for sid in scene_ids:
        text = f"正文 {sid}"
        (work / "pipeline" / "scenes" / f"scene_{sid}.md").write_text(text, encoding="utf-8")
        (work / "pipeline" / "review" / "lint" / f"{sid}.ai_filler.yaml").write_text(
            yaml.safe_dump({
                "scene_id": sid,
                "language": "zh",
                "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "cluster_alerts": [],
                "hits": [],
            }),
            encoding="utf-8",
        )
    return work


def _write_review(work: Path, scene_id: str, verdict: str) -> None:
    (work / "pipeline" / "review" / f"scene_{scene_id}.yaml").write_text(
        yaml.safe_dump({"verdict": verdict, "findings": []}),
        encoding="utf-8",
    )


def _write_ledger(work: Path, scene_id: str) -> None:
    (work / "pipeline" / "review" / f"scene_{scene_id}.lint_resolution_ledger.yaml").write_text(
        yaml.safe_dump({"v1_triage": [], "post_revision_updates": {}}),
        encoding="utf-8",
    )


def _write_verified_applied_patch(
    work: Path,
    scene_id: str,
    post_review: dict,
) -> None:
    from protected_integrity import (
        snapshot_patch_documents,
        verify_post_revision_review,
    )

    scene_text = (
        work / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    ).read_text(encoding="utf-8")
    directive = {
        "source": "scene_review",
        "scene_id": scene_id,
        "application_id": f"{scene_id}-test-round1",
        "patches": [{
            "patch_id": "patch_01",
            "patch_kind": None,
            "anchor_quote": scene_text,
        }],
    }
    snapshot_patch_documents(work, [(scene_id, directive)])
    applied = work / "pipeline" / f"scene_{scene_id}" / "patch_directive.applied.yaml"
    applied.parent.mkdir(parents=True, exist_ok=True)
    applied.write_text(
        yaml.safe_dump(directive, allow_unicode=True),
        encoding="utf-8",
    )
    post_path = work / "pipeline" / "review" / f"scene_{scene_id}.post_revision.yaml"
    post_path.write_text(
        yaml.safe_dump(post_review, allow_unicode=True),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(work, scene_id)
    assert rc == 0, report


# ---------- 放行 case ----------

def test_complete_review_passes(tmp_path):
    """§1.5 全部跑完 → exit 0。"""
    work = _scaffold(tmp_path, ["S01", "S02", "S03"])
    for sid in ["S01", "S02", "S03"]:
        _write_review(work, sid, "PASS")
    result = _run(work)
    assert result.returncode == 0


def test_phase6_not_run_fails_closed(tmp_path):
    """admission 被调用但 phase6 缺失时 fail-closed。"""
    work = tmp_path / "work"
    work.mkdir()
    result = _run(work)
    assert result.returncode == 2


def test_patch_verdict_with_applied_and_post_revision_passes(tmp_path):
    """PATCH verdict + applied + post_revision PASS → exit 0。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    _write_verified_applied_patch(work, "S01", {"verdict": "PASS"})
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 0


# ---------- 阻断 case ----------

def test_missing_review_blocks(tmp_path):
    """scene_*.yaml 缺失 → exit 2。"""
    work = _scaffold(tmp_path, ["S01", "S02"])
    _write_review(work, "S01", "PASS")
    # S02 没产
    result = _run(work)
    assert result.returncode == 2
    assert "S02" in result.stderr


def test_invalid_verdict_blocks(tmp_path):
    """verdict 不在合法集 → exit 2。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "UNKNOWN")
    result = _run(work)
    assert result.returncode == 2
    assert "UNKNOWN" in result.stderr


def test_escalated_input_gate_blocks(tmp_path):
    """ESCALATED + written_by=orchestrator_input_gate → exit 2。"""
    work = _scaffold(tmp_path, ["S01"])
    (work / "pipeline" / "review" / "scene_S01.yaml").write_text(
        yaml.safe_dump({
            "verdict": "ESCALATED",
            "review_incomplete": True,
            "written_by": "orchestrator_input_gate",
            "missing_inputs": ["scene_card.yaml"],
        }),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2
    assert "ESCALATED 未闭合" in result.stderr


def test_escalated_review_incomplete_blocks(tmp_path):
    """ESCALATED + review_incomplete=true → exit 2 即使 written_by 不同。"""
    work = _scaffold(tmp_path, ["S01"])
    (work / "pipeline" / "review" / "scene_S01.yaml").write_text(
        yaml.safe_dump({
            "verdict": "ESCALATED",
            "review_incomplete": True,
            "written_by": "scene_reviewer",
        }),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2


def test_patch_without_applied_blocks(tmp_path):
    """PATCH verdict 但 patch_directive.applied.yaml 缺失 → exit 2。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    _write_ledger(work, "S01")
    # 没创建 applied.yaml
    result = _run(work)
    assert result.returncode == 2
    assert "patch_directive.applied" in result.stderr


def test_patch_with_applied_but_no_post_revision_blocks(tmp_path):
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    (work / "pipeline" / "scene_S01" / "patch_directive.applied.yaml").parent.mkdir(parents=True)
    (work / "pipeline" / "scene_S01" / "patch_directive.applied.yaml").write_text(
        "source: scene_review\n",
        encoding="utf-8",
    )
    _write_ledger(work, "S01")
    # 没 post_revision.yaml
    result = _run(work)
    assert result.returncode == 2
    assert "post_revision" in result.stderr


def test_patch_complete_with_post_revision_pass(tmp_path):
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    _write_verified_applied_patch(work, "S01", {"verdict": "PASS"})
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 0


def test_post_revision_pass_cannot_bypass_protected_relation_verification(tmp_path):
    """伪造 PASS 不能绕过 relation active-anchor 复验。"""
    from protected_integrity import append_declaration_snapshot

    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "patch_directive.applied.yaml").write_text(
        "source: scene_review\n",
        encoding="utf-8",
    )
    (work / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS"}), encoding="utf-8"
    )
    _write_ledger(work, "S01")
    append_declaration_snapshot(
        work,
        "S01",
        "post_revision_round1",
        tokens=[],
        relations=[{
            "relation_id": "R1",
            "patch_id": "patch_01",
            "type": "agency",
            "expected": "说话者仍是同一人",
            "before_quote": "正文 S01",
        }],
    )
    result = _run(work)

    assert result.returncode == 2
    assert "protected_integrity" in result.stderr


def test_verified_protected_relation_allows_admission(tmp_path):
    """reviewer evidence 经脚本落 active anchor 后可进入 Phase 7。"""
    from protected_integrity import (
        scene_sha256,
        snapshot_patch_documents,
        verify_post_revision_review,
    )

    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "revision_summary.md").write_text(
        "# Revision Summary: S01\n\n**status**: complete\n",
        encoding="utf-8",
    )
    _write_ledger(work, "S01")
    scene_text = (work / "pipeline" / "scenes" / "scene_S01.md").read_text(
        encoding="utf-8"
    )
    directive = {
        "source": "scene_review",
        "scene_id": "S01",
        "application_id": "post_revision_round1",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": scene_text,
            "protected_relations": [{
                "relation_id": "R1",
                "patch_id": "patch_01",
                "type": "agency",
                "expected": "说话者仍是同一人",
                "before_quote": scene_text,
            }],
        }],
    }
    snapshot_patch_documents(work, [("S01", directive)])
    (scene_dir / "patch_directive.applied.yaml").write_text(
        yaml.safe_dump(directive, allow_unicode=True),
        encoding="utf-8",
    )
    (work / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [{
                    "relation_id": "R1",
                    "patch_id": "patch_01",
                    "preserved": True,
                    "after_quote": scene_text,
                    "reason": "说话者身份保持不变",
                    "current_span": {"start": 0, "end": len(scene_text)},
                    "scene_sha": scene_sha256(scene_text),
                }],
            },
        }),
        encoding="utf-8",
    )
    rc, protected_report = verify_post_revision_review(work, "S01")
    assert rc == 0, protected_report.get("reason", protected_report)

    result = _run(work)

    assert result.returncode == 0


def test_pass_verdict_cannot_bypass_a_pending_protected_application(tmp_path):
    from protected_integrity import snapshot_patch_documents

    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PASS")
    scene_text = (
        work / "pipeline" / "scenes" / "scene_S01.md"
    ).read_text(encoding="utf-8")
    snapshot_patch_documents(work, [("S01", {
        "scene_id": "S01",
        "application_id": "emergency-round1",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": scene_text,
        }],
    })])

    result = _run(work)

    assert result.returncode == 2
    assert "protected_integrity" in result.stderr


def test_post_revision_ai_pattern_gate_pass_override_passes(tmp_path):
    """machine_gate=fail 但 override.applied=true 应通过。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    _write_verified_applied_patch(work, "S01", {
        "verdict": "PASS",
        "ai_pattern_gate": {
            "machine_gate": "fail",
            "reviewer_gate": "override",
            "override": {"applied": True, "override_reason": "narrative_design"},
        },
    })
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 0


def test_post_revision_ai_pattern_gate_no_override_machine_fail_blocks(tmp_path):
    """machine_gate=fail 但 override.applied=false -> 阻断。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    (work / "pipeline" / "scene_S01" / "patch_directive.applied.yaml").parent.mkdir(parents=True, exist_ok=True)
    (work / "pipeline" / "scene_S01" / "patch_directive.applied.yaml").write_text(
        "source: scene_review\n",
        encoding="utf-8",
    )
    (work / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(yaml.safe_dump({
        "verdict": "PASS",
        "ai_pattern_gate": {
            "machine_gate": "fail",
            "override": {"applied": False},
        },
    }), encoding="utf-8")
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 2
    assert "ai_pattern_gate" in result.stderr or "override" in result.stderr


def test_current_patch_run_does_not_require_legacy_lint_resolution_ledger(tmp_path):
    """当前 machine-ledger 通道不要求退役的 reviewer lint ledger。"""
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "PATCH")
    _write_verified_applied_patch(work, "S01", {"verdict": "PASS"})
    result = _run(work)
    assert result.returncode == 0, result.stderr


def test_rollback_without_post_revision_blocks(tmp_path):
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "ROLLBACK")
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 2
    assert "ROLLBACK" in result.stderr or "post_revision" in result.stderr


def test_rewrite_with_post_revision_pass(tmp_path):
    work = _scaffold(tmp_path, ["S01"])
    _write_review(work, "S01", "REWRITE")
    (work / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS"}), encoding="utf-8"
    )
    _write_ledger(work, "S01")
    result = _run(work)
    assert result.returncode == 0


def test_real_pipeline_layout_missing_review_blocks(tmp_path):
    """真实 pipeline 布局 + 缺 review/scene_*.yaml → exit 2（防 fail-open）。"""
    work = _scaffold(tmp_path, ["S01", "S02"])
    # 故意不产 review/scene_*.yaml
    result = _run(work)
    assert result.returncode == 2
    assert "S01" in result.stderr or "S02" in result.stderr


def test_dev_yaml_at_root_no_longer_recognized(tmp_path):
    """phase6_development.yaml 在错误位置时 fail-closed。"""
    work = tmp_path / "work"
    work.mkdir()
    # 写到错误位置
    (work / "phase6_development.yaml").write_text(
        yaml.safe_dump({"scenes": [{"id": "S01"}]}),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2


def test_legacy_id_field_still_supported(tmp_path):
    """兼容旧 scaffold / 旧产物中 scenes[].id 字段。"""
    work = tmp_path / "work"
    (work / "pipeline" / "review").mkdir(parents=True)
    (work / "pipeline" / "audit").mkdir(parents=True)
    (work / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump({"scenes": [{"id": "S01", "file_path": "pipeline/scenes/scene_S01.md"}]}),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2
    assert "S01" in result.stderr


# ---------- escape hatch case ----------

def test_valid_human_skip_passes_phase7_but_is_release_fatal(tmp_path):
    """封闭 enum 的人工 skip 可进 Phase7，release_candidate=false。"""
    work = _scaffold(tmp_path, ["S01"])
    # 故意缺 review
    skip = work / "pipeline" / "audit" / "skip_review.yaml"
    skip.write_text(
        yaml.safe_dump({"skipped_checks": ["scene_review"]}),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 0
    state = yaml.safe_load(
        (work / "pipeline" / "audit" / "release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert state["admission"]["release_candidate"] is False


def test_empty_reason_escape_hatch_blocks(tmp_path):
    """reason 空洞（"skip"）→ exit 2。"""
    work = _scaffold(tmp_path, ["S01"])
    skip = work / "pipeline" / "audit" / "skip_review.yaml"
    skip.write_text(
        yaml.safe_dump({"reason": "skip", "risk_acknowledged": True}),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2


def test_no_ack_escape_hatch_blocks(tmp_path):
    """risk_acknowledged=false → exit 2。"""
    work = _scaffold(tmp_path, ["S01"])
    skip = work / "pipeline" / "audit" / "skip_review.yaml"
    skip.write_text(
        yaml.safe_dump({"reason": "evaluation_time_window", "risk_acknowledged": False}),
        encoding="utf-8",
    )
    result = _run(work)
    assert result.returncode == 2


# ---------- 边界 case ----------

def test_missing_work_dir_does_not_break(tmp_path):
    """work_dir 不存在 → fail-closed + warn。"""
    result = _run(tmp_path / "nonexistent")
    assert result.returncode == 2
    assert "WARN" in result.stderr


def test_no_arg_does_not_break(tmp_path):
    """无参数 → fail-closed + warn。"""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "WARN" in result.stderr
