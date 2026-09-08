from __future__ import annotations

from collections import Counter
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "MUSE-writing" / "scripts"
GOLDEN = Path(__file__).with_name("fixtures") / "policy_semantic_golden.yaml"
sys.path.insert(0, str(SCRIPTS))


TEXTS = {
    "dirty_zh": "他怔了怔。\n\n她没说话。\n\n不是恐惧，是认出来了。\n\n" * 30,
    "clean_zh": (
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修他那把旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架。" * 20
    ),
    "dirty_en": "Not fear, but recognition — and then another aside. " * 40,
}


def test_policy_migration_matches_frozen_semantic_golden_and_expected_delta():
    from ai_filler_lint import analyze
    from ai_policy import effective_policy
    from machine_directive import _classify_level
    import wholetext_gate

    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    deltas = []
    for case_id, case in golden["cases"].items():
        lint = analyze(
            TEXTS[case["corpus_fixture"]],
            scene_id="GOLDEN",
            lang=case["language"],
        )
        hit_family_counts = dict(sorted(Counter(
            hit.get("family") for hit in lint["hits"] if hit.get("family")
        ).items()))
        assert hit_family_counts == case["hit_family_counts"], case_id
        alert_decisions = sorted(
            ({
                "family": alert["family"],
                "severity": alert["severity"],
                "total_count": alert["total_count"],
                "lifecycle": effective_policy(
                    alert["family"], case["language"]
                )["lifecycle"],
                "directive_level": _classify_level(
                    effective_policy(alert["family"], case["language"]),
                    alert["severity"],
                    alert["family"],
                    alert.get("cluster", alert["family"]),
                ),
            } for alert in lint["cluster_alerts"]),
            key=lambda item: item["family"],
        )
        assert alert_decisions == case["alert_decisions"], case_id

        report = wholetext_gate.build_report(
            TEXTS[case["corpus_fixture"]], case["language"]
        )
        assert report["verdict"] == case["expected_verdict"], case_id
        changed = case["old_verdict"] != case["expected_verdict"]
        if changed:
            deltas.append(case_id)
            assert case["delta"] == "expected"
            assert case.get("reason")
        else:
            assert case["delta"] == "unchanged"

    assert deltas == ["zh_clean", "en_observe_policy"]


def test_pre_migration_directive_level_oracle_is_frozen():
    from ai_policy import effective_policy
    from machine_directive import _classify_level

    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    for case in golden["directive_levels"]:
        policy = effective_policy(case["family"], case["language"])
        assert _classify_level(
            policy,
            case["severity"],
            case["family"],
            case["cluster"],
        ) == case["expected"]


def test_every_consumed_baseline_matches_the_frozen_pre_migration_oracle():
    from ai_policy import FAMILY_MANIFEST, calibration_value, effective_policy

    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    actual = {}
    for family, record in FAMILY_MANIFEST.items():
        for language in record["policy"]:
            policy = effective_policy(family, language)
            if (
                policy["lifecycle"] == "enforced"
                and policy.get("baseline_policy") == "calibrated"
            ):
                actual[f"{family}/{language}"] = {
                    "metric": policy["baseline_metric"],
                    "ref": policy["baseline_ref"],
                    "value": calibration_value(policy),
                }

    assert actual == golden["consumed_baselines"]
