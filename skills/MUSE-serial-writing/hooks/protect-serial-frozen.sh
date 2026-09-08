#!/usr/bin/env bash
# PreToolUse hook (Edit|Write): frozen/published 结构性写保护
# 命中 series/story_bible.yaml 或 published/*.md 时调 serial_lint.py
# frozen-protect,published-protect（比对 git HEAD + decisions/manifest 通道）
# 设计文档 §7 结构性 lint（frozen / published 写保护走机器兜底）

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# 从 FILE_PATH 剥出 work_dir（published/ 或 series/ 段之前的目录，即 works/<slug> 层）
WORK_DIR=""
if [[ "$FILE_PATH" =~ ^(.*)/published/[^/]+\.md$ ]]; then
  WORK_DIR="${BASH_REMATCH[1]}"
elif [[ "$FILE_PATH" =~ ^(.*)/series/story_bible\.yaml$ ]]; then
  WORK_DIR="${BASH_REMATCH[1]}"
else
  exit 0
fi

SERIAL_LINT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/scripts/serial_lint.py"

if [ -z "$WORK_DIR" ] || [ ! -d "$WORK_DIR" ]; then
  echo "[serial-protect WARN] work-dir 不存在（$WORK_DIR），跳过 frozen/published 保护检查" >&2
  exit 0
fi

# 工作区骨架守卫：目录恰好叫 published/ 或恰好有 series/story_bible.yaml 不等于
# serial workspace——只有三海拔骨架（series/ + chapters|published）齐备才触发检查，
# 否则会把无关项目里同名路径的正常编辑误判成违规硬阻断
if [ ! -d "$WORK_DIR/series" ] || { [ ! -d "$WORK_DIR/chapters" ] && [ ! -d "$WORK_DIR/published" ]; }; then
  exit 0
fi

if [ ! -f "$SERIAL_LINT" ]; then
  echo "BLOCK: $FILE_PATH 的冻结检查器缺失：$SERIAL_LINT；恢复检查器后重试" >&2
  exit 2
fi

OUTPUT=$(python3 "$SERIAL_LINT" --work-dir "$WORK_DIR" \
  --check frozen-protect,published-protect --file "$FILE_PATH" 2>&1) && RC=0 || RC=$?

if [ "$RC" -eq 2 ]; then
  echo "BLOCK: $FILE_PATH 触发 frozen/published 写保护（serial_lint frozen-protect/published-protect 未通过）" >&2
  echo "" >&2
  echo "$OUTPUT" >&2
  exit 2
fi

if [ "$RC" -eq 1 ]; then
  # 已确定是 serial 的冻结目标；输入错误使必要保护检查无法完成。
  echo "BLOCK: serial_lint 无法完成 $FILE_PATH 的 frozen/published 校验；修复以下输入后重试：" >&2
  echo "$OUTPUT" >&2
  exit 2
fi

if [ "$RC" -ne 0 ]; then
  echo "BLOCK: $FILE_PATH 的冻结检查异常退出（$RC）：$OUTPUT" >&2
  exit 2
fi

# RC = 0：PASS（含 serial_lint 内部因无 git HEAD 基线而 WARN-视为通过 的情形）
if [ -n "$OUTPUT" ]; then
  echo "$OUTPUT" >&2
fi

exit 0
