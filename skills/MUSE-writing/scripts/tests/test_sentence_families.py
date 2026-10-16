"""逐句家族（AI 口癖治理升级设计 §5）：定义、晋升证据与成对夹具。

should-fix 取作者标注句与 A/B 稿原句；should-not-fix 取作者认可的 183 与人类原著里落在定义之外的句子。
夹具检验定义的精度，不是对规则的豁免。
"""
from pathlib import Path

import pytest
import yaml

from ai_filler_lint import analyze, detect_contrastive_negation_assertion, detect_negation_restriction_pivot
from ai_policy import (
    CALIBRATION_RECORDS,
    FAMILY_MANIFEST,
    MECHANISMS,
    PROMOTION_RECORDS,
    RULE_REGISTRY,
    effective_policy,
    validate_manifest,
)
import sentence_families as SF

FIXTURES = Path(__file__).parent / "fixtures"
ANNOTATIONS = yaml.safe_load((FIXTURES / "ai_pattern_annotations.yaml").read_text(encoding="utf-8"))
STORY_183 = (FIXTURES / "story_183_opus47.md").read_text(encoding="utf-8")

PER_SENTENCE = {
    "echo_negation": "zh",
    "negation_list": "zh",
    "single_sentence_paragraph": "zh",
    "precise_number_repeat": "zh",
    "abstract_classifier": "zh",
    "contrastive_negation_assertion": "zh",
    "rather_stance_en": "en",
}
DENSITY_ONLY = ("couplet_fragment", "mirrored_pair", "body_closeup_filler", "stiff_adverb")

# 594 L 稿原文：同一时刻表达在一场里各出现三次
NUMBER_PASSAGE = (
    "他名下那一格补领的时间是凌晨三点十七分，经手号不是他的，红签挂上了那串数字。"
    "紧挨着亮起一只冷链周转箱的温度记录，从三点十九分起算，封条经手人：杜芷方。"
    "三点十九分排在三点十七分底下，这句话就说不出口了。"
    "她在“本人决定”底下写的是：三点十七分补本格饭单，三点十九分封冷链箱一只，本班经手，仅本人。"
)
SHOULD_FIX = {
    "echo_negation": ("zh", "石秋准看了她一眼，没有改口。"),
    "negation_list": ("zh", "没有检测单，没有检测员，没有取样。"),
    "single_sentence_paragraph": ("zh", "她性子急，他慢。"),
    "precise_number_repeat": ("zh", NUMBER_PASSAGE),
    "abstract_classifier": ("zh", "心里先是愤怒，随后又生出一种卑微的羡慕。"),
    "contrastive_negation_assertion": ("zh", "黎颂要留的不是一道痕，是整条记录。"),
    "rather_stance_en": ("en", "Min has her things laid out there, and I'd rather nobody had to move them twice."),
}
# 183（作者认可）与 I Am Legend 原句
SHOULD_NOT_FIX = {
    "echo_negation": ("zh", "去年秋天我还从这道楼梯上去过，搜到十五层就下来了，十七层一直没去。"),
    "negation_list": ("zh", "我把袋子两面都翻过来看，没找到漏口；隔着袋子捏，里面不结块；凑近闻，只有干谷子的气味，没有哈喇味。"),
    "single_sentence_paragraph": ("zh", "我对自己说该走了，铁罐却还捧在手里，人站在冰箱前没挪步。"),
    "precise_number_repeat": ("zh", "腕上那块太阳能表还走着，指在一点五十。这一趟我给了自己三个钟头：上楼四十分钟，搜一个钟头。"),
    "abstract_classifier": ("zh", "这种箱子里装些什么我大概知道，就没打开，整只塞进了包里。"),
    "contrastive_negation_assertion": ("zh", "跑出停车道，我的腿软得再也迈不动，只好扶着那辆银色轿车站住。"),
    "rather_stance_en": ("en", "he said, glad to restate something she already knew rather than go into fresh material."),
}


def _per_sentence_families(text: str, lang: str) -> set[str]:
    return {h["family"] for h in analyze(text, lang=lang)["hits"] if h.get("per_sentence")}


@pytest.mark.parametrize("family", sorted(PER_SENTENCE))
def test_should_fix(family):
    lang, text = SHOULD_FIX[family]
    assert family in _per_sentence_families(text, lang)


@pytest.mark.parametrize("family", sorted(PER_SENTENCE))
def test_should_not_fix(family):
    lang, text = SHOULD_NOT_FIX[family]
    assert family not in _per_sentence_families(text, lang)


def test_annotation_hits_are_fixed():
    """22 句标注的逐句命中集合：变化即说明定义变了，要重算三项证据。"""
    hit = {item["text"] for item in ANNOTATIONS["sentences"] if _per_sentence_families(item["text"], "zh")}
    missed = {item["text"] for item in ANNOTATIONS["sentences"]} - hit
    assert missed == {
        "北水十三，布面那件，平放，两个人上下夹护。",
        "日期在一个月前，木料一段，签收人邵青。",
        "她看得见整张地图，看不见水；他认得每一段水，却说不清要往哪儿去。",
        "人员栏第三行的沈砚舟，现在是韩拓带下去的人。",
    }
    assert all(_per_sentence_families(item["text"], "zh") for item in ANNOTATIONS["sentences"] if item["group"] == "A")


def test_story_183_per_sentence_hits_only_judged_lines():
    judged = set(ANNOTATIONS["judged_183"])
    hits = [h for h in analyze(STORY_183, lang="zh")["hits"] if h.get("per_sentence")]
    assert all(any(h["span"] in line or line in h["span"] for line in judged) for h in hits)


