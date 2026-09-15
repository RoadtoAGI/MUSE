"""post_revision_gate contract tests."""
from __future__ import annotations

from pathlib import Path

import yaml

from post_revision_gate import (
    check_cluster_patch_gate,
    check_semantic_function_migration,
    decide_escalation,
    on_semantic_migration_fail,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_cluster_patch_suggestions_do_not_override_actual_repair():
    cluster_alert = {
        "cluster_id": "S01-cna-1",
        "governance": {
            "required_patch_kind_options": ["rewrite_sentence", "rewrite_span"],
            "forbidden_patch_kind": ["delete_token", "replace_phrase"],
        },
    }
    patch = {"cluster_id": "S01-cna-1", "patch_kind": "carrier_then_explain"}
    result = check_cluster_patch_gate(patch, cluster_alert)
    assert result["gate_pass"] is True
    assert "actual defect" in result["reason"]
    assert check_cluster_patch_gate({}, cluster_alert)["gate_pass"] is False


def test_cluster_patch_allowlist_gate_allows_rewrite_sentence():
    cluster_alert = {
        "cluster_id": "S01-cna-1",
        "governance": {
            "required_patch_kind_options": ["rewrite_sentence", "rewrite_span"],
            "forbidden_patch_kind": ["delete_token", "replace_phrase"],
        },
    }
    patch = {"cluster_id": "S01-cna-1", "patch_kind": "rewrite_sentence"}
    result = check_cluster_patch_gate(patch, cluster_alert)
    assert result["gate_pass"] is True


def test_semantic_function_migration_detects_actually_assertion():
    v1_anchor_text = "这不是他的战术，是他的威信。"
    v2_anchor_text = "真正支撑他的，是七部眼里的威信。"
    result = check_semantic_function_migration(
        v1_anchor_text,
        v2_anchor_text,
        family="contrastive_negation_assertion",
    )
    assert result["detected"] is True
    assert result["matched_pattern"] in ["true_actual_template", "actually_assertion"]


def test_semantic_migration_negative_fixture_triggers():
    fixture = yaml.safe_load((FIXTURES_DIR / "synthetic_semantic_migration_fail.yaml").read_text())
    result = check_semantic_function_migration(
        fixture["v1_anchor_text"],
        fixture["v2_anchor_text"],
        family=fixture["family"],
    )
    assert result["detected"] is fixture["expected_detected"]
    assert result["matched_pattern"] == fixture["expected_pattern"]


def test_semantic_function_migration_passes_visible_action():
    v1_anchor_text = "这不是他的战术，是他的威信。"
    v2_anchor_text = "七部还在看他。狼王不能先退。"
    result = check_semantic_function_migration(
        v1_anchor_text,
        v2_anchor_text,
        family="contrastive_negation_assertion",
    )
    assert result["detected"] is False


def test_semantic_migration_state_sibling_field():
    ledger = {
        "v1_triage": [],
        "post_revision_updates": [
            {"review_round": "post_revision_round1", "updates": []},
        ],
        "semantic_migration_state": {"attempt_count": 0, "last_failed_patch_ids": []},
    }
    new_ledger = on_semantic_migration_fail(ledger, failed_patch_ids=["patch_03", "patch_04"])
    assert new_ledger["semantic_migration_state"]["attempt_count"] == 1
    assert new_ledger["semantic_migration_state"]["last_failed_patch_ids"] == ["patch_03", "patch_04"]
    assert isinstance(new_ledger["post_revision_updates"], list)
    assert len(new_ledger["post_revision_updates"]) == 1
    assert new_ledger["post_revision_updates"][0]["review_round"] == "post_revision_round1"


def test_semantic_migration_state_initializes_if_missing():
    ledger = {"v1_triage": [], "post_revision_updates": []}
    new_ledger = on_semantic_migration_fail(ledger, failed_patch_ids=["p_x"])
    assert "semantic_migration_state" in new_ledger
    assert new_ledger["semantic_migration_state"]["attempt_count"] == 1
    assert new_ledger["semantic_migration_state"]["last_failed_patch_ids"] == ["p_x"]


def test_confirmed_repair_failure_returns_to_caller():
    ledger_1 = {"semantic_migration_state": {"attempt_count": 1, "last_failed_patch_ids": ["p_x"]}}
    assert decide_escalation(ledger_1) == "orchestrator_escalate"
    ledger_2 = {"semantic_migration_state": {"attempt_count": 2, "last_failed_patch_ids": ["p_x"]}}
    assert decide_escalation(ledger_2) == "orchestrator_escalate"
    ledger_empty = {}
    assert decide_escalation(ledger_empty) == "reviser_retry"


def test_observed_expression_can_be_retained_with_reason():
    """A recorded context judgment may retain a statistical match."""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    ledger = {
        "v1_triage": [{"lint_id": "S01-cna-001", "status": "observed"}],
        "post_revision_updates": {
            "S01-cna-001": {"status": "observed_not_patched", "reason": "保留功能性节拍"}
        }
    }
    lint_v2 = {"cluster_alerts": [{"alert_id": "S01-cna-1", "severity": "high",
                                    "hit_ids": ["S01-cna-001"]}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card={})
    assert result.valid
    ledger["post_revision_updates"]["S01-cna-001"]["status"] = "pending"
    assert not validate_post_revision_pass(review, ledger, lint_v2).valid


def test_post_revision_round_triggers_pass_gate():
    """Documented review_round marker must activate post-revision PASS checks."""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_round": "post_revision_round1"}
    ledger = {"v1_triage": [], "post_revision_updates": {}}
    lint_v2 = {"language": "zh", "density": {"total_chars": 100}, "hits": [{"family": "dummy_pronoun", "rule": "dummy_pronoun", "lint_id": "S01-cna-001"}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card={})
    assert result.valid
    # The post-revision round still checks actual unresolved decisions.
    ledger["post_revision_updates"] = {"S01-cna-001": {"status": "pending"}}
    assert not validate_post_revision_pass(review, ledger, lint_v2).valid


def test_formal_function_exempted_requires_carrier_function_link():
    """Rn+2 R1 F4 fix: 绑定 physical_carrier.function_link（真实 schema 字段），非 id。"""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    ledger = {
        "v1_triage": [],
        "post_revision_updates": {
            "S01-mpc-001": {"status": "formal_function_exempted"}  # 缺 carrier_function_link
        }
    }
    lint_v2 = {"cluster_alerts": [{"severity": "high", "hit_ids": ["S01-mpc-001"]}]}
    scene_card = {"physical_carrier": [{"text": "祭旗仪式", "function_link": "祭旗承载战场郑重"}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card=scene_card)
    assert not result.valid
    assert "function_link" in result.reason or "carrier" in result.reason.lower()


def test_retained_function_links_have_no_count_quota():
    """Each declared function link is validated independently."""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    fl = "祭旗承载战场郑重"
    ledger = {
        "v1_triage": [],
        "post_revision_updates": {
            f"S01-mpc-{i:03d}": {"status": "formal_function_exempted",
                                  "carrier_function_link": fl}
            for i in range(1, 5)
        }
    }
    lint_v2 = {"cluster_alerts": [{"severity": "high",
                                    "hit_ids": [f"S01-mpc-{i:03d}" for i in range(1, 5)]}]}
    scene_card = {"physical_carrier": [{"text": "祭旗仪式", "function_link": fl}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card=scene_card)
    assert result.valid


def test_post_revision_pass_with_all_high_resolved():
    """所有 high cluster ledger status=patched -> PASS 准入通过。"""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    ledger = {
        "v1_triage": [],
        "post_revision_updates": {
            "S01-cna-001": {"status": "patched", "reason": "改写为直接意象句"}
        }
    }
    lint_v2 = {"cluster_alerts": [{"severity": "high", "hit_ids": ["S01-cna-001"]}]}
    scene_card = {}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card=scene_card)
    assert result.valid


def test_statistical_candidates_do_not_require_duplicate_triage():
    """The existing semantic reviewer determines whether a candidate needs repair."""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    ledger = {"v1_triage": [], "post_revision_updates": {}}  # 缺 triage
    lint_v2 = {"cluster_alerts": [{"severity": "medium", "hit_ids": ["S01-sp-001"]}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card={})
    assert result.valid
    lint_v2["cluster_alerts"][0]["severity"] = "high"
    assert validate_post_revision_pass(review, ledger, lint_v2).valid


def test_post_revision_pass_medium_with_valid_triage():
    """Rn+2 R1 F7 fix: medium cluster status=observed + reason 长度合法 -> PASS。"""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    ledger = {
        "v1_triage": [
            {"lint_id": "S01-sp-001", "status": "observed",
             "reason": "同锚点重复 2 次但有 change_delta"}  # 18 字符
        ],
        "post_revision_updates": {}
    }
    lint_v2 = {"cluster_alerts": [{"severity": "medium", "hit_ids": ["S01-sp-001"]}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card={})
    assert result.valid


def test_post_revision_pass_physical_carrier_in_scene_tasks():
    """Rn+2 R1 F4 实证 fix: physical_carrier 真实嵌在 scene_tasks 内层（367 实证位置）。"""
    from scene_review_schema_validator import validate_post_revision_pass
    review = {"scene_id": "S01", "verdict": "PASS", "review_stage": "post_revision"}
    fl = "决断瞬间可观察化"
    ledger = {
        "v1_triage": [],
        "post_revision_updates": {
            "S01-mpc-001": {"status": "formal_function_exempted", "carrier_function_link": fl}
        }
    }
    lint_v2 = {"cluster_alerts": [{"severity": "high", "hit_ids": ["S01-mpc-001"]}]}
    # phase5 scene 结构：physical_carrier 在 scene_tasks 内层
    scene_card = {"scene_tasks": [{"physical_carrier": [{"text": "卫怀慎抚旧匕", "function_link": fl}]}]}
    result = validate_post_revision_pass(review, ledger, lint_v2, scene_card=scene_card)
    assert result.valid


def test_clear_reference_can_keep_its_recorded_function():
    from scene_review_schema_validator import validate_post_revision_pass

    review = {"verdict": "PASS", "review_stage": "post_revision"}
    ledger = {"post_revision_updates": {"d1": {
        "status": "formal_function_exempted", "carrier_function_link": "指向唯一旧物"}}}
    lint = {"language": "zh", "density": {"total_chars": 100}, "hits": [
        {"family": "dummy_pronoun", "rule": "dummy_pronoun", "lint_id": "d1"}]}
    card = {"physical_carrier": [{"function_link": "指向唯一旧物"}]}
    assert validate_post_revision_pass(review, ledger, lint, card).valid
