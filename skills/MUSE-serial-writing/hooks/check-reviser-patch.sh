#!/usr/bin/env bash
# PreToolUse: validate the selected scene-reviser input before dispatch.
set -euo pipefail
INPUT=$(cat)
HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
export HOOK_ROOT PROJECT_DIR
printf '%s' "$INPUT" | python3 -c '
import json, os, re, shlex, subprocess, sys
from pathlib import Path
payload = json.load(sys.stdin)
if payload.get("tool_name") not in {"Agent", "spawn_agent"}:
    sys.exit(0)
args = payload.get("tool_input") or {}
kind = str(args.get("subagent_type") or args.get("agent_type") or "").split(":")[-1].replace("_", "-")
prompt = str(args.get("prompt") or "")
text = str(args.get("description") or "") + " " + prompt
allowed = {"serial-reviser", "reviser"}
strict = kind in allowed or "/agents/serial-reviser.md" in prompt
if not strict and kind not in {"", "general-purpose", "default", "worker"}:
    sys.exit(0)
if not strict and not re.search(r"reviser|修订|patch_directive|apply.*patch", text, re.I):
    sys.exit(0)
if not strict:
    print("[H7 WARN] 派发未绑定场景 reviser；确认角色后再校验补丁", file=sys.stderr)
    sys.exit(0)
def fail(message):
    print("BLOCK: " + message, file=sys.stderr)
    sys.exit(2)
sid = args.get("scene_id")
if not sid:
    composite = re.search(r"C[0-9]{4}(S[0-9]{2,})", text)
    match = re.search(r"(?:scene(?:[_ -]?id)?|场景)[=：:_ -]+(S\d+|[A-Z]\d+)", text)
    sid = composite.group(1) if composite else (match.group(1) if match else None)
if not sid:
    fail("reviser 缺 scene_id；在派发中明确当前场景")
if not isinstance(sid, str) or Path(sid).name != sid or sid in {".", ".."}:
    fail("scene_id 无效")
work = args.get("work_dir")
if not work:
    match = re.search(r"(?m)^\s*work_dir=(.+?)\s*$", prompt)
    try:
        words = shlex.split(match.group(1)) if match else []
    except ValueError:
        words = []
    work = words[0] if len(words) == 1 else None
if not work:
    # Legacy discovery is safe only when the selected scene has one run.
    candidates = list((Path(os.environ["PROJECT_DIR"]) / "results").glob(f"**/pipeline/scene_{sid}/patch_directive.yaml"))
    if len(candidates) != 1:
        fail("reviser 需要明确 work_dir；现有场景目录无法唯一确定")
    work = candidates[0].parents[2]
root = Path(work)
if not root.is_absolute():
    root = Path(os.environ["PROJECT_DIR"]) / root
patch = root / "pipeline" / f"scene_{sid}" / "patch_directive.yaml"
scene = root / "pipeline/scenes" / f"scene_{sid}.md"
if not root.is_dir() or not patch.is_file() or not scene.is_file():
    fail("当前 work_dir 缺 patch_directive 或场景正文")
scripts = Path(os.environ["HOOK_ROOT"]) / "scripts"
for command in ([sys.executable, str(scripts / "verify_rewrite_patch_schema.py"), str(root), "--scene-id", sid],
                [sys.executable, str(scripts / "verify_patch_directive_traceability.py"), "--scene-id", sid, "--pipeline-root", str(root), "--source-filter", "scene_review"]):
    result = subprocess.run(command)
    if result.returncode:
        fail(f"scene {sid} patch schema / traceability 未通过")
'
