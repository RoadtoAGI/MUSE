from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scaffold(tmp_path: Path, *, review: bool = True, intent: str | None = "release") -> Path:
    wd = tmp_path / "run"
    review_dir = wd / "pipeline" / "review"
    lint_dir = review_dir / "lint"
    scenes_dir = wd / "pipeline" / "scenes"
    audit_dir = wd / "pipeline" / "audit"
    lint_dir.mkdir(parents=True)
    scenes_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)
    text = (
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架。" * 20
    )
    (scenes_dir / "scene_S01.md").write_text(text, encoding="utf-8")
    (wd / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump({"scenes": [{"scene_id": "S01", "file_path": "pipeline/scenes/scene_S01.md"}]}),
        encoding="utf-8",
    )
    if intent is not None:
        (wd / "pipeline" / "run_state.yaml").write_text(
            yaml.safe_dump({"run_intent": intent}), encoding="utf-8"
        )
    if review:
        (review_dir / "scene_S01.yaml").write_text(
            yaml.safe_dump({"scene_id": "S01", "verdict": "PASS"}), encoding="utf-8"
        )
    (lint_dir / "S01.ai_filler.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "input_text_sha256": _sha(text),
            "cluster_alerts": [],
            "hits": [],
        }),
        encoding="utf-8",
    )
    return wd


def _set_machine_entries(wd: Path, statuses: list[tuple[str, str]]) -> None:
    review = wd / "pipeline" / "review"
    text = (wd / "pipeline" / "scenes" / "scene_S01.md").read_text(encoding="utf-8")
    lint = {
        "scene_id": "S01",
        "input_text_sha256": _sha(text),
        "cluster_alerts": [{
            "alert_id": "S01-dummy_pronoun-1",
            "family": "dummy_pronoun",
            "severity": "medium",
            "hit_ids": [entry_id for entry_id, _ in statuses],
            "hits": len(statuses),
        }],
        "hits": [{
            "lint_id": entry_id,
            "family": "dummy_pronoun",
            "rule": "dummy_pronoun",
        } for entry_id, _ in statuses],
    }
    lint_path = review / "lint" / "S01.ai_filler.yaml"
    lint_path.write_text(yaml.safe_dump(lint), encoding="utf-8")
    artifact_sha = hashlib.sha256(lint_path.read_bytes()).hexdigest()
    revision = {
        "artifact": "pipeline/review/lint/S01.ai_filler.yaml",
        "artifact_sha256": artifact_sha,
        "input_text_sha256": _sha(text),
    }
    entries = []
    ledger_entries = []
    for entry_id, status in statuses:
        exempted = [entry_id] if status == "objection_granted" else []
        remaining = [] if exempted else [entry_id]
        base = {
            "id": entry_id,
            "family": "dummy_pronoun",
            "level": "M",
            "status": status,
            "all_hit_ids": [entry_id],
            "exempted_hit_ids": exempted,
            "remaining_hit_ids": remaining,
        }
        entries.append(base)
        ledger_entries.append({
            **base,
            "hit_resolutions": [{"hit_id": entry_id, "status": status}],
        })
    (review / "S01.machine_directive.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "active_revision_id": artifact_sha,
            "lint_revision": revision,
            "stage": "refreshed",
            "entries": entries,
        }),
        encoding="utf-8",
    )
    (review / "S01.machine_ledger.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "active_revision_id": artifact_sha,
            "lint_revision": revision,
            "entries": ledger_entries,
        }),
        encoding="utf-8",
    )


def _admission(wd: Path) -> dict:
    state = yaml.safe_load(
        (wd / "pipeline" / "audit" / "release_eligibility.yaml").read_text(encoding="utf-8")
    )
    return state["admission"]


