"""Expression diagnostics preserve current-text review and existing state contracts."""
from pathlib import Path
import subprocess
import sys

import yaml

SCRIPTS = Path(__file__).resolve().parents[1]


def run(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          capture_output=True, text=True)


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_real_lint_candidates_reach_review_without_automatic_rewrite(tmp_path):
    scene = tmp_path / "pipeline/scenes/scene_S01.md"
    scene.parent.mkdir(parents=True)
    scene.write_text("他怔了怔。\n\n她没说话。\n\n不是恐惧，是认出来了。\n\n" * 12)
    lint = run("ai_filler_lint.py", "--work-dir", tmp_path, "--scene-id", "S01", "--lang", "zh")
    assert lint.returncode == 0, lint.stderr
    issued = run("machine_directive.py", "--work-dir", tmp_path, "--scene-id", "S01")
    assert issued.returncode == 0, issued.stderr
    review = tmp_path / "pipeline/review"
    directive = yaml.safe_load((review / "S01.machine_directive.yaml").read_text())
    ledger = yaml.safe_load((review / "S01.machine_ledger.yaml").read_text())
    assert directive["entries"] == []
    assert ledger["entries"] and all(e["status"] == "observed" for e in ledger["entries"])
    summary = tmp_path / "pipeline/scene_S01/revision_summary.md"
    summary.parent.mkdir()
    summary.write_text("[patch_01 · issue_id I1 · kind rewrite_span · applied] 开场\npreserve：等待仍由甲主动选择\n")
    refreshed = run("machine_directive.py", "--work-dir", tmp_path, "--scene-id", "S01", "--refresh")
    assert refreshed.returncode == 0, refreshed.stderr
    refreshed_directive = yaml.safe_load((review / "S01.machine_directive.yaml").read_text())
    assert refreshed_directive["dispatch_ready"] is True
    assert refreshed_directive["protected_regions"] == [{"patch_id": "patch_01", "issue_id": "I1",
        "location": "开场", "preserve": "等待仍由甲主动选择"}]
    report_run = run("wholetext_gate.py", "--story", scene, "--work-dir", tmp_path, "--lang", "zh")
    assert report_run.returncode == 0, report_run.stderr
    report = yaml.safe_load((review / "wholetext_gate.yaml").read_text())
    assert report["verdict"] == "REVIEW" and report["review_required"]
    assert report["observations"][0]["hit_records"]
    assert report["triggers"] == []
    # Re-running initial issue creation cannot overwrite a refreshed pair.
    assert run("machine_directive.py", "--work-dir", tmp_path, "--scene-id", "S01").returncode == 2


def test_legacy_objections_require_current_evidence_without_quantity_quota(tmp_path):
    review = tmp_path / "pipeline/review"
    scene = tmp_path / "pipeline/scenes/scene_S01.md"
    scene.parent.mkdir(parents=True)
    scene.write_text("甲等乙。乙在等丙。丙等丁。丁等甲。门还开着。")
    entries = [{"id": f"i{i}", "family": "silence_pause_cliche", "level": "S", "status": "pending"}
               for i in range(5)]
    put(review / "S01.machine_directive.yaml", {"scene_id": "S01", "entries": entries})
    put(review / "S01.machine_ledger.yaml", {"scene_id": "S01", "entries": entries})
    put(review / "lint/S01.ai_filler.yaml", {"hits": [], "cluster_alerts": []})
    objections = [{"target_entry_id": f"i{i}", "family": "silence_pause_cliche",
                   "evidence_quote": quote, "function_claim": "保留此刻等待的人物关系"}
                  for i, quote in enumerate(["甲等乙", "乙在等丙", "丙等丁", "丁等甲", "此句不在正文"])]
    put(review / "S01.machine_objection.yaml", {"objections": objections})
    result = run("machine_directive.py", "--work-dir", tmp_path, "--scene-id", "S01", "--refresh")
    assert result.returncode == 0, result.stderr
    directive = yaml.safe_load((review / "S01.machine_directive.yaml").read_text())
    assert [entry["id"] for entry in directive["entries"]] == ["i4"]
    ledger = yaml.safe_load((review / "S01.machine_ledger.yaml").read_text())
    assert [entry["status"] for entry in ledger["entries"]] == ["objection_granted"] * 4 + ["pending"]
    assert ledger["entries"][-1]["objection_denied_reason"] == "evidence_quote_not_found"


def test_family_observation_and_bad_input_have_distinct_results(tmp_path):
    before, after = tmp_path / "before.yaml", tmp_path / "after.yaml"
    put(before, {"hits": []})
    put(after, {"hits": [{"family": "silence_pause_cliche"}]})
    result = run("family_gate.py", "--before", before, "--after", after)
    assert result.returncode == 0 and result.stdout.startswith("REVIEW")
    after.write_text("[unclosed")
    assert run("family_gate.py", "--before", before, "--after", after).returncode == 2


def test_orchestrator_fastpath_cannot_supply_semantic_pass(tmp_path):
    scene = tmp_path / "pipeline/scenes/scene_S01.md"
    scene.parent.mkdir(parents=True)
    scene.write_text("雨停了。")
    put(tmp_path / "pipeline/phase6_development.yaml", {"scenes": [{"scene_id": "S01"}]})
    review_path = tmp_path / "pipeline/review/scene_S01.yaml"
    put(review_path, {"scene_id": "S01", "verdict": "PASS"})
    assert run("verify_review_complete.py", tmp_path).returncode == 0
    put(review_path, {"scene_id": "S01", "verdict": "PASS", "written_by": "orchestrator_fastpath_gate"})
    result = run("verify_review_complete.py", tmp_path)
    assert result.returncode == 2 and "orchestrator_fastpath_gate" in result.stderr
