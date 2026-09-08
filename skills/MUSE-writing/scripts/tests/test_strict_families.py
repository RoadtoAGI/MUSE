"""表面形态候选：光杆转折否定与碎切短分句链。

检测器保留定位能力；中文策略为 observe，机械命中不直接立案。
对白（引号内）不属于检测范围。
"""
from ai_filler_lint import (
    analyze,
    detect_contrastive_negation_assertion,
    detect_micro_clause_chain,
)
from ai_policy import (
    BASELINE_EXEMPT_FAMILIES,
    FAMILY_DENSITY_BASELINE,
    FAMILY_SOVEREIGNTY,
    PER_FAMILY_OVERRIDE,
    effective_policy,
)


# ---------- 光杆转折否定 ----------

def test_bare_negation_restriction_hit():
    text = "老关按住他要解甲绦的手，不掰开，只是裹住，把甲绦重新绕回去。"
    hits = detect_contrastive_negation_assertion(text)
    assert any(h["variant"] == "不X只Y" for h in hits)
    hit = next(h for h in hits if h["variant"] == "不X只Y")
    assert text[hit["start"]:hit["end"]] == hit["span"]
    assert "不掰开" in hit["span"]


def test_bare_mei_restriction_hit():
    text = "她没说话，只是看着他，目光落在别处。"
    hits = detect_contrastive_negation_assertion(text)
    assert any(h["variant"] == "没X只Y" for h in hits)


def test_negation_restriction_dialogue_out_of_scope():
    text = "他说：「我不掰开，只是裹住。」然后收了手。"
    assert detect_contrastive_negation_assertion(text) == []


def test_existing_bushi_pattern_still_hits_narration():
    text = "他停下来。不是想休息，而是腿已经不听使唤了。"
    hits = detect_contrastive_negation_assertion(text)
    assert any(h["variant"] == "不是A而是B" for h in hits)


def test_contrastive_single_hit_is_non_blocking_candidate():
    text = "山道无人。" * 100 + "老关按住他的手，不掰开，只是裹住。"
    r = analyze(text, scene_id="S01", lang="zh")
    hits = [h for h in r["hits"] if h["family"] == "contrastive_negation_assertion"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "contrastive_negation_assertion"]
    assert hits and all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []


# ---------- 碎切短分句链 ----------

def test_chain_hit_with_offsets():
    text = "他往右探了一下手，碰到空的，收回来，按住怀里那半袋炒麦。"
    hits = detect_micro_clause_chain(text)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["span"] == "碰到空的，收回来"
    assert text[hit["start"]:hit["end"]] == hit["span"]
    assert hit["run_length"] == 2


def test_chain_two_clause_sentence_hits():
    text = "鸣金声起，各队点旗，什长挨个数人头。"
    hits = detect_micro_clause_chain(text)
    assert len(hits) == 1
    assert hits[0]["span"] == "鸣金声起，各队点旗"


def test_single_short_clause_not_hit():
    """孤立短分句（前后都是长分句）不构成链。"""
    text = "掰不开自己握弩的手指，弯着，扣弩机的形状怎么也伸不直。"
    assert detect_micro_clause_chain(text) == []


def test_seven_char_clause_not_hit():
    text = "他扶着墙站起来了，朝着门口走过去了。"
    assert detect_micro_clause_chain(text) == []


def test_chain_dialogue_out_of_scope():
    text = "他只报数：「陌刀营，还剩一千六。」说完就站到帅台底下。"
    assert detect_micro_clause_chain(text) == []


def test_enumeration_not_split():
    """顿号列举不切分句读，不构成链。"""
    text = "案上摆着刀、弓、箭囊，都是他用惯的旧物。"
    assert detect_micro_clause_chain(text) == []


def test_chain_single_hit_is_non_blocking_candidate():
    text = "山道无人。" * 100 + "他探了一下手，碰到空的，收回来。"
    r = analyze(text, scene_id="S02", lang="zh")
    hits = [h for h in r["hits"] if h["family"] == "micro_clause_chain"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "micro_clause_chain"]
    assert hits and all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []


def test_colloquial_micro_clause_run_is_retained_as_non_blocking_sample():
    text = "\n".join(
        f"他进第{i}间门，放下书，喊一声。"
        for i in range(1, 9)
    )
    r = analyze(text, scene_id="S03", lang="zh")
    hits = [h for h in r["hits"] if h["family"] == "micro_clause_chain"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "micro_clause_chain"]
    assert len(hits) >= 8
    assert all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []


# ---------- 治理契约 ----------

def test_candidate_families_have_no_enforcement_override():
    for family in ("contrastive_negation_assertion", "micro_clause_chain"):
        assert effective_policy(family, "zh")["lifecycle"] == "observe"
        assert family not in FAMILY_SOVEREIGNTY
        assert family not in PER_FAMILY_OVERRIDE
        assert family not in BASELINE_EXEMPT_FAMILIES

    assert effective_policy("lexical_cliche", "zh", "parallel_negation")["lifecycle"] == "observe"


def test_candidate_families_have_no_calibrated_baseline():
    for lang, table in FAMILY_DENSITY_BASELINE.items():
        for family in ("contrastive_negation_assertion", "micro_clause_chain"):
            assert family not in table, f"{lang}/{family} 尚无可用于决策的校准基线"
