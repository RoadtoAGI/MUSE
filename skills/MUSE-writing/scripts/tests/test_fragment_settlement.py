"""fragment_settlement：保留四子形态定位，命中只作语义复核候选。"""
from ai_filler_lint import detect_fragment_settlement, analyze


def test_four_subforms_hit():
    cases = {
        "negation_dangling": "他站住了。不是因为犹豫。",
        "binary_evaluative_pair": "冰糖咬下去。很脆，很清。",
        "self_assurance": "还有半袋米。可以的。",
        "commentary_settlement": "系带勒得肩膀发疼，他没解开。勒着，倒踏实。",
    }
    for subform, text in cases.items():
        hits = detect_fragment_settlement(text)
        assert hits, f"{subform} 未命中"
        assert hits[0]["pattern"] == subform
        # offset 指回原文
        assert text[hits[0]["start"]:hits[0]["end"]] == hits[0]["span"]


def test_quoted_dialogue_out_of_scope():
    text = "他说：「不是因为犹豫。」然后转身走了。"
    assert detect_fragment_settlement(text) == []


def test_verb_dao_not_hit():
    """动词'倒'（倒了/倒退/倒在）不命中评注形态。"""
    text = "他晃了晃，倒在地上。她扶起茶壶，倒了半杯。"
    assert detect_fragment_settlement(text) == []


def test_clean_text_no_hits():
    text = "陈禾把重心倒到另一条腿上，嘴里数着息，声音吞在喉咙里。"
    assert detect_fragment_settlement(text) == []


def test_single_hit_is_non_blocking_candidate():
    text = "山道无人。" * 100 + "系带勒得肩膀发疼，他没解开。勒着，倒踏实。"
    r = analyze(text, scene_id="S01", lang="zh")
    hits = [h for h in r["hits"] if h["family"] == "fragment_settlement"]
    alerts = [a for a in r["cluster_alerts"] if a["family"] == "fragment_settlement"]
    assert hits and all(h["policy_lifecycle"] == "observe" for h in hits)
    assert alerts == []
