#!/usr/bin/env bash
# PostToolUse Agent hook: 追加 subagent dispatch 完成记录到 pipeline/audit/subagent_dispatches.jsonl
# 纯 debug log，永远 exit 0，不阻断模型流程

set -euo pipefail

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"')
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')
REPLY=$(echo "$INPUT" | jq -r '(.tool_response.result // .tool_response.output // .tool_response // "")' 2>/dev/null || echo "")

PIPELINE_DIR=""
if [ -d "$PWD/pipeline" ]; then
  PIPELINE_DIR="$PWD/pipeline"
else
  CANDIDATE=$(echo "$PROMPT" | grep -oE '[^[:space:]]*results/[^/[:space:]]+/pipeline' | head -1 || true)
  if [ -n "$CANDIDATE" ]; then
    [[ "$CANDIDATE" != /* ]] && CANDIDATE="$PWD/$CANDIDATE"
    [ -d "$CANDIDATE" ] && PIPELINE_DIR="$CANDIDATE"
  fi
fi

[ -z "$PIPELINE_DIR" ] && exit 0

AUDIT_DIR="$PIPELINE_DIR/audit"
mkdir -p "$AUDIT_DIR" 2>/dev/null || exit 0
LOG="$AUDIT_DIR/subagent_dispatches.jsonl"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REPLY_HEAD=$(echo "$REPLY" | head -c 500 | tr '\n' ' ')

jq -nc \
  --arg event "complete" \
  --arg ts "$TS" \
  --arg agent_type "$AGENT_TYPE" \
  --arg reply_head "$REPLY_HEAD" \
  '{event: $event, ts: $ts, agent_type: $agent_type, reply_head: $reply_head}' \
  >> "$LOG" 2>/dev/null || true

exit 0
