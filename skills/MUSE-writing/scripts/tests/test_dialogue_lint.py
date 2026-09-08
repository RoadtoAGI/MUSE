"""S3 dialogue_lint.py 单测。

覆盖 55+1 条清单第 16/20/56 条 + 条 4 说话动词模板扩展。
"""
from pathlib import Path

from dialogue_lint import (
    extract_dialogue_blocks,
    detect_pure_dialogue,
    detect_ambiguous_referent,
    detect_template_speech_verb,
    detect_weak_character_expression_candidate,
)

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def test_extract_cn_dialogue():
    text = '他说："师父。"小龙女没回头。'
    blocks = extract_dialogue_blocks(text)
    assert any('"师父。"' in b["content"] or '"师父。"' in b["content"] for b in blocks)


def test_pure_dialogue_hit_isolated():
    """连续 3 段全引号、前后无描写 → 命中。"""
    text = '"A。"\n\n"B。"\n\n"C。"'
    hits = detect_pure_dialogue(text)
    assert len(hits) >= 1


def test_pure_dialogue_no_hit_when_neighbors_have_description():
    """r3 F5：对白段前后 ±1 段含描写句 → 不命中。"""
    text = (
        "灯苗在石台上跳了一下，她停住手。\n\n"
        '"师父。"\n\n'
        "小龙女没回头，指尖在石面上轻轻一划。"
    )
    hits = detect_pure_dialogue(text)
    assert len(hits) == 0


def test_ambiguous_referent_hit_narrow_scope():
    """r3 F5 收窄：仅匹配"那人/对方"。"""
    text = (
        '"一。"那人说。\n'
        '"二。"对方答。\n'
        '"三。"他开口。\n'
    )
    hits = detect_ambiguous_referent(text)
    assert len(hits) >= 1


def test_ambiguous_referent_no_hit_on_only_regular_pronouns():
    """仅"他"作说话人 → 不命中（"他"不是模糊代词）。"""
    text = (
        '"一。"他说。\n'
        '"二。"他答。\n'
        '"三。"他开口。\n'
    )
    hits = detect_ambiguous_referent(text)
    assert len(hits) == 0


def test_template_speech_verb():
    text = "他轻轻地说道。她沉声地说道。他冷冷地说道。"
    hits = detect_template_speech_verb(text)
    assert len(hits) >= 3


# ---------------------------------------------------------------------------
# stock_speech_tag (commit 7 / plan v9 §11.4 — round-3 实证驱动)
# ---------------------------------------------------------------------------

def test_stock_speech_tag_dandan_dao():
    """命中 '他淡淡道' / '司徒照淡淡道'（round-3 scene_S01 实证）"""
    from dialogue_lint import detect_stock_speech_tag
    text = "他淡淡道：「刀断了，人还在。」\n司徒照收起铁券，淡淡道：「案由已入册。」"
    hits = detect_stock_speech_tag(text)
    assert len(hits) == 2
    assert all(h["rule"] == "stock_speech_tag" for h in hits)
    assert all(h["confidence"] == "medium" for h in hits)


def test_stock_speech_tag_sheng_yin_bu_gao():
    """命中 '声音不高' / '杨过声音不高'（round-3 实证）"""
    from dialogue_lint import detect_stock_speech_tag
    text = "那声音不高，追兵却一齐垂手。\n杨过声音不高，对司徒照说。"
    hits = detect_stock_speech_tag(text)
    assert len(hits) == 2
    assert all("声音不高" in h["pattern"] for h in hits)


def test_stock_speech_tag_other_patterns():
    """命中 '低声道' / '平静道' / '沉声道' / '悠悠道'"""
    from dialogue_lint import detect_stock_speech_tag
    text = "他低声道：「来了。」\n她平静道：「好。」\n那人沉声道：「不行。」\n老者悠悠道：「久违。」"
    hits = detect_stock_speech_tag(text)
    assert len(hits) == 4


def test_stock_speech_tag_no_false_positive_on_normal_speech():
    """不命中正常对白动作描写（无库存标签）"""
    from dialogue_lint import detect_stock_speech_tag
    text = "他握紧拳头说：「来吧。」\n她转身道：「走。」\n老人摇头说：「不行。」"
    hits = detect_stock_speech_tag(text)
    assert len(hits) == 0


