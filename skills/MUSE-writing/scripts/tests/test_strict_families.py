"""表面形态候选：转折否定。

"不是 X，是 Y" 一类转折否定按 AI 口癖治理升级设计 §5.1 三项证据恢复单发；光杆否定加限缩转折
（不X只Y、没X只Y）单列 negation_restriction_pivot 留 observe。对白（引号内）不属于检测范围。
"""
from ai_filler_lint import (
    analyze,
    detect_contrastive_negation_assertion,
    detect_negation_restriction_pivot,
)
from ai_policy import (
    BASELINE_EXEMPT_FAMILIES,
    FAMILY_DENSITY_BASELINE,
    PER_FAMILY_OVERRIDE,
    PROMOTION_RECORDS,
    effective_policy,
)


# ---------- 光杆转折否定 ----------

def test_bare_negation_restriction_hit():
    text = "老关按住他要解甲绦的手，不掰开，只是裹住，把甲绦重新绕回去。"
    assert detect_contrastive_negation_assertion(text) == []
    hits = detect_negation_restriction_pivot(text)
    assert any(h["variant"] == "不X只Y" for h in hits)
    hit = next(h for h in hits if h["variant"] == "不X只Y")
    assert text[hit["start"]:hit["end"]] == hit["span"]
    assert "不掰开" in hit["span"]


def test_bare_mei_restriction_hit():
    text = "她没说话，只是看着他，目光落在别处。"
    hits = detect_negation_restriction_pivot(text)
    assert any(h["variant"] == "没X只Y" for h in hits)


def test_negation_restriction_dialogue_out_of_scope():
    text = "他说：「我不掰开，只是裹住。」然后收了手。"
    assert detect_negation_restriction_pivot(text) == []


def test_existing_bushi_pattern_still_hits_narration():
    text = "他停下来。不是想休息，而是腿已经不听使唤了。"
    hits = detect_contrastive_negation_assertion(text)
    assert any(h["variant"] == "不是A而是B" for h in hits)


def test_bare_restriction_hit_is_non_blocking_candidate():
    text = "山道无人。" * 100 + "老关按住他的手，不掰开，只是裹住。"
    r = analyze(text, scene_id="S01", lang="zh")
    hits = [h for h in r["hits"] if h["rule"] == "negation_restriction_pivot"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "contrastive_negation_assertion"]
    assert hits and all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []


def test_contrastive_single_hit_opens_alert():
    text = "山道无人。" * 100 + "他停下来。不是想休息，而是腿已经不听使唤了。"
    r = analyze(text, scene_id="S01", lang="zh")
    hits = [h for h in r["hits"] if h["rule"] == "contrastive_negation_assertion"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "contrastive_negation_assertion"]
    assert len(hits) == 1 and hits[0]["per_sentence"]
    assert len(alerts) == 1 and alerts[0]["hit_ids"] == [hits[0]["lint_id"]]


# ---------- 治理契约 ----------

def test_candidate_families_have_no_enforcement_override():
    assert effective_policy(
        "contrastive_negation_assertion", "zh", "negation_restriction_pivot")["lifecycle"] == "observe"


def test_contrastive_promotion_goes_through_contract():
    policy = effective_policy("contrastive_negation_assertion", "zh")
    assert policy["lifecycle"] == "enforced" and policy["single_hit"]
    assert not policy.get("pre_contract")
    assert PROMOTION_RECORDS[policy["promoted_ref"]]["family"] == "contrastive_negation_assertion"
    assert "contrastive_negation_assertion" in BASELINE_EXEMPT_FAMILIES
    assert PER_FAMILY_OVERRIDE["contrastive_negation_assertion"] == {"same_family_scene_count_gte": 1}


def test_candidate_families_have_no_calibrated_baseline():
    for lang, table in FAMILY_DENSITY_BASELINE.items():
        assert "contrastive_negation_assertion" not in table, f"{lang} 尚无可用于决策的校准基线"
