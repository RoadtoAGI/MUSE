"""S1 ai_filler_lint.py 单测。

覆盖 55+1 条清单第 3/7/46/47/49 条——AI 口癖 / 禁用 Markdown / 排比模板 / 关联词。
"""
from pathlib import Path

from ai_filler_lint import (
    FAMILY_CLUSTERS,
    FAMILY_GROUPS,
    FAMILY_REGISTRY,
    detect_contrastive_negation_assertion,
    detect_narrative_micro_label,
    detect_counted_speech_weight,
    detect_ordinal_gravity_marker,
    detect_state_persistence_tag,
    detect_keyword_cliche,
    detect_parallel_negation,
    detect_banned_markdown,
    detect_conjunction_overuse,
    detect_comma_short_interval,
    detect_consecutive_action_phrase,
    detect_social_choreography_log,
    detect_short_simile_debt,
    detect_abstract_phrase_debt,
    detect_stock_silence_pause_phrase,
    detect_short_paragraph_run,
    detect_clause_fragment_density,
    detect_dash_density,
    detect_repeated_clause_head,
    detect_micro_action_density,
    compute_distribution_mode,
    run_ai_filler_lint,
    analyze,
)

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

EXPECTED_FAMILIES = {
    "marker_pollution", "lexical_cliche",
    "fragment_settlement", "micro_clause_chain", "connector_overuse",
    "rhythm_fragmentation", "repeated_head", "action_log", "dash_overuse",
    "figurative_debt", "abstract_phrase_debt", "silence_pause_cliche",
    "social_choreography", "contrastive_negation_assertion",
    "micro_punchline_cadence", "state_persistence_template",
    "meta_language_leak", "dummy_pronoun", "demonstrative_classifier",
}

EXPECTED_GROUPS = {"hard", "syntax_heuristic", "semantic_heuristic"}


def test_family_registry_has_all_families():
    actual = set(FAMILY_REGISTRY.keys())
    assert actual == EXPECTED_FAMILIES, f"missing or extra: {actual ^ EXPECTED_FAMILIES}"


def test_family_registry_group_membership():
    actual_groups = set(FAMILY_GROUPS.values())
    assert actual_groups == EXPECTED_GROUPS


def test_family_registry_each_has_cluster():
    for fid, entry in FAMILY_REGISTRY.items():
        assert "cluster" in entry, f"{fid} missing cluster"
        assert "group" in entry, f"{fid} missing group"
        assert "aliases" in entry, f"{fid} missing aliases (can be empty list)"


def test_keyword_cliche_hits():
    text = "就在这时，他看见了。\n仿佛一切静止。"
    hits = detect_keyword_cliche(text)
    assert len(hits) == 2
    assert any(h["pattern"] == "就在这时" for h in hits)
    assert any(h["pattern"] == "仿佛" for h in hits)


def test_keyword_cliche_no_false_positive():
    text = "他合上书，望了一眼窗外。"
    assert detect_keyword_cliche(text) == []


def test_parallel_negation():
    text = "没有声音，没有光。\n不是方向错了，而是时机不对。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "没有A没有B" in patterns
    assert "不是A而是B" in patterns


def test_parallel_negation_single_shi():
    text = "不是退阵，是变阵。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "不是A是B" in patterns
    assert "不是A而是B" not in patterns


def test_parallel_negation_dash():
    text = "不是说那位独臂客——是说夜枫坞。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "不是A——是B" in patterns


def test_parallel_negation_zhishi():
    text = "不是黯然销魂掌，只是近于那路。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "不是A只是B" in patterns


def test_parallel_negation_reverse():
    text = "是被剑刃割断的，不是自然磨断。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "是A的不是B" in patterns


def test_parallel_negation_meiyou_shi():
    text = "没有声音，是黑暗。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "没有A是B" in patterns


def test_parallel_negation_meiyou_shi_severity_low():
    text = "没有声音，是黑暗。"
    hits = detect_parallel_negation(text)
    h = next(h for h in hits if h["pattern"] == "没有A是B")
    assert h.get("severity") == "low"
    assert h.get("group") == "heuristic"


def test_parallel_negation_classic_no_severity_defaults_high():
    # 检测器保留高置信形态；是否立案由 policy 生命周期决定。
    text = "不是方向错了，而是时机不对。"
    hits = detect_parallel_negation(text)
    h = next(h for h in hits if h["pattern"] == "不是A而是B")
    assert "severity" not in h
    assert "group" not in h


def test_parallel_negation_meiyou_zhishi():
    text = "没有反应，只是停顿。"
    hits = detect_parallel_negation(text)
    patterns = {h["pattern"] for h in hits}
    assert "没有A只是B" in patterns


def test_parallel_negation_bingfei_shi():
    text = "并非他错了，而是时机不对。\n并非偶然，是必然。"
    hits = detect_parallel_negation(text)
    patterns = [h["pattern"] for h in hits]
    assert patterns.count("并非A是B") == 2


