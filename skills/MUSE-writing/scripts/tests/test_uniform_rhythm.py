import ai_filler_lint as lint


def test_sentence_lengths_zh_counts_sentence_terminal_punctuation():
    text = "风停了。她抬头！他说：“走。”"
    assert lint._sentence_lengths(text, "zh") == [3, 3, 3]


def test_uniform_rhythm_equal_length_sequence_triggers_with_test_floor(monkeypatch):
    monkeypatch.setitem(lint.UNIFORM_RHYTHM_CV_FLOOR, "zh", 0.01)
    text = "他推开门。" * 12

    issue = lint.check_uniform_rhythm(text, "zh")

    assert issue is not None
    assert issue["issue_type"] == "uniform_rhythm"
    assert issue["trigger"]["sentence_count"] == 12
    assert issue["trigger"]["sentence_cv"] == 0.0
    assert issue["trigger"]["cv_floor"] == 0.01


def test_uniform_rhythm_varied_lengths_do_not_trigger(monkeypatch):
    monkeypatch.setitem(lint.UNIFORM_RHYTHM_CV_FLOOR, "zh", 0.10)
    sentences = [
        "风停了。",
        "他沿着长廊慢慢走到尽头，又折回来。",
        "灯灭。",
        "她把信纸压在碗底，没有立刻说话。",
    ] * 3
    assert lint.check_uniform_rhythm("".join(sentences), "zh") is None


def test_uniform_rhythm_ignores_short_scene(monkeypatch):
    monkeypatch.setitem(lint.UNIFORM_RHYTHM_CV_FLOOR, "zh", 0.99)
    text = "他推开门。" * 11
    assert lint.check_uniform_rhythm(text, "zh") is None


def test_uniform_rhythm_is_in_analyze_scene_level_issues(monkeypatch):
    monkeypatch.setitem(lint.UNIFORM_RHYTHM_CV_FLOOR, "zh", 0.01)
    result = lint.analyze("他推开门。" * 12, lang="zh")
    assert any(
        issue["issue_type"] == "uniform_rhythm"
        for issue in result["scene_level_issues"]
    )