def test_stock_speech_tag_no_false_positive_on_unrelated_text():
    """不命中无关场景描述（'声音不高' 不在对白上下文也不应硬抓——但当前简化版正则会抓；
    这是 plan v9 §11.4 已说明的 medium confidence 设计：脚本作低风险 hit list，
    A 组人工核实'删去后信息不损失'原则）"""
    from dialogue_lint import detect_stock_speech_tag
    text = "天色昏暗，远处传来声音不高的钟声。"  # '声音不高' 在景物描写而非对白
    hits = detect_stock_speech_tag(text)
    # 当前实现简化为正则匹配，会命中（confidence=medium，A 组人工筛）
    assert len(hits) == 1
    assert hits[0]["confidence"] == "medium"


def test_stock_speech_tag_round3_scene_s01_4_hits():
    """plan v9 回归 #10 实证：round-3 scene_S01.md 4 处实例"""
    from dialogue_lint import detect_stock_speech_tag
    text = (
        "他淡淡道：“刀断了，人还在。”\n"
        "便在此时，那声音不高，追兵却一齐垂手。\n"
        "“看清楚。”杨过声音不高，“这条路给他退……”\n"
        "司徒照收起铁券，淡淡道：“案由已入册。”\n"
    )
    hits = detect_stock_speech_tag(text)
    assert len(hits) == 4
    patterns_hit = sorted(h["pattern"] for h in hits)
    assert patterns_hit == ["声音不高", "声音不高", "淡淡道", "淡淡道"]


def test_stock_speech_tag_integrated_in_analyze():
    """analyze() 输出 hits 应含 stock_speech_tag 命中"""
    from dialogue_lint import analyze
    text = "他淡淡道：「test。」\n那声音不高，他想着。"
    result = analyze(text)
    rules = {h["rule"] for h in result["hits"]}
    assert "stock_speech_tag" in rules


# ---------------------------------------------------------------------------
# weak_character_expression_candidate — 人物描写附近的弱表述候选
# ---------------------------------------------------------------------------

def test_weak_character_expression_voice_positive():
    text = (
        "小龙女看着那条无灯的水，声音仍平。\n"
        "凌霜看向门槛外的夜色，声音平。"
    )
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) == 2
    assert all(h["rule"] == "weak_character_expression_candidate" for h in hits)
    assert {h["confidence"] for h in hits} == {"medium"}


def test_weak_character_expression_face_positive():
    text = "陈默没有立刻移动。他站在那里，表情没有变化。\n小龙女神色不变。"
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) == 2
    assert any("表情没有变化" in h["pattern"] for h in hits)
    assert any("神色不变" in h["pattern"] for h in hits)


def test_weak_character_expression_motion_positive():
    text = "他穿过雨棚，脚步不慢。\n茶馆主人手仍抖着。"
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) == 2
    assert any("脚步不慢" in h["pattern"] for h in hits)
    assert any("手仍抖" in h["pattern"] for h in hits)


def test_weak_character_expression_not_question_positive():
    text = '"废堡在哪里。"她说，不是问句。'
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) == 1
    assert hits[0]["pattern"] == "不是问句"


def test_weak_character_expression_ignores_factual_negation():
    text = (
        "公审是今夜，不是明晨。\n"
        "“他喝的不是我的方。”女子说。\n"
        "“这柄刀不是我塞到你们手里。”杨过道。"
    )
    hits = detect_weak_character_expression_candidate(text)
    assert hits == []


def test_weak_character_expression_ignores_environment_sound():
    text = "芦苇荡里传来一阵水鸟掠翅的声音，远处江面上什么也没有。"
    hits = detect_weak_character_expression_candidate(text)
    assert hits == []


def test_weak_character_expression_does_not_duplicate_stock_speech_tag():
    text = "那声音不高，追兵却一齐垂手。\n他淡淡道：「刀断了，人还在。」"
    hits = detect_weak_character_expression_candidate(text)
    assert hits == []


def test_weak_character_expression_integrated_in_analyze():
    from dialogue_lint import analyze
    text = "小龙女看着那条无灯的水，声音仍平。"
    result = analyze(text)
    rules = {h["rule"] for h in result["hits"]}
    assert "weak_character_expression_candidate" in rules


def test_weak_character_expression_pronoun_candidate_low_confidence():
    """代词锚点 candidate（无身体部位/感官名词锚点）固定 confidence=low。"""
    text = "她没有动。\n他只是看着远方。"
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) == 2
    assert all(h["confidence"] == "low" for h in hits)
    assert any("她没有动" in h["pattern"] for h in hits)
    assert any("他只是看着" in h["pattern"] for h in hits)


