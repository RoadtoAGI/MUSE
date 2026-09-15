from __future__ import annotations

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


def test_historical_corpus_now_produces_contextual_review_candidates():
    from ai_filler_lint import analyze
    from wholetext_gate import build_report

    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    assert golden["frozen_from"] == "pre-manifest-runtime"
    for case in golden["cases"].values():
        text = TEXTS[case["corpus_fixture"]]
        lint = analyze(text, scene_id="GOLDEN", lang=case["language"])
        report = build_report(text, case["language"])
        assert lint["hits"]  # Original corpus still reaches the reviewer with locations.
        assert lint["cluster_alerts"] == []
        assert report["triggers"] == []
        assert report["verdict"] == "REVIEW"
        assert report["semantic_review"] == "not_run"
        assert report["overall_review"] == "incomplete"


def test_clear_reference_remains_a_candidate_at_high_density():
    from ai_filler_lint import analyze
    from ai_policy import effective_policy
    from wholetext_gate import build_report

    text = "门槛上卧着一条黑狗。它听见脚步便抬起头。她从两把伞中拿起那把旧伞。"
    lint = analyze(text, scene_id="GOLDEN", lang="zh")
    assert {h["family"] for h in lint["hits"]} >= {"dummy_pronoun", "demonstrative_classifier"}
    assert lint["cluster_alerts"] == []
    for hit in lint["hits"]:
        assert effective_policy(hit["family"], "zh", hit["rule"])["lifecycle"] == "observe"
    report = build_report(text, "zh")
    assert report["verdict"] == "REVIEW"
    assert report["triggers"] == []
    assert report["semantic_review"] == "not_run"


def test_historical_calibrations_remain_observations_without_deletion_budgets():
    from ai_policy import calibration_value, density_contract_max_count, effective_policy

    golden = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    for identity, baseline in golden["consumed_baselines"].items():
        family, language = identity.split("/")
        policy = effective_policy(family, language)
        assert policy["lifecycle"] == "observe"
        assert policy["baseline_metric"] == baseline["metric"]
        assert policy["baseline_ref"] == baseline["ref"]
        assert calibration_value(policy) == baseline["value"]
        assert density_contract_max_count(policy, 50) is None
