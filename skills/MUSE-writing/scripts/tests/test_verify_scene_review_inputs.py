"""Tests for verify_scene_review_inputs.py — review pipeline 输入门槛校验脚本。

覆盖 required input 缺失、adaptive B/C 与输出格式 YAML 友好等场景。
fixture 用 tmp_path 风格，与 test_verify_phase2_assets 一致。
"""
import subprocess
import sys
import yaml
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "verify_scene_review_inputs.py"


def make_pipeline(tmp, scene_id="S01", *,
                  scene_md=True, scene_card=True,
                  a_aesthetic=True, b_narrative=True, c_structural=True,
                  lint_ai_filler=True, lint_lexical=True, lint_dialogue=True):
    """构造最小 pipeline/ 目录；每个标志 True=写文件，False=不写。"""
    root = Path(tmp) / "pipeline"
    if scene_md:
        p = root / "scenes" / f"scene_{scene_id}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Scene\nbody\n")
    if scene_card:
        p = root / f"scene_{scene_id}" / "scene_card.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Scene Card\n")
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    if a_aesthetic:
        (review / "A_aesthetic.yaml").write_text(
            yaml.safe_dump({"review_findings": []}, allow_unicode=True))
    if b_narrative:
        (review / "B_narrative_consistency.yaml").write_text(
            yaml.safe_dump({"findings": []}, allow_unicode=True))
    if c_structural:
        (review / "C_structural_consistency.yaml").write_text(
            yaml.safe_dump({"findings": []}, allow_unicode=True))
    lint_dir = review / "lint"
    lint_dir.mkdir(parents=True, exist_ok=True)
    if lint_ai_filler:
        (lint_dir / f"{scene_id}.ai_filler.yaml").write_text("hits: []\n")
    if lint_lexical:
        (lint_dir / f"{scene_id}.lexical_stats.yaml").write_text("density: {}\n")
    if lint_dialogue:
        (lint_dir / f"{scene_id}.dialogue.yaml").write_text("hits: []\n")
    # 返回 run 根（包含 pipeline/ 子目录），与 --pipeline-root 命名约定一致
    return Path(tmp)


def run_script(pipeline_root, scene_id="S01"):
    """跑脚本，返回 (returncode, parsed_yaml_stdout)"""
    cmd = [sys.executable, str(SCRIPT), "--scene-id", scene_id,
           "--pipeline-root", str(pipeline_root)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    parsed = yaml.safe_load(result.stdout) if result.stdout.strip() else {}
    return result.returncode, parsed


def test_all_required_present_returns_zero(tmp_path):
    """全部 required + 无 voice_consistency → 退出 0，missing_inputs 空"""
    root = make_pipeline(tmp_path)
    code, out = run_script(root)
    assert code == 0
    assert out["status"] == "ok"
    assert out["scene_id"] == "S01"
    assert out["missing_inputs"] == []


def test_missing_scene_md_returns_nonzero(tmp_path):
    root = make_pipeline(tmp_path, scene_md=False)
    code, out = run_script(root)
    assert code == 1
    assert "pipeline/scenes/scene_S01.md" in out["missing_inputs"]


def test_missing_scene_card_returns_nonzero(tmp_path):
    root = make_pipeline(tmp_path, scene_card=False)
    code, out = run_script(root)
    assert code == 1
    assert "pipeline/scene_S01/scene_card.md" in out["missing_inputs"]


def test_missing_a_aesthetic_returns_nonzero(tmp_path):
    root = make_pipeline(tmp_path, a_aesthetic=False)
    code, out = run_script(root)
    assert code == 1
    assert "pipeline/review/A_aesthetic.yaml" in out["missing_inputs"]


def test_standard_passes_with_a_only_no_bc(tmp_path):
    """adaptive：standard 模式 B/C 缺失不阻断（A + lint 全在）"""
    root = make_pipeline(tmp_path, b_narrative=False, c_structural=False)
    code, out = run_script(root)
    assert code == 0
    assert out["status"] == "ok"
    assert out["missing_inputs"] == []


def test_standard_optional_present_lists_b_and_c(tmp_path):
    """adaptive：B/C 文件存在时列入 optional_present，便于 scene-reviewer 按需消费"""
    root = make_pipeline(tmp_path)  # 全部都写
    code, out = run_script(root)
    assert code == 0
    assert "pipeline/review/B_narrative_consistency.yaml" in out.get("optional_present", [])
    assert "pipeline/review/C_structural_consistency.yaml" in out.get("optional_present", [])


def test_missing_any_lint_returns_nonzero(tmp_path):
    """3 份 lint 任一缺失 → 退出 1"""
    for missing in ("ai_filler", "lexical_stats", "dialogue"):
        root = make_pipeline(tmp_path / missing,
                             lint_ai_filler=missing != "ai_filler",
                             lint_lexical=missing != "lexical_stats",
                             lint_dialogue=missing != "dialogue")
        code, out = run_script(root)
        assert code == 1, f"missing {missing} should fail"
        assert f"pipeline/review/lint/S01.{missing}.yaml" in out["missing_inputs"]


def test_multiple_missing_listed_all(tmp_path):
    """多个 missing → 全部列出（standard 模式：B 已不在 required，故缺 A + lint = 2 项）"""
    root = make_pipeline(tmp_path, a_aesthetic=False, b_narrative=False,
                         lint_ai_filler=False)
    code, out = run_script(root)
    assert code == 1
    assert len(out["missing_inputs"]) == 2
    assert "pipeline/review/A_aesthetic.yaml" in out["missing_inputs"]
    assert "pipeline/review/lint/S01.ai_filler.yaml" in out["missing_inputs"]


def test_output_yaml_parseable(tmp_path):
    """stdout 是 YAML 格式，含 status / scene_id / missing_inputs 字段"""
    root = make_pipeline(tmp_path, a_aesthetic=False)
    code, out = run_script(root)
    assert code == 1
    assert "status" in out and "scene_id" in out and "missing_inputs" in out
    assert isinstance(out["missing_inputs"], list)


def test_different_scene_id(tmp_path):
    """--scene-id S02 校验 S02 路径"""
    root = make_pipeline(tmp_path, scene_id="S02")
    code, out = run_script(root, scene_id="S02")
    assert code == 0
