from ai_filler_lint import analyze


def test_span_aggregation_single_family_low():
    text = "她嘴角动了动。"
    result = analyze(text)
    assert "span_aggregation" in result
    spans = result["span_aggregation"]
    assert len(spans) >= 1
    s0 = spans[0]
    assert s0["severity_aggregate"] == "low"
    assert s0["dominant_cluster"] == "silence_pause_cliche"


def test_span_aggregation_multi_family_medium():
    """syntax + semantic 同段 -> medium/high."""
    text = "她转身去倒了杯酒，去看别的画了，嘴角动了动，停了一秒。"
    result = analyze(text)
    spans = result["span_aggregation"]
    high_or_med = [s for s in spans if s["severity_aggregate"] in ("medium", "high")]
    assert len(high_or_med) >= 1
    s = high_or_med[0]
    assert "severity_basis" in s
    assert isinstance(s["severity_basis"], list)
    assert any("co-occurred" in b or "family" in b for b in s["severity_basis"])


def test_span_aggregation_dominant_cluster_semantic_priority():
    """语义层 cluster 优先（family_count 并列时）。"""
    text = "她转身去倒酒。她嘴角动了动。"
    result = analyze(text)
    spans = result["span_aggregation"]
    s = next(iter(spans))
    assert s["dominant_cluster"] in {"silence_pause_cliche", "action_log"}
    if s["family_counts"].get("silence_pause_cliche", 0) == s["family_counts"].get("action_log", 0):
        assert s["dominant_cluster"] == "silence_pause_cliche"


def test_span_aggregation_rule_counts_vs_family_counts_separation():
    """rule_counts 与 family_counts 分字段。"""
    text = "她接电话去了。她走开了。"
    result = analyze(text)
    spans = result["span_aggregation"]
    s = next(iter(spans))
    assert "rule_counts" in s
    assert "family_counts" in s
    assert "social_choreography_log" in s["rule_counts"]
    assert "social_choreography" in s["family_counts"]
