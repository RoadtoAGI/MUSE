"""protected_integrity.py machine-contract tests."""

from __future__ import annotations

import copy

import pytest
import yaml

from protected_integrity import (
    ProtectedIntegrityError,
    append_declaration_snapshot,
    append_relation_verifications,
    audit_scene_revision_integrity,
    assert_no_relation_overlap,
    collect_patch_declarations,
    diff_change_spans,
    derive_active_relation_anchors,
    has_pending_relation_declarations,
    load_scene_integrity,
    main,
    scene_sha256,
    snapshot_patch_declarations,
    validate_declarations,
    validate_partial_relation_update,
    validate_post_revision_proof,
    validate_verification_coverage,
    verify_scene_literal_integrity,
    verify_post_revision_review,
    verify_literal_tokens,
)


def _token(
    token_id: str = "T1",
    patch_id: str = "patch_01",
    *,
    raw: str = "十七岁",
    match_mode: str = "exact",
    accepted_forms: list[str] | None = None,
    scope: str = "scene",
) -> dict:
    return {
        "token_id": token_id,
        "patch_id": patch_id,
        "source": "old_span",
        "raw": raw,
        "match_mode": match_mode,
        "accepted_forms": accepted_forms or [],
        "scope": scope,
    }


def _relation(
    relation_id: str = "R1",
    patch_id: str = "patch_01",
    *,
    before_quote: str = "甲没有下令。",
) -> dict:
    return {
        "relation_id": relation_id,
        "patch_id": patch_id,
        "type": "polarity",
        "expected": "命令并非出自甲",
        "before_quote": before_quote,
    }


def _relation_record(
    scene_text: str,
    quote: str,
    *,
    relation_id: str = "R1",
    patch_id: str = "patch_01",
    preserved: bool = True,
    reason: str = "否定极性保持",
) -> dict:
    start = scene_text.index(quote)
    return {
        "relation_id": relation_id,
        "patch_id": patch_id,
        "preserved": preserved,
        "after_quote": quote,
        "reason": reason,
        "current_span": {"start": start, "end": start + len(quote)},
        "scene_sha": scene_sha256(scene_text),
    }


def test_scene_snapshot_is_immutable_idempotent_and_run_ids_are_global(tmp_path):
    token = _token()
    relation = _relation()

    path = append_declaration_snapshot(
        tmp_path,
        "S01",
        "post_revision_round1",
        tokens=[token],
        relations=[relation],
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "post_revision_round1",
        tokens=[copy.deepcopy(token)],
        relations=[copy.deepcopy(relation)],
    )

    state = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(state["declaration_snapshots"]) == 1
    assert state["declaration_snapshots"][0]["declaration_sha"]

    changed = _token(raw="十八岁")
    with pytest.raises(ProtectedIntegrityError, match="immutable_snapshot_conflict"):
        append_declaration_snapshot(
            tmp_path,
            "S01",
            "post_revision_round1",
            tokens=[changed],
            relations=[relation],
        )

    with pytest.raises(ProtectedIntegrityError, match="duplicate_protected_id"):
        append_declaration_snapshot(
            tmp_path,
            "S02",
            "post_revision_round1",
            tokens=[_token(patch_id="patch_other")],
            relations=[],
        )


