import hashlib
import pathlib
import subprocess
import sys

import yaml

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"


def _mk_workdir(tmp_path):
    text = "正文。"
    hit_ids = [f"S02-micro-{index:03d}" for index in range(1, 17)]
    lint = {
        "scene_id": "S02",
        "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "hits": [
            {
                "lint_id": hit_id,
                "rule": "zero_yield_micro_clause_candidate",
                "family": "micro_punchline_cadence",
            }
            for hit_id in hit_ids
        ],
        "cluster_alerts": [
            {
                "alert_id": "S02-micro_punchline_cadence-1",
                "cluster": "micro_punchline_cadence",
                "family": "micro_punchline_cadence",
                "severity": "high",
                "hits": 16,
                "hit_ids": hit_ids,
            }
        ],
    }
    lint_dir = tmp_path / "pipeline" / "review" / "lint"
    lint_dir.mkdir(parents=True)
    (lint_dir / "S02.ai_filler.yaml").write_text(yaml.safe_dump(lint, allow_unicode=True))
    scene_dir = tmp_path / "pipeline" / "scenes"
    scene_dir.mkdir(parents=True)
    (scene_dir / "scene_S02.md").write_text(text, encoding="utf-8")
    return tmp_path


def _run(work_dir, scene_id, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(work_dir),
            "--scene-id",
            scene_id,
            *extra,
        ],
        check=True,
    )


def test_refresh_injects_protected_regions(tmp_path):
    work_dir = _mk_workdir(tmp_path)
    _run(work_dir, "S02")
    scene_dir = work_dir / "pipeline" / "scene_S02"
    scene_dir.mkdir(parents=True)
    (scene_dir / "revision_summary.md").write_text(
        "status: complete\n\n"
        "1. **[patch 1 · issue_id A-7 · applied]** L45\n"
        "   - preserve: 判官式称谓与克制语态\n"
    )

    lint_path = work_dir / "pipeline/review/lint/S02.ai_filler.yaml"
    _run(work_dir, "S02", "--refresh", "--lint-artifact", str(lint_path))

    directive = yaml.safe_load((work_dir / "pipeline/review/S02.machine_directive.yaml").read_text())
    assert directive["stage"] == "refreshed"
    assert directive["dispatch_ready"] is True
    assert directive["protected_regions"]
    assert directive["protected_regions"][0]["patch_id"] == "patch 1"


def test_refresh_without_summary_empty_regions(tmp_path):
    work_dir = _mk_workdir(tmp_path)
    _run(work_dir, "S02")

    lint_path = work_dir / "pipeline/review/lint/S02.ai_filler.yaml"
    _run(work_dir, "S02", "--refresh", "--lint-artifact", str(lint_path))

    directive = yaml.safe_load((work_dir / "pipeline/review/S02.machine_directive.yaml").read_text())
    assert directive["dispatch_ready"] is True
    assert directive["protected_regions"] == []


def test_refresh_requires_explicit_lint_artifact(tmp_path):
    work_dir = _mk_workdir(tmp_path)
    _run(work_dir, "S02")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(work_dir),
            "--scene-id",
            "S02",
            "--refresh",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--lint-artifact is required with --refresh" in result.stderr


def test_refresh_rejects_stale_lint_without_mutating_active_pair(tmp_path):
    work_dir = _mk_workdir(tmp_path)
    _run(work_dir, "S02")
    directive_path = work_dir / "pipeline/review/S02.machine_directive.yaml"
    ledger_path = work_dir / "pipeline/review/S02.machine_ledger.yaml"
    directive_before = directive_path.read_bytes()
    ledger_before = ledger_path.read_bytes()
    (work_dir / "pipeline/scenes/scene_S02.md").write_text("已修订正文。", encoding="utf-8")
    lint_path = work_dir / "pipeline/review/lint/S02.ai_filler.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(work_dir),
            "--scene-id",
            "S02",
            "--refresh",
            "--lint-artifact",
            str(lint_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "lint input hash does not match current scene" in result.stderr
    assert directive_path.read_bytes() == directive_before
    assert ledger_path.read_bytes() == ledger_before
