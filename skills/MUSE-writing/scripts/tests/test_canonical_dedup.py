"""Rn+2 Task 2: canonical_family + aggregation_only 去重。

parallel_negation 的形态已逐 pattern 迁入 contrastive_negation_assertion 与 negation_list，
当前 CANONICAL_FAMILY_MAP 为空；同 span 去重机制本身用临时映射检验。
"""
import pytest

import ai_filler_lint
from ai_filler_lint import (
    aggregate_cluster_alerts,
    apply_canonical_dedup,
    CANONICAL_FAMILY_MAP,
    RULE_REGISTRY_AGGREGATION_ONLY,
)


@pytest.fixture
def supporting_map(monkeypatch):
    monkeypatch.setitem(
        ai_filler_lint.CANONICAL_FAMILY_MAP,
        "negation_restriction_pivot",
        {"canonical_rule": "contrastive_negation_assertion", "scope": "same_span"},
    )


def test_no_live_overlap_pairs_after_parallel_negation_migration():
    assert CANONICAL_FAMILY_MAP == {}


def test_canonical_dedup_same_span_marks_supporting(supporting_map):
    hits = [
        {"rule": "negation_restriction_pivot", "lint_id": "S01-nrp-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "lint_id": "S01-cna-001", "start": 100, "end": 130},
    ]
    enriched = apply_canonical_dedup(hits)
    sup = next(h for h in enriched if h["rule"] == "negation_restriction_pivot")
    cna = next(h for h in enriched if h["rule"] == "contrastive_negation_assertion")
    assert sup.get("dedup_supporting") is True
    assert sup.get("merged_into") == "S01-cna-001"
    assert not cna.get("dedup_supporting"), "canonical rule 自身不该被标 dedup_supporting"


def test_canonical_dedup_different_span_not_merged(supporting_map):
    hits = [
        {"rule": "negation_restriction_pivot", "lint_id": "S01-nrp-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "lint_id": "S01-cna-001", "start": 500, "end": 530},
    ]
    enriched = apply_canonical_dedup(hits)
    sup = next(h for h in enriched if h["rule"] == "negation_restriction_pivot")
    assert not sup.get("dedup_supporting")


def test_canonical_dedup_supporting_without_offsets_uses_snippet(supporting_map):
    hits = [
        {"rule": "negation_restriction_pivot", "lint_id": "S01-nrp-001", "snippet": "不是扔，是放"},
        {"rule": "contrastive_negation_assertion", "lint_id": "S01-cna-001", "start": 1977, "end": 1983,
         "text": "不是扔，是放"},
    ]
    enriched = apply_canonical_dedup(hits)
    sup = next(h for h in enriched if h["rule"] == "negation_restriction_pivot")
    assert sup.get("dedup_supporting") is True
    assert sup.get("merged_into") == "S01-cna-001"


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


def test_observe_and_enforced_lanes_never_merge(supporting_map):
    """observe 规则与 enforced 规则同 span 时各留各的证据：单发立案不被 observe 命中吞掉。"""
    hits = [
        {"rule": "negation_restriction_pivot", "family": "contrastive_negation_assertion",
         "lint_id": "S01-nrp-001", "start": 100, "end": 130},
        {"rule": "contrastive_negation_assertion", "family": "contrastive_negation_assertion",
         "lint_id": "S01-cna-001", "start": 100, "end": 130},
    ]
    alerts = aggregate_cluster_alerts(hits, "S01", "x" * 2000)
    assert hits[0]["policy_lifecycle"] == "observe"
    assert hits[1]["policy_lifecycle"] == "enforced"
    assert not hits[0].get("dedup_supporting")
    cna_alert = next(a for a in alerts if a["family"] == "contrastive_negation_assertion")
    assert cna_alert["hit_ids"] == ["S01-cna-001"]
