#!/usr/bin/env bash
# PreToolUse Agent hook: 追加 subagent dispatch 起始记录到 pipeline/audit/subagent_dispatches.jsonl
# 纯 debug log，永远 exit 0，不阻断模型流程

set -euo pipefail

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"')
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')

# 推断 pipeline_dir：优先 cwd，其次从 prompt 中 grep results/<id>/pipeline
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

[ -z "$PIPELINE_DIR" ] && exit 0  # graceful skip — 非 pipeline 上下文

AUDIT_DIR="$PIPELINE_DIR/audit"
mkdir -p "$AUDIT_DIR" 2>/dev/null || exit 0
LOG="$AUDIT_DIR/subagent_dispatches.jsonl"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PROMPT_HEAD=$(echo "$PROMPT" | head -c 240 | tr '\n' ' ')

jq -nc \
  --arg event "dispatch" \
  --arg ts "$TS" \
  --arg agent_type "$AGENT_TYPE" \
  --arg prompt_head "$PROMPT_HEAD" \
  '{event: $event, ts: $ts, agent_type: $agent_type, prompt_head: $prompt_head}' \
  >> "$LOG" 2>/dev/null || true

exit 0
