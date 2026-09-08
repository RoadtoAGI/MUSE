"""Current-policy dispatch, hit partition, and input authenticity checks."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/MUSE-writing/scripts"
SCENE_ID = "S02"


def _write(tmp_path, hits, alerts=(), *, text="它伏在门边。它随风晃动。", observed=(), lang="zh"):
    review = tmp_path / "pipeline/review"
    (review / "lint").mkdir(parents=True)
    scenes = tmp_path / "pipeline/scenes"
    scenes.mkdir(parents=True)
    (scenes / f"scene_{SCENE_ID}.md").write_text(text, encoding="utf-8")
    lint = {
        "scene_id": SCENE_ID, "language": lang,
        "input_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "hits": hits, "cluster_alerts": list(alerts), "observed_alerts": list(observed),
    }
    path = review / "lint" / f"{SCENE_ID}.ai_filler.yaml"
    path.write_text(yaml.safe_dump(lint, allow_unicode=True), encoding="utf-8")
    return path


def _run(work_dir, *, error=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "machine_directive.py"),
         "--work-dir", str(work_dir), "--scene-id", SCENE_ID],
        capture_output=True, text=True,
    )
    if error:
        assert result.returncode == 2
        assert error in result.stderr
        assert not (work_dir / f"pipeline/review/{SCENE_ID}.machine_directive.yaml").exists()
        return
    assert result.returncode == 0, result.stderr
    return tuple(yaml.safe_load((work_dir / f"pipeline/review/{SCENE_ID}.machine_{kind}.yaml").read_text())
                 for kind in ("directive", "ledger"))


def _hit(hit_id, start, span="它", family="dummy_pronoun"):
    return {"lint_id": hit_id, "rule": family, "family": family,
            "locator": {"start": start, "end": start + len(span), "span": span},
            "evidence_quote": span}


@pytest.mark.parametrize("lang,family,severity", [
    ("zh", "micro_punchline_cadence", "high"),
    ("zh", "lexical_cliche", "medium"),
    ("zh", "action_log", "high"),
    ("zh", "meta_language_leak", "catastrophic"),
    ("en", "contrastive_negation_assertion", "high"),
])
def test_observe_alert_severity_does_not_create_repair_tasks(tmp_path, lang, family, severity):
    _write(tmp_path, [], [{"family": family, "severity": severity, "hits": 9}], lang=lang)
    directive, ledger = _run(tmp_path)
    assert directive["entries"] == []
    assert directive["stage"] == "post_lint"
    assert directive["dispatch_ready"] is False
    assert [(e["family"], e["level"], e["status"]) for e in ledger["entries"]] == [(family, "L", "observed")]


def test_referential_contract_reaches_directive_and_pending_ledger(tmp_path):
    text = "它伏在门边。这道口子很深。"
    hits = [_hit("dummy-1", 0), _hit("classifier-1", text.index("这道"), "这道", "demonstrative_classifier")]
    _write(tmp_path, hits, text=text)
    directive, ledger = _run(tmp_path)
    assert {(e["family"], e["level"]) for e in directive["entries"]} == {
        ("dummy_pronoun", "S"), ("demonstrative_classifier", "S")}
    assert directive["active_revision_id"] == ledger["active_revision_id"]
    for entry, reducer in zip(directive["entries"], ledger["entries"]):
        assert [r["lint_id"] for r in entry["hit_records"]] == entry["all_hit_ids"]
        assert entry["remaining_hit_ids"] == entry["all_hit_ids"]
        assert entry["exempted_hit_ids"] == []
        assert reducer["status"] == "issued"
        assert {r["status"] for r in reducer["hit_resolutions"]} == {"pending"}


def test_current_contract_cannot_be_routed_through_old_observed_artifact(tmp_path):
    _write(tmp_path, [_hit("dummy-1", 0)], observed=[{
        "family": "dummy_pronoun", "blocking": False, "hit_ids": ["dummy-1"]}])
    _run(tmp_path, error="enforced family routed through observed_alerts")


def test_contract_rebuilds_partition_from_raw_hits_not_stale_alert_ids(tmp_path):
    hits = [_hit("dummy-1", 0), _hit("dummy-2", 6)]
    _write(tmp_path, hits, [{"family": "dummy_pronoun", "severity": "low",
                             "hits": 99, "hit_ids": ["dummy-1", "missing", "dummy-1"]}])
    directive, ledger = _run(tmp_path)
    entry = directive["entries"][0]
    assert entry["all_hit_ids"] == ["dummy-1", "dummy-2"]
    assert entry["remaining_hit_ids"] == entry["all_hit_ids"]
    assert [r["lint_id"] for r in entry["hit_records"]] == entry["all_hit_ids"]
    assert ledger["entries"][0]["remaining_hit_ids"] == entry["all_hit_ids"]


def test_duplicate_raw_hit_ids_are_rejected(tmp_path):
    _write(tmp_path, [_hit("duplicate", 0), _hit("duplicate", 6)])
    _run(tmp_path, error="duplicate lint_id")


def test_density_contract_requires_actual_current_scene(tmp_path):
    _write(tmp_path, [_hit("dummy-1", 0)])
    (tmp_path / f"pipeline/scenes/scene_{SCENE_ID}.md").write_text("改写后的正文。", encoding="utf-8")
    _run(tmp_path, error="requires lint for the current scene text")


def test_legal_referential_density_does_not_create_a_task(tmp_path):
    text = "它伏在门边。" + "雨沿瓦沟落下，祖父把断裂的竹骨一根根换好。" * 100
    _write(tmp_path, [_hit("dummy-1", 0)], [{"family": "dummy_pronoun", "severity": "high", "hit_ids": ["dummy-1"]}], text=text)
    directive, ledger = _run(tmp_path)
    assert directive["entries"] == []
    assert ledger["entries"][0]["status"] == "observed"
