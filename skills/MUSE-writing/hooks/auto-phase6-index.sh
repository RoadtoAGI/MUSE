#!/bin/bash
# PostToolUse hook (Edit|Write): phase5_scenes.yaml 写入后自动生成 Phase 6 索引
# 触发匹配：*phase5_scenes.yaml
# 设计文档：docs/Level_3_implementation/pipeline/2026-05-18-单路径协议与hooks增量-plan.md T19

set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

if [[ ! "$FILE_PATH" =~ phase5_scenes\.yaml$ ]]; then
  exit 0
fi

# Skip canon-distill 逆向 Phase 5 产物：与 MUSE-writing 正向产物共用同名文件，但 schema/语义不同。
if [[ "$FILE_PATH" == *"knowledge-base/novels/"* ]]; then
  exit 0
fi

# 推断 work-dir：phase5_scenes.yaml 在 work_dir/pipeline/ 下
WORK_DIR=$(echo "$FILE_PATH" | sed -E 's|(.*)/pipeline/phase5_scenes\.yaml$|\1|')
if [ "$WORK_DIR" = "$FILE_PATH" ]; then
  exit 0  # 路径不规范，跳过
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SCRIPT="${CLAUDE_PLUGIN_ROOT:-$PROJECT_DIR/MUSE-writing}/scripts/generate_phase6_index.py"

if [ ! -f "$SCRIPT" ]; then
  SCRIPT="$PROJECT_DIR/skills/MUSE-writing/scripts/generate_phase6_index.py"
fi

if [ ! -f "$SCRIPT" ]; then
  exit 0
fi

python3 "$SCRIPT" "$WORK_DIR" >/dev/null 2>&1 \
  || echo "[auto-phase6-index WARN] generate_phase6_index.py 失败" >&2

exit 0
