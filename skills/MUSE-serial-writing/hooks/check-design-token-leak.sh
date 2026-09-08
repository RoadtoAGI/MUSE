#!/bin/bash
# PostToolUse hook (Edit|Write): 定位可能进入正文的设计 marker / 字段名 / rehearsal 标题
# 触发 if: Write(*/pipeline/scenes/scene_*.md)|Edit(*/pipeline/scenes/scene_*.md)
# 设计文档：docs/Level_3_implementation/pipeline/2026-05-18-单路径协议与hooks增量-plan.md T13
#
# 三组检测：
#   Group A: 双 marker — [核心]/[灵感]/[惊艳]/[main]/[support]/[atmosphere]
#   Group B: 设计字段名 — scene_tasks/value_start/value_end/spine_statement/
#                         handoff/reader_track/beat_direction/craft_carrier/
#                         boldness_guardrails
#   Group C: rehearsal 标题 — 想说但不会直说/台词候选/禁用语气/动作或停顿
# 命中时给出位置，由既有语义审阅判断；正常故事术语与授权原文可以保留。

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# 仅匹配 pipeline/scenes/scene_*.md（单路径协议下的正文文件）
if ! [[ "$FILE_PATH" =~ /pipeline/scenes/scene_[^/]+\.md$ ]]; then
  exit 0
fi

VIOLATIONS=""

# Group A: 双 marker（字面字符串匹配）
for token in '[核心]' '[灵感]' '[惊艳]' '[main]' '[support]' '[atmosphere]'; do
  matches=$(grep -nF "$token" "$FILE_PATH" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    while IFS= read -r line; do
      VIOLATIONS+="${FILE_PATH}:${line%%:*}:[A]${token}"$'\n'
    done <<< "$matches"
  fi
done

# Group B: 设计字段名（字面字符串）
for field in 'scene_tasks' 'value_start' 'value_end' 'spine_statement' \
             'handoff' 'reader_track' 'beat_direction' 'craft_carrier' \
             'boldness_guardrails'; do
  matches=$(grep -nF "$field" "$FILE_PATH" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    while IFS= read -r line; do
      VIOLATIONS+="${FILE_PATH}:${line%%:*}:[B]${field}"$'\n'
    done <<< "$matches"
  fi
done

# Group C: rehearsal 标题
for heading in '想说但不会直说' '台词候选' '禁用语气' '动作或停顿'; do
  matches=$(grep -nF "$heading" "$FILE_PATH" 2>/dev/null || true)
  if [ -n "$matches" ]; then
    while IFS= read -r line; do
      VIOLATIONS+="${FILE_PATH}:${line%%:*}:[C]${heading}"$'\n'
    done <<< "$matches"
  fi
done

if [ -n "$VIOLATIONS" ]; then
  echo "[design-token WARN] 正文含候选设计用词，请结合当前语境核对：" >&2
  echo "" >&2
  echo "$VIOLATIONS" >&2
  echo "" >&2
  echo "Group A = 双 marker / B = 设计字段名 / C = rehearsal 标题。正常故事术语和授权原文可保留；实际执行痕迹交既有 scene-review 定位修订，不按词汇命中自动删改。" >&2
fi

exit 0
