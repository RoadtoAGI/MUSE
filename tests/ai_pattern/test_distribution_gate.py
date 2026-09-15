import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _wd(
    tmp_path,
    post_alerts,
    post_hits,
    summary_status="complete",
    protected=(),
    declare=True,
    *,
    pre_alerts=None,
    pre_hits=None,
    before_text=None,
    after_text=None,
    target_family="dummy_pronoun",
):
    wd = tmp_path / "run"
    (wd / "pipeline" / "review" / "lint").mkdir(parents=True)
    (wd / "pipeline" / "scenes").mkdir(parents=True)
    (wd / "pipeline" / "scene_S02").mkdir(parents=True)
    before_text = before_text if before_text is not None else "正文" * 500
    after_text = after_text if after_text is not None else before_text
    (wd / "pipeline" / "scenes" / "scene_S02.md").write_text(after_text, encoding="utf-8")
    snapshots = wd / "pipeline" / "review" / "snapshots"
    snapshots.mkdir(parents=True)
    (snapshots / "S02.pre_dist.md").write_text(before_text, encoding="utf-8")
    (wd / "pipeline" / "review" / "lint" / "S02.ai_filler.pre_dist.yaml").write_text(
        yaml.safe_dump(
            {
                "language": "zh",
                "input_text_sha256": hashlib.sha256(before_text.encode()).hexdigest(),
                "density": {"total_chars": len(before_text)},
                "cluster_alerts": pre_alerts if pre_alerts is not None else [],
                "hits": pre_hits or [],
            }
        ),
        encoding="utf-8",
    )
    (wd / "pipeline" / "review" / "lint" / "S02.ai_filler.dist1.yaml").write_text(
        yaml.safe_dump({
            "language": "zh",
            "input_text_sha256": hashlib.sha256(after_text.encode()).hexdigest(),
            "density": {"total_chars": len(after_text)},
            "cluster_alerts": post_alerts,
            "hits": post_hits,
        }), encoding="utf-8"
    )
    (wd / "pipeline" / "review" / "S02.machine_directive.yaml").write_text(
        yaml.safe_dump(
            {
                "scene_id": "S02",
                "stage": "refreshed",
                "dispatch_ready": True,
                "entries": [
                    {
                        "id": f"S02-{target_family}-1",
                        "family": target_family,
                        "level": "S",
                        "severity": "high",
                        "hits": 9,
                        "repair_hint": "x",
                        "status": "pending",
                    }
                ],
                "protected_regions": [{"patch_id": p, "preserve": ["x"]} for p in protected],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (wd / "pipeline" / "review" / "S02.machine_ledger.yaml").write_text(
        yaml.safe_dump(
            {
                "entries": [
                    {
                        "id": f"S02-{target_family}-1",
                        "family": target_family,
                        "level": "S",
                        "status": "issued",
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    lines = [f"**status**: {summary_status}", ""]
    if declare:
        lines += [f"- 保护区 {p}：未动" for p in protected]
    (wd / "pipeline" / "scene_S02" / "distribution_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return wd


def _gate(wd, attempt=1, max_attempts=2):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "distribution_gate.py"),
            "--work-dir",
            str(wd),
            "--scene-id",
            "S02",
            "--attempt",
            str(attempt),
            "--max-attempts",
            str(max_attempts),
        ],
        capture_output=True,
        text=True,
    )


def test_clean_pass_resolves_entries(tmp_path):
    wd = _wd(tmp_path, post_alerts=[], post_hits=[], protected=("patch 1",))
    r = _gate(wd)
    assert r.returncode == 0, r.stdout + r.stderr
    d = yaml.safe_load((wd / "pipeline" / "review" / "S02.machine_directive.yaml").read_text())
    assert all(e["status"] == "resolved" for e in d["entries"])
    report = yaml.safe_load((wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text())
    assert report["verdict"] == "PASS"
    assert report["revision_quality"]["lane"] == "distribution"
    assert report["revision_quality"]["retention"]["chars"] == 1.0
    assert report["protected_results"] == {
        "verdict": "PASS",
        "literal_results": [],
        "active_tokens_before": [],
        "active_tokens_after": [],
        "active_relations_before": [],
        "active_relations_after": [],
        "relation_overlaps": [],
    }


def test_retention_observation_is_joint_audit_and_does_not_block(tmp_path):
    wd = _wd(
        tmp_path,
        post_alerts=[],
        post_hits=[],
        before_text="甲。" * 500,
        after_text="甲。" * 300,
    )

    result = _gate(wd)

    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["revision_quality"]["retention"]["chars"] == 0.6
    assert report["revision_quality"]["observations"][0]["blocking"] is False
    assert report["audit_observations"] == report["revision_quality"]["observations"]


def test_distribution_rejects_literal_loss_and_relation_overlap(tmp_path):
    from protected_integrity import (
        append_declaration_snapshot,
        append_relation_verifications,
        append_token_verifications,
        scene_sha256,
    )

    before = "开头。甲没有下令。她仍是十七岁。结尾。"
    after = "开头。甲已经下令。她的年龄被删掉。结尾。"
    wd = _wd(
        tmp_path,
        post_alerts=[],
        post_hits=[],
        before_text=before,
        after_text=after,
    )
    token = {
        "token_id": "T1",
        "patch_id": "patch_01",
        "source": "old_span",
        "raw": "十七岁",
        "match_mode": "exact",
        "accepted_forms": [],
        "scope": "scene",
    }
    relation = {
        "relation_id": "R1",
        "patch_id": "patch_01",
        "type": "polarity",
        "expected": "甲未下令",
        "before_quote": "甲没有下令。",
    }
    append_declaration_snapshot(
        wd, "S02", "round1", tokens=[token], relations=[relation]
    )
    literal = "十七岁"
    literal_start = before.index(literal)
    append_token_verifications(wd, "S02", before, [{
        "patch_id": "patch_01",
        "token_id": "T1",
        "matched_form": literal,
        "current_span": {
            "start": literal_start,
            "end": literal_start + len(literal),
        },
        "scene_sha": scene_sha256(before),
    }])
    quote = "甲没有下令。"
    start = before.index(quote)
    append_relation_verifications(wd, "S02", before, [{
        "relation_id": "R1",
        "patch_id": "patch_01",
        "preserved": True,
        "after_quote": quote,
        "reason": "否定极性保持",
        "current_span": {"start": start, "end": start + len(quote)},
        "scene_sha": scene_sha256(before),
    }])

    result = _gate(wd)

    assert result.returncode == 1, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["protected_results"]["verdict"] == "FAIL"
    assert "active_token_not_found" in report["protected_results"]["reason"]
    protected_check = next(
        check for check in report["checks"] if check["name"] == "protected_integrity"
    )
    assert protected_check["blocking"] is True
    assert protected_check["ok"] is False


def test_distribution_allows_change_outside_active_relation(tmp_path):
    from protected_integrity import (
        append_declaration_snapshot,
        append_relation_verifications,
        scene_sha256,
    )

    before = "开头。甲没有下令。旧结尾。"
    after = "开头。甲没有下令。新结尾更具体。"
    wd = _wd(
        tmp_path,
        post_alerts=[],
        post_hits=[],
        before_text=before,
        after_text=after,
    )
    relation = {
        "relation_id": "R1",
        "patch_id": "patch_01",
        "type": "polarity",
        "expected": "甲未下令",
        "before_quote": "甲没有下令。",
    }
    append_declaration_snapshot(wd, "S02", "round1", tokens=[], relations=[relation])
    quote = "甲没有下令。"
    start = before.index(quote)
    append_relation_verifications(wd, "S02", before, [{
        "relation_id": "R1",
        "patch_id": "patch_01",
        "preserved": True,
        "after_quote": quote,
        "reason": "否定极性保持",
        "current_span": {"start": start, "end": start + len(quote)},
        "scene_sha": scene_sha256(before),
    }])

    result = _gate(wd)

    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["protected_results"]["verdict"] == "PASS"
    assert report["protected_results"]["relation_overlaps"] == []


def test_protected_distribution_requires_the_pre_dist_snapshot(tmp_path):
    from protected_integrity import append_declaration_snapshot

    wd = _wd(tmp_path, post_alerts=[], post_hits=[])
    append_declaration_snapshot(
        wd,
        "S02",
        "round1",
        tokens=[{
            "token_id": "T1",
            "patch_id": "patch_01",
            "source": "old_span",
            "raw": "正文",
            "match_mode": "exact",
            "accepted_forms": [],
            "scope": "scene",
        }],
        relations=[],
    )
    (wd / "pipeline" / "review" / "snapshots" / "S02.pre_dist.md").unlink()

    result = _gate(wd)

    assert result.returncode == 1
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert "pre_dist_snapshot_missing" in report["protected_results"]["reason"]


def test_distribution_reuses_post_revision_patch_span_token_anchor(tmp_path):
    from protected_integrity import (
        append_declaration_snapshot,
        load_scene_integrity,
        verify_post_revision_review,
    )

    before = "开头。她仍是十七岁。旧结尾。"
    after = "更具体的开头。她仍是十七岁。新结尾。"
    wd = _wd(
        tmp_path,
        post_alerts=[],
        post_hits=[],
        before_text=before,
        after_text=before,
    )
    append_declaration_snapshot(
        wd,
        "S02",
        "round1",
        tokens=[{
            "token_id": "T1",
            "patch_id": "patch_01",
            "source": "old_span",
            "raw": "十七岁",
            "match_mode": "exact",
            "accepted_forms": [],
            "scope": "patch_span",
        }],
        relations=[],
    )
    (wd / "pipeline" / "scene_S02" / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** 保留年龄\n"
        "   - new_span：她仍是十七岁。\n",
        encoding="utf-8",
    )
    (wd / "pipeline" / "review" / "scene_S02.post_revision.yaml").write_text(
        yaml.safe_dump({"verdict": "PASS", "written_by": "orchestrator_fastpath_gate"}),
        encoding="utf-8",
    )
    assert verify_post_revision_review(wd, "S02")[0] == 0
    (wd / "pipeline" / "scenes" / "scene_S02.md").write_text(after, encoding="utf-8")
    post_path = wd / "pipeline" / "review" / "lint" / "S02.ai_filler.dist1.yaml"
    post = yaml.safe_load(post_path.read_text(encoding="utf-8"))
    post["input_text_sha256"] = hashlib.sha256(after.encode()).hexdigest()
    post_path.write_text(yaml.safe_dump(post), encoding="utf-8")

    result = _gate(wd)

    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["protected_results"]["verdict"] == "PASS"
    assert report["protected_results"]["active_tokens_after"][0]["matched_form"] == "十七岁"
    token_history = load_scene_integrity(wd, "S02")["token_verifications"]
    assert token_history[-1]["scene_sha"] == hashlib.sha256(after.encode()).hexdigest()


@pytest.mark.parametrize("family", ["micro_punchline_cadence", "lexical_cliche"])
def test_observed_residual_does_not_block(tmp_path, family):
    wd = _wd(tmp_path, post_alerts=[{"family": family, "severity": "high", "hits": 9}], post_hits=[])
    assert _gate(wd).returncode == 0


def test_final_attempt_reference_density_remains_observation(tmp_path):
    from ai_filler_lint import analyze

    text = "它伏在门边。" * 9 + "正文" * 500
    lint = analyze(text, scene_id="S02", lang="zh")
    wd = _wd(tmp_path, post_alerts=lint["cluster_alerts"], post_hits=lint["hits"],
             pre_alerts=lint["cluster_alerts"], pre_hits=lint["hits"],
             before_text=text, after_text=text)
    lint_dir = wd / "pipeline/review/lint"
    (lint_dir / "S02.ai_filler.dist2.yaml").write_bytes((lint_dir / "S02.ai_filler.dist1.yaml").read_bytes())
    assert _gate(wd, attempt=2, max_attempts=2).returncode == 0
    report = yaml.safe_load((wd / "pipeline/review/S02.distribution_gate.yaml").read_text())
    assert report["family_regression"]["families"]["dummy_pronoun"]["decision"] == "observe_only"


def test_missing_attempt_lint_is_input_error(tmp_path):
    wd = _wd(tmp_path, post_alerts=[], post_hits=[])
    assert _gate(wd, attempt=2, max_attempts=2).returncode == 2


def test_undeclared_protected_region_fails(tmp_path):
    wd = _wd(tmp_path, post_alerts=[], post_hits=[], protected=("patch 1",), declare=False)
    assert _gate(wd).returncode == 1


def test_reference_count_change_does_not_decide_semantic_repair(tmp_path):
    from ai_filler_lint import analyze

    before_text = "它伏在门边。" * 4 + "正文" * 500
    after_text = "它伏在门边。" + "正文" * 500
    before = analyze(before_text, scene_id="S02", lang="zh")
    after = analyze(after_text, scene_id="S02", lang="zh")
    wd = _wd(tmp_path, post_alerts=after["cluster_alerts"], post_hits=after["hits"],
             pre_alerts=before["cluster_alerts"], pre_hits=before["hits"],
             before_text=before_text, after_text=after_text)
    result = _gate(wd)
    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load((wd / "pipeline/review/S02.distribution_gate.yaml").read_text())
    assert report["family_regression"]["families"]["dummy_pronoun"]["decision"] == "observe_only"


def test_non_target_worsening_is_observed_but_does_not_block(tmp_path):
    wd = _wd(
        tmp_path,
        post_alerts=[{"family": "dash_overuse", "severity": "high", "hits": 2}],
        post_hits=[
            {"family": "dash_overuse", "lint_id": "d1", "severity": "high"},
            {"family": "dash_overuse", "lint_id": "d2", "severity": "high"},
        ],
        pre_alerts=[{"family": "dash_overuse", "severity": "low", "hits": 1}],
        pre_hits=[{"family": "dash_overuse", "lint_id": "d0", "severity": "low"}],
    )
    # Keep the directive's target family absent in both snapshots; the family is
    # therefore a non-target observation, not a newly introduced family.
    result = _gate(wd)
    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["family_regression"]["families"]["dash_overuse"]["decision"] == "observe_only"


def test_observe_family_is_report_only(tmp_path):
    wd = _wd(
        tmp_path,
        post_alerts=[{"family": "meta_language_leak", "severity": "high", "hits": 3}],
        post_hits=[
            {"family": "meta_language_leak", "lint_id": f"o{i}", "severity": "high"}
            for i in range(3)
        ],
        pre_alerts=[],
    )
    result = _gate(wd)
    assert result.returncode == 0, result.stdout + result.stderr
    report = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.distribution_gate.yaml").read_text()
    )
    assert report["family_regression"]["families"]["meta_language_leak"]["decision"] == "observe_only"