def test_empty_protected_patch_registers_and_verifies_application_rounds(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_text = "她把窗推开，让雨声进来。"
    (scene_dir / "scene_S01.md").write_text(scene_text, encoding="utf-8")
    base_patch = {
        "patch_id": "patch_01",
        "anchor_quote": scene_text,
    }

    first = {"application_id": "apply_01", "patches": [base_patch]}
    snapshot_patch_declarations(tmp_path, "S01", first)
    applied_path = detail_dir / "patch_directive.applied.yaml"
    applied_path.write_text(yaml.safe_dump(first), encoding="utf-8")
    pending = load_scene_integrity(tmp_path, "S01")
    assert pending["declaration_snapshots"] == []
    assert len(pending["application_batches"]) == 1
    assert pending["application_batches"][0]["token_keys"] == []
    assert pending["application_batches"][0]["relation_scopes"] == []
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** empty set\n"
        f"   - new_span：{scene_text}\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "written_by": "orchestrator_fastpath_gate",
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0, report
    assert report.get("compatibility") is None
    assert report["verified_batch_ids"] == [
        pending["application_batches"][0]["batch_id"]
    ]
    assert validate_post_revision_proof(tmp_path, "S01")["verdict"] == "PASS"

    # A later distribution-only edit refreshes the scene-bound proof without
    # re-applying the already verified patch batch.
    distributed_text = scene_text + "雨势渐小。"
    (scene_dir / "scene_S01.md").write_text(distributed_text, encoding="utf-8")
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 0, report
    assert report["verified_batch_ids"] == []
    assert validate_post_revision_proof(tmp_path, "S01")["verdict"] == "PASS"

    with pytest.raises(ProtectedIntegrityError, match="application_id_reused"):
        snapshot_patch_declarations(tmp_path, "S01", first)

    second = {"application_id": "apply_02", "patches": [base_patch]}
    applied_path.write_text(yaml.safe_dump(second), encoding="utf-8")
    with pytest.raises(
        ProtectedIntegrityError, match="proof_applied_directive_batch_mismatch"
    ):
        validate_post_revision_proof(tmp_path, "S01")
    snapshot_patch_declarations(tmp_path, "S01", second)
    two_rounds = load_scene_integrity(tmp_path, "S01")
    assert len(two_rounds["application_batches"]) == 2
    assert two_rounds["application_batches"][0]["pre_scene_sha"] != (
        two_rounds["application_batches"][1]["pre_scene_sha"]
    )
    assert two_rounds["application_batches"][0]["batch_id"] != (
        two_rounds["application_batches"][1]["batch_id"]
    )


def test_patch_application_identity_and_patch_ids_fail_closed(tmp_path):
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "她把窗推开，让雨声进来。", encoding="utf-8"
    )
    with pytest.raises(ProtectedIntegrityError, match="application_id_required"):
        snapshot_patch_declarations(tmp_path, "S01", {
            "patches": [{"patch_id": "patch_01", "anchor_quote": "她把窗推开"}],
        })
    with pytest.raises(ProtectedIntegrityError, match="duplicate_patch_id"):
        collect_patch_declarations({
            "patches": [{"patch_id": "patch_01"}, {"patch_id": "patch_01"}],
        })


def test_requires_review_cli_exit_contract(tmp_path, capsys):
    assert main([
        "requires-review",
        "--work-dir",
        str(tmp_path),
        "--scene-id",
        "S01",
    ]) == 1
    assert capsys.readouterr().out.strip() == "false"

    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "甲没有下令。", encoding="utf-8"
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation()],
    )
    assert main([
        "requires-review",
        "--work-dir",
        str(tmp_path),
        "--scene-id",
        "S01",
    ]) == 0
    assert capsys.readouterr().out.strip() == "true"

    state_path = tmp_path / "pipeline" / "scene_S01" / "protected_integrity.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["schema_version"] = 999
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    assert main([
        "requires-review",
        "--work-dir",
        str(tmp_path),
        "--scene-id",
        "S01",
    ]) == 2
    assert "protected_integrity_schema_version" in capsys.readouterr().err

def test_declaration_schema_rejects_bad_binding_duplicate_id_and_relation_type():
    with pytest.raises(ProtectedIntegrityError, match="duplicate_protected_id"):
        validate_declarations(
            [_token("same")],
            [_relation("same")],
        )

    bad_token = _token()
    bad_token["source"] = "invented"
    with pytest.raises(ProtectedIntegrityError, match="source"):
        validate_declarations([bad_token], [])

    bad_relation = _relation()
    bad_relation["type"] = "ownership_guess"
    with pytest.raises(ProtectedIntegrityError, match="type"):
        validate_declarations([], [bad_relation])


def test_literal_exact_and_explicit_accepted_forms_are_deterministic():
    scene_text = "阿遥十七岁。阿岚今年 17 岁。尾声。"
    tokens = [
        _token("T1", "patch_01", raw="十七岁"),
        _token(
            "T2",
            "patch_02",
            raw="十七岁",
            match_mode="normalized",
            accepted_forms=["17 岁", "17岁"],
            scope="patch_span",
        ),
        _token("T3", "patch_03", raw="十九岁"),
    ]
    patch_start = scene_text.index("阿岚")
    patch_end = scene_text.index("尾声")

    results = verify_literal_tokens(
        scene_text,
        tokens,
        patch_spans={"patch_02": {"start": patch_start, "end": patch_end}},
    )

    by_id = {item["token_id"]: item for item in results}
    assert by_id["T1"]["found"] is True
    assert by_id["T1"]["matched_form"] == "十七岁"
    assert by_id["T2"]["found"] is True
    assert by_id["T2"]["matched_form"] == "17 岁"
    assert by_id["T2"]["region"] == {
        "scope": "patch_span",
        "start": patch_start,
        "end": patch_end,
    }
    assert by_id["T3"]["found"] is False
    assert by_id["T3"]["matched_form"] is None

    with pytest.raises(ProtectedIntegrityError, match="literal_not_found"):
        validate_verification_coverage(tokens, [], results, [])

    with pytest.raises(ProtectedIntegrityError, match="patch_span_missing"):
        verify_literal_tokens(scene_text, [tokens[1]], patch_spans={})


