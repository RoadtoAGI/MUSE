"""聚合本次选中且有效的报告；未选中的旧文件不产生新问题。"""
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "aggregate_global_findings.py"
NAMES = {"A": "A_aesthetic.yaml", "B": "B_narrative_consistency.yaml", "C": "C_structural_consistency.yaml"}


def write_review(work_dir, group, findings):
    review = work_dir / "pipeline/review"
    review.mkdir(parents=True, exist_ok=True)
    path = review / NAMES[group]
    path.write_text(yaml.safe_dump({"review_findings": findings}, allow_unicode=True))
    return path


def run(work_dir, *sources):
    args = [sys.executable, str(SCRIPT), "--work-dir", str(work_dir)]
    for source in sources:
        args.extend(["--source", source])
    return subprocess.run(args, capture_output=True, text=True)


def read_output(work_dir):
    return yaml.safe_load((work_dir / "pipeline/review/global_findings.yaml").read_text())


def write_manuscript_review(work_dir, review_round, text, findings):
    review = work_dir / "pipeline/review"
    snapshot_relative = f"pipeline/review/snapshots/story.semantic.round{review_round}.md"
    snapshot = work_dir / snapshot_relative
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(text)
    name = "A_aesthetic.manuscript.yaml" if review_round == 1 else "A_aesthetic.manuscript.post_revision.yaml"
    (review / name).write_text(yaml.safe_dump({
        "review_scope": "manuscript", "review_round": review_round,
        "input_snapshot": snapshot_relative,
        "semantic_review": "findings" if findings else "clear",
        "coverage": {"planning_trace_leakage": "clear"},
        "review_findings": findings,
        "summary": {"total_issues": len(findings), "by_dimension": {}},
    }, allow_unicode=True))


def test_selected_groups_filter_scene_findings_and_ignore_old_reports(tmp_path):
    write_review(tmp_path, "B", [{"scene_id": None, "issue": "B 全文问题"}, {"scene_id": "S02", "issue": "局部"}])
    write_review(tmp_path, "C", [{"scene_id": None, "issue": "C 全文问题"}])
    write_review(tmp_path, "A", [{"scene_id": None, "issue": "未采用的旧问题"}])
    result = run(tmp_path, "B", "C")
    assert result.returncode == 0, result.stderr
    out = read_output(tmp_path)
    assert out["total"] == 2
    assert out["sources_present"] == ["B", "C"]
    assert [item["source_group"] for item in out["global_findings"]] == ["B", "C"]
    assert [item["issue"] for item in out["global_findings"]] == ["B 全文问题", "C 全文问题"]


def test_selected_empty_review_is_valid_but_missing_or_invalid_is_not(tmp_path):
    path = write_review(tmp_path, "A", [])
    assert run(tmp_path, "A").returncode == 0
    assert read_output(tmp_path)["total"] == 0
    assert run(tmp_path, "B").returncode != 0
    path.write_text("review_findings: [")
    assert run(tmp_path, "A").returncode != 0
    assert run(tmp_path).returncode != 0


def test_manuscript_source_selects_current_round_and_keeps_located_findings(tmp_path):
    write_manuscript_review(tmp_path, 1, "初稿。", [])
    current = "修订稿仍有一处人物声音错误。"
    findings = [{
        "scene_id": "S01", "dimension": "voice_consistency", "source": "story",
        "location": "开头", "evidence_quote": "人物声音错误", "issue": "与当前人物冲突",
        "suggestion": "按角色依据修订",
    }]
    write_manuscript_review(tmp_path, 2, current, findings)
    (tmp_path / "story.md").write_text(current)
    result = run(tmp_path, "A-manuscript")
    assert result.returncode == 0, result.stderr
    out = read_output(tmp_path)
    assert out["total"] == 1
    assert out["global_findings"][0]["scene_id"] == "S01"
    assert out["source_reports"]["A-manuscript"].endswith(".post_revision.yaml")
    (tmp_path / "story.md").write_text("再次改变后的正文。")
    assert run(tmp_path, "A-manuscript").returncode != 0