def test_clean_release_admission_is_release_candidate(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    assert verify.check(wd) == 0
    admission = _admission(wd)
    assert admission["phase7_admitted"] is True
    assert admission["release_candidate"] is True
    assert admission["scenes"][0]["scene_path"] == "pipeline/scenes/scene_S01.md"
    assert admission["input_fingerprints"] == sorted(
        admission["input_fingerprints"], key=lambda item: item["path"]
    )
    assert {
        item["path"] for item in admission["input_fingerprints"]
    } >= {
        "pipeline/phase6_development.yaml",
        "pipeline/run_state.yaml",
        "pipeline/audit/skip_review.yaml",
        "pipeline/phase5_scenes.yaml",
        "pipeline/scenes/scene_S01.md",
        "pipeline/review/scene_S01.yaml",
        "pipeline/review/scene_S01.post_revision.yaml",
        "pipeline/scene_S01/patch_directive.yaml",
        "pipeline/scene_S01/patch_directive.applied.yaml",
        "pipeline/scene_S01/revision_summary.md",
        "pipeline/review/scene_S01.lint_resolution_ledger.yaml",
        "pipeline/review/lint/S01.ai_filler.yaml",
        "pipeline/review/lint/S01.ai_filler.v2.yaml",
        "pipeline/review/S01.machine_directive.yaml",
        "pipeline/review/S01.machine_ledger.yaml",
        "pipeline/review/S01.protected_integrity.post_revision.yaml",
    }
    assert admission["scenes"][0]["machine"]["closed"] is True


def test_missing_run_intent_and_malformed_lint_fail_closed(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path, intent=None)
    assert verify.check(wd) == 2
    assert "run_intent" in " ".join(_admission(wd)["reasons"])

    wd = _scaffold(tmp_path / "malformed")
    (wd / "pipeline" / "review" / "lint" / "S01.ai_filler.yaml").write_text("hits: [")
    assert verify.check(wd) == 2
    machine = _admission(wd)["scenes"][0]["machine"]
    assert machine["closed"] is False
    assert machine["entry_states"] == ["unknown"]


def test_observe_rule_high_hit_does_not_require_human_resolution_ledger(
    tmp_path,
    monkeypatch,
):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    lint_path = wd / "pipeline" / "review" / "lint" / "S01.ai_filler.yaml"
    lint = yaml.safe_load(lint_path.read_text(encoding="utf-8"))
    lint["hits"] = [{
        "lint_id": "observe-1",
        "family": "action_log",
        "rule": "observed_subtype",
        "severity": "high",
    }]
    lint_path.write_text(yaml.safe_dump(lint), encoding="utf-8")
    assert verify.check(wd) == 0


def test_machine_reducer_preserves_mixed_closed_modes_and_blocks_pending(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    _set_machine_entries(wd, [("h1", "resolved"), ("h2", "objection_granted")])
    assert verify.check(wd) == 0
    machine = _admission(wd)["scenes"][0]["machine"]
    assert machine["closed"] is True
    assert machine["closure_modes"] == ["objection_granted", "resolved"]

    _set_machine_entries(wd, [("h1", "objection_granted"), ("h2", "pending")])
    assert verify.check(wd) == 2
    assert _admission(wd)["scenes"][0]["machine"]["closed"] is False

    _set_machine_entries(wd, [("h1", "escalated")])
    assert verify.check(wd) == 2


def test_empty_hit_partition_cannot_close_an_enforced_alert(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    _set_machine_entries(wd, [])
    review = wd / "pipeline" / "review"
    directive_path = review / "S01.machine_directive.yaml"
    ledger_path = review / "S01.machine_ledger.yaml"
    directive = yaml.safe_load(directive_path.read_text(encoding="utf-8"))
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    empty_entry = {
        "id": "S01-action_log-1",
        "family": "action_log",
        "level": "M",
        "status": "resolved",
        "all_hit_ids": [],
        "exempted_hit_ids": [],
        "remaining_hit_ids": [],
    }
    directive["entries"] = [empty_entry]
    ledger["entries"] = [{**empty_entry, "hit_resolutions": []}]
    directive_path.write_text(yaml.safe_dump(directive), encoding="utf-8")
    ledger_path.write_text(yaml.safe_dump(ledger), encoding="utf-8")

    assert verify.check(wd) == 2
    machine = _admission(wd)["scenes"][0]["machine"]
    assert machine["entry_states"] == ["unknown"]
    assert "hit" in machine["reason"]


def test_human_skip_is_closed_enum_release_fatal_and_never_skips_machine(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path, review=False)
    skip = wd / "pipeline" / "audit" / "skip_review.yaml"
    skip.write_text(yaml.safe_dump({"skipped_checks": ["scene_review"]}), encoding="utf-8")
    assert verify.check(wd) == 0
    admission = _admission(wd)
    assert admission["phase7_admitted"] is True
    assert admission["release_candidate"] is False

    _set_machine_entries(wd, [("h1", "pending")])
    assert verify.check(wd) == 2

    skip.write_text(yaml.safe_dump({"skipped_checks": ["machine_channel"]}), encoding="utf-8")
    assert verify.check(wd) == 2
    assert any("skipped_checks" in reason for reason in _admission(wd)["reasons"])


def test_new_admission_clears_released_terminal(tmp_path):
    import release_eligibility as rel
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    rel.atomic_write_state(wd, {
        "admission": {"old": True},
        "terminal": {"outcome": "released", "release_eligible": True},
    })
    assert verify.check(wd) == 0
    assert "terminal" not in rel.load_state(wd)


def test_applied_patch_without_protected_proof_cannot_enter_admission(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    review = wd / "pipeline" / "review"
    (review / "scene_S01.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "PATCH"}), encoding="utf-8"
    )
    detail = wd / "pipeline" / "scene_S01"
    detail.mkdir(parents=True)
    (detail / "patch_directive.applied.yaml").write_text(
        yaml.safe_dump({"source": "scene_review", "patches": []}), encoding="utf-8"
    )
    (review / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "PASS"}), encoding="utf-8"
    )
    (review / "scene_S01.lint_resolution_ledger.yaml").write_text(
        yaml.safe_dump({"v1_triage": [], "post_revision_updates": {}}), encoding="utf-8"
    )

    assert verify.check(wd) == 2
    failures = _admission(wd)["scenes"][0]["human"]["failures"]
    assert any(
        "protected_integrity_sidecar_missing_for_applied_patch" in item["reason"]
        for item in failures
    )


def test_forged_pass_proof_cannot_close_pending_application_batch(tmp_path):
    import verify_review_complete as verify
    from protected_integrity import append_declaration_snapshot, load_scene_integrity

    wd = _scaffold(tmp_path)
    review = wd / "pipeline" / "review"
    detail = wd / "pipeline" / "scene_S01"
    detail.mkdir(parents=True)
    (review / "scene_S01.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "PATCH"}), encoding="utf-8"
    )
    (detail / "patch_directive.applied.yaml").write_text(
        yaml.safe_dump({"source": "scene_review", "patches": []}), encoding="utf-8"
    )
    (review / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "PASS"}), encoding="utf-8"
    )
    (review / "scene_S01.lint_resolution_ledger.yaml").write_text(
        yaml.safe_dump({"v1_triage": [], "post_revision_updates": {}}), encoding="utf-8"
    )
    scene_text = (wd / "pipeline" / "scenes" / "scene_S01.md").read_text(
        encoding="utf-8"
    )
    append_declaration_snapshot(
        wd,
        "S01",
        "forged_round",
        tokens=[],
        relations=[{
            "relation_id": "R-forged",
            "patch_id": "patch-forged",
            "type": "causality",
            "expected": "因果保持",
            "before_quote": scene_text,
        }],
    )
    state = load_scene_integrity(wd, "S01")
    (review / "S01.protected_integrity.post_revision.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "verdict": "PASS",
            "scene_sha": _sha(scene_text),
            "verified_batch_ids": [state["application_batches"][0]["batch_id"]],
            "review_path": str(review / "scene_S01.post_revision.yaml"),
            "token_verifications": [],
            "relation_verifications": [],
        }),
        encoding="utf-8",
    )

    assert verify.check(wd) == 2
    failures = _admission(wd)["scenes"][0]["human"]["failures"]
    assert any(
        "proof_batch_not_verified" in item["reason"]
        for item in failures
    )


