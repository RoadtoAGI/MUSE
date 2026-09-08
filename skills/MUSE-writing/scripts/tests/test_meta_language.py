from ai_filler_lint import (
    META_LANGUAGE_EN,
    META_LANGUAGE_ZH,
    analyze,
    detect_meta_language,
)


def test_meta_language_seed_tables_match_design():
    assert META_LANGUAGE_ZH == (
        "综上所述",
        "值得注意的是",
        "需要指出的是",
        "不难发现",
        "由此可见",
        "总的来说",
        "换言之",
        "综合来看",
    )
    assert META_LANGUAGE_EN == (
        "it is worth noting",
        "it should be noted",
        "it is important to note",
        "in conclusion",
        "as previously mentioned",
        "firstly, ... secondly",
        "to summarize",
    )


def test_meta_language_zh_narration_hits_with_original_offsets():
    text = "雨停了。\n综上所述，他还是推开门。"
    hits = detect_meta_language(text, "zh")
    assert len(hits) == 1
    hit = hits[0]
    expected_start = text.index("综上所述")
    assert hit["rule"] == "meta_language_leak_zh"
    assert hit["family"] == "meta_language_leak"
    assert hit["severity"] == "medium"
    assert hit["start"] == expected_start
    assert hit["end"] == expected_start + len("综上所述")
    assert text[hit["start"]:hit["end"]] == "综上所述"


def test_meta_language_zh_quoted_phrase_is_masked():
    text = "他清了清嗓子，说：“综上所述，我们撤。”\n雨还在下。"
    assert detect_meta_language(text, "zh") == []


def test_meta_language_en_phrase_hits_case_insensitive():
    text = "It is worth noting that the house stayed dark. The road was empty."
    hits = detect_meta_language(text, "en")
    assert len(hits) == 1
    assert hits[0]["rule"] == "meta_language_leak_en"
    assert hits[0]["pattern"] == "it is worth noting"
    assert text[hits[0]["start"]:hits[0]["end"]] == "It is worth noting"


def test_meta_language_clean_text_has_no_hits_in_analyze():
    text = "The road narrowed after the bridge. He kept walking until the lights went out."
    result = analyze(text, lang="en")
    assert [h for h in result["hits"] if h["family"] == "meta_language_leak"] == []