def test_scene_literal_gate_reads_authoritative_snapshot_after_directive_is_gone(tmp_path):
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token(raw="十七岁")],
        relations=[],
    )

    results = verify_scene_literal_integrity(tmp_path, "S01", "她仍是十七岁。")
    assert results[0]["found"] is True

    with pytest.raises(ProtectedIntegrityError, match="literal_not_found"):
        verify_scene_literal_integrity(tmp_path, "S01", "年龄已经被改掉。")


def test_distribution_audit_requires_post_revision_token_record(tmp_path):
    """声明进入修订后链路时，现场找到 literal 不能代替逐项核验记录。"""
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token(raw="十七岁", scope="scene")],
        relations=[],
    )

    audit = audit_scene_revision_integrity(
        tmp_path,
        "S01",
        "她仍是十七岁。",
        "她仍是十七岁。",
    )

    assert audit["verdict"] == "FAIL"
    assert "active_token_verification_missing" in audit["reason"]


def test_post_revision_advances_patch_span_token_and_distribution_reuses_it(tmp_path):
    scene_text = "开头。她仍是十七岁。旧结尾。"
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    (scene_dir / "scene_S01.md").write_text(scene_text, encoding="utf-8")
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token(scope="patch_span")],
        relations=[],
    )
    (detail_dir / "revision_summary.md").write_text(
        "# Revision Summary: S01\n\n"
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** 保留年龄\n"
        "   - new_span：她仍是十七岁。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS", "written_by": "orchestrator_fastpath_gate"}),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(
        tmp_path,
        "S01",
        review_path="pipeline/review/scene_S01.post_revision.yaml",
    )

    assert rc == 0
    assert report["literal_results"][0]["matched_form"] == "十七岁"
    state = load_scene_integrity(tmp_path, "S01")
    assert state["token_verifications"][0]["matched_form"] == "十七岁"
    assert state["token_verifications"][0]["scene_sha"] == scene_sha256(scene_text)

    after = "新开头更具体。她仍是十七岁。新结尾。"
    audit = audit_scene_revision_integrity(tmp_path, "S01", scene_text, after)
    assert audit["verdict"] == "PASS"
    assert audit["literal_results"][0]["matched_form"] == "十七岁"

    duplicated_elsewhere = scene_text + "旁人也说她十七岁。"
    duplicate_audit = audit_scene_revision_integrity(
        tmp_path,
        "S01",
        scene_text,
        duplicated_elsewhere,
    )
    assert duplicate_audit["verdict"] == "PASS"

    # A later point-revision summary contains only its new patch.  The first
    # round token remains bound through its active occurrence record.
    (scene_dir / "scene_S01.md").write_text(after, encoding="utf-8")
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_02 · applied · patch_kind=rewrite_sentence]** 改开头\n"
        "   - new_span：新开头更具体。\n",
        encoding="utf-8",
    )
    rc, second_report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 0
    assert second_report["literal_results"][0]["matched_form"] == "十七岁"
    second_state = load_scene_integrity(tmp_path, "S01")
    assert second_state["token_verifications"][-1]["scene_sha"] == scene_sha256(after)


def test_relation_declaration_closes_literal_only_fastpath(tmp_path):
    scene_text = "甲没有下令。"
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "review").mkdir(parents=True)
    (tmp_path / "pipeline" / "scene_S01").mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        scene_text, encoding="utf-8"
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation()],
    )
    (tmp_path / "pipeline" / "scene_S01" / "revision_summary.md").write_text(
        "**status**: complete\n", encoding="utf-8"
    )
    (tmp_path / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS", "written_by": "orchestrator_fastpath_gate"}),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 2
    assert report["reason"] == "protected_integrity_gate_not_evaluated"


def test_post_revision_yaml_advances_relation_active_anchor(tmp_path):
    scene_text = "开头。命令并非出自甲。结尾。"
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "review").mkdir(parents=True)
    (tmp_path / "pipeline" / "scene_S01").mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        scene_text, encoding="utf-8"
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation()],
    )
    record = _relation_record(scene_text, "命令并非出自甲。")
    (tmp_path / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [record],
            },
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0
    assert report["active_relations"][0]["after_quote"] == "命令并非出自甲。"
    state = load_scene_integrity(tmp_path, "S01")
    assert len(state["relation_verifications"]) == 1
    assert state["relation_verifications"][0]["after_quote"] == "命令并非出自甲。"


