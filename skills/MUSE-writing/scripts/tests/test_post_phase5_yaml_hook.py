"""post-phase5-yaml hook（PostToolUse）端到端测试。退出码契约：0=放行；2=阻断。"""
import json
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "post-phase5-yaml.py"
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def run_hook(file_path):
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(file_path)}}
    return subprocess.run(
        ["python3", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True,
        env={"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def _scene_body():
    return (
        "sequence_expansions:\n"
        "  - sequence_id: SEQ1\n"
        "    scenes:\n"
        "      - scene_id: S01\n"
        "        scene_tasks:\n"
        "          - \"[核心][main] 让主角失去容身处\"\n"
        "        prose_risk_contract:\n"
        "          used: false\n"
    )


def test_no_marker_string_tasks_blocked(tmp_path):
    p = tmp_path / "run" / "pipeline"
    p.mkdir(parents=True)
    f = p / "phase5_scenes.yaml"
    f.write_text(_scene_body(), encoding="utf-8")
    r = run_hook(f)
    assert r.returncode == 2
    assert "scene_task 必须是 object" in (r.stderr + r.stdout)


def test_full_scan_always_on():
    """T3 回退后：scene-tasks 与 inspiration-refs 双扫描恒开，无任何跳闸分支（源码级断言）。"""
    src = HOOK.read_text(encoding="utf-8")
    assert "blueprint_meta" not in src
    assert "--scan-scene-tasks" in src
    assert "--scan-inspiration-refs" in src


def test_analysis_meta_skips_validation(tmp_path):
    """novel-analysis 逆向产物（analysis_meta 标记）豁免 r10 校验——现役字符串用户不误伤。"""
    p = tmp_path / "run" / "pipeline"
    p.mkdir(parents=True)
    f = p / "phase5_scenes.yaml"
    f.write_text("analysis_meta:\n  source: novel-analysis\n" + _scene_body(), encoding="utf-8")
    r = run_hook(f)
    assert r.returncode == 0, r.stderr
