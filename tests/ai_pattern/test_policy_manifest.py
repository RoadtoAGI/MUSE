import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_MODULE = ROOT / "skills" / "MUSE-writing" / "scripts" / "ai_policy.py"
sys.path.insert(0, str(POLICY_MODULE.parent))



def _historical_manifest():
    """Exercise policy-validation mechanics against explicit historical fixtures."""
    import ai_policy

    manifest = copy.deepcopy(ai_policy.FAMILY_MANIFEST)
    for (family, lang), policy in ai_policy.PRE_CONTRACT_POLICY_BASELINE.items():
        manifest[family]["policy"][lang] = {
            **copy.deepcopy(policy), "pre_contract": True, "rules": {},
        }
    return manifest


def test_policy_manifest_module_exists():
    assert POLICY_MODULE.exists(), "统一 family policy 模块尚未落地"


def test_manifest_static_closure_and_explicit_contract_decisions():
    import ai_policy

    assert ai_policy.validate_manifest() == []
    enforced = {family for family in ai_policy.FAMILY_MANIFEST
                if ai_policy.effective_policy(family, "zh")["lifecycle"] == "enforced"}
    assert enforced == set()
    for family in ("dummy_pronoun", "demonstrative_classifier"):
        policy = ai_policy.effective_policy(family, "zh")
        assert not policy.get("density_contract")
        assert policy["decision_ref"] == "aigc-readability-2026-09-15"


def test_effective_policy_is_language_and_rule_aware():
    import ai_policy

    assert ai_policy.effective_policy("marker_pollution", "zh")["lifecycle"] == "observe"
    assert ai_policy.effective_policy("marker_pollution", "en")["lifecycle"] == "observe"

    # en-only rule cannot be revived by an enforced zh family.
    missing = ai_policy.effective_policy(
        "contrastive_negation_assertion", "zh", "negation_pivot_en"
    )
    assert missing["registered"] is False
    assert missing["lifecycle"] == "not_registered"


def test_rule_override_inherits_or_lowers_and_retains_promotion_provenance():
    import ai_policy

    manifest = _historical_manifest()
    manifest["marker_pollution"]["policy"]["zh"]["rules"] = {
        "banned_markdown": {"lifecycle": "observe"}
    }
    lowered = ai_policy.effective_policy(
        "marker_pollution", "zh", "banned_markdown", manifest=manifest
    )
    assert lowered["lifecycle"] == "observe"

    manifest["marker_pollution"]["policy"]["zh"]["rules"]["banned_markdown"] = {
        "lifecycle": "enforced",
        "promoted_ref": "CHANGELOG:promotion-1",
    }
    promoted = ai_policy.effective_policy(
        "marker_pollution", "zh", "banned_markdown", manifest=manifest
    )
    assert promoted["promoted_ref"] == "CHANGELOG:promotion-1"


def test_manifest_rejects_invalid_calibration_and_illegal_rule_promotion():
    import ai_policy

    manifest = _historical_manifest()
    manifest["marker_pollution"]["policy"]["zh"]["baseline_metric"] = "p95_magic"
    errors = ai_policy.validate_manifest(manifest=manifest)
    assert any("baseline_metric" in error for error in errors)

    manifest = _historical_manifest()
    manifest["meta_language_leak"]["policy"]["en"]["rules"] = {
        "meta_language_leak_en": {
            "lifecycle": "enforced",
            "promoted_ref": "CHANGELOG:illegal",
        }
    }
    errors = ai_policy.validate_manifest(manifest=manifest)
    assert any("above family lifecycle" in error for error in errors)


def test_calibrated_policy_requires_metric_and_resolvable_matching_reference():
    import ai_policy

    manifest = _historical_manifest()
    manifest["action_log"]["policy"]["zh"].pop("baseline_metric")
    errors = ai_policy.validate_manifest(manifest=manifest)
    assert any("action_log/zh" in error and "baseline_metric" in error for error in errors)

    manifest = _historical_manifest()
    manifest["action_log"]["policy"]["zh"]["baseline_ref"] = "builtin:missing"
    errors = ai_policy.validate_manifest(manifest=manifest)
    assert any("action_log/zh" in error and "unresolved" in error for error in errors)

    manifest = _historical_manifest()
    manifest["action_log"]["policy"]["zh"]["baseline_ref"] = (
        manifest["marker_pollution"]["policy"]["zh"]["baseline_ref"]
    )
    errors = ai_policy.validate_manifest(manifest=manifest)
    assert any(
        "action_log/zh" in error and "another policy" in error
        for error in errors
    )


def test_exempt_or_single_hit_policy_requires_a_decision_reference():
    import ai_policy

    manifest = _historical_manifest()
    manifest["fragment_settlement"]["decision_ref"] = None

    errors = ai_policy.validate_manifest(manifest=manifest)

    assert any("exempt policy missing decision_ref" in error for error in errors)
    assert any("single_hit missing decision_ref" in error for error in errors)


