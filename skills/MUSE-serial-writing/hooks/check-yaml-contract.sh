#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): YAML contract 校验，仅对 .yaml/.yml 触发
# 设计文档 §2 H4 / v5 plugin 形态迁入本包 hooks/

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# 仅对 .yaml / .yml 触发
case "$FILE_PATH" in
  *.yaml|*.yml) ;;
  *) exit 0 ;;
esac

# plugin 形态下脚本路径走 ${CLAUDE_PLUGIN_ROOT}（plugin 安装根）；本地开发态走脚本自身相对路径兜底
SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
python3 "$SCRIPT_DIR/scripts/muse_hook_check.py" yaml-contract --file "$FILE_PATH" || true
exit 0