def test_first_partial_reuses_declaration_seed_for_not_applied_relation(tmp_path):
    old_text = "甲没有下令。乙先抵达。"
    new_text = "命令并非出自甲。乙先抵达。"
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "review").mkdir(parents=True)
    (tmp_path / "pipeline" / "scene_S01").mkdir(parents=True)
    scene_path = tmp_path / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text(old_text, encoding="utf-8")
    relations = [
        _relation("R1", "patch_01", before_quote="甲没有下令。"),
        _relation("R2", "patch_02", before_quote="乙先抵达。"),
    ]
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [
            {"patch_id": "patch_01", "protected_relations": [relations[0]]},
            {"patch_id": "patch_02", "protected_relations": [relations[1]]},
        ],
    })
    seeded = load_scene_integrity(tmp_path, "S01")
    assert len(seeded["relation_verifications"]) == 2
    assert all(
        item["reason"] == "declaration_before_quote_seed"
        for item in seeded["relation_verifications"]
    )

    scene_path.write_text(new_text, encoding="utf-8")
    (tmp_path / "pipeline" / "scene_S01" / "revision_summary.md").write_text(
        "**status**: partial\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** 改写\n"
        "   - new_span：命令并非出自甲。\n\n"
        "2. **[patch_02 · not_applied]** 未施工\n",
        encoding="utf-8",
    )
    record = _relation_record(
        new_text,
        "命令并非出自甲。",
        relation_id="R1",
        patch_id="patch_01",
    )
    (tmp_path / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [record],
            },
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0, report
    by_key = {
        (item["patch_id"], item["relation_id"]): item
        for item in report["active_relations"]
    }
    assert by_key[("patch_01", "R1")]["after_quote"] == "命令并非出自甲。"
    assert by_key[("patch_02", "R2")]["after_quote"] == "乙先抵达。"
    assert validate_post_revision_proof(tmp_path, "S01")["verdict"] == "PASS"


def test_revision_summary_must_partition_every_current_batch_patch(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_text = "甲没有下令。乙先抵达。"
    (scene_dir / "scene_S01.md").write_text(scene_text, encoding="utf-8")
    snapshot_patch_declarations(tmp_path, "S01", {
        "application_id": "apply_01",
        "patches": [
            {
                "patch_id": "patch_01",
                "protected_relations": [
                    _relation("R1", "patch_01", before_quote="甲没有下令。")
                ],
            },
            {
                "patch_id": "patch_02",
                "protected_relations": [
                    _relation("R2", "patch_02", before_quote="乙先抵达。")
                ],
            },
        ],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: partial\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** only one\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [
                    _relation_record(scene_text, "甲没有下令。")
                ],
            },
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 2
    assert report["reason"] == (
        "revision_summary_batch_partition_incomplete:missing=['patch_02']"
    )


def test_reused_patch_id_projects_summary_only_to_latest_snapshot(tmp_path):
    """round2 patch_01 must not retarget round1 T1/R1 declarations."""
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_path = scene_dir / "scene_S01.md"

    round1_text = "甲没有下令。她仍是十七岁。"
    scene_path.write_text(round1_text, encoding="utf-8")
    token1 = _token("T1", "patch_01", raw="十七岁", scope="patch_span")
    relation1 = _relation("R1", "patch_01", before_quote="甲没有下令。")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [{
            "patch_id": "patch_01",
            "protected_tokens": [token1],
            "protected_relations": [relation1],
        }],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round1\n"
        "   - new_span：甲没有下令。她仍是十七岁。\n",
        encoding="utf-8",
    )
    relation1_record = _relation_record(
        round1_text,
        "甲没有下令。",
        relation_id="R1",
        patch_id="patch_01",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [relation1_record],
            },
        }),
        encoding="utf-8",
    )
    assert verify_post_revision_review(tmp_path, "S01")[0] == 0

    round2_text = round1_text + "乙先抵达。她已十八岁。"
    scene_path.write_text(round2_text, encoding="utf-8")
    token2 = _token("T2", "patch_01", raw="十八岁", scope="patch_span")
    relation2 = _relation("R2", "patch_01", before_quote="乙先抵达。")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round2",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": "乙先抵达。她已十八岁。",
            "protected_tokens": [token2],
            "protected_relations": [relation2],
        }],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round2\n"
        "   - new_span：乙先抵达。她已十八岁。\n",
        encoding="utf-8",
    )
    relation2_record = _relation_record(
        round2_text,
        "乙先抵达。",
        relation_id="R2",
        patch_id="patch_01",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [relation2_record],
            },
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0, report
    token_by_id = {item["token_id"]: item for item in report["literal_results"]}
    assert token_by_id["T1"]["matched_form"] == "十七岁"
    assert token_by_id["T2"]["matched_form"] == "十八岁"
    relation_by_id = {
        item["relation_id"]: item for item in report["active_relations"]
    }
    assert relation_by_id["R1"]["after_quote"] == "甲没有下令。"
    assert relation_by_id["R2"]["after_quote"] == "乙先抵达。"


