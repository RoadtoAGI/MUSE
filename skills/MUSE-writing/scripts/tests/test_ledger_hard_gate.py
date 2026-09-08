"""Rn+2 Task 3: ledger hard gate + malformed YAML 回归。"""
import subprocess
import sys
import hashlib
from pathlib import Path
import yaml
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "verify_review_complete.py"


def _setup_work(tmp_path, verdict, ledger_content=None, lint_v2=None):
    """Rn+2 R1 F1: 构造 work_dir/pipeline/... 结构。verify_review_complete.py 接 work_dir，
    内部访问 work_dir/pipeline/phase6_development.yaml；fixture 必须建 work_dir 而非 pipeline_dir。
    """
    work = tmp_path / "work"
    pipeline = work / "pipeline"
    review = pipeline / "review"
    lint = review / "lint"
    lint.mkdir(parents=True)
    scenes = pipeline / "scenes"
    scenes.mkdir(parents=True)
    text = "正文"
    (scenes / "scene_S01.md").write_text(text, encoding="utf-8")
    (pipeline / "run_state.yaml").write_text(
        yaml.safe_dump({"run_intent": "release"}), encoding="utf-8"
    )
    # phase6_development.yaml 让 check() 通过开头存在性 gate
    (pipeline / "phase6_development.yaml").write_text(
        yaml.dump(
            {
                "scenes": [
                    {
                        "scene_id": "S01",
                        "file_path": "pipeline/scenes/scene_S01.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (review / "scene_S01.yaml").write_text(
        yaml.dump({"scene_id": "S01", "verdict": verdict, "review_stage": "first_cut"}),
        encoding="utf-8",
    )
    if ledger_content is not None:
        (review / "scene_S01.lint_resolution_ledger.yaml").write_text(ledger_content, encoding="utf-8")
    if lint_v2 is not None:
        lint_v2 = dict(lint_v2)
        lint_v2.setdefault("input_text_sha256", hashlib.sha256(text.encode("utf-8")).hexdigest())
        lint_v2.setdefault("language", "zh")
        (lint / "S01.ai_filler.v2.yaml").write_text(yaml.dump(lint_v2), encoding="utf-8")
    else:
        (lint / "S01.ai_filler.yaml").write_text(yaml.safe_dump({
            "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "language": "zh",
            "hits": [],
            "cluster_alerts": [],
        }), encoding="utf-8")
    (review / "design_validation.yaml").write_text(yaml.dump({"verdict": "PASS"}), encoding="utf-8")
    # PATCH 需 patch_directive.applied + post_revision PASS 才不会被既有 PATCH 路径拦
    if verdict == "PATCH":
        scene_dir = pipeline / "scene_S01"
        scene_dir.mkdir()
        (scene_dir / "patch_directive.applied.yaml").write_text("applied: []", encoding="utf-8")
        (review / "scene_S01.post_revision.yaml").write_text(
            yaml.dump({"verdict": "PASS", "review_stage": "post_revision"}),
            encoding="utf-8",
        )
    return work


def _run(work_dir):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(work_dir)],
        capture_output=True, text=True,
    )




def test_ledger_malformed_yaml_hard_fail(tmp_path):
    bad = 'v1_triage:\n  - lint_id: "S01-x-001"\n    reason: "不是扔，是放" — 非法\n'
    work = _setup_work(tmp_path, "PASS", ledger_content=bad)
    result = _run(work)
    assert result.returncode != 0
    assert ("malformed" in (result.stderr + result.stdout).lower()
            or "parser" in (result.stderr + result.stdout).lower()
            or "yaml" in (result.stderr + result.stdout).lower())




def test_ledger_missing_pass_zero_hit_advisory(tmp_path):
    lint_v2 = {"lint_hits": [], "cluster_alerts": []}
    work = _setup_work(tmp_path, "PASS", ledger_content=None, lint_v2=lint_v2)
    result = _run(work)
    assert result.returncode == 0


def test_diagnostic_high_hit_does_not_require_a_second_ledger(tmp_path):
    lint = {"hits": [{"lint_id": "S01-x-001", "family": "lexical_cliche",
                      "rule": "keyword_cliche", "severity": "high"}], "cluster_alerts": []}
    work = _setup_work(tmp_path, "PASS", lint_v2=lint)
    assert _run(work).returncode == 0
