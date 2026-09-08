"""en 检测规则：negation_pivot_en 显式对照锚 + slop_phrase_en 词表。"""
from ai_filler_lint import detect_negation_pivot_en, detect_slop_phrase_en, SLOP_PHRASES_EN


def test_negation_pivot_requires_contrast_anchor():
    """普通叙事否定不命中；显式对照（not X, but Y）命中。"""
    plain = "He did not come back. I waited by the door. She would not move at all."
    assert detect_negation_pivot_en(plain) == []

    pivot = "It was not fear, but recognition."
    hits = detect_negation_pivot_en(pivot)
    assert len(hits) == 1


def test_negation_pivot_because_and_instead_forms():
    because = "He fought not because he hated them, but because he loved her."
    assert len(detect_negation_pivot_en(because)) >= 1

    instead = "She was not angry. Instead, she smiled slowly."
    assert len(detect_negation_pivot_en(instead)) == 1


def test_slop_phrase_lexicon_matches_case_insensitive():
    assert "voice barely above a whisper" in SLOP_PHRASES_EN
    text = "Her Voice Barely Above A Whisper, she said yes."
    hits = detect_slop_phrase_en(text)
    assert len(hits) == 1
    assert hits[0]["family"] == "lexical_cliche"
    assert hits[0]["severity"] == "low"


def test_slop_phrase_no_hits_on_clean_text():
    clean = "He poured the coffee and read the letter twice before answering."
    assert detect_slop_phrase_en(clean) == []