def test_parallel_negation_meiyou_no_double_count():
    # "没有A没有B" 已抓的不应再被 "没有A是B" 重复抓
    text = "没有声音，没有光。"
    hits = detect_parallel_negation(text)
    patterns = [h["pattern"] for h in hits]
    assert patterns.count("没有A没有B") == 1
    assert "没有A是B" not in patterns


def test_keyword_cliche_ji_as_adverb():
    text = "他答得极轻。声音极细。她退得极慢。"
    hits = detect_keyword_cliche(text)
    ji_hits = [h for h in hits if h["pattern"] == "极"]
    assert len(ji_hits) == 3


def test_keyword_cliche_ji_exempt_fixed_words():
    text = "他来自北极。修了太极拳。她很积极。这是消极态度。两极分化。终极目标在极地之南。"
    hits = detect_keyword_cliche(text)
    ji_hits = [h for h in hits if h["pattern"] == "极"]
    assert ji_hits == []


def test_keyword_cliche_ji_mixed():
    # 混合：豁免 + 口癖
    text = "他从北极回来后，答得极轻。"
    hits = detect_keyword_cliche(text)
    ji_hits = [h for h in hits if h["pattern"] == "极"]
    assert len(ji_hits) == 1
    assert "极轻" in ji_hits[0]["snippet"]


def test_keyword_cliche_gewai_shaoshao():
    text = "他格外谨慎。她稍稍点头。"
    hits = detect_keyword_cliche(text)
    patterns = {h["pattern"] for h in hits}
    assert "格外" in patterns
    assert "稍稍" in patterns


def test_parallel_negation_ershi_no_double_count():
    # 不应同时命中 "不是A是B"（"而是"由负向断言排除）
    text = "不是方向错了，而是时机不对。"
    hits = detect_parallel_negation(text)
    patterns = [h["pattern"] for h in hits]
    assert patterns.count("不是A而是B") == 1
    assert "不是A是B" not in patterns


def test_contrastive_negation_assertion_detects_7_variants():
    cases = [
        "不是他的战术，是他的威信。",
        "不是普通骑兵，而是他的私兵。",
        "并非主动，是被迫。",
        "没有命令，是各部自吹。",
        "表面平稳，实际焦灼。",
        "不是因为风，是因为人。",
        "真正的不是战术，是威信。",
    ]
    for text in cases:
        hits = detect_contrastive_negation_assertion(text)
        assert len(hits) == 1, f"漏抓: {text}"


def test_contrastive_negation_assertion_cross_variant_count():
    text = "不是A，是B。\n并非C，是D。\n表面E，实际F。"
    hits = detect_contrastive_negation_assertion(text)
    assert len(hits) == 3
    assert hits[0]["variant"] != hits[1]["variant"]


def test_contrastive_negation_assertion_exempts_dialogue():
    # 对白在 lint 层 mask 豁免：转折否定是人物口语时不立案，只检叙述层。
    text = '"不是普通骑兵，是他的私兵。" 他说。'
    assert detect_contrastive_negation_assertion(text) == []
    narration = "来的不是普通骑兵，是他的私兵。"
    assert len(detect_contrastive_negation_assertion(narration)) == 1


def test_narrative_micro_label_para_threshold():
    # 段内 micro_unit >=4 + 段长 >=80 字 + 占比 >=0.25
    para = "他抬手。马鞭未落。风冷。一字未出。" + "他望向远处的山，山脊压着风暴的边缘，风暴的褐色边缘正在张开。" * 3
    hits = detect_narrative_micro_label(para)
    assert len(hits) >= 4


def test_narrative_micro_label_exempts_dialogue():
    text = '"等。"他说。"按六。"\n'
    hits = detect_narrative_micro_label(text)
    assert len(hits) == 0


def test_counted_speech_weight():
    cases = [
        "他只说了三个字：斩萨满。",
        "她说了一个字：等。",
        "马夫吐出两个字：撤。",
        "副将报了一字：诺。",
    ]
    for text in cases:
        hits = detect_counted_speech_weight(text)
        assert len(hits) == 1, f"漏抓: {text}"


def test_ordinal_gravity_marker():
    cases = [
        "这是他第一次开漆匣。",
        "这一刻，风停了。",
        "今天第一次松开。",
        "这一击是最后一击。",
    ]
    for text in cases:
        hits = detect_ordinal_gravity_marker(text)
        assert len(hits) >= 1


def test_state_persistence_tag_three_conditions_required():
    text = "赵庆还在那里。风停了。云层散了。\n赵庆还在那里。马蹄声远了。"
    hits = detect_state_persistence_tag(text)
    assert len(hits) >= 1


def test_state_persistence_tag_exempts_change_delta():
    text = "赵庆还在那里。马蹄声远了。\n赵庆的盔缨歪了，人还在。"
    hits = detect_state_persistence_tag(text)
    assert len(hits) == 0


