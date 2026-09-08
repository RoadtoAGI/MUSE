from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


HOOK = Path(__file__).resolve().parents[2] / "hooks" / "verify-review-complete.sh"


def test_missing_verifier_blocks_assemble(tmp_path):
    work_dir = tmp_path / "run"
    work_dir.mkdir()
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    payload = {
        "tool_input": {
            "command": f"python3 {plugin_root}/scripts/assemble_story.py {work_dir}"
        }
    }
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(plugin_root))
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode == 2
    assert "verify_review_complete.py" in result.stderr



def test_local_hook_resolves_verifier_from_its_package(tmp_path):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    payload = {"tool_input": {"command": f"python3 assemble_story.py {tmp_path}"}}
    result = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload), text=True, capture_output=True, env=env)
    assert result.returncode == 2  # The real verifier rejects the incomplete run.
    assert "未找到" not in result.stderr
    assert "run_intent" in result.stdout + result.stderr