def test_rule_promotion_requires_resolved_three_evidence_record():
    import ai_policy

    manifest = _historical_manifest()
    manifest["marker_pollution"]["policy"]["zh"]["rules"] = {
        "banned_markdown": {
            "lifecycle": "enforced",
            "promoted_ref": "promotion:new-markdown-shape",
        }
    }
    errors = ai_policy.validate_manifest(manifest=manifest, promotion_records={})
    assert any("promoted_ref" in error and "unresolved" in error for error in errors)

    # 真 manifest 已带两族晋升，合成 records 须以真 PROMOTION_RECORDS 打底，
    # 否则其 promoted_ref 报 unresolved 干扰本测试的合成对象断言
    promotion_records = {
        **ai_policy.PROMOTION_RECORDS,
        "promotion:new-markdown-shape": {
            "family": "marker_pollution",
            "language": "zh",
            "rule": "banned_markdown",
            "prevalence_ref": "calibration:story-studio-heldout",
            "hard_negative_ref": "calibration:classics-heldout",
            "fixture_refs": ["tests/fixtures/markdown-should-fix.yaml", "tests/fixtures/markdown-should-not-fix.yaml"],
            "decision_ref": "CHANGELOG:markdown-shape-promotion",
        }
    }
    assert ai_policy.validate_manifest(
        manifest=manifest,
        promotion_records=promotion_records,
    ) == []

    del promotion_records["promotion:new-markdown-shape"]["hard_negative_ref"]
    errors = ai_policy.validate_manifest(
        manifest=manifest,
        promotion_records=promotion_records,
    )
    assert any("hard_negative_ref" in error for error in errors)


def test_family_promotion_requires_resolved_three_evidence_record():
    import ai_policy

    manifest = _historical_manifest()
    policy = manifest["dummy_pronoun"]["policy"]["zh"]
    policy.update(
        {
            "lifecycle": "enforced",
            "sovereignty": "M",
            "baseline_policy": "calibrated",
            "baseline_metric": "p90_positive",
            "baseline_ref": "builtin:v1:zh:dummy_pronoun:p90_positive",
        }
    )

    errors = ai_policy.validate_manifest(manifest=manifest, promotion_records={})
    assert any("dummy_pronoun/zh" in error and "promoted_ref" in error for error in errors)

    policy["promoted_ref"] = "promotion:dummy-pronoun-family"
    promotion_records = {
        **ai_policy.PROMOTION_RECORDS,
        "promotion:dummy-pronoun-family": {
            "family": "dummy_pronoun",
            "language": "zh",
            "prevalence_ref": "calibration:story-output-train",
            "hard_negative_ref": "calibration:novels-held-out",
            "fixture_refs": [
                "tests/fixtures/dummy-pronoun-should-fix.yaml",
                "tests/fixtures/dummy-pronoun-should-not-fix.yaml",
            ],
            "decision_ref": "CHANGELOG:dummy-pronoun-family-promotion",
        }
    }
    assert ai_policy.validate_manifest(
        manifest=manifest,
        promotion_records=promotion_records,
    ) == []
    promoted = ai_policy.effective_policy("dummy_pronoun", "zh", manifest=manifest)
    assert promoted["promoted_ref"] == "promotion:dummy-pronoun-family"

    promotion_records["promotion:dummy-pronoun-family"]["rule"] = "dummy_pronoun"
    errors = ai_policy.validate_manifest(
        manifest=manifest,
        promotion_records=promotion_records,
    )
    assert any("promotion rule" in error for error in errors)


def test_pre_contract_marker_is_frozen_to_original_policy_identities():
    import ai_policy

    manifest = _historical_manifest()
    promoted_without_evidence = manifest["dummy_pronoun"]["policy"]["zh"]
    promoted_without_evidence.update({
        "lifecycle": "enforced",
        "sovereignty": "M",
        "baseline_policy": "calibrated",
        "baseline_metric": "p90_positive",
        "baseline_ref": "builtin:v1:zh:dummy_pronoun:p90_positive",
        "pre_contract": True,
    })

    errors = ai_policy.validate_manifest(manifest=manifest)

    assert any("pre_contract identity" in error for error in errors)

    manifest = _historical_manifest()
    action = manifest["action_log"]
    action["decision_ref"] = "CHANGELOG:forged-exempt"
    policy = action["policy"]["zh"]
    policy["baseline_policy"] = "exempt"
    policy["single_hit"] = True
    policy.pop("baseline_metric", None)
    policy.pop("baseline_ref", None)

    errors = ai_policy.validate_manifest(manifest=manifest)

    assert any("pre_contract policy drift" in error for error in errors)

    manifest = _historical_manifest()
    manifest["state_persistence_template"]["policy"]["zh"]["aggregation"] = {
        "same_rule_scene_count_gte": 1,
    }

    errors = ai_policy.validate_manifest(manifest=manifest)

    assert any("pre_contract policy drift" in error for error in errors)


def test_new_rule_must_start_observe_instead_of_inheriting_enforcement():
    import ai_policy

    manifest = _historical_manifest()
    registry = copy.deepcopy(ai_policy.RULE_REGISTRY)
    registry["new_action_shape"] = {
        "family": "action_log",
        "languages": ["zh"],
    }

    errors = ai_policy.validate_manifest(
        manifest=manifest,
        rule_registry=registry,
    )

    assert any("new rule cannot inherit enforced lifecycle" in error for error in errors)

    manifest["action_log"]["policy"]["zh"]["rules"]["new_action_shape"] = {
        "lifecycle": "observe",
    }
    assert ai_policy.validate_manifest(
        manifest=manifest,
        rule_registry=registry,
    ) == []