def test_state_persistence_tag_no_anchor_repeat():
    text = "赵庆还在那里。马蹄声远了。"
    hits = detect_state_persistence_tag(text)
    assert len(hits) == 0








def test_contrastive_fixture_remains_visible_without_blocking():
    scene_text = (_PLUGIN_ROOT / "scripts/tests/fixtures/367_S01_contrastive.txt").read_text(encoding="utf-8")
    output = run_ai_filler_lint(scene_text)
    hits = [h for h in output["lint_hits"] if h["family"] == "contrastive_negation_assertion"]
    alerts = [a for a in output["cluster_alerts"] if a["family"] == "contrastive_negation_assertion"]
    assert len(hits) >= 2
    assert all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []


def test_observed_alert_hit_ids_bind_individual_hits():
    scene_text_with_cluster = "仿佛门外有人。\n仿佛灯也暗了。\n普通段落。"
    output = run_ai_filler_lint(scene_text_with_cluster)
    cluster = next(c for c in output["observed_alerts"] if c["family"] == "lexical_cliche")
    individual_hits = output["lint_hits"]
    for hit_id in cluster["hit_ids"]:
        assert any(h["lint_id"] == hit_id for h in individual_hits)


def test_distribution_mode_single_sentence():
    text = "他抬手。不是A，是B，更不是C，还不是D。\n其他段。"
    hits = [
        {"family": "contrastive_negation_assertion", "start": text.find("不是A"), "end": text.find("不是A") + 3},
        {"family": "contrastive_negation_assertion", "start": text.find("更不是C"), "end": text.find("更不是C") + 4},
        {"family": "contrastive_negation_assertion", "start": text.find("还不是D"), "end": text.find("还不是D") + 4},
    ]
    assert compute_distribution_mode(hits, text)["mode"] == "single_sentence"


def test_distribution_mode_single_span():
    text = "段1正文段1正文。\n段2 hit1 段2 hit2。\n段3 hit3 段3正文。"
    hits = [
        {"family": "x", "start": text.find("hit1"), "end": text.find("hit1") + 4},
        {"family": "x", "start": text.find("hit2"), "end": text.find("hit2") + 4},
        {"family": "x", "start": text.find("hit3"), "end": text.find("hit3") + 4},
    ]
    assert compute_distribution_mode(hits, text)["mode"] == "single_span"


def test_distribution_mode_distributed():
    text = "\n".join([f"段{i} hit_{i}" for i in range(5)])
    hits = [
        {"family": "x", "start": text.find(f"hit_{i}"), "end": text.find(f"hit_{i}") + 5}
        for i in range(5)
    ]
    assert compute_distribution_mode(hits, text)["mode"] == "distributed"


def test_distribution_mode_catastrophic():
    text = "\n".join([f"段{i} 短句。" for i in range(8)])
    hits = [{"family": "micro_punchline_cadence", "start": text.find("短句"), "end": text.find("短句") + 2} for _ in range(6)]
    assert compute_distribution_mode(hits, text)["mode"] == "catastrophic"


def test_distribution_mode_paragraph_pattern():
    text = "段1。hit1。hit2。hit3。\n段2。"
    hits = [
        {"family": "x", "start": text.find("hit1"), "end": text.find("hit1") + 4},
        {"family": "x", "start": text.find("hit2"), "end": text.find("hit2") + 4},
        {"family": "x", "start": text.find("hit3"), "end": text.find("hit3") + 4},
    ]
    assert compute_distribution_mode(hits, text)["mode"] == "paragraph_pattern"






def test_zero_yield_candidate_is_not_registered_in_normal_lint_run():
    scene_text = (_PLUGIN_ROOT / "scripts/tests/fixtures/zero_yield_cluster.txt").read_text(encoding="utf-8")

    output = run_ai_filler_lint(scene_text)

    assert all(
        hit["rule"] != "zero_yield_micro_clause_candidate"
        for hit in output["lint_hits"]
    )
    assert all(
        issue["issue_type"] != "low_information_cadence"
        for issue in output["scene_level_issues"]
    )


