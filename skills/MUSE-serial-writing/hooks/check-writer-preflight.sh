#!/usr/bin/env bash
# PreToolUse hook (Edit|Write): writer 写 pipeline/scenes/scene_{id}.md 前 inline 校验关键 inputs 物理存在

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

if ! [[ "$FILE_PATH" =~ /pipeline/scenes/scene_([^/]+)\.md$ ]]; then
  exit 0
fi

SCENE_ID="${BASH_REMATCH[1]}"

# greedy 抓到 /pipeline/ 之前的全部路径段——兼容 MUSE 单段 + StoryStudio 4 段布局
# v4 修法（StoryStudio smoke 报告 §A）：原 (.*/results/[^/]+) 只吃单段，深层 run 静默 exit 0
PIPELINE_ROOT=$(echo "$FILE_PATH" | sed -E 's|(.*)/pipeline/scenes/.*|\1|')
if [ "$PIPELINE_ROOT" = "$FILE_PATH" ]; then
  exit 0
fi

# 连载章（run 根有 chapter_card.yaml）：serial_context 缺失/过期是阻断项——
# 缺失 = 装配未跑，writer 会在零连载上下文下静默按中短篇语义写完全章；
# 过期 = 章卡在装配之后被改写（编排补全 recap_inputs/pov），未履行重装配义务
CHAPTER_CARD="$PIPELINE_ROOT/chapter_card.yaml"
if [ -f "$CHAPTER_CARD" ]; then
  SERIAL_CONTEXT="$PIPELINE_ROOT/pipeline/serial_context.md"
  if [ ! -f "$SERIAL_CONTEXT" ]; then
    echo "[H6 BLOCK] 连载章缺 pipeline/serial_context.md：先跑 assemble_serial_context.py 装配连载上下文，再写场景正文" >&2
    exit 2
  fi
  if [ "$SERIAL_CONTEXT" -ot "$CHAPTER_CARD" ]; then
    echo "[H6 BLOCK] serial_context.md 早于 chapter_card.yaml——章卡补全后未重装配：重跑 assemble_serial_context.py 后再写场景正文" >&2
    exit 2
  fi
fi

SCENE_DIR="$PIPELINE_ROOT/pipeline/scene_${SCENE_ID}"
MISSING=()
[ -f "$SCENE_DIR/scene_card.md" ] || MISSING+=("scene_card.md")
if [ ! -d "$SCENE_DIR/role_views" ] || ! compgen -G "$SCENE_DIR/role_views/*.yaml" > /dev/null; then
  MISSING+=("role_views/*.yaml（有在场角色时需要）")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "[H6 WARN] writer inputs 缺失（${SCENE_DIR}）: ${MISSING[*]}；按本包 writer 与上下文协议核对 participants。必要输入缺失时先回编排或派生环节，修复后再写正文"
fi

exit 0
