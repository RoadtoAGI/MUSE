"""Rn+2 Task 2: canonical_family + aggregation_only 去重。"""
from ai_filler_lint import (
    aggregate_cluster_alerts,
    apply_canonical_dedup,
    CANONICAL_FAMILY_MAP,
    RULE_REGISTRY_AGGREGATION_ONLY,
)


def test_canonical_dedup_same_span_marks_supporting():
    """parallel_negation + contrastive_negation_assertion 同 span -> parallel 标 dedup_supporting。"""
    hits = [
        {"rule": "parallel_negation", "family": "lexical_cliche",
         "lint_id": "S01-pn-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-001", "start": 100, "end": 130},
    ]
    enriched = apply_canonical_dedup(hits)
    pn = next(h for h in enriched if h["rule"] == "parallel_negation")
    cna = next(h for h in enriched if h["rule"] == "contrastive_negation_assertion")
    assert pn.get("dedup_supporting") is True
    assert pn.get("merged_into") == "S01-cna-001"
    assert not cna.get("dedup_supporting"), "canonical rule 自身不该被标 dedup_supporting"


def test_canonical_dedup_different_span_not_merged():
    """parallel_negation 与 contrastive_negation_assertion 不同 span -> 不归并。"""
    hits = [
        {"rule": "parallel_negation", "family": "lexical_cliche",
         "lint_id": "S01-pn-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-001", "start": 500, "end": 530},
    ]
    enriched = apply_canonical_dedup(hits)
    pn = next(h for h in enriched if h["rule"] == "parallel_negation")
    assert not pn.get("dedup_supporting")


def test_canonical_dedup_supporting_without_offsets_uses_snippet():
    """真实 parallel_negation hit 无 start/end；用 snippet 对齐 canonical text。"""
    hits = [
        {"rule": "parallel_negation", "family": "lexical_cliche",
         "lint_id": "S01-pn-001", "snippet": "不是扔，是放"},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-001", "start": 1977, "end": 1983, "text": "不是扔，是放"},
    ]
    enriched = apply_canonical_dedup(hits)
    pn = next(h for h in enriched if h["rule"] == "parallel_negation")
    assert pn.get("dedup_supporting") is True
    assert pn.get("merged_into") == "S01-cna-001"


def test_aggregation_only_rule_not_in_total_count():
    """narrative_micro_label aggregation_only -> cluster total_count 不计入。"""
    assert "narrative_micro_label" in RULE_REGISTRY_AGGREGATION_ONLY
    hits = [
        {"rule": "narrative_micro_label", "family": "micro_punchline_cadence",
         "lint_id": "S01-nml-001", "start": 50, "end": 80},
        {"rule": "zero_yield_micro_clause_candidate", "family": "micro_punchline_cadence",
         "lint_id": "S01-zyc-001", "start": 200, "end": 210},
        {"rule": "zero_yield_micro_clause_candidate", "family": "micro_punchline_cadence",
         "lint_id": "S01-zyc-002", "start": 500, "end": 510},
    ]
    alerts = aggregate_cluster_alerts(hits, "S01", "x" * 5000)
    # narrative_micro_label 不计入 total_count；zero_yield_micro_clause_candidate ×2 应触发
    if alerts:
        assert alerts[0]["total_count"] == 2, f"期望 2，实得 {alerts[0]['total_count']}"


def test_overlapping_observe_rules_deduplicate_without_blocking():
    """旧词法命中与语义候选同为 observe，同 span 只保留一份聚合证据。"""
    hits = [
        {"rule": "parallel_negation", "family": "lexical_cliche",
         "lint_id": "S01-pn-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-002", "start": 300, "end": 330},
    ]
    alerts = aggregate_cluster_alerts(hits, "S01", "x" * 2000)
    cna_alert = next((a for a in alerts if a["family"] == "contrastive_negation_assertion"), None)
    assert cna_alert is None
    assert not any(a["family"] == "lexical_cliche" for a in alerts)
    assert hits[0]["policy_lifecycle"] == "observe"
    assert hits[1]["policy_lifecycle"] == "observe"
    assert hits[2]["policy_lifecycle"] == "observe"
    assert hits[0].get("dedup_supporting") is True
    assert hits[0].get("merged_into") == "S01-cna-001"
    assert not hits[1].get("dedup_supporting")
