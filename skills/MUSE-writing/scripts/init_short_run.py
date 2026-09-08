#!/usr/bin/env python3
"""init_short_run.py — 创建一个短链（short-story-writing）run 目录。

fork 自 init_run.py：CLI 与时间戳策略完全一致，仅目录骨架不同——短链不产
scenes/staging/角色包等分场目录，设计产物住 pipeline/shortform/。

两种模式（由 --results-dir 与 --run-dir 二选一区分）：

  A. 派生模式（默认）：脚本自己派生 slug + 时间戳
       python3 init_short_run.py --results-dir results/ --query "用户的写作需求"
  B. 显式模式（caller 已算好完整路径）：
       python3 init_short_run.py --run-dir /abs/path/to/run

输出（两种模式相同）：
  stdout：run 目录绝对路径（orchestrator 用这个作 work_dir）
  stderr：本次策略选择的简短说明

由本脚本创建短链目录；恢复任务由入口核对现有阶段和有效产物。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

SUBDIRS = [
    "pipeline/shortform",
    "pipeline/shortform/review",
    "pipeline/review/lint",
]


def _slugify(query: str, max_len: int = 32) -> str:
    if not query:
        return "run"
    s = re.sub(r"[^\w一-鿿-]+", "-", query.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len] or "run"


def _hour_rounded(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H00")


def _precise(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H%M%S")


def _validate_user_timestamp(ts: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{4}(\d{2})?", ts):
        raise ValueError(
            f"--timestamp 格式应为 YYYY-MM-DDTHHMM 或 YYYY-MM-DDTHHMMSS（如 2026-05-19T1500），实为：{ts}"
        )
    return ts


def init_run_explicit(run_path: Path) -> tuple[Path, str]:
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
        hour_ts = _hour_rounded(now)
        hour_path = results_dir / f"{hour_ts}_{actual_slug}"
        if not hour_path.exists():
            run_path = hour_path
            note = f"使用整点 timestamp={hour_ts}"
        else:
            precise_ts = _precise(now)
            run_path = results_dir / f"{precise_ts}_{actual_slug}"
            if run_path.exists():
                import secrets
                suffix = secrets.token_hex(2)
                run_path = results_dir / f"{precise_ts}_{actual_slug}-{suffix}"
            note = f"整点 {hour_ts} 已被占用，fallback 到精确 timestamp={precise_ts}"

    run_path.mkdir(parents=True, exist_ok=False)
    for sub in SUBDIRS:
        (run_path / sub).mkdir(parents=True, exist_ok=True)

    return run_path, note


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
    args = p.parse_args(argv)

    try:
        if args.run_dir:
            ignored = [name for name, val in (("--query", args.query),
                                              ("--slug", args.slug),
                                              ("--timestamp", args.timestamp)) if val]
            if ignored:
                print(f"[init_short_run WARN] --run-dir 模式下忽略派生参数：{', '.join(ignored)}",
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
    except (ValueError, FileExistsError) as e:
        print(f"[init_short_run ERROR] {e}", file=sys.stderr)
        return 2

    print(f"[init_short_run] {note}", file=sys.stderr)
    print(str(run_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