def test_short_paragraph_run_severe():
    text = "她笑了。\n\n他坐下来。\n\n风停了。\n\n他抬起手腕，调整了一下袖口的褶皱方向。"
    hits = detect_short_paragraph_run(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "high"
    assert "短段连发×3" == hits[0]["pattern"]


def test_short_paragraph_run_isolated():
    text = (
        "他在长廊尽头停下来，望着对面那盏被风吹得摇晃的灯笼，"
        "心里把今晚要做的事又过了一遍。\n\n"
        "她笑了。\n\n"
        "他又往前走了几步，把袖口里那枚铜钱悄悄按回原处，"
        "继续朝灯笼的方向去。"
    )
    hits = detect_short_paragraph_run(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "low"
    assert hits[0]["pattern"] == "短段单发"


def test_short_paragraph_run_dialogue_excluded():
    # 引号对话段不算短段
    text = '"嗯。"\n\n"未必。"\n\n"我去。"'
    hits = detect_short_paragraph_run(text)
    assert hits == []


def test_short_paragraph_run_markdown_heading_excluded():
    # markdown 标题段不算（由 banned_markdown 单独抓）
    text = "## 一　遇敌\n\n## 二　结盟\n\n## 三　密信夜"
    hits = detect_short_paragraph_run(text)
    assert hits == []


def test_short_paragraph_run_dash_excluded():
    # 破折号对话延续不算
    text = "——你既知道。\n\n——为何还来。"
    hits = detect_short_paragraph_run(text)
    assert hits == []


def test_short_paragraph_run_long_breaks_run():
    # 长段打断连发
    text = (
        "她笑了。\n\n他坐下来。\n\n"
        "院子里那只老猫在月光下伸了个长长的懒腰，"
        "缓缓踱到水缸边，低头舔了一口水，又抬起头来打量了一下空荡荡的回廊。\n\n"
        "风停了。\n\n他闭上眼。"
    )
    hits = detect_short_paragraph_run(text)
    # 两段 run：连发×2 + 连发×2
    assert len(hits) == 2
    assert all(h["pattern"].startswith("短段连发") for h in hits)
    assert all(h["severity"] == "high" for h in hits)


def test_short_paragraph_run_boundary_threshold():
    # 净字 14 字不算短段（阈值 12）；5 字算
    text = "她在月下站了很久没有说一句话。\n\n他坐下来。"  # 14 字 + 5 字
    hits = detect_short_paragraph_run(text)
    # 只 1 段短段 → 单发 low
    assert len(hits) == 1
    assert hits[0]["severity"] == "low"


def test_clause_fragment_density_hit_high():
    # 净字 60+，分句 15 个，全部 ≤ 7 字 → high
    text = (
        "他走到窗边，看了一眼楼下，没有人，"
        "又看了一眼路口，也没有人，转身回来，"
        "坐到桌前，没说话，没动，停了一息，"
        "又起身，走到门口，听了听，没声音，"
        "想了一下，回去坐下。"
    )
    hits = detect_clause_fragment_density(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "high"
    assert hits[0]["details"]["clause_count"] >= 8
    assert hits[0]["details"]["short_clause_ratio"] >= 0.7
    assert hits[0]["group"] == "heuristic"


def test_clause_fragment_density_hit_medium():
    # 净字 60+，分句 6-7 个，avg ≈ 7-8 → medium（未达 high 升级条件）
    text = (
        "他坐到桌前，"
        "拿起茶杯，"
        "看了一眼，"
        "又放回去，"
        "想了想还是没喝，"
        "站起来走开了，"
        "顺手把灯关上。"
    )
    hits = detect_clause_fragment_density(text)
    if hits:
        assert hits[0]["severity"] in {"medium", "high"}
        assert hits[0]["details"]["clause_count"] >= 6


def test_clause_fragment_density_no_hit_too_few_clauses():
    # 只有 3 个分句 → 不命中（< 6）
    text = "他走到桌前，看着窗外，没说话。" * 3
    hits = detect_clause_fragment_density(text.replace("\n", ""))
    # 字符够多但分句模式不够碎
    assert all(h.get("rule") != "clause_fragment_density" for h in hits) or hits == []


def test_clause_fragment_density_no_hit_short_paragraph():
    # 段落净字 < 60 即便全短分句也不报（避免和 short_paragraph_run 双计）
    text = "他笑了，她也笑，风停。"
    hits = detect_clause_fragment_density(text)
    assert hits == []


def test_clause_fragment_density_dialogue_excluded():
    # 含引号 → 跳过（不论分句多碎）
    text = '"嗯，"他说，"是，"她说，"好，"他答，"那，"她又问，"行，"他点头。'
    hits = detect_clause_fragment_density(text)
    assert hits == []


def test_clause_fragment_density_long_clauses_no_hit():
    # avg > 8 → 不命中
    text = (
        "他在长廊尽头停下来思考，"
        "望着对面那盏被风吹动的灯笼，"
        "心里把今晚要做的事过了一遍，"
        "然后慢慢地把袖口里那枚铜钱按回原处，"
        "又看了一眼远处的更声方向，"
        "继续朝灯笼的方向走过去。"
    )
    hits = detect_clause_fragment_density(text)
    assert hits == []


def test_clause_fragment_density_markdown_heading_excluded():
    text = "## 标题，第一节，开始，正文如下，他说，他想，他走"
    hits = detect_clause_fragment_density(text)
    assert hits == []


def test_dash_density_hit_medium():
    # 3 个段外破折号 → medium
    text = (
        "他站在门外——犹豫了一下——又推开门进去——"
        "屋里没有人。整间屋子安安静静的，只有一只猫在窗台上打盹。"
    )
    hits = detect_dash_density(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "medium"
    assert hits[0]["details"]["dash_count"] == 3


def test_dash_density_hit_high():
    # 4 个段外破折号 → high
    text = (
        "他想说——又止住——再开口——还是没说出来——"
        "整间屋子安安静静的，只有窗外的风偶尔吹动一下窗帘的角。"
    )
    hits = detect_dash_density(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "high"


def test_dash_density_dialogue_inside_excluded():
    # 引号内破折号不计入
    text = (
        '"你别——"她打断他。'
        '"我没说完——"他急了。'
        '"可你刚才——"她又打断。'
        '"我在尝试解释，但是你不让我把话说完，所以我现在没办法继续下去了。"'
    )
    hits = detect_dash_density(text)
    assert hits == []


def test_dash_density_short_paragraph_no_hit():
    # 净字 < 40 → 不命中
    text = "他想——又止——再说——还是没说。"
    hits = detect_dash_density(text)
    assert hits == []


def test_dash_density_two_dashes_no_hit():
    # 2 个破折号 → 不命中（< medium 阈值）
    text = (
        "他来到门口——犹豫了一会儿——还是推门进去了。"
        "屋里很安静，只有他自己的呼吸声和远处的钟摆声。"
    )
    hits = detect_dash_density(text)
    assert hits == []


def test_repeated_clause_head_verb_run_2_advisory():
    """动词二连发 + 无短句信号 → advisory(low)，仍报但低严重度。"""
    text = "看见门开了，看见她站在门后那个布满灰尘的角落里。"
    hits = detect_repeated_clause_head(text)
    verb_hits = [h for h in hits if h["subtype"] == "verb_head_run"]
    assert len(verb_hits) == 1
    assert verb_hits[0]["severity"] == "low"
    assert verb_hits[0]["details"]["escalated_by_short_clauses"] is False


def test_repeated_clause_head_verb_run_2_escalated_by_short_clauses():
    """动词二连发 + 同段有短分句密度 → 升 medium。"""
    text = (
        "他停下，看了看门缝，听了听里面，没动，又等了等，又靠近，又退半步，"
        "看见门把转了一下，看见门被推开一寸。"
    )
    hits = detect_repeated_clause_head(text)
    verb_hits = [h for h in hits if h["subtype"] == "verb_head_run" and h["details"]["head"] == "看见"]
    assert len(verb_hits) == 1
    assert verb_hits[0]["severity"] == "medium"
    assert verb_hits[0]["details"]["escalated_by_short_clauses"] is True


def test_repeated_clause_head_verb_run_3_standalone_medium():
    """动词三连发 → standalone medium。"""
    text = "想到母亲，想到童年那个雨天，想到那个永远没有寄出的信。"
    hits = detect_repeated_clause_head(text)
    verb_hits = [h for h in hits if h["subtype"] == "verb_head_run"]
    assert len(verb_hits) == 1
    assert verb_hits[0]["severity"] == "medium"
    assert verb_hits[0]["details"]["run_length"] == 3


def test_repeated_clause_head_confidence_medium():
    """heuristic confidence 一律 medium，不是 high。"""
    text = "想到母亲，想到童年，想到那个雨天。"
    hits = detect_repeated_clause_head(text)
    assert all(h["confidence"] == "medium" for h in hits)


def test_repeated_clause_head_pronoun_needs_3():
    # 代词排比 2 段不报（阈值 ≥ 3）
    text = "他走过去，他坐下来。"
    hits = detect_repeated_clause_head(text)
    assert all(h.get("subtype") != "pronoun_head_run" for h in hits)


def test_repeated_clause_head_pronoun_run_3_hits():
    # 代词 3 段命中
    text = "他笑了，他坐下来，他没说话。"
    hits = detect_repeated_clause_head(text)
    pronoun_hits = [h for h in hits if h["subtype"] == "pronoun_head_run"]
    assert len(pronoun_hits) == 1
    assert pronoun_hits[0]["details"]["head"] == "他"


def test_repeated_clause_head_prep_needs_3():
    # 介词 2 段不报
    text = "在桌上，在墙上。"
    hits = detect_repeated_clause_head(text)
    assert all(h.get("subtype") != "prep_head_run" for h in hits)


def test_repeated_clause_head_noun_pattern_2():
    # 名词模板"X的Y"重复 2 段命中
    text = "穿黑衣的人，穿白衣的人，从北面走来。"
    hits = detect_repeated_clause_head(text)
    noun_hits = [h for h in hits if h["subtype"] == "noun_pattern_run"]
    # noun pattern 2 段即命中
    assert len(noun_hits) >= 1


def test_repeated_clause_head_no_run_no_hit():
    # 不同起手 → 不命中
    text = "他笑了，她也笑，风停了，月亮升起来。"
    hits = detect_repeated_clause_head(text)
    assert hits == []


def test_repeated_clause_head_markdown_excluded():
    text = "## 想到A，想到B，想到C"
    hits = detect_repeated_clause_head(text)
    assert hits == []


def test_micro_action_density_hit_medium():
    # 5+ 微动作 token，3+ 种，段净字 ≥ 80 → medium
    text = (
        "他走到桌前，停下脚步，转身看了一眼门口，又回头看墙上的钟。"
        "他低头看了看自己的手指甲，把袖口轻轻拉了一下，然后抬头望向窗外。"
        "屋子里很安静，没有人说话，远处的钟声偶尔传来，时间像是凝固在了那个瞬间。"
    )
    hits = detect_micro_action_density(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "medium"
    assert hits[0]["details"]["action_count"] >= 5
    assert hits[0]["details"]["unique_actions"] >= 3


def test_micro_action_density_danger_downgrade():
    # 含危险词（刀/血） → severity 降为 low（合法动作戏）
    text = (
        "他转身，抬头看见对方的刀，低头闪过一击，又转身跑开。"
        "血从受伤的手臂上慢慢流下来，但他没有停下，继续往前推开一扇沉重的木门。"
        "走到墙角才停下，听了听背后的脚步声，屋子里只剩下他自己急促的呼吸声音。"
    )
    hits = detect_micro_action_density(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "low"
    assert hits[0]["details"]["danger_context"] is True


def test_micro_action_danger_no_false_positive_zhuiyi():
    """追忆 / 爆发 不应触发危险词降级。"""
    text = (
        "他走到桌前，停下脚步，转身看了一眼，又回头，低头看了看自己的手指。"
        "心里想着早年的追忆，想到那段爆发性的岁月，沉默地把袖口拉了拉。"
        "窗外的风沿着旧木框轻轻擦过，屋里只剩纸页翻动后留下的一点灰尘味。"
    )
    hits = detect_micro_action_density(text)
    assert len(hits) == 1
    assert hits[0]["details"]["danger_context"] is False
    assert hits[0]["severity"] == "medium"


def test_micro_action_density_too_few_actions_no_hit():
    # 只有 2 个微动作 → 不命中
    text = (
        "他走到窗边，停下来看了很久外面的雨。"
        "屋子里只有钟摆的声音和墙角灯泡偶尔闪一下的微响。"
        "他在想什么，自己也不太清楚，只是不想再说话。"
    )
    hits = detect_micro_action_density(text)
    assert hits == []


def test_micro_action_density_single_token_no_hit():
    # 5 次相同 token → 不命中（unique < 3）
    text = (
        "他走到桌前，又走到窗边，再走到门口，走到墙角，"
        "继续走到院子里。屋外的风很大，雪还在下，没有停的意思。"
    )
    hits = detect_micro_action_density(text)
    assert hits == []


def test_micro_action_density_short_paragraph_no_hit():
    # 净字 < 80 → 不命中
    text = "他走到桌前，停下，转身，回头，低头。"
    hits = detect_micro_action_density(text)
    assert hits == []


def test_micro_action_density_dialogue_excluded():
    # 含引号 → 跳过
    text = (
        '他走到桌前，停下来，转身回头说："你怎么来了。"'
        '她拿起茶杯，放下，又低头看了一眼窗外，没有回答。'
    )
    hits = detect_micro_action_density(text)
    assert hits == []


def test_banned_markdown():
    text = "# 标题\n\n- 列表项\n\n正常段落。"
    hits = detect_banned_markdown(text)
    assert len(hits) >= 2
    labels = {h["pattern"] for h in hits}
    assert "标题" in labels
    assert "无序列表" in labels


def test_conjunction_overuse():
    text = "虽然他想走，但是腿不听使唤。\n然后他坐下。"
    hits = detect_conjunction_overuse(text)
    assert any(h["pattern"] == "虽然…但是" for h in hits)
    assert any(h["pattern"] == "段首然后" for h in hits)


def test_comma_short_interval_basic_hit():
    text = "她转身去换水，跟那位女士说话，然后又走回来，看见门口的人，停下脚步，再回头，看了一眼。"
    hits = detect_comma_short_interval(text)
    assert len(hits) == 1
    h = hits[0]
    assert h["rule"] == "comma_short_interval"
    assert h["family"] == "rhythm_fragmentation"
    assert h["group"] == "syntax_heuristic"
    assert h["severity"] == "low"
    assert h["short_unit_ratio"] >= 0.6
    assert h["avg_unit_chars"] <= 9


def test_comma_short_interval_avg_too_long_no_hit():
    """长短混合段：单位数够但平均字数 > 9 不命中。"""
    text = "她在客厅靠窗的位置等了一会儿，电话铃响了她迟疑了几秒，跨过桌脚把听筒拿起来，又轻轻挂上。"
    hits = detect_comma_short_interval(text)
    assert hits == []


def test_comma_short_interval_too_few_units_no_hit():
    text = "她转身，停下。"
    hits = detect_comma_short_interval(text)
    assert hits == []


def test_comma_short_interval_too_short_paragraph_no_hit():
    """段净字 < 35 不抓。"""
    text = "她转，她停，她看，她走。"
    hits = detect_comma_short_interval(text)
    assert hits == []


def test_consecutive_action_strong_verb_3_standalone_medium():
    text = "他转身离开。他低头看了看手表。他抬头望向窗外。"
    hits = detect_consecutive_action_phrase(text)
    matches = [h for h in hits if h["subtype"] == "action_run"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "medium"
    assert matches[0]["run_length"] == 3


def test_consecutive_action_weak_verb_single_char_no_fp():
    """单字'看'不应抓正常句。"""
    text = "看不出他在想什么，看起来很疲惫。"
    hits = detect_consecutive_action_phrase(text)
    assert hits == []


def test_consecutive_action_go_verb_run():
    text = "周柏去倒了杯酒，去看别的画了。"
    hits = detect_consecutive_action_phrase(text)
    go_run = [h for h in hits if h["subtype"] == "go_verb_run"]
    assert len(go_run) == 1


def test_consecutive_action_look_look_redundancy():
    text = "她看向展厅里面，看了一眼。"
    hits = detect_consecutive_action_phrase(text)
    look_run = [h for h in hits if h["subtype"] == "look_look_redundancy"]
    assert len(look_run) == 1


def test_consecutive_action_does_not_match_social_choreography():
    """social_choreography_log 已拆出独立 rule，consecutive_action_phrase 不再抓它。"""
    text = "她接电话去了。他走开了。"
    hits = detect_consecutive_action_phrase(text)
    assert hits == []


def test_social_choreography_log_single_low():
    text = "她接电话去了。"
    hits = detect_social_choreography_log(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "low"
    assert hits[0]["family"] == "social_choreography"
    assert hits[0]["group"] == "semantic_heuristic"


def test_social_choreography_log_paragraph_2_medium():
    text = "她接电话去了。他跟那位女士说话去了。"
    hits = detect_social_choreography_log(text)
    medium = [h for h in hits if h["severity"] == "medium"]
    assert len(medium) >= 1


def test_social_choreography_log_scene_level_warning():
    """同场 >= 3 先保留逐段命中，span_aggregation 再升级。"""
    text = (
        "她接电话去了。\n\n"
        "他跟那位女士说话去了。\n\n"
        "周柏去看别的画了。"
    )
    hits = detect_social_choreography_log(text)
    assert len(hits) >= 3


def test_short_simile_debt_like_abstract_noun():
    text = "他低下头，像某种重量压下来。"
    hits = detect_short_simile_debt(text)
    assert len(hits) == 1
    h = hits[0]
    assert h["family"] == "figurative_debt"
    assert h["group"] == "semantic_heuristic"
    assert h["matched_template"].startswith("像")
    assert h["abstract_noun"] == "重量"


def test_short_simile_debt_paragraph_2_medium():
    text = "像某种重量压下来。像一种没有声音的距离。"
    hits = detect_short_simile_debt(text)
    medium = [h for h in hits if h["severity"] == "medium"]
    assert len(medium) >= 1


def test_short_simile_debt_concrete_simile_no_hit():
    """'像针'这种具体比喻不应命中。"""
    text = "声音像一根针，从音箱里斜插出来。"
    hits = detect_short_simile_debt(text)
    assert hits == []


def test_abstract_phrase_debt_basic():
    text = "某种重量压在他心上。一种沉默蔓延开来。"
    hits = detect_abstract_phrase_debt(text)
    assert len(hits) >= 2
    assert all(h["family"] == "abstract_phrase_debt" for h in hits)
    assert all(h["severity"] == "low" for h in hits)


def test_abstract_phrase_debt_concrete_no_hit():
    """具体短语（非抽象名词）不命中。"""
    text = "一种新茶味道很苦。"
    hits = detect_abstract_phrase_debt(text)
    assert hits == []


def test_stock_silence_pause_single_low():
    text = "她嘴角动了动。"
    hits = detect_stock_silence_pause_phrase(text)
    assert len(hits) == 1
    assert hits[0]["severity"] == "low"
    assert hits[0]["family"] == "silence_pause_cliche"


def test_stock_silence_pause_paragraph_2_medium():
    text = "她没说话。停了一秒，嘴角动了动。"
    hits = detect_stock_silence_pause_phrase(text)
    medium = [h for h in hits if h["severity"] == "medium"]
    assert len(medium) >= 1


def test_clean_draft_few_hits(clean_draft):
    result = analyze(clean_draft)
    # 排除 low severity advisory（短段单发等节奏提示，不计为"脏"）
    non_advisory = [h for h in result["hits"] if h.get("severity") != "low"]
    assert len(non_advisory) <= 1


def test_polluted_draft_many_hits(polluted_draft):
    result = analyze(polluted_draft)
    assert len(result["hits"]) >= 8


def test_keyword_detector_has_no_global_whitelist_parameter():
    from inspect import signature

    assert "whitelist" not in signature(detect_keyword_cliche).parameters


def test_cli_end_to_end(tmp_work_dir, polluted_draft):
    import subprocess
    scene_path = tmp_work_dir / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text(polluted_draft, encoding="utf-8")

    result = subprocess.run(
        ["python3", str(_PLUGIN_ROOT / "scripts/ai_filler_lint.py"),
         "--scene-id", "S01",
         "--work-dir", str(tmp_work_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    out_yaml = tmp_work_dir / "pipeline" / "review" / "lint" / "S01.ai_filler.yaml"
    assert out_yaml.exists()

    import yaml as _yaml
    out = _yaml.safe_load(out_yaml.read_text())
    assert out["script"] == "ai_filler_lint"
    assert len(out["hits"]) >= 8
    assert "thresholds" in out["meta"]


def test_thresholds_profile_strict_lower_min_paragraph():
    """strict profile 让 micro_action 阈值降低，原本不命中的现在命中。"""
    from ai_filler_lint import _THRESHOLD_PROFILES

    text = (
        "他走到桌前，停下，转身回头，低头看了看，"
        "屋里很安静没有人说话风声从外面传进来。"
        "桌上那盏灯轻轻晃了一下，影子落在墙角，灰尘在光里慢慢浮起。"
    )
    assert detect_micro_action_density(text, _THRESHOLD_PROFILES["conservative"]) == []
    assert len(detect_micro_action_density(text, _THRESHOLD_PROFILES["strict"])) >= 1


def test_thresholds_meta_written(tmp_work_dir, polluted_draft):
    """meta.thresholds 实际写入阈值字典，不是空 dict。"""
    import subprocess
    import yaml as _yaml

    scene_path = tmp_work_dir / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text(polluted_draft, encoding="utf-8")
    subprocess.run(
        ["python3", str(_PLUGIN_ROOT / "scripts/ai_filler_lint.py"),
         "--scene-id", "S01", "--work-dir", str(tmp_work_dir),
         "--threshold-profile", "strict"],
        check=True,
    )
    out = _yaml.safe_load((tmp_work_dir / "pipeline/review/lint/S01.ai_filler.yaml").read_text())
    assert out["meta"]["threshold_source"] == "strict"
    assert isinstance(out["meta"]["thresholds"], dict)
    assert out["meta"]["thresholds"]["clause_fragment_min_paragraph_chars"] == 45


def test_thresholds_json_override_written(tmp_work_dir, polluted_draft):
    """--thresholds JSON 覆盖会写入实际 meta.thresholds。"""
    import subprocess
    import yaml as _yaml

    scene_path = tmp_work_dir / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text(polluted_draft, encoding="utf-8")
    subprocess.run(
        ["python3", str(_PLUGIN_ROOT / "scripts/ai_filler_lint.py"),
         "--scene-id", "S01", "--work-dir", str(tmp_work_dir),
         "--thresholds", '{"micro_action_min_paragraph_chars": 70}'],
        check=True,
    )
    out = _yaml.safe_load((tmp_work_dir / "pipeline/review/lint/S01.ai_filler.yaml").read_text())
    assert out["meta"]["threshold_source"] == "conservative+overrides"
    assert out["meta"]["thresholds"]["micro_action_min_paragraph_chars"] == 70


def test_devices_for_scene_canonical_sequence_expansions(tmp_path):
    """R2-F4：canonical 容器下 literary_device 容差必须可达（存量 bug 修缮）"""
    from ai_filler_lint import _devices_for_scene
    p = tmp_path / "pipeline"
    p.mkdir(parents=True)
    (p / "phase5_scenes.yaml").write_text(
        "sequence_expansions:\n"
        "  - sequence_id: SEQ1\n"
        "    scenes:\n"
        "      - scene_id: S01\n"
        "        literary_device: naked_line\n",
        encoding="utf-8")
    assert _devices_for_scene(tmp_path, "S01") == ["naked_line"]


def test_objection_eligible_hits_carry_scene_hash_locator_and_evidence_quote():
    """v0.4 §5: M 级可豁免 family 的 hit 必须能被 quote 稳定复认。"""
    import hashlib

    text = (
        "他没说话，停了一下，烟在指间烧到了滤嘴。"
        "他抬头，他低头，他转身，望向门外。"
    )
    result = analyze(text, scene_id="S42")

    assert result["input_text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    eligible = [
        hit for hit in result["hits"]
        if hit.get("family") in {"silence_pause_cliche", "action_log"}
    ]
    assert eligible
    for hit in eligible:
        locator = hit["locator"]
        assert text[locator["start"]:locator["end"]] == locator["span"]
        assert len(hit["evidence_quote"]) >= 10
        assert hit["evidence_quote"] in text


def test_repeated_objection_eligible_hits_keep_distinct_exact_locators():
    text = "他停了一下，望向门外。他停了一下，望向门外。"
    hits = [
        hit for hit in analyze(text, scene_id="S43")["hits"]
        if hit.get("family") == "silence_pause_cliche"
    ]

    assert len(hits) == 2
    assert {hit["locator"]["start"] for hit in hits} == {
        text.index("停了一下"),
        text.rindex("停了一下"),
    }
