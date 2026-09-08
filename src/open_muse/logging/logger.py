"""Structured JSONL event logging for the writing runner."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class RunLogger:
    """结构化 JSONL 事件记录器，支持批次级和 query 级双层日志。"""

    def __init__(
        self,
        query_log_dir: Path | None = None,
        batch_log_path: Path | None = None,
    ):
        """
        Args:
            query_log_dir: query 级日志目录，写入 events.jsonl。为 None 时不写 query 日志。
            batch_log_path: 批次级日志文件路径（通常是 timestamp 目录下的 batch.jsonl）。
        """
        self._query_log: Path | None = None
        if query_log_dir is not None:
            p = Path(query_log_dir)
            p.mkdir(parents=True, exist_ok=True)
            self._query_log = p / "events.jsonl"

        self._batch_log: Path | None = None
        if batch_log_path is not None:
            bl = Path(batch_log_path)
            bl.parent.mkdir(parents=True, exist_ok=True)
            self._batch_log = bl

    # ------------------------------------------------------------------
    # 核心 emit（所有具名方法最终调这里）
    # ------------------------------------------------------------------

    def emit(self, event: str, **data: Any) -> None:
        """发布一个事件，同时写日志文件和打印到 stdout。"""
        now = datetime.now()
        record: dict[str, Any] = {
            "time": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event,
        }
        record.update({k: v for k, v in data.items() if v is not None})

        line = json.dumps(record, ensure_ascii=False)
        if self._query_log:
            _append(self._query_log, line)
        if self._batch_log:
            _append(self._batch_log, line)

        _print_human(now, event, data)

    # ------------------------------------------------------------------
    # Pipeline 事件
    # ------------------------------------------------------------------

    def run_start(self, model: str, query_id: str, num_phases: int,
                  request_preview: str) -> None:
        self.emit("run_start", model=model, query_id=query_id,
                  num_phases=num_phases, request=request_preview[:120])

    def run_end(self, success: bool, duration_s: float, phases_done: int) -> None:
        self.emit("run_end", success=success,
                  duration_s=round(duration_s, 1), phases_done=phases_done)

    def phase_start(self, phase_name: str, stage: str, attempt: int = 1) -> None:
        self.emit("phase_start", phase_name=phase_name, stage=stage, attempt=attempt)

    def phase_end(self, phase_name: str, stage: str,
                  success: bool, duration_s: float) -> None:
        self.emit("phase_end", phase_name=phase_name, stage=stage,
                  success=success, duration_s=round(duration_s, 1))

    def llm_call(self, turn: int) -> None:
        self.emit("llm_call", turn=turn)

    def tool_call(self, tool_name: str, args: dict) -> None:
        self.emit("tool_call", tool_name=tool_name,
                  args_preview=_format_args(tool_name, args))

    def tool_result(self, tool_name: str, result: str) -> None:
        ok = not result.startswith("Error:")
        preview = result[:100].replace("\n", " ") if result else ""
        self.emit("tool_result", tool_name=tool_name, success=ok, preview=preview)

    def validation_fail(self, errors: list[str], attempt: int) -> None:
        self.emit("validation_fail", errors=errors, attempt=attempt)

    def retry(self, attempt: int, reason: str) -> None:
        self.emit("retry", attempt=attempt, reason=reason)

    # ------------------------------------------------------------------
    # 批处理事件（evaluate runner 使用）
    # ------------------------------------------------------------------

    def query_start(self, query_id: str | int, query_preview: str = "") -> None:
        self.emit("query_start", query_id=str(query_id),
                  query=query_preview[:80] if query_preview else None)

    def query_end(self, query_id: str | int, success: bool, duration_s: float) -> None:
        self.emit("query_end", query_id=str(query_id),
                  success=success, duration_s=round(duration_s, 1))

    def batch_start(self, method: str, model: str, total: int) -> None:
        self.emit("batch_start", method=method, model=model, total=total)

    def batch_end(self, total: int, succeeded: int, duration_s: float) -> None:
        self.emit("batch_end", total=total, succeeded=succeeded,
                  failed=total - succeeded, duration_s=round(duration_s, 1))


# ------------------------------------------------------------------
# 内部工具函数
# ------------------------------------------------------------------

def _append(path: Path, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _format_args(tool_name: str, args: dict) -> str:
    """生成工具调用参数的简短预览。"""
    if tool_name == "load_skill":
        return args.get("name", "?")
    if tool_name == "load_reference":
        return f"{args.get('skill', '?')}/{args.get('path', '?')}"
    if tool_name == "write_deliverable":
        return f"{args.get('name', '?')} ({args.get('format', '?')})"
    if tool_name == "read_deliverable":
        return args.get("name", "?")
    for v in args.values():
        if isinstance(v, str):
            return v[:60]
    return str(args)[:60]


def _print_human(now: datetime, event: str, data: dict) -> None:
    """以人类可读格式打印到 stdout。"""
    ts = now.strftime("%H:%M:%S")

    if event == "run_start":
        print(f"[{ts}] 🚀 Open-MUSE  query={data.get('query_id')}  "
              f"model={data.get('model')}  phases={data.get('num_phases')}", flush=True)

    elif event == "phase_start":
        attempt = data.get("attempt", 1)
        retry_tag = f"  [retry {attempt}]" if attempt > 1 else ""
        print(f"[{ts}] ▶  {data.get('phase_name')}  ({data.get('stage')}){retry_tag}",
              flush=True)

    elif event == "phase_end":
        icon = "✓" if data.get("success") else "✗"
        print(f"[{ts}] {icon}  {data.get('phase_name')}  "
              f"{data.get('duration_s', 0):.1f}s", flush=True)

    elif event == "llm_call":
        print(f"[{ts}]    · llm turn {data.get('turn')}", flush=True)

    elif event == "tool_call":
        print(f"[{ts}]    → {data.get('tool_name')}({data.get('args_preview', '')})",
              flush=True)

    elif event == "tool_result":
        ok = data.get("success", True)
        icon = "←" if ok else "✗"
        print(f"[{ts}]    {icon} {'OK' if ok else 'ERR'}  {data.get('preview', '')}",
              flush=True)

    elif event == "validation_fail":
        errors = data.get("errors", [])
        print(f"[{ts}]    ⚠  validation: {'; '.join(str(e) for e in errors[:2])}",
              flush=True)

    elif event == "retry":
        print(f"[{ts}]    ↩  retry attempt {data.get('attempt')}", flush=True)

    elif event == "run_end":
        icon = "✅" if data.get("success") else "❌"
        print(f"[{ts}] {icon} done  phases={data.get('phases_done')}  "
              f"{data.get('duration_s', 0):.1f}s", flush=True)

    elif event == "query_start":
        print(f"[{ts}] ── query {data.get('query_id')} "
              f"{'─' * max(0, 40 - len(str(data.get('query_id', ''))))}", flush=True)

    elif event == "query_end":
        icon = "✓" if data.get("success") else "✗"
        print(f"[{ts}] {icon}  query {data.get('query_id')}  "
              f"{data.get('duration_s', 0):.1f}s", flush=True)

    elif event == "batch_start":
        print(f"[{ts}] 📋 batch  method={data.get('method')}  "
              f"model={data.get('model')}  total={data.get('total')}", flush=True)

    elif event == "batch_end":
        icon = "✅" if data.get("failed", 0) == 0 else "⚠"
        print(f"[{ts}] {icon} batch done  {data.get('succeeded')}/{data.get('total')}  "
              f"{data.get('duration_s', 0):.1f}s", flush=True)

    else:
        summary = "  ".join(f"{k}={v}" for k, v in list(data.items())[:4])
        print(f"[{ts}] {event}  {summary}", flush=True)
