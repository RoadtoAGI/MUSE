import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"

MICRO_HIT_IDS = [f"S03-micro-{index:03d}" for index in range(1, 10)]
DIRTY_ALERT = {
    "family": "micro_punchline_cadence",
    "cluster": "micro_punchline_cadence",
    "severity": "high",
    "hits": 9,
    "hit_ids": MICRO_HIT_IDS,
}


def _wd(tmp_path):
    wd = tmp_path / "run"
    (wd / "pipeline" / "review" / "lint").mkdir(parents=True)
    (wd / "pipeline" / "scenes").mkdir(parents=True)
    (wd / "pipeline" / "scene_S03").mkdir(parents=True)
    text = "正文。"
    (wd / "pipeline" / "scenes" / "scene_S03.md").write_text(text, encoding="utf-8")
    (wd / "pipeline" / "review" / "lint" / "S03.ai_filler.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S03",
            "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "cluster_alerts": [dict(DIRTY_ALERT)],
            "hits": [
                {
                    "lint_id": hit_id,
                    "rule": "zero_yield_micro_clause_candidate",
                    "family": "micro_punchline_cadence",
                }
                for hit_id in MICRO_HIT_IDS
            ],
        }), encoding="utf-8"
    )
    return wd


def _run(wd, *extra):
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(wd),
            "--scene-id",
            "S03",
            *extra,
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return yaml.safe_load((wd / "pipeline" / "review" / "S03.machine_directive.yaml").read_text())


def test_lint_suffix_regenerates_from_residual(tmp_path):
    wd = _wd(tmp_path)
    _run(wd)
    lexical_hit_ids = [f"S03-lexical-{index:03d}" for index in range(1, 4)]
    residual = {
        "scene_id": "S03",
        "input_text_sha256": hashlib.sha256("正文。".encode("utf-8")).hexdigest(),
        "cluster_alerts": [
            {
                "family": "lexical_cliche",
                "cluster": "lexical_cliche",
                "severity": "high",
                "hits": 3,
                "hit_ids": lexical_hit_ids,
            }
        ],
        "hits": [
            {
                "lint_id": hit_id,
                "rule": "keyword_ai_cliche",
                "family": "lexical_cliche",
            }
            for hit_id in lexical_hit_ids
        ],
    }
    (wd / "pipeline" / "review" / "lint" / "S03.ai_filler.dist1.yaml").write_text(
        yaml.safe_dump(residual), encoding="utf-8"
    )
    d = _run(wd, "--lint-suffix", "dist1")
    assert d["entries"] == []
    assert d["dispatch_ready"] is False
    ledger = yaml.safe_load((wd / "pipeline" / "review" / "S03.machine_ledger.yaml").read_text())
    assert {e["family"] for e in ledger["entries"]} == {"lexical_cliche"}
    assert all(e["status"] == "observed" for e in ledger["entries"])
    ids = {e["id"] for e in ledger["entries"]}
    assert not any("micro_punchline_cadence" in i for i in ids)
    assert any(
        any("micro_punchline_cadence" in entry["id"] for entry in revision["entries"])
        for revision in ledger["history"]
    )


def test_refresh_snapshots_pre_dist_once(tmp_path):
    wd = _wd(tmp_path)
    _run(wd)
    lint_path = wd / "pipeline/review/lint/S03.ai_filler.yaml"
    _run(wd, "--refresh", "--lint-artifact", str(lint_path))
    pre = wd / "pipeline" / "review" / "lint" / "S03.ai_filler.pre_dist.yaml"
    assert pre.exists()
    scene_snapshot = wd / "pipeline" / "review" / "snapshots" / "S03.pre_dist.md"
    assert scene_snapshot.read_text(encoding="utf-8") == "正文。"
    marker = pre.read_text() + "\n# marker"
    pre.write_text(marker, encoding="utf-8")
    scene_marker = scene_snapshot.read_text(encoding="utf-8") + "\n<!-- marker -->"
    scene_snapshot.write_text(scene_marker, encoding="utf-8")
    _run(wd, "--refresh", "--lint-artifact", str(lint_path))
    assert pre.read_text() == marker
    assert scene_snapshot.read_text(encoding="utf-8") == scene_marker
