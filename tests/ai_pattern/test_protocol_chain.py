import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"


def _sh(args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_step56_one_round(tmp_path):
    wd = tmp_path / "run"
    (wd / "pipeline" / "review" / "lint").mkdir(parents=True)
    (wd / "pipeline" / "scenes").mkdir(parents=True)
    (wd / "pipeline" / "scene_S05").mkdir(parents=True)
    (wd / "pipeline" / "scenes" / "scene_S05.md").write_text("正文" * 300, encoding="utf-8")
    (wd / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump(
            {"scenes": [{"scene_id": "S05", "file_path": "pipeline/scenes/scene_S05.md"}]}
        ),
        encoding="utf-8",
    )
    (wd / "pipeline" / "run_state.yaml").write_text(
        yaml.safe_dump({"run_intent": "release"}), encoding="utf-8"
    )
    (wd / "pipeline" / "review" / "scene_S05.yaml").write_text(
        yaml.safe_dump({"scene_id": "S05", "verdict": "PASS", "written_by": "scene-reviewer"}),
        encoding="utf-8",
    )
    (wd / "pipeline" / "review" / "A_aesthetic.yaml").write_text(
        "findings: []\n", encoding="utf-8"
    )
    for sfx in ("lexical_stats", "dialogue"):
        (wd / "pipeline" / "review" / "lint" / f"S05.{sfx}.yaml").write_text(
            yaml.safe_dump({"hits": []}), encoding="utf-8"
        )
    hit_ids = [f"S05-micro-{index:03d}" for index in range(1, 10)]
    (wd / "pipeline" / "review" / "lint" / "S05.ai_filler.yaml").write_text(
        yaml.safe_dump(
            {
                "scene_id": "S05",
                "language": "zh",
                "input_text_sha256": hashlib.sha256(
                    ("正文" * 300).encode("utf-8")
                ).hexdigest(),
                "cluster_alerts": [
                    {
                        "family": "micro_punchline_cadence",
                        "cluster": "micro_punchline_cadence",
                        "severity": "high",
                        "hits": 9,
                        "hit_ids": hit_ids,
                    }
                ],
                "hits": [
                    {
                        "lint_id": hit_id,
                        "rule": "zero_yield_micro_clause_candidate",
                        "family": "micro_punchline_cadence",
                    }
                    for hit_id in hit_ids
                ],
            }
        ),
        encoding="utf-8",
    )

    rc, *_ = _sh([SCRIPTS / "machine_directive.py", "--work-dir", wd, "--scene-id", "S05"])
    assert rc == 0
    rc, *_ = _sh(
        [
            SCRIPTS / "machine_directive.py",
            "--work-dir",
            wd,
            "--scene-id",
            "S05",
            "--refresh",
            "--lint-artifact",
            wd / "pipeline/review/lint/S05.ai_filler.yaml",
        ]
    )
    assert rc == 0
    d = yaml.safe_load((wd / "pipeline" / "review" / "S05.machine_directive.yaml").read_text())
    assert d["dispatch_ready"] is True
    assert (wd / "pipeline" / "review" / "lint" / "S05.ai_filler.pre_dist.yaml").exists()

    (wd / "pipeline" / "scene_S05" / "distribution_summary.md").write_text(
        "**status**: complete\n", encoding="utf-8"
    )
    (wd / "pipeline" / "review" / "lint" / "S05.ai_filler.dist1.yaml").write_text(
        yaml.safe_dump({"cluster_alerts": [], "hits": []}), encoding="utf-8"
    )
    rc, *_ = _sh(
        [
            SCRIPTS / "distribution_gate.py",
            "--work-dir",
            wd,
            "--scene-id",
            "S05",
            "--attempt",
            "1",
            "--max-attempts",
            "2",
        ]
    )
    assert rc == 0

    sys.path.insert(0, str(SCRIPTS))
    import verify_review_complete as vrc

    assert vrc.check(wd) == 0
