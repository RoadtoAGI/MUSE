import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"))

from ai_filler_lint import analyze, detect_lang


EN = (
    "Not silence — something colder. Wet stone. A section of wall. Then darkness. "
    "It felt like a dropped packet. Not fear — recognition. Cold air. Static hum. "
) * 6


def test_detect_lang():
    assert detect_lang("他怔了怔。她没说话。") == "zh"
    assert detect_lang(EN) == "en"


def test_en_rules_fire():
    result = analyze(EN, lang="en")

    assert result["language"] == "en"
    families = {hit["rule"] for hit in result["hits"]}
    assert families & {"em_dash_density", "negation_pivot_en", "staccato_run", "simile_density_en"}


def test_zh_text_en_profile_quiet():
    result = analyze("他怔了怔。\n\n她没说话。\n\n" * 10, lang="en")

    assert len(result["hits"]) < 3
