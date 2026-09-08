#!/usr/bin/env bash
# SessionStart hook: 异步 git pull plugin cache，让下次启动用最新版
# 当前 session 仍用旧版本——不阻塞启动；网络失败不阻断
# 设计文档 §2 H9（v5.1 新增）

set -euo pipefail

PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-}"

# 兜底：本地开发态（cwd 是 MUSE 主仓）跳过——MUSE-writing 是源，不应自更新
if [ -z "$PLUGIN_DIR" ] || [ ! -d "$PLUGIN_DIR/.git" ]; then
  exit 0
fi

# 后台异步 pull——不阻塞 session 启动
# stderr/stdout 全静默；失败 silently 不阻断
(
  cd "$PLUGIN_DIR"
  # --quiet：抑制 progress；--rebase：保留 plugin cache 本地未推改动（极罕见，按理 cache 无人改）
  timeout 30 git pull --quiet --rebase 2>/dev/null || true
) >/dev/null 2>&1 &
disown

exit 0
