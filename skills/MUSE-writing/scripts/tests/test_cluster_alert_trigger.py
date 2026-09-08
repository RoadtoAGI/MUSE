"""Rn+2 Task 1: cluster_alert 触发主公式回归测试。"""
from ai_filler_lint import aggregate_cluster_alerts, aggregate_observed_alerts


def test_short_text_single_hit_density_high_not_triggered():
    """短文本 + 1 hit + density>2 -> 不触发 cluster（修 GPT P0-1）。

    夹具使用当前 enforced family。"""
    hits = [{
        "rule": "stock_silence_pause_phrase",
        "family": "silence_pause_cliche",
        "lint_id": "S01-spc-001",
        "start": 10,
        "end": 30,
    }]
    scene_text = "x" * 400  # 400 字符，1 hit density=2.5 > 2.0
    alerts = aggregate_cluster_alerts(hits, "S01", scene_text)
    assert len(alerts) == 0, f"期望 0 alert，实得 {len(alerts)}（density={1/0.4}）"


def test_two_hits_high_density_triggered():
    """短文本 + 2 hits + density 高 -> 触发（count gate 通过）。"""
    hits = [
        {"rule": "stock_silence_pause_phrase", "family": "silence_pause_cliche",
         "lint_id": "S01-spc-001", "start": 10, "end": 30},
        {"rule": "stock_silence_pause_phrase", "family": "silence_pause_cliche",
         "lint_id": "S01-spc-002", "start": 100, "end": 130},
    ]
    scene_text = "x" * 400
    alerts = aggregate_observed_alerts(hits, "S01", scene_text)
    assert aggregate_cluster_alerts(hits, "S01", scene_text) == []
    assert len(alerts) == 1
    assert alerts[0]["total_count"] == 2




def test_same_family_scene_count_triggered_independently():
    """count 路径独立于通用 density 阈值（same_family_scene_count_gte=3），
    前提是 density 已超该 family 的名著基线。"""
    hits = [
        {"rule": "stock_silence_pause_phrase", "family": "silence_pause_cliche", "lint_id": f"S01-x-{i:03d}",
         "start": i * 100, "end": i * 100 + 10}
        for i in range(3)
    ]
    # density = 1.5：> 名著基线 0.72，< 通用 density 阈值 2.0 —— 只有 count 路径可触发
    scene_text = "x" * 2000
    alerts = aggregate_observed_alerts(hits, "S01", scene_text)
    assert aggregate_cluster_alerts(hits, "S01", scene_text) == []
    assert len(alerts) == 1
    assert alerts[0]["family"] == "silence_pause_cliche"


def test_en_observe_policy_reports_without_cluster_alert_at_low_density():
    """en 当前显式 observe；命中保留，聚合层不产 enforced alert。"""
    hits = [
        {"rule": "staccato_run", "family": "rhythm_fragmentation", "lint_id": f"S01-x-{i:03d}",
         "start": i * 100, "end": i * 100 + 10}
        for i in range(3)
    ]
    scene_text = "x" * 10000  # density 0.3 < en rhythm_fragmentation 基线 0.82
    alerts = aggregate_cluster_alerts(hits, "S01", scene_text, lang="en")
    assert alerts == []


def test_en_observe_policy_remains_non_blocking_at_high_density():
    """高密度 en 命中也保持 observe，不进入 enforced cluster alert。"""
    hits = [
        {"rule": "negation_pivot_en", "family": "contrastive_negation_assertion", "lint_id": f"S01-x-{i:03d}",
         "start": i * 100, "end": i * 100 + 10}
        for i in range(4)
    ]
    scene_text = "x" * 2000  # density 2.0 >> en cna 基线 0.48
    alerts = aggregate_cluster_alerts(hits, "S01", scene_text, lang="en")
    assert alerts == []
    assert all(hit["policy_lifecycle"] == "observe" for hit in hits)


def test_masterwork_baseline_suppresses_low_density_cluster():
    """count 证据成立但 density 低于名著基线 -> 不产 cluster alert（hits 不受影响）。"""
    hits = [
        {"rule": f"r{i}", "family": "lexical_cliche", "lint_id": f"S01-x-{i:03d}",
         "start": i * 100, "end": i * 100 + 10}
        for i in range(4)
    ]
    scene_text = "x" * 10000  # density 0.4 << lexical_cliche 名著基线 3.75
    alerts = aggregate_cluster_alerts(hits, "S01", scene_text)
    assert alerts == []