def test_historical_relation_does_not_close_later_literal_only_fastpath(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_path = scene_dir / "scene_S01.md"
    scene_text = "甲没有下令。她仍是十七岁。"
    scene_path.write_text(scene_text, encoding="utf-8")

    relation = _relation("R1", "patch_01", before_quote="甲没有下令。")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [{
            "patch_id": "patch_01",
            "protected_relations": [relation],
        }],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round1\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [
                    _relation_record(scene_text, "甲没有下令。")
                ],
            },
        }),
        encoding="utf-8",
    )
    assert verify_post_revision_review(tmp_path, "S01")[0] == 0

    token = _token("T2", "patch_01", raw="十七岁", scope="patch_span")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round2",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": "她仍是十七岁。",
            "protected_tokens": [token],
        }],
    })
    assert has_pending_relation_declarations(tmp_path, "S01") is False
    with pytest.raises(ProtectedIntegrityError, match="proof_pending_application_batches"):
        validate_post_revision_proof(tmp_path, "S01")
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round2\n"
        "   - new_span：她仍是十七岁。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "written_by": "orchestrator_fastpath_gate",
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0, report
    assert report["literal_results"][-1]["matched_form"] == "十七岁"


def test_historical_relation_overlap_closes_literal_fastpath(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_path = scene_dir / "scene_S01.md"
    before = "甲没有下令。她仍是十七岁。"
    scene_path.write_text(before, encoding="utf-8")
    relation = _relation("R1", "patch_01", before_quote="甲没有下令。")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": "甲没有下令。",
            "protected_relations": [relation],
        }],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round1\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [
                    _relation_record(before, "甲没有下令。")
                ],
            },
        }),
        encoding="utf-8",
    )
    assert verify_post_revision_review(tmp_path, "S01")[0] == 0

    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round2",
        "patches": [{
            "patch_id": "patch_02",
            "anchor_quote": "甲没有下令。",
            "protected_tokens": [
                _token("T2", "patch_02", raw="十七岁", scope="scene")
            ],
        }],
    })
    assert has_pending_relation_declarations(tmp_path, "S01") is True
    scene_path.write_text("据说甲没有下令。她仍是十七岁。", encoding="utf-8")
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_02 · applied · patch_kind=rewrite_sentence]** round2\n"
        "   - new_span：据说甲没有下令。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "written_by": "orchestrator_fastpath_gate",
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 2
    assert report["reason"] == "protected_integrity_gate_not_evaluated"


def test_reused_relation_identity_creates_new_review_batch(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_text = "甲没有下令。"
    (scene_dir / "scene_S01.md").write_text(scene_text, encoding="utf-8")
    relation = _relation("R1", "patch_01", before_quote=scene_text)

    def snapshot(round_id: str) -> None:
        snapshot_patch_declarations(tmp_path, "S01", {
            "review_round": round_id,
            "patches": [{
                "patch_id": "patch_01",
                "protected_relations": [relation],
            }],
        })

    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** keep\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    snapshot("round1")
    record = _relation_record(scene_text, scene_text)
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [record],
            },
        }),
        encoding="utf-8",
    )
    assert verify_post_revision_review(tmp_path, "S01")[0] == 0

    snapshot("round2")
    assert has_pending_relation_declarations(tmp_path, "S01") is True
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "written_by": "orchestrator_fastpath_gate",
        }),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 2
    assert report["reason"] == "protected_integrity_gate_not_evaluated"

    record["reason"] = "round2 reviewer reverified"
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [record],
            },
        }),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 0, report
    valid_proof = validate_post_revision_proof(tmp_path, "S01")
    assert valid_proof["verdict"] == "PASS"
    forged = copy.deepcopy(valid_proof)
    forged["relation_verifications"] = []
    with pytest.raises(
        ProtectedIntegrityError, match="proof_relation_records_sidecar_mismatch"
    ):
        validate_post_revision_proof(tmp_path, "S01", forged)


def test_full_scene_rollback_requires_reverification_of_historical_relations(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_path = scene_dir / "scene_S01.md"
    before = "甲没有下令。"
    scene_path.write_text(before, encoding="utf-8")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [{
            "patch_id": "patch_01",
            "anchor_quote": before,
            "protected_relations": [_relation(before_quote=before)],
        }],
    })
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** round1\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [
                    _relation_record(before, before)
                ],
            },
        }),
        encoding="utf-8",
    )
    assert verify_post_revision_review(tmp_path, "S01")[0] == 0

    (review_dir / "scene_S01.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "ROLLBACK"}),
        encoding="utf-8",
    )
    after = "命令并非出自甲。"
    scene_path.write_text(after, encoding="utf-8")
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n", encoding="utf-8"
    )
    assert has_pending_relation_declarations(tmp_path, "S01") is True
    try:
        prepare_rc = main([
            "prepare-post-rewrite",
            "--work-dir",
            str(tmp_path),
            "--scene-id",
            "S01",
        ])
    except SystemExit as exc:
        prepare_rc = int(exc.code)
    assert prepare_rc == 0
    prepared_state = load_scene_integrity(tmp_path, "S01")
    pending_batches = [
        batch for batch in prepared_state["application_batches"]
        if batch["batch_id"] not in prepared_state["verified_batch_ids"]
    ]
    assert len(pending_batches) == 1
    assert pending_batches[0]["round_id"] == "post_rewrite:rollback"
    assert pending_batches[0]["relation_scopes"] == [{
        "patch_id": "patch_01",
        "relation_id": "R1",
        "trigger_patch_ids": ["__rollback__"],
    }]
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS", "review_round": "rollback_round2"}),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 2
    assert report["reason"] == "protected_integrity_gate_not_evaluated"

    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "review_round": "rollback_round2",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [
                    _relation_record(after, after, reason="rollback reverified")
                ],
            },
        }),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 0, report
    assert report["active_relations"][0]["after_quote"] == after


