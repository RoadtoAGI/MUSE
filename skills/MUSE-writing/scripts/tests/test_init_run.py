from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import init_run  # noqa: E402


def test_explicit_run_intent_is_written_and_reuse_preserves_sibling_fields(tmp_path):
    run_dir = tmp_path / "run"
    assert init_run.main(["--run-dir", str(run_dir), "--run-intent", "release"]) == 0
    state_path = run_dir / "pipeline" / "run_state.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert state["run_intent"] == "release"

    state["outline_gate"] = {"verdict": "PASS"}
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    assert init_run.main(["--run-dir", str(run_dir), "--run-intent", "release"]) == 0
    reused = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert reused == {"outline_gate": {"verdict": "PASS"}, "run_intent": "release"}


def test_explicit_reuse_refuses_run_intent_change(tmp_path):
    run_dir = tmp_path / "run"
    assert init_run.main(["--run-dir", str(run_dir), "--run-intent", "evaluation"]) == 0
    assert init_run.main(["--run-dir", str(run_dir), "--run-intent", "release"]) == 2
    state = yaml.safe_load((run_dir / "pipeline" / "run_state.yaml").read_text(encoding="utf-8"))
    assert state["run_intent"] == "evaluation"


def test_derived_run_writes_smoke_intent(tmp_path, capsys):
    rc = init_run.main([
        "--results-dir", str(tmp_path),
        "--slug", "intent-smoke",
        "--timestamp", "2026-07-16T1200",
        "--run-intent", "smoke",
    ])
    assert rc == 0
    run_dir = Path(capsys.readouterr().out.strip())
    state = yaml.safe_load((run_dir / "pipeline" / "run_state.yaml").read_text(encoding="utf-8"))
    assert state["run_intent"] == "smoke"
