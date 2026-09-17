#!/usr/bin/env python3
"""init_run.py — 创建一个 MUSE run 目录，封装时间戳策略与子目录骨架。

两种模式（由 --results-dir 与 --run-dir 二选一区分）：

  A. 派生模式（默认）：脚本自己派生 slug + 时间戳
       python3 init_run.py --results-dir results/ --query "用户的写作需求"
       python3 init_run.py --results-dir results/ --timestamp 2026-05-19T1500
       python3 init_run.py --results-dir results/ --slug "nurse-eol" --timestamp 2026-05-19T1500
     时间戳策略：
       1. 优先用"整点"时间戳（HH:00），格式 `YYYY-MM-DDTHH00`
       2. 整点目录已存在 → 落到精确时间戳，格式 `YYYY-MM-DDTHHMMSS`
       3. 用户 --timestamp 显式指定 → 直接用，冲突报错退出（不 fallback）

  B. 显式模式（caller 已算好完整路径，如 StoryStudio benchmark/model/index 三件套）：
       python3 init_run.py --run-dir /abs/path/to/results/<benchmark>/<model>/<ts>/<index>
     语义：在该绝对路径下幂等建 `pipeline/` + 6 个子目录。目录已存在则 reuse，不报错。
     宽容：同时传 --query/--slug/--timestamp 不报错，仅 stderr WARN + 静默忽略
           （--run-dir 已包含完整路径信息，派生参数无用武之地）。

输出（两种模式相同）：
  stdout：run 目录绝对路径（orchestrator 用这个作 work_dir）
  stderr：本次策略选择的简短说明

设计：orchestrator 应一次性调本脚本完成全部目录初始化，禁止 ls 探索 / 手动 mkdir。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml


SUBDIRS = [
    "pipeline/scenes",
    "pipeline/staging",
    "pipeline/references",
    "pipeline/references/prototypes",
    "pipeline/screenplay",
    "pipeline/screenplay/scenes",
    "pipeline/review/lint",
    "pipeline/audit",
    "pipeline/story-character-skills/.claude/skills",
]


def _slugify(query: str, max_len: int = 32) -> str:
    """从 query 提取一个文件系统友好的 slug。"""
    if not query:
        return "run"
    # 保留中英文字母数字和连字符，其他换 -
    s = re.sub(r"[^\w一-鿿-]+", "-", query.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len] or "run"


def _hour_rounded(now: datetime) -> str:
    """`YYYY-MM-DDTHH00` 格式。"""
    return now.strftime("%Y-%m-%dT%H00")


def _precise(now: datetime) -> str:
    """`YYYY-MM-DDTHHMMSS` 格式。"""
    return now.strftime("%Y-%m-%dT%H%M%S")


def _validate_user_timestamp(ts: str) -> str:
    """校验用户指定的 timestamp 格式。允许 `YYYY-MM-DDTHHMM` 或 `YYYY-MM-DDTHHMMSS`。"""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{4}(\d{2})?", ts):
        raise ValueError(
            f"--timestamp 格式应为 YYYY-MM-DDTHHMM 或 YYYY-MM-DDTHHMMSS（如 2026-05-19T1500），实为：{ts}"
        )
    return ts


def init_run_explicit(run_path: Path) -> tuple[Path, str]:
    """显式模式：caller 已算好完整路径，幂等建 pipeline/ + 6 子目录。

    已存在的目录与子目录 reuse 不报错；只补缺失项。
    """
    run_path = run_path.resolve()
    run_path.mkdir(parents=True, exist_ok=True)
    created = []
    for sub in SUBDIRS:
        sub_path = run_path / sub
        if not sub_path.exists():
            sub_path.mkdir(parents=True, exist_ok=True)
            created.append(sub)
    if created:
        note = f"使用显式 run-dir={run_path}（补齐 {len(created)}/{len(SUBDIRS)} 个子目录）"
    else:
        note = f"使用显式 run-dir={run_path}（所有子目录已存在，reuse）"
    return run_path, note


def init_run(results_dir: Path, query: str, slug: str | None,
             user_timestamp: str | None, now: datetime) -> tuple[Path, str]:
    """根据策略选定 run 目录路径并创建。返回 (run_path, strategy_note)。"""
    actual_slug = slug if slug else _slugify(query)

    if user_timestamp:
        timestamp = _validate_user_timestamp(user_timestamp)
        run_path = results_dir / f"{timestamp}_{actual_slug}"
        if run_path.exists():
            raise FileExistsError(
                f"用户指定的 timestamp 已存在：{run_path}（用户指定模式下不自动 fallback，请改名或换 timestamp）"
            )
        note = f"使用用户指定 timestamp={timestamp}"
    else:
        # 先试整点
        hour_ts = _hour_rounded(now)
        hour_path = results_dir / f"{hour_ts}_{actual_slug}"
        if not hour_path.exists():
            run_path = hour_path
            note = f"使用整点 timestamp={hour_ts}"
        else:
            # fallback 到精确时间戳
            precise_ts = _precise(now)
            run_path = results_dir / f"{precise_ts}_{actual_slug}"
            if run_path.exists():
                # 极小概率：同一秒第二次调用——降级在 slug 加随机后缀
                import secrets
                suffix = secrets.token_hex(2)
                run_path = results_dir / f"{precise_ts}_{actual_slug}-{suffix}"
            note = f"整点 {hour_ts} 已被占用，fallback 到精确 timestamp={precise_ts}"

    run_path.mkdir(parents=True, exist_ok=False)
    for sub in SUBDIRS:
        (run_path / sub).mkdir(parents=True, exist_ok=True)

    return run_path, note


def _write_run_intent(run_path: Path, run_intent: str) -> None:
    """Write-once run intent while preserving sibling run_state fields."""
    state_path = run_path / "pipeline" / "run_state.yaml"
    state: dict = {}
    if state_path.exists():
        loaded = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("pipeline/run_state.yaml 顶层必须是 mapping")
        state = loaded
    existing = state.get("run_intent")
    if existing is not None and existing != run_intent:
        raise ValueError(
            f"run_intent 已写为 {existing!r}，拒绝覆盖为 {run_intent!r}"
        )
    state["run_intent"] = run_intent
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )
    os.replace(tmp_path, state_path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--results-dir",
                      help="派生模式：results 根目录（如 results/）；脚本自己派生 slug + timestamp")
    mode.add_argument("--run-dir",
                      help="显式模式：caller 已算好的完整 run 目录绝对路径；幂等建子目录")
    p.add_argument("--query", default="",
                   help="[派生模式] 用户写作需求（用于自动生成 slug，可省略）")
    p.add_argument("--slug", default=None,
                   help="[派生模式] 显式指定 slug（覆盖 --query 派生）")
    p.add_argument("--timestamp", default=None,
                   help="[派生模式] 显式指定 timestamp（YYYY-MM-DDTHHMM 或 -DDTHHMMSS）；冲突直接报错不 fallback")
    p.add_argument(
        "--run-intent",
        choices=["smoke", "evaluation", "release"],
        default=None,
        help="进入完整小说发布链时必填；其他只产设计稿的入口可省略",
    )
    args = p.parse_args(argv)

    try:
        if args.run_dir:
            ignored = [name for name, val in (("--query", args.query),
                                              ("--slug", args.slug),
                                              ("--timestamp", args.timestamp)) if val]
            if ignored:
                print(f"[init_run WARN] --run-dir 模式下忽略派生参数：{', '.join(ignored)}",
                      file=sys.stderr)
            run_path, note = init_run_explicit(Path(args.run_dir))
        else:
            results_dir = Path(args.results_dir).resolve()
            results_dir.mkdir(parents=True, exist_ok=True)
            run_path, note = init_run(
                results_dir=results_dir,
                query=args.query,
                slug=args.slug,
                user_timestamp=args.timestamp,
                now=datetime.now(),
            )
        if args.run_intent:
            _write_run_intent(run_path, args.run_intent)
    except (ValueError, FileExistsError) as e:
        print(f"[init_run ERROR] {e}", file=sys.stderr)
        return 2

    print(f"[init_run] {note}", file=sys.stderr)
    print(str(run_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