def test_phase6_scene_index_is_strict_and_fail_closed(tmp_path):
    import verify_review_complete as verify

    cases = [
        {"scenes": ["S01"]},
        {"scenes": [{"scene_id": "", "file_path": "pipeline/scenes/scene_.md"}]},
        {"scenes": [{
            "scene_id": "S01",
            "file_path": "pipeline/scenes/wrong.md",
        }]},
        {"scenes": [
            {"scene_id": "S01", "file_path": "pipeline/scenes/scene_S01.md"},
            {"id": "S01", "file_path": "pipeline/scenes/scene_S01.md"},
        ]},
        {"scenes": [{
            "scene_id": "S02",
            "file_path": "pipeline/scenes/scene_S02.md",
        }]},
    ]
    for index, payload in enumerate(cases):
        wd = _scaffold(tmp_path / str(index))
        (wd / "pipeline" / "phase6_development.yaml").write_text(
            yaml.safe_dump(payload), encoding="utf-8"
        )
        assert verify.check(wd) == 2
        assert any(
            "phase6_development" in reason
            for reason in _admission(wd)["reasons"]
        )


def test_assembler_uses_strict_scene_index_and_missing_scene_is_fatal(tmp_path):
    wd = _scaffold(tmp_path)
    (wd / "pipeline" / "scenes" / "scene_S01.md").unlink()

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "assemble_story.py"), str(wd)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert not (wd / "story.md").exists()