def test_weak_character_expression_pronoun_excludes_plural_pronouns():
    """他们 / 她们 不触发代词锚点——避免群体动作误报。"""
    text = "他们没有动。\n她们只是看着远方。"
    hits = detect_weak_character_expression_candidate(text)
    assert hits == []


def test_weak_character_expression_pronoun_fires_on_contrast_action():
    """对比式具体动作（没饮 + 望着）pattern 5 仍触发，confidence=low——
    由 A 组按 weak_character_expression 豁免规则筛除有效描写。
    """
    text = "他接过茶，却没饮，望着远去的背影。"
    hits = detect_weak_character_expression_candidate(text)
    assert len(hits) >= 1
    assert any(h["confidence"] == "low" for h in hits)


# ---------------------------------------------------------------------------
# weak_character_expression hot zone — near_dialogue 字段
# ---------------------------------------------------------------------------

def test_weak_character_expression_near_dialogue_true_after_dialogue():
    """对白后 1 行的弱表述 candidate → near_dialogue=True。"""
    text = '"我们走。"她说。\n她声音平。'
    hits = detect_weak_character_expression_candidate(text)
    voice_hits = [h for h in hits if "声音平" in h["pattern"]]
    assert voice_hits
    assert all(h["near_dialogue"] is True for h in voice_hits)


def test_weak_character_expression_near_dialogue_false_far_from_dialogue():
    """远离对白（前后 ±2 行均无对白）→ near_dialogue=False。"""
    text = (
        "茶馆主人手仍抖着。\n"
        "远处传来雨声。\n"
        "他立在窗边等了很久。\n"
        "屋脊滴水未停。"
    )
    hits = detect_weak_character_expression_candidate(text)
    motion_hits = [h for h in hits if "手仍抖" in h["pattern"]]
    assert motion_hits
    assert all(h["near_dialogue"] is False for h in motion_hits)


def test_weak_character_expression_between_two_dialogues_near_true():
    """两句对白之间的垫句（典型 hot zone）→ near_dialogue=True。"""
    text = (
        '"先把证据拿稳。"她说。\n'
        '她没有动。\n'
        '"今夜以前。"她又说。'
    )
    hits = detect_weak_character_expression_candidate(text)
    pad_hits = [h for h in hits if "她没有动" in h["pattern"]]
    assert pad_hits
    assert all(h["near_dialogue"] is True for h in pad_hits)


def test_weak_character_expression_voice_anchor_yuqi():
    """语气 + 平/平平/平淡/不带情绪 等弱标签——codex 91 文件扫描实证 50 hits。"""
    text = '他说到"胁迫证人"四字，语气平平。\n她语气平淡。\n他语气不带情绪。'
    hits = detect_weak_character_expression_candidate(text)
    patterns = [h["pattern"] for h in hits]
    assert any("语气平平" in p for p in patterns)
    assert any("语气平淡" in p for p in patterns)
    assert any("语气不带情绪" in p for p in patterns)


def test_weak_character_expression_voice_anchor_di_dao():
    """实证补词：声音低到 / 声音压低到 属人物声音弱表述候选。"""
    text = (
        '他停了半秒，声音低到只有她能听见："你还年轻。"\n'
        "她没有转身，只是声音压低到刚好越过两人之间那点距离。"
    )
    hits = detect_weak_character_expression_candidate(text)
    patterns = [h["pattern"] for h in hits]
    assert any("声音低到" in p for p in patterns)
    assert any("声音压低到" in p for p in patterns)


def test_weak_character_expression_does_not_match_jiang_di_dao():
    """降低到/降低到了 属变化动词，不等同于声音低到。"""
    text = "旁边的同学在低声说话，然后他们的声音又降低到了白噪音里。"
    hits = detect_weak_character_expression_candidate(text)
    assert hits == []


def test_cli_pure_dialogue_threshold_override(tmp_work_dir):
    """S3 CLI 阈值可覆盖默认 0.80，meta 回写。"""
    import subprocess
    scene_path = tmp_work_dir / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text('"A。"\n\n"B。"\n\n"C。"', encoding="utf-8")
    result = subprocess.run(
        ["python3", str(_PLUGIN_ROOT / "scripts/dialogue_lint.py"),
         "--scene-id", "S01",
         "--work-dir", str(tmp_work_dir),
         "--pure-dialogue-threshold", "0.95"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    import yaml as _yaml
    out = _yaml.safe_load(
        (tmp_work_dir / "pipeline" / "review" / "lint" / "S01.dialogue.yaml").read_text()
    )
    assert out["meta"]["thresholds"]["pure_dialogue"] == 0.95
    assert out["meta"]["threshold_source"] == "cli"