def test_forged_minimal_proof_cannot_borrow_declaration_seed(tmp_path):
    scene_dir = tmp_path / "pipeline" / "scenes"
    review_dir = tmp_path / "pipeline" / "review"
    detail_dir = tmp_path / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    detail_dir.mkdir(parents=True)
    scene_text = "甲没有下令。"
    (scene_dir / "scene_S01.md").write_text(scene_text, encoding="utf-8")
    snapshot_patch_declarations(tmp_path, "S01", {
        "review_round": "round1",
        "patches": [{
            "patch_id": "patch_01",
            "protected_relations": [_relation(before_quote=scene_text)],
        }],
    })
    state = load_scene_integrity(tmp_path, "S01")
    assert state["relation_verifications"][0]["reason"] == "declaration_before_quote_seed"
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** forged\n"
        "   - new_span：甲没有下令。\n",
        encoding="utf-8",
    )
    seed_record = {
        key: copy.deepcopy(value)
        for key, value in state["relation_verifications"][0].items()
        if key != "record_sha"
    }
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [seed_record],
            },
        }),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(tmp_path, "S01")
    assert rc == 2
    assert report["reason"] == "applied_relation_uses_declaration_seed"
    fake = {
        "scene_id": "S01",
        "verdict": "PASS",
        "scene_sha": scene_sha256(scene_text),
        "review_path": str(review_dir / "scene_S01.post_revision.yaml"),
        "verified_batch_ids": [state["application_batches"][0]["batch_id"]],
        "token_verifications": [],
        "relation_verifications": [],
    }

    with pytest.raises(ProtectedIntegrityError, match="proof_batch_not_verified"):
        validate_post_revision_proof(tmp_path, "S01", fake)


def test_patch_span_post_revision_without_applied_new_span_fails_closed(tmp_path):
    scene_text = "她仍是十七岁。"
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "review").mkdir(parents=True)
    (tmp_path / "pipeline" / "scene_S01").mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        scene_text, encoding="utf-8"
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token(scope="patch_span")],
        relations=[],
    )
    (tmp_path / "pipeline" / "scene_S01" / "revision_summary.md").write_text(
        "**status**: complete\n", encoding="utf-8"
    )
    (tmp_path / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": False,
                "relation_verifications": [],
            },
        }),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 2
    assert "applied_new_span_missing:patch_01" in report["reason"]
    assert load_scene_integrity(tmp_path, "S01")["token_verifications"] == []


def test_first_partial_not_applied_patch_span_uses_pending_old_span(tmp_path):
    scene_text = "开头。她仍是十七岁。结尾。"
    (tmp_path / "pipeline" / "scenes").mkdir(parents=True)
    (tmp_path / "pipeline" / "review").mkdir(parents=True)
    detail = tmp_path / "pipeline" / "scene_S01"
    detail.mkdir(parents=True)
    (tmp_path / "pipeline" / "scenes" / "scene_S01.md").write_text(
        scene_text, encoding="utf-8"
    )
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token(scope="patch_span")],
        relations=[],
    )
    (detail / "patch_directive.yaml").write_text(
        yaml.safe_dump({
            "patches": [{
                "patch_id": "patch_01",
                "anchor_quote": "她仍是十七岁。",
            }],
        }),
        encoding="utf-8",
    )
    (detail / "revision_summary.md").write_text(
        "**status**: partial\n\n"
        "1. **[patch_01 · not_applied]** 未施工\n",
        encoding="utf-8",
    )
    (tmp_path / "pipeline" / "review" / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS", "written_by": "orchestrator_fastpath_gate"}),
        encoding="utf-8",
    )

    rc, report = verify_post_revision_review(tmp_path, "S01")

    assert rc == 0, report
    assert report["literal_results"][0]["matched_form"] == "十七岁"
    state = load_scene_integrity(tmp_path, "S01")
    assert state["token_verifications"][0]["matched_form"] == "十七岁"


