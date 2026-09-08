#!/bin/bash
# PreToolUse hook (Bash matcher): assemble_story.py 调用前验证 §1.5 完整性
# 拦截 Phase 7 入口：scripts/assemble_story.py <work_dir>
# 缺失 review/scene_*.yaml 或 verifier → exit 2 阻断
# assemble_story.py 命令明确出现但 work_dir 无法解析 / 不存在 → exit 2 阻断
#
# 设计文档：phase7-integration/SKILL.md Step 0 / execution-protocol.md §1.5

set -uo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# 仅匹配 assemble_story.py 调用
if [[ "$COMMAND" != *"assemble_story.py"* ]]; then
  exit 0
fi

# 提取 work_dir：assemble_story.py 后第一个非选项参数
WORK_DIR=$(echo "$COMMAND" | python3 -c "
import re, sys, shlex
cmd = sys.stdin.read()
m = re.search(r'assemble_story\.py\s+(.+)', cmd)
if not m:
    sys.exit(0)
try:
    parts = shlex.split(m.group(1))
except ValueError:
    sys.exit(0)
for p in parts:
    if not p.startswith('-'):
        print(p)
        break
")

if [ -z "$WORK_DIR" ]; then
  echo "[verify-review-complete] ❌ assemble_story.py 调用但无法解析 work_dir 参数" >&2
  echo "  ↳ 命令形如：python \${CLAUDE_PLUGIN_ROOT}/scripts/assemble_story.py <work_dir>" >&2
  echo "  ↳ 阻断以防 §1.5 gate 失守" >&2
  exit 2
fi

if [ ! -d "$WORK_DIR" ]; then
  echo "[verify-review-complete] ❌ work_dir 不存在: $WORK_DIR" >&2
  exit 2
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-$HOOK_ROOT}/scripts"

if [ ! -f "$SCRIPT_DIR/verify_review_complete.py" ]; then
  echo "[verify-review-complete] ❌ verify_review_complete.py 未找到" >&2
  echo "  ↳ admission verifier 缺失，按 fail-closed 阻断" >&2
  exit 2
fi

python3 "$SCRIPT_DIR/verify_review_complete.py" "$WORK_DIR"
exit $?
