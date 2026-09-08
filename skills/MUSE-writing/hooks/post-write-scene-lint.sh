#!/bin/bash
# PostToolUse hook (Edit|Write): scenes/scene_*.md 写入后自动跑 L1 lint 三件套
# 触发匹配：pipeline/scenes/scene_*.md
# 设计文档：docs/Level_3_implementation/pipeline/2026-05-18-单路径协议与hooks增量-plan.md T18
#
# 三件套：
#   ai_filler_lint.py  → review/lint/{scene_id}.ai_filler.yaml
#   lexical_stats.py   → review/lint/{scene_id}.lexical_stats.yaml
#   dialogue_lint.py   → review/lint/{scene_id}.dialogue.yaml
#
# 始终 exit 0（lint 是质量信号，不阻断流程）

set -uo pipefail   # 不用 -e；单脚本失败不中断后续

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

# 推断 work-dir：FILE_PATH 形如 .../<work_dir>/pipeline/scenes/scene_*.md
WORK_DIR=$(echo "$FILE_PATH" | sed -E 's|(.*)/pipeline/scenes/.*|\1|')

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-$PROJECT_DIR/MUSE-writing}/scripts"

if [ ! -d "$SCRIPT_DIR" ]; then
  SCRIPT_DIR="$PROJECT_DIR/skills/MUSE-writing/scripts"
fi

# F2（R 轮测试态）：v1/v2 自动区分
# - 首次写（writer 首版）: ai_filler.yaml 不存在 → 跑无 suffix → 产 v1（default）
# - 二次及之后（reviser 修订后）: ai_filler.yaml 已存在 → 跑 --output-suffix v2 → 产 v2
# 防止 superficial_patch_failed 检测因 v1==v2（同一份文件覆盖）失效——
# 让 v1 / v2 真正反映 writer 首版 vs revised scene 的客观 lint 差异。
V1_PATH="$WORK_DIR/pipeline/review/lint/$SCENE_ID.ai_filler.yaml"
if [ -f "$V1_PATH" ]; then
  AI_FILLER_SUFFIX_ARGS=(--output-suffix v2)
else
  AI_FILLER_SUFFIX_ARGS=()
fi

for script in ai_filler_lint.py lexical_stats.py dialogue_lint.py; do
  if [ -f "$SCRIPT_DIR/$script" ]; then
    if [ "$script" = "ai_filler_lint.py" ]; then
      python3 "$SCRIPT_DIR/$script" --scene-id "$SCENE_ID" --work-dir "$WORK_DIR" \
        "${AI_FILLER_SUFFIX_ARGS[@]}" >/dev/null 2>&1 \
        || echo "[post-write-scene-lint WARN] $script 失败：scene $SCENE_ID" >&2
    else
      python3 "$SCRIPT_DIR/$script" --scene-id "$SCENE_ID" --work-dir "$WORK_DIR" >/dev/null 2>&1 \
        || echo "[post-write-scene-lint WARN] $script 失败：scene $SCENE_ID" >&2
    fi
  fi
done

exit 0
