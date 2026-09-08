#!/usr/bin/env bash
# PreToolUse hook: enforce predefined character-actor agent
# Blocks Agent tool calls that create ad-hoc character/rehearsal agents
# instead of using the predefined agent `character-actor`.

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# 兼容宿主 Agent / spawn_agent；包内命名保持 serial-character-actor。
if [[ "$TOOL_NAME" != "Agent" && "$TOOL_NAME" != "spawn_agent" ]]; then
  exit 0
fi

AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // .tool_input.agent_type // ""')
AGENT_TYPE="${AGENT_TYPE##*:}"
AGENT_TYPE="${AGENT_TYPE//_/-}"
if [[ "$AGENT_TYPE" == "serial-character-actor" || "$AGENT_TYPE" == "character-actor" ]]; then
  exit 0
fi

PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')
DESC=$(echo "$INPUT" | jq -r '.tool_input.description // ""')
COMBINED="$DESC $PROMPT"

# Check if this is a character/rehearsal related agent call
if echo "$COMBINED" | grep -qiE '排练|角色演员|character.?actor|rehearsal|情境排练|角色校验|进入角色'; then
  # Must reference the predefined agent by name
  if ! echo "$COMBINED" | grep -q 'character-actor'; then
    echo "BLOCK: 角色任务须绑定本包 serial-character-actor 元配置；未注册宿主按 execution-protocol §0 派 fresh 子执行者并加载该元配置的确切路径。"
    exit 2
  fi
fi

exit 0
