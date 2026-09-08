"""init_short_run.py — 短链 run 目录骨架测试。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import init_short_run  # noqa: E402


def test_explicit_mode_creates_shortform_skeleton(tmp_path, capsys):
    run_dir = tmp_path / "results" / "bench" / "model" / "t1" / "001"
    rc = init_short_run.main(["--run-dir", str(run_dir)])
    assert rc == 0
    assert (run_dir / "pipeline" / "shortform").is_dir()
    assert (run_dir / "pipeline" / "shortform" / "review").is_dir()
    assert (run_dir / "pipeline" / "review" / "lint").is_dir()
    # 短链不产分场机制目录
    assert not (run_dir / "pipeline" / "scenes").exists()
    assert not (run_dir / "pipeline" / "staging").exists()
    assert not (run_dir / "pipeline" / "story-character-skills").exists()
    out = capsys.readouterr().out.strip()
    assert out == str(run_dir.resolve())


def test_explicit_mode_idempotent(tmp_path):
    run_dir = tmp_path / "run"
    assert init_short_run.main(["--run-dir", str(run_dir)]) == 0
    assert init_short_run.main(["--run-dir", str(run_dir)]) == 0


def test_derived_mode_with_timestamp(tmp_path, capsys):
    rc = init_short_run.main([
        "--results-dir", str(tmp_path), "--slug", "du-kou", "--timestamp", "2026-07-16T1200",
    ])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("2026-07-16T1200_du-kou")
    assert (Path(out) / "pipeline" / "shortform").is_dir()


def test_derived_mode_timestamp_conflict_errors(tmp_path):
    args = ["--results-dir", str(tmp_path), "--slug", "du-kou", "--timestamp", "2026-07-16T1200"]
    assert init_short_run.main(args) == 0
    assert init_short_run.main(args) == 2
