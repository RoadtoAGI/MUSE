#!/bin/bash
# PreToolUse hook (Edit|Write): 自动建父目录（不阻断）
# 设计文档：docs/Level_3_implementation/pipeline/2026-05-16-hooks-治理设计.md §2 H2
# 单路径协议（2026-05-18 plan）后 Tier 1 hard block 删除（writer/reviser 合法直写 scenes/）

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# === 自动建父目录（仅在 pipeline/ 或 results/ 路径下）===
# 这条规避 LLM 反复跑 `ls / test -d / mkdir -p` 检查路径存在性的痛点
if [[ "$FILE_PATH" =~ /(pipeline|results)/ ]]; then
  mkdir -p "$(dirname "$FILE_PATH")" 2>/dev/null || true
fi

exit 0