def test_density_only_families_stay_observe_with_baseline():
    for family in DENSITY_ONLY:
        policy = effective_policy(family, "zh")
        assert policy["lifecycle"] == "observe"
        assert CALIBRATION_RECORDS[policy["baseline_ref"]]["provenance"] == "ai-pattern-calibration-2026-10-17"
        assert family not in _per_sentence_families("是纸，湿的。指腹压住纸角。他仍等着。卡是我的卡。", "zh")


def test_per_sentence_policies_carry_three_evidence_legs():
    assert validate_manifest() == []
    for family, lang in PER_SENTENCE.items():
        policy = effective_policy(family, lang, family if family in RULE_REGISTRY else None)
        assert policy["lifecycle"] == "enforced" and policy["single_hit"]
        record = PROMOTION_RECORDS[policy["promoted_ref"]]
        for leg in ("prevalence_ref", "hard_negative_ref", "decision_ref"):
            assert record[leg]
        assert record["fixture_refs"] == [
            f"scripts/tests/test_sentence_families.py::test_should_fix[{family}]",
            f"scripts/tests/test_sentence_families.py::test_should_not_fix[{family}]",
        ]


def test_tic_families_name_a_mechanism():
    for family in (*PER_SENTENCE, *DENSITY_ONLY, "silence_pause_cliche", "micro_clause_chain"):
        assert FAMILY_MANIFEST[family]["mechanism"] in MECHANISMS
    for family in ("dummy_pronoun", "demonstrative_classifier", "marker_pollution"):
        assert FAMILY_MANIFEST[family]["mechanism"] is None


def test_hits_point_to_repair_entry():
    hit = next(h for h in analyze("没有人接。他走了很远的路才到。", lang="zh")["hits"] if h["family"] == "echo_negation")
    assert hit["mechanism"] == "posture_line"
    assert hit["repair"] == "prose-craft/references/prose-rules.md#口癖的改法"


# ---------- parallel_negation 逐 pattern 迁移后仍被定位 ----------

@pytest.mark.parametrize("text,rule", [
    ("没有声音，没有光。", "negation_list"),
    ("没有A，甚至没有B。", "negation_list"),
    ("不是这一件，不是那一件。", "negation_list"),
    ("不是方向错了，而是时机不对。", "contrastive_negation_assertion"),
    ("不是退阵，是变阵。", "contrastive_negation_assertion"),
    ("不是说那位独臂客——是说夜枫坞。", "contrastive_negation_assertion"),
    ("不是黯然销魂掌，只是近于那路。", "contrastive_negation_assertion"),
    ("是被剑刃割断的，不是自然磨断。", "contrastive_negation_assertion"),
    ("没有声音，是黑暗。", "contrastive_negation_assertion"),
    ("没有反应，只是停顿。", "contrastive_negation_assertion"),
    ("并非他错了，而是时机不对。", "contrastive_negation_assertion"),
    ("并非偶然，是必然。", "contrastive_negation_assertion"),
    ("他并不着急，却一直看表。", "contrastive_negation_assertion"),
])
def test_parallel_negation_variants_still_located(text, rule):
    rules = {h["rule"] for h in analyze(text, lang="zh")["hits"]}
    assert rule in rules
    assert "parallel_negation" not in rules


def test_bare_negation_restriction_is_observe_rule():
    text = "他不掰开，只是裹住。"
    assert detect_contrastive_negation_assertion(text) == []
    hits = detect_negation_restriction_pivot(text)
    assert [h["variant"] for h in hits] == ["不X只Y"]
    assert effective_policy("contrastive_negation_assertion", "zh", "negation_restriction_pivot")["lifecycle"] == "observe"


# ---------- 定义细节 ----------

def test_couplet_fragment_skips_dialogue():
    assert SF.detect_couplet_fragment("“是纸，湿的。”他说。") == []
    assert len(SF.detect_couplet_fragment("是纸，湿的。")) == 1


def test_single_sentence_paragraph_skips_quoted_paragraphs():
    assert SF.detect_single_sentence_paragraph("陈晏答：“谈过。”") == []
    assert len(SF.detect_single_sentence_paragraph("石秋准等着。")) == 1


def test_precise_number_ignores_adverbs_and_titles():
    text = "她有一点累。一时语塞。他一度想走。" * 3 + "《凌晨三点》《凌晨三点》《凌晨三点》"
    assert SF.detect_precise_number_repeat(text) == []


def test_mirrored_pair_ignores_you_mei_you():
    assert SF.detect_mirrored_pair("你有没有看见？") == []
    assert len(SF.detect_mirrored_pair("取没取，上没上，我没有回去看。")) == 1


# ---------- 首稿自查 ----------

def test_self_check_exit_codes(tmp_path):
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "ai_filler_lint.py"
    dirty = tmp_path / "story.md"
    dirty.write_text("他说完看着他们，等人复述。没有人复述。他又说了一遍规矩，才把单子收回去。\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), "--self-check", str(dirty)], capture_output=True, text=True)
    assert r.returncode == 2
    assert "没有人复述。" in r.stdout and "回声否定" in r.stdout and "口癖的改法" in r.stdout

    clean = tmp_path / "clean.md"
    clean.write_text(STORY_183, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), "--self-check", str(clean)], capture_output=True, text=True)
    assert r.returncode == 0

    r = subprocess.run([sys.executable, str(script), "--self-check", str(tmp_path / "missing.md")],
                       capture_output=True, text=True)
    assert r.returncode == 1