def test_declared_and_verified_sets_compare_compound_identity():
    tokens = [_token("T1", "patch_01")]
    relations = [_relation("R1", "patch_02")]
    token_results = [{
        "token_id": "T1",
        "patch_id": "patch_wrong",
        "found": True,
        "matched_form": "十七岁",
        "region": {"scope": "scene", "start": 0, "end": 3},
    }]
    relation_records = [{
        "relation_id": "R1",
        "patch_id": "patch_02",
        "preserved": True,
        "after_quote": "甲没有下令。",
        "reason": "保持",
        "current_span": {"start": 0, "end": 6},
        "scene_sha": "0" * 64,
    }]

    with pytest.raises(ProtectedIntegrityError, match="verification_set_mismatch"):
        validate_verification_coverage(
            tokens,
            relations,
            token_results,
            relation_records,
        )

    token_results[0]["patch_id"] = "patch_01"
    validate_verification_coverage(
        tokens,
        relations,
        token_results,
        relation_records,
    )

    with pytest.raises(ProtectedIntegrityError, match="duplicate_verification"):
        validate_verification_coverage(
            tokens,
            relations,
            token_results * 2,
            relation_records,
        )


def test_relation_records_are_append_only_and_bound_to_scene_sha_and_span(tmp_path):
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation()],
    )
    scene_text = "开头。命令并非出自甲。结尾。"
    record = _relation_record(scene_text, "命令并非出自甲。")

    path = append_relation_verifications(tmp_path, "S01", scene_text, [record])
    append_relation_verifications(tmp_path, "S01", scene_text, [copy.deepcopy(record)])
    state = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(state["relation_verifications"]) == 1
    assert state["relation_verifications"][0]["record_sha"]

    rewritten = "开头。命令确实并非出自甲。结尾。"
    second = _relation_record(rewritten, "命令确实并非出自甲。")
    append_relation_verifications(tmp_path, "S01", rewritten, [second])
    two_rounds = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(two_rounds["relation_verifications"]) == 2
    assert two_rounds["relation_verifications"][0] == state["relation_verifications"][0]

    bad_sha = copy.deepcopy(record)
    bad_sha["scene_sha"] = "0" * 64
    with pytest.raises(ProtectedIntegrityError, match="scene_sha_mismatch"):
        append_relation_verifications(tmp_path, "S01", scene_text, [bad_sha])

    bad_span = copy.deepcopy(record)
    bad_span["current_span"] = {"start": 0, "end": len(record["after_quote"])}
    with pytest.raises(ProtectedIntegrityError, match="current_span_mismatch"):
        append_relation_verifications(tmp_path, "S01", scene_text, [bad_span])


def test_appending_relation_records_requires_full_declared_compound_set(tmp_path):
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation("R1", "patch_01"), _relation("R2", "patch_02")],
    )
    scene_text = "甲没有下令。乙先抵达。"
    only_one = _relation_record(
        scene_text,
        "甲没有下令。",
        relation_id="R1",
        patch_id="patch_01",
    )

    with pytest.raises(ProtectedIntegrityError, match="verification_set_mismatch"):
        append_relation_verifications(tmp_path, "S01", scene_text, [only_one])


def test_one_review_batch_cannot_duplicate_relation_compound_identity(tmp_path):
    append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[],
        relations=[_relation()],
    )
    scene_text = "甲没有下令。"
    first = _relation_record(scene_text, "甲没有下令。")
    second = _relation_record(scene_text, "甲没有下令。", reason="再次声称保持")

    with pytest.raises(ProtectedIntegrityError, match="duplicate_verification"):
        append_relation_verifications(tmp_path, "S01", scene_text, [first, second])


def test_active_anchor_moves_after_preserving_rewrite_and_keeps_other_rounds():
    relations = [
        _relation("R1", "patch_01", before_quote="甲没有下令。"),
        _relation("R2", "patch_02", before_quote="乙先抵达。"),
    ]
    old_text = "甲没有下令。乙先抵达。"
    new_text = "命令并非出自甲。乙先抵达。"
    records = [
        _relation_record(old_text, "甲没有下令。", relation_id="R1", patch_id="patch_01"),
        _relation_record(old_text, "乙先抵达。", relation_id="R2", patch_id="patch_02"),
        _relation_record(new_text, "命令并非出自甲。", relation_id="R1", patch_id="patch_01"),
    ]

    anchors = derive_active_relation_anchors(relations, records, new_text)
    by_key = {(a["patch_id"], a["relation_id"]): a for a in anchors}
    assert by_key[("patch_01", "R1")]["after_quote"] == "命令并非出自甲。"
    assert by_key[("patch_02", "R2")]["after_quote"] == "乙先抵达。"
    assert by_key[("patch_02", "R2")]["scene_sha"] == scene_sha256(new_text)


