#!/bin/bash
# PostToolUse hook (Edit|Write): 校验正文兑现 scene_card 硬字段（narration_style / pov）
# 触发 if: Write(*/pipeline/scenes/scene_*.md)|Edit(*/pipeline/scenes/scene_*.md)
# 设计文档：docs/Level_3_implementation/pipeline/2026-05-18-单路径协议与hooks增量-plan.md T14
# 来源：183 run POV 全链漏检事故催生
# v3 收敛（codex R2-F1）：participants 字段当前仅 parse-only，预留 Phase 2 aliases 扩展；
#                        不 WARN、不影响 exit code。
#
# 失败模式：统一软警告——全部 exit 0，stderr 输出违规清单

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# 仅匹配 pipeline/scenes/scene_*.md
if ! [[ "$FILE_PATH" =~ /pipeline/scenes/scene_([^/]+)\.md$ ]]; then
  exit 0
fi

SCENE_ID="${BASH_REMATCH[1]}"

# 推断 pipeline-root 和 scene_card 路径
PIPELINE_ROOT=$(echo "$FILE_PATH" | sed -E 's|(.*)/pipeline/scenes/.*|\1|')
SCENE_CARD="$PIPELINE_ROOT/pipeline/scene_${SCENE_ID}/scene_card.md"

if [ ! -f "$SCENE_CARD" ]; then
  echo "[scene-card-compliance WARN] scene_card 缺失：$SCENE_CARD（场景刚新建？）" >&2
  exit 0
fi

# 调 Python 校验脚本
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HOOK_CHECK="${CLAUDE_PLUGIN_ROOT:-$PROJECT_DIR/MUSE-writing}/scripts/muse_hook_check.py"

if [ ! -f "$HOOK_CHECK" ]; then
  HOOK_CHECK="$PROJECT_DIR/skills/MUSE-writing/scripts/muse_hook_check.py"
fi

if [ ! -f "$HOOK_CHECK" ]; then
  echo "[scene-card-compliance WARN] muse_hook_check.py 不存在，跳过" >&2
  exit 0
fi

python3 "$HOOK_CHECK" scene-card-compliance \
  --scene-card "$SCENE_CARD" \
  --scene-text "$FILE_PATH" || true
exit 0