def _admit_and_write_story(wd: Path) -> None:
    import verify_review_complete as verify

    assert verify.check(wd) == 0
    text = (wd / "pipeline" / "scenes" / "scene_S01.md").read_text(
        encoding="utf-8"
    )
    (wd / "story.md").write_text(text + "\n", encoding="utf-8")
    (wd / "pipeline" / "review" / "reader_review.yaml").write_text(
        yaml.safe_dump({"input_snapshot": "pipeline/review/snapshots/story.semantic.round1.md", "reader_findings": []}), encoding="utf-8"
    )
    snapshot_relative = "pipeline/review/snapshots/story.semantic.round1.md"
    snapshot = wd / snapshot_relative
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes((wd / "story.md").read_bytes())
    (wd / "pipeline" / "review" / "A_aesthetic.manuscript.yaml").write_text(
        yaml.safe_dump({
            "review_scope": "manuscript",
            "review_round": 1,
            "input_snapshot": snapshot_relative,
            "semantic_review": "clear",
            "coverage": {"planning_trace_leakage": "clear"},
            "review_findings": [],
            "summary": {"total_issues": 0, "by_dimension": {}},
        }),
        encoding="utf-8",
    )


def test_finalizer_rejects_scene_edit_after_admission(tmp_path):
    import release_eligibility as rel

    wd = _scaffold(tmp_path)
    _admit_and_write_story(wd)
    scene = wd / "pipeline" / "scenes" / "scene_S01.md"
    scene.write_text(scene.read_text(encoding="utf-8") + "后来又添一句。", encoding="utf-8")

    assert rel.finalize(wd) == 2
    assert rel.load_state(wd)["terminal"]["reason"] == "admission_inputs_changed"


def test_finalizer_rejects_phase6_index_edit_after_admission(tmp_path):
    import release_eligibility as rel

    wd = _scaffold(tmp_path)
    _admit_and_write_story(wd)
    index = wd / "pipeline" / "phase6_development.yaml"
    payload = yaml.safe_load(index.read_text(encoding="utf-8"))
    payload["late_note"] = "mutated after admission"
    index.write_text(yaml.safe_dump(payload), encoding="utf-8")

    assert rel.finalize(wd) == 2
    assert rel.load_state(wd)["terminal"]["reason"] == "admission_inputs_changed"


def test_finalizer_rejects_directive_or_ledger_addition_after_admission(tmp_path):
    import release_eligibility as rel

    cases = (
        ("pipeline/review/S01.machine_directive.yaml", {"late": True}),
        ("pipeline/review/S01.machine_ledger.yaml", {"late": True}),
        ("pipeline/scene_S01/patch_directive.yaml", {"patches": [{"id": "late"}]}),
    )
    for relative, payload in cases:
        wd = _scaffold(tmp_path / relative.replace("/", "_"))
        _admit_and_write_story(wd)
        path = wd / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")

        assert rel.finalize(wd) == 2
        assert rel.load_state(wd)["terminal"]["reason"] == "admission_inputs_changed"


