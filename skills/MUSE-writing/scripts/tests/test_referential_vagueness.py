"""referential_vagueness 两族：dummy_pronoun（形式主宾语）+ demonstrative_classifier（这/那+量词）。

阈值制立案（名著场景 P90 基线，非单发）；enforced aggregate S + 密度合同
（promoted_ref 晋升，decision_ref=pronoun-density-2026-07-17：修订后密度须严格 <
名著基线）。对白 mask 豁免。
"""
from ai_filler_lint import (
    analyze,
    detect_demonstrative_classifier,
    detect_dummy_pronoun,
)
from ai_policy import (
    FAMILY_DENSITY_BASELINE,
    calibration_value,
    effective_policy,
)


# ---------- dummy_pronoun 形式主宾语 ----------

def test_formal_lexicon_hit_with_offset():
    text = "他把那东西塞回怀里，转身走了。"
    hits = detect_dummy_pronoun(text)
    assert len(hits) == 1
    assert hits[0]["pattern"] == "formal_lexicon"
    assert text[hits[0]["start"]:hits[0]["end"]] == hits[0]["span"] == "那东西"


def test_it_subject_and_object_anchored():
    text = "它趴在门口不动。老关嫌它响，把它踢到一边。"
    patterns = {h["pattern"] for h in detect_dummy_pronoun(text)}
    assert "it_subject" in patterns
    assert "it_object" in patterns


def test_bare_it_possessive_not_hit():
    """所有格/非主宾语位的'它'不锚定（'它的爪子'的'它'跟名词，不匹配动词谓语锚）。"""
    text = "老关看清了它的爪子上沾着泥。"
    assert all(h["pattern"] != "it_subject" for h in detect_dummy_pronoun(text))


def test_dummy_pronoun_dialogue_exempt():
    text = "他说：「这玩意到底是什么？把它扔了吧。」"
    assert detect_dummy_pronoun(text) == []


# ---------- demonstrative_classifier 这/那+量词 ----------

def test_classifier_hit():
    text = "这道口子比昨天深。他按住那片阴影不放。"
    hits = detect_demonstrative_classifier(text)
    assert {h["span"] for h in hits} == {"这道", "那片"}


def test_time_words_not_hit():
    """时间指示（这天/那年/这时）是常规语言，不入量词表。"""
    text = "这天早上他起得早，那年冬天的事这时又浮上来。"
    assert detect_demonstrative_classifier(text) == []


def test_ordinal_gravity_overlap_excluded():
    """这一刻/这一次归 ordinal_gravity 家族，本族不重复计。"""
    text = "这一刻他终于明白，这一次没有退路。"
    assert detect_demonstrative_classifier(text) == []


def test_classifier_dialogue_exempt():
    text = "「这把刀给你。」他递了过去。"
    assert detect_demonstrative_classifier(text) == []


# ---------- 阈值制与观测通道 ----------

def test_threshold_below_baseline_no_alert():
    """低于名著 P90 密度不立案（阈值制，与单发族不同）。"""
    filler = "山道上无人，风把旗吹得笔直，远处的号角断断续续。" * 80
    text = filler + "他把那东西塞回怀里。"
    r = analyze(text, scene_id="S01", lang="zh")
    assert not [a for a in r["cluster_alerts"] if a["cluster"] == "referential_vagueness"]
    assert not [a for a in r["observed_alerts"] if a["cluster"] == "referential_vagueness"]


def test_threshold_above_baseline_emits_locatable_enforced_alert():
    """守卫：超基线必须产 enforced cluster_alert（发牌端不可静默拆除）。

    晋升前该守卫锚 observed_alerts；enforced 化后锚 cluster_alerts——两个时期
    共同的不变量是"超基线必须立案且逐 hit 可定位"，不允许两通道都为空。
    """
    sick = "它趴在门口。他嫌它响，把它踢开，又把那东西捡回来。这话没人接。"
    text = sick * 6
    r = analyze(text, scene_id="S02", lang="zh")
    assert any(h["family"] == "dummy_pronoun" for h in r["hits"])
    alert = next(a for a in r["cluster_alerts"] if a["family"] == "dummy_pronoun")
    assert alert["density_per_1k"] > FAMILY_DENSITY_BASELINE["zh"]["dummy_pronoun"]
    assert alert["hit_ids"]
    assert [record["lint_id"] for record in alert["hit_records"]] == alert["hit_ids"]
    assert all(record["locator"]["span"] for record in alert["hit_records"])
    assert all(record["evidence_quote"] for record in alert["hit_records"])
    assert alert["escalation_threshold"]["high_gte"] == 4
    # S 级主权：拒逐处 objection，只收整簇改写
    assert alert["governance"]["individual_exemption_allowed"] is False
    assert all(
        h["policy_lifecycle"] == "enforced"
        for h in r["hits"] if h["family"] == "dummy_pronoun"
    )
    # enforced 化后不得再走观测通道（防双列造成消费端重复裁决）
    assert not any(
        a["family"] == "dummy_pronoun" for a in r["observed_alerts"]
    )


def test_families_have_zh_baseline_not_exempt():
    """阈值制正是靠名著基线——两族必须有 zh 基线（与 BASELINE_EXEMPT 单发族相反）。"""
    for family in ("dummy_pronoun", "demonstrative_classifier"):
        assert FAMILY_DENSITY_BASELINE["zh"][family] > 0
        policy = effective_policy(family, "zh")
        assert policy["lifecycle"] == "enforced"
        assert policy["sovereignty"] == "S"
        assert calibration_value(policy) == FAMILY_DENSITY_BASELINE["zh"][family]


def test_promotion_contract_fields():
    """晋升合同（§1.3）：promoted_ref 可解析、三证据腿齐全、密度合同挂载。"""
    from ai_policy import PROMOTION_RECORDS

    for family in ("dummy_pronoun", "demonstrative_classifier"):
        policy = effective_policy(family, "zh")
        assert policy.get("pre_contract") is None  # 晋升形态不是 grandfather 形态
        assert policy["density_contract"] is True
        record = PROMOTION_RECORDS[policy["promoted_ref"]]
        assert record["family"] == family and record["language"] == "zh"
        assert record["decision_ref"] == "pronoun-density-2026-07-17"
        assert policy["decision_ref"] == "pronoun-density-2026-07-17"
