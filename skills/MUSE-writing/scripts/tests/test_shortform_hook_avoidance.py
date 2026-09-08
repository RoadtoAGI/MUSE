"""短链避让面回归——仍在运行的 Agent hook 对短链 dispatch payload 必须放行。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOKS = PLUGIN_ROOT / "hooks"

def _run_agent_hook(script: str, subagent_type: str, prompt: str):
    payload = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": subagent_type, "prompt": prompt, "description": ""},
    }
    return subprocess.run(
        ["bash", str(HOOKS / script)], input=json.dumps(payload),
        capture_output=True, text=True,
        env={"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def test_reviser_dispatch_passes_check_reviser_patch():
    """短链修订 dispatch 无 scene_id——check-reviser-patch fuzzy 路径静默跳过。"""
    r = _run_agent_hook("check-reviser-patch.sh", "short-manuscript-reviser",
                        "按 reader 模式修订 /tmp/run 的全文。")
    assert r.returncode == 0, r.stdout + r.stderr


def test_review_dispatch_passes_check_reviser_patch():
    r = _run_agent_hook("check-reviser-patch.sh", "short-story-review",
                        "为 /tmp/run 出第 1 轮全文审阅报告。")
    assert r.returncode == 0, r.stdout + r.stderr