def test_pending_patch_cannot_enter_admission(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    pending = wd / "pipeline" / "scene_S01" / "patch_directive.yaml"
    pending.parent.mkdir(parents=True)
    pending.write_text(yaml.safe_dump({"patches": [{"id": "p1"}]}), encoding="utf-8")

    assert verify.check(wd) == 2
    human = _admission(wd)["scenes"][0]["human"]
    assert human["closed"] is False
    assert any("pending_patch_unclosed" in item["reason"] for item in human["failures"])


def test_release_consumer_rejects_input_edit_after_terminal(tmp_path):
    import release_eligibility as rel

    wd = _scaffold(tmp_path)
    _admit_and_write_story(wd)
    assert rel.finalize(wd) == 0
    review = wd / "pipeline" / "review" / "scene_S01.yaml"
    review.write_text(review.read_text(encoding="utf-8") + "late: true\n", encoding="utf-8")

    assert rel.validate_release(wd) == (
        False,
        "admission_input_manifest_mismatch",
    )


def test_assembler_preserves_revised_story_and_accepts_identical_assembly(tmp_path):
    import assemble_story

    wd = _scaffold(tmp_path)
    assert assemble_story.assemble(wd) == 0
    story = wd / "story.md"
    original = story.read_bytes()
    assert assemble_story.assemble(wd) == 0
    assert story.read_bytes() == original
    revised = original + "全文修订增加的内容。".encode("utf-8")
    story.write_bytes(revised)
    assert assemble_story.assemble(wd) != 0
    assert story.read_bytes() == revised


def test_assembler_rejects_blank_scene_without_creating_story(tmp_path):
    import assemble_story

    wd = _scaffold(tmp_path)
    (wd / "pipeline/scenes/scene_S01.md").write_text(" \n\t", encoding="utf-8")
    assert assemble_story.assemble(wd) != 0
    assert not (wd / "story.md").exists()


def _use_current_lint(wd, text):
    from ai_filler_lint import analyze
    scene = wd / "pipeline/scenes/scene_S01.md"
    scene.write_text(text, encoding="utf-8")
    lint = wd / "pipeline/review/lint/S01.ai_filler.yaml"
    lint.write_text(yaml.safe_dump(analyze(text, scene_id="S01"), allow_unicode=True), encoding="utf-8")


def test_density_contract_projection_is_shared_by_dispatch_and_admission(tmp_path):
    import verify_review_complete as verify
    from machine_directive import build_directive

    wd = _scaffold(tmp_path)
    _use_current_lint(wd, "他把那东西收进柜底。")
    review = wd / "pipeline/review"
    # One hit exceeds the density contract although old cluster thresholds stay silent.
    assert verify.check(wd) == 2
    assert _admission(wd)["scenes"][0]["machine"]["reason"] == "enforced_alert_without_directive"
    directive, ledger = build_directive(wd, "S01")
    for name, data in (("machine_directive", directive), ("machine_ledger", ledger)):
        (review / f"S01.{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert verify.check(wd) == 2
    machine = _admission(wd)["scenes"][0]["machine"]
    assert machine["entry_states"] == ["pending"]
    # The normal revision/refresh path removes the real violation and closes admission.
    _use_current_lint(wd, "他把钥匙收进柜底。")
    directive, ledger = build_directive(wd, "S01")
    for name, data in (("machine_directive", directive), ("machine_ledger", ledger)):
        (review / f"S01.{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert verify.check(wd) == 0


def test_orchestrator_fastpath_cannot_supply_semantic_pass(tmp_path):
    import verify_review_complete as verify

    wd = _scaffold(tmp_path)
    review = wd / "pipeline/review"
    data = {"scene_id": "S01", "verdict": "PASS", "written_by": "orchestrator_fastpath_gate"}
    (review / "scene_S01.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert verify.check(wd) == 2
    (review / "scene_S01.post_revision.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert verify._post_revision_closed(wd, "S01") == (False, "post_revision_semantic_review_incomplete")


def test_explicit_semantic_failure_cannot_hide_behind_pass_or_machine_closure(tmp_path):
    import verify_review_complete as verify
    from machine_directive import build_directive

    wd = _scaffold(tmp_path)
    review = wd / "pipeline/review"
    directive, ledger = build_directive(wd, "S01")
    for name, data in (("machine_directive", directive), ("machine_ledger", ledger)):
        (review / f"S01.{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    post = review / "scene_S01.post_revision.yaml"
    post.write_text(yaml.safe_dump({"verdict": "PASS", "ai_pattern_gate": {"machine_gate": "pass", "reviewer_gate": "fail"}}), encoding="utf-8")
    assert verify._post_revision_closed(wd, "S01") == (False, "reviewer_gate_fail")
    post.write_text(yaml.safe_dump({"verdict": "PASS", "targeted_span_gate": {"per_patch": [{"patch_id": "p1", "semantic_function_preserved": False}]}}), encoding="utf-8")
    assert verify._post_revision_closed(wd, "S01") == (False, "post_revision_semantic_conflict")
    post.write_text(yaml.safe_dump({"verdict": "PASS", "ai_pattern_gate": {"machine_gate": "fail", "reviewer_gate": "pass"}}), encoding="utf-8")
    assert verify._post_revision_closed(wd, "S01") == (True, "")
