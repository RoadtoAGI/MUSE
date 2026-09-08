"""S2 lexical_stats.py 单测。

覆盖 55+1 条清单第 5/11/13/30 条——副词密度 / TTR / 高频词 / 感官平衡。
"""
from pathlib import Path

from lexical_stats import (
    adverb_density,
    sensory_balance,
    type_token_ratio,
    top_k_nouns,
    analyze,
)

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def test_adverb_density():
    text = "非常缓慢地走过。极其轻轻地说。" * 10
    stats = adverb_density(text)
    assert stats["per_1k"] > 50


def test_sensory_visual_only():
    text = "他看着她。他望着窗外。" * 10
    balance = sensory_balance(text)
    assert balance["visual_ratio"] > 0.7


def test_sensory_balanced():
    text = "他看着窗外。听见远处的声响。指尖触到石面的冷。闻到淡淡的檀香。"
    balance = sensory_balance(text)
    assert balance["visual_ratio"] < 0.7


def test_ttr_basic():
    text = "他走他走他走"
    result = type_token_ratio(text)
    assert result["ttr"] < 0.5


def test_top_k_nouns(clean_draft):
    tokens = top_k_nouns(clean_draft, k=5)
    assert isinstance(tokens, list)
    assert len(tokens) >= 1


def test_density_imbalanced_when_visual_dominant():
    """统计型脚本 hits 保持空，视觉主导通过 density.sensory_balance.imbalanced 标。"""
    text = "他看着她。他望着窗外。他凝视。他注视。" * 20
    result = analyze(text, visual_ratio_threshold=0.70)
    assert result["hits"] == []
    assert result["density"]["sensory_balance"]["imbalanced"] is True


def test_density_balanced_not_flagged():
    text = "他看着窗外。听见远处的声响。指尖触到石面的冷。闻到淡淡的檀香。"
    result = analyze(text, visual_ratio_threshold=0.70)
    assert result["density"]["sensory_balance"]["imbalanced"] is False


def test_cli_thresholds_override(tmp_work_dir, polluted_draft):
    """CLI 阈值能覆盖默认值，meta.threshold_source 标 cli。"""
    import subprocess
    scene_path = tmp_work_dir / "pipeline" / "scenes" / "scene_S01.md"
    scene_path.write_text(polluted_draft, encoding="utf-8")
    result = subprocess.run(
        ["python3", str(_PLUGIN_ROOT / "scripts/lexical_stats.py"),
         "--scene-id", "S01",
         "--work-dir", str(tmp_work_dir),
         "--visual-ratio-threshold", "0.90",
         "--genre", "武侠"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    import yaml as _yaml
    out = _yaml.safe_load(
        (tmp_work_dir / "pipeline" / "review" / "lint" / "S01.lexical_stats.yaml").read_text()
    )
    assert out["meta"]["thresholds"]["visual_ratio"] == 0.90
    assert out["meta"]["threshold_source"] == "cli"
    assert out["meta"]["genre"] == "武侠"