def test_partial_applied_gets_new_record_and_not_applied_reuses_old_anchor():
    relations = [
        _relation("R1", "patch_01"),
        _relation("R2", "patch_02", before_quote="乙先抵达。"),
    ]
    old_text = "甲没有下令。乙先抵达。"
    new_text = "命令并非出自甲。乙先抵达。"
    prior = [
        _relation_record(old_text, "甲没有下令。", relation_id="R1", patch_id="patch_01"),
        _relation_record(old_text, "乙先抵达。", relation_id="R2", patch_id="patch_02"),
    ]
    new = [
        _relation_record(new_text, "命令并非出自甲。", relation_id="R1", patch_id="patch_01"),
    ]

    combined = validate_partial_relation_update(
        relations,
        prior,
        new,
        applied_patch_ids={"patch_01"},
        not_applied_patch_ids={"patch_02"},
    )
    anchors = derive_active_relation_anchors(relations, combined, new_text)
    by_key = {(a["patch_id"], a["relation_id"]): a for a in anchors}
    assert by_key[("patch_01", "R1")]["after_quote"] == "命令并非出自甲。"
    assert by_key[("patch_02", "R2")]["after_quote"] == "乙先抵达。"

    with pytest.raises(ProtectedIntegrityError, match="applied_relation_missing_verification"):
        validate_partial_relation_update(
            relations,
            prior,
            [],
            applied_patch_ids={"patch_01"},
            not_applied_patch_ids={"patch_02"},
        )

    with pytest.raises(ProtectedIntegrityError, match="not_applied_relation_has_verification"):
        validate_partial_relation_update(
            relations,
            prior,
            new + [_relation_record(
                new_text,
                "乙先抵达。",
                relation_id="R2",
                patch_id="patch_02",
            )],
            applied_patch_ids={"patch_01"},
            not_applied_patch_ids={"patch_02"},
        )


def test_duplicate_or_unlocatable_active_anchor_fails_closed():
    relation = _relation()
    old_text = "甲没有下令。"
    record = _relation_record(old_text, "甲没有下令。")

    with pytest.raises(ProtectedIntegrityError, match="active_anchor_ambiguous"):
        derive_active_relation_anchors(
            [relation],
            [record],
            "甲没有下令。旁人重复：甲没有下令。",
        )

    with pytest.raises(ProtectedIntegrityError, match="active_anchor_not_found"):
        derive_active_relation_anchors([relation], [record], "命令已经发出。")


def test_relation_overlap_uses_half_open_spans_and_fails_closed():
    active = [{
        "patch_id": "patch_01",
        "relation_id": "R1",
        "after_quote": "命令并非出自甲。",
        "current_span": {"start": 5, "end": 14},
        "scene_sha": "a" * 64,
    }]

    with pytest.raises(ProtectedIntegrityError, match="relation_span_overlap"):
        assert_no_relation_overlap(
            [{"change_id": "dist_1", "current_span": {"start": 13, "end": 18}}],
            active,
        )

    assert_no_relation_overlap(
        [{"change_id": "dist_2", "current_span": {"start": 14, "end": 18}}],
        active,
    )

    duplicate = active + [copy.deepcopy(active[0])]
    with pytest.raises(ProtectedIntegrityError, match="duplicate_active_anchor"):
        assert_no_relation_overlap([], duplicate)


def test_relation_start_modifier_is_overlap_while_end_boundary_is_safe():
    text = "开头。甲没有下令。结尾。"
    quote = "甲没有下令。"
    start = text.index(quote)
    active = [{
        "patch_id": "patch_01",
        "relation_id": "R1",
        "after_quote": quote,
        "current_span": {"start": start, "end": start + len(quote)},
        "scene_sha": "a" * 64,
    }]

    inside = text[: start + 1] + "确实" + text[start + 1 :]
    with pytest.raises(ProtectedIntegrityError, match="relation_span_overlap"):
        assert_no_relation_overlap(diff_change_spans(text, inside), active)

    at_start = text[:start] + "据说" + text[start:]
    with pytest.raises(ProtectedIntegrityError, match="relation_span_overlap"):
        assert_no_relation_overlap(diff_change_spans(text, at_start), active)

    at_end = text[: start + len(quote)] + "随后" + text[start + len(quote) :]
    assert_no_relation_overlap(diff_change_spans(text, at_end), active)


def test_loading_detects_tampered_immutable_snapshot(tmp_path):
    path = append_declaration_snapshot(
        tmp_path,
        "S01",
        "round1",
        tokens=[_token()],
        relations=[],
    )
    state = yaml.safe_load(path.read_text(encoding="utf-8"))
    state["declaration_snapshots"][0]["tokens"][0]["raw"] = "十八岁"
    path.write_text(yaml.safe_dump(state, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ProtectedIntegrityError, match="immutable_snapshot_tampered"):
        load_scene_integrity(tmp_path, "S01")
