#!/usr/bin/env python3
"""export_gate.py —— 出口 B 交换格式契约校验（自验交付前必跑）

对 takeover-distill 产出的交付目录（<交付根>/series, chapters, published）做七项
契约校验，机械判据，不调 LLM；字段契约权威见
skills/takeover-distill/references/exchange-format.md。

  required-files   必备文件/目录齐全：series/story_bible.yaml、series/series_state.yaml、
                   series/volumes/ 下至少一卷、series/ledgers/{threads,world_facts}.yaml、
                   published/manifest.yaml、published/ 下至少一章 .md；
                   chapters/、series/decisions/、series/ledgers/characters/ 目录存在（可空）
  schema-version   交付树内所有 .yaml 均含 schema_version: 1
  manifest-match   published/manifest.yaml entries 与 published/*.md 一一对应，章 ID/卷归属与卷纲一致
  cursor-valid     series_state 指向续写点：cursor.volume 存在于 volumes/、
                   cursor.working_chapter 为 null、cursor.stage=breaking、
                   active_session 为 null/缺失、buffer.drafted_unpublished 为空
  thread-closure   卷纲条目 opened/closed 与 threads.yaml 台账双向引用自洽
                   （与 muse-serial-writing 的 serial_lint thread-closure 同判据，
                   独立实现——两包不共享代码，不 import 不复制）
  limitation-filled world_facts 中 kind=ability/rule 的条目 limitation 非空
                   （消费方 import 按同判据硬校验；原文取不到真值时按回填协议
                   填显式待定语句，不留空）
  worldbook-consistency worldbook/index.yaml 存在时注册一致（section_id 唯一 /
                   mutability 合法 / 分册文件齐）；genre_profile 或 worldbook
                   缺失仅 WARN（可选交付件，消费方降级解释）

用法：
    python3 export_gate.py --work-dir <交付根>

输出：stderr 逐项列出契约缺口（数据错误时列出解析失败的文件）；stdout 末行打印
机器可读汇总 `checks=<N> failures=<M>`。

退出码：
    0 —— 全部校验通过
    1 —— 数据错：--work-dir 不存在 / 相关 YAML 解析失败
    2 —— 契约缺口：failures 非空，按 stderr 补齐后重跑
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

CHECK_NAMES = [
    "required-files",
    "schema-version",
    "manifest-match",
    "cursor-valid",
    "thread-closure",
    "limitation-filled",
    "worldbook-consistency",
]


class DataError(Exception):
    """YAML 解析失败等数据错误（exit 1）。"""


def _rel(path: Path, work_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(work_dir.resolve()))
    except ValueError:
        return str(path)


def load_yaml_or_none(path: Path) -> Any:
    """文件不存在 → None（调用方按空结构解释）；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


# ---------------------------------------------------------------------------
# 1. required-files —— 必备文件/目录齐全
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    "series/story_bible.yaml",
    "series/series_state.yaml",
    "series/ledgers/threads.yaml",
    "series/ledgers/world_facts.yaml",
    "published/manifest.yaml",
]

REQUIRED_EMPTY_DIRS = [
    "chapters",
    "series/decisions",
    "series/ledgers/characters",
]


def check_required_files(work_dir: Path) -> list[str]:
    failures: list[str] = []
    for rel in REQUIRED_FILES:
        if not (work_dir / rel).is_file():
            failures.append(f"缺必备文件: {rel}")

    volumes_dir = work_dir / "series" / "volumes"
    if not volumes_dir.is_dir() or not any(volumes_dir.glob("*.yaml")):
        failures.append("缺 series/volumes/ 下至少一卷 *.yaml")

    published_dir = work_dir / "published"
    if not published_dir.is_dir() or not any(published_dir.glob("*.md")):
        failures.append("缺 published/ 下至少一章 *.md")

    for rel in REQUIRED_EMPTY_DIRS:
        if not (work_dir / rel).is_dir():
            failures.append(f"缺目录（可空但须存在）: {rel}")

    return failures


# ---------------------------------------------------------------------------
# 2. schema-version —— 交付树内所有 .yaml 均含 schema_version: 1
# ---------------------------------------------------------------------------


def check_schema_version(work_dir: Path) -> list[str]:
    failures: list[str] = []
    for yaml_path in sorted(work_dir.rglob("*.yaml")):
        data = load_yaml_or_none(yaml_path)
        if not isinstance(data, dict):
            failures.append(
                f"{_rel(yaml_path, work_dir)}: YAML 顶层非映射结构，无法读取 schema_version"
            )
            continue
        version = data.get("schema_version")
        if version != 1:
            failures.append(
                f"{_rel(yaml_path, work_dir)}: 缺 schema_version: 1（实际: {version!r}）"
            )
    return failures


# ---------------------------------------------------------------------------
# 3. manifest-match —— manifest entries 与 published/*.md 一一对应
# ---------------------------------------------------------------------------


def check_manifest_match(work_dir: Path) -> list[str]:
    failures: list[str] = []
    published_dir = work_dir / "published"
    manifest = load_yaml_or_none(published_dir / "manifest.yaml")
    if not isinstance(manifest, dict):
        # required-files 已报缺失；文件存在但非法结构时在此提示一次
        if (published_dir / "manifest.yaml").exists():
            failures.append("published/manifest.yaml 顶层非映射结构，无法读取 entries")
        return failures

    entries = manifest.get("entries") or []
    manifest_files: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        file_name = entry.get("file")
        if file_name:
            manifest_files[file_name] = entry.get("chapter_id")

    actual_files = {p.name for p in published_dir.glob("*.md")} if published_dir.is_dir() else set()

    for f in sorted(set(manifest_files) - actual_files):
        failures.append(
            f"published/manifest.yaml 登记 {f}（chapter_id={manifest_files[f]}），"
            "published/ 下不存在该文件"
        )
    for f in sorted(actual_files - set(manifest_files)):
        failures.append(f"published/{f} 存在，manifest.yaml entries 未登记该文件")

    chapter_volumes: dict[str, list[str]] = {}
    for path in sorted((work_dir / "series" / "volumes").glob("V*.yaml")):
        volume = load_yaml_or_none(path) or {}
        for chapter in volume.get("chapters") or []:
            if isinstance(chapter, dict) and chapter.get("chapter_id"):
                chapter_volumes.setdefault(chapter["chapter_id"], []).append(volume.get("volume_id") or path.stem)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        match = re.fullmatch(r"(V\d+)(C\d+)\.md", str(entry.get("file", "")))
        cid = entry.get("chapter_id")
        if not match or match.group(2) != cid or chapter_volumes.get(cid) != [match.group(1)]:
            failures.append(f"manifest 章 {cid}: 发布文件卷号与卷纲所属卷不一致或章条目缺失/重复")

    return failures


# ---------------------------------------------------------------------------
# 4. cursor-valid —— series_state 指向续写点
# ---------------------------------------------------------------------------


def check_cursor_valid(work_dir: Path) -> list[str]:
    failures: list[str] = []
    state_path = work_dir / "series" / "series_state.yaml"
    state = load_yaml_or_none(state_path)
    if not isinstance(state, dict):
        if state_path.exists():
            failures.append("series/series_state.yaml 顶层非映射结构，无法读取 cursor")
        return failures

    cursor = state.get("cursor")
    if not isinstance(cursor, dict):
        failures.append("series/series_state.yaml 缺 cursor 字段或字段非法")
        return failures

    volume_id = cursor.get("volume")
    volumes_dir = work_dir / "series" / "volumes"
    volume_ids: set[str] = set()
    if volumes_dir.is_dir():
        for vol_path in sorted(volumes_dir.glob("*.yaml")):
            vol_data = load_yaml_or_none(vol_path)
            vid = vol_data.get("volume_id") if isinstance(vol_data, dict) else None
            volume_ids.add(vid or vol_path.stem)

    if not volume_id:
        failures.append("series_state.yaml cursor.volume 缺失")
    elif volume_id not in volume_ids:
        failures.append(
            f"series_state.yaml cursor.volume={volume_id!r} 在 series/volumes/ 下不存在"
        )

    stage = cursor.get("stage")
    if stage != "breaking":
        failures.append(f"series_state.yaml cursor.stage 应为 breaking（实际: {stage!r}）")

    working_chapter = cursor.get("working_chapter")
    if working_chapter is not None:
        failures.append(
            f"series_state.yaml cursor.working_chapter={working_chapter!r} 应为 null"
            "（交付时无在写章，接管后第一动作是开卷 breaking）"
        )

    active_session = state.get("active_session")
    if active_session is not None:
        failures.append(
            f"series_state.yaml active_session={active_session!r} 应为 null/缺失"
            "（残留 session marker 会让接管方 claim-session 被硬阻断）"
        )

    buffer = state.get("buffer")
    drafted = (buffer.get("drafted_unpublished") if isinstance(buffer, dict) else None) or []
    if drafted:
        failures.append(
            f"series_state.yaml buffer.drafted_unpublished={drafted!r} 应为空列表"
            "（交付树内不存在未发布草稿，published/ 是唯一正文来源）"
        )

    return failures


# ---------------------------------------------------------------------------
# 5. thread-closure —— 卷纲 opened/closed 与 threads.yaml 双向引用自洽
#    （与 muse-serial-writing serial_lint 的 thread-closure 同判据，独立实现）
# ---------------------------------------------------------------------------


def check_thread_closure(work_dir: Path) -> list[str]:
    failures: list[str] = []

    volumes_dir = work_dir / "series" / "volumes"
    chapter_entries: list[dict] = []
    if volumes_dir.is_dir():
        for vol_path in sorted(volumes_dir.glob("*.yaml")):
            data = load_yaml_or_none(vol_path)
            if not isinstance(data, dict):
                continue
            for chap in data.get("chapters") or []:
                if not isinstance(chap, dict) or not chap.get("chapter_id"):
                    continue
                chapter_entries.append({
                    "chapter_id": chap["chapter_id"],
                    "opened": chap.get("opened") or [],
                    "closed": chap.get("closed") or [],
                    "vol_path": vol_path,
                })
    chapter_by_id = {c["chapter_id"]: c for c in chapter_entries}

    threads_path = work_dir / "series" / "ledgers" / "threads.yaml"
    threads_data = load_yaml_or_none(threads_path)
    threads_by_id = {
        t.get("thread_id"): t
        for t in ((threads_data.get("threads") or []) if isinstance(threads_data, dict) else [])
        if isinstance(t, dict) and t.get("thread_id")
    }

    # 方向 A：卷纲 opened/closed → threads.yaml
    for entry in chapter_entries:
        for tid in entry["opened"]:
            thread = threads_by_id.get(tid)
            if thread is None or thread.get("opened_at") != entry["chapter_id"]:
                failures.append(
                    f"{_rel(entry['vol_path'], work_dir)}: chapter_id={entry['chapter_id']} "
                    f"opened 列出 {tid}，threads.yaml 无对应 opened_at 一致的条目"
                )
        for tid in entry["closed"]:
            thread = threads_by_id.get(tid)
            has_payoff = bool(thread) and any(
                isinstance(ev, dict) and ev.get("kind") == "payoff" and ev.get("at") == entry["chapter_id"]
                for ev in (thread.get("events") or [])
            )
            if not has_payoff:
                failures.append(
                    f"{_rel(entry['vol_path'], work_dir)}: chapter_id={entry['chapter_id']} "
                    f"closed 列出 {tid}，threads.yaml 无对应 payoff 事件（kind=payoff, at 一致）"
                )

    # 方向 B：threads.yaml → 卷纲 opened/closed
    for tid, thread in threads_by_id.items():
        opened_at = thread.get("opened_at")
        if opened_at is not None:
            chap = chapter_by_id.get(opened_at)
            if chap is None or tid not in chap["opened"]:
                failures.append(
                    f"{_rel(threads_path, work_dir)}: {tid} opened_at={opened_at}，"
                    "对应卷纲章条目 opened 未列出该 thread_id（或该章不存在）"
                )
        for ev in thread.get("events") or []:
            if not isinstance(ev, dict) or ev.get("kind") != "payoff":
                continue
            at = ev.get("at")
            chap = chapter_by_id.get(at)
            if chap is None or tid not in chap["closed"]:
                failures.append(
                    f"{_rel(threads_path, work_dir)}: {tid} payoff 事件 at={at}，"
                    "对应卷纲章条目 closed 未列出该 thread_id（或该章不存在）"
                )

    return failures


# ---------------------------------------------------------------------------
# 6. limitation-filled —— ability/rule 条目 limitation 非空
#    （与 muse-serial-writing serial_lint 的 limitation 检查同判据，独立实现）
# ---------------------------------------------------------------------------


def check_limitation_filled(work_dir: Path) -> list[str]:
    failures: list[str] = []
    path = work_dir / "series" / "ledgers" / "world_facts.yaml"
    data = load_yaml_or_none(path)
    if not isinstance(data, dict):
        return failures
    for fact in data.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if fact.get("kind") in ("ability", "rule"):
            limitation = fact.get("limitation")
            if not (isinstance(limitation, str) and limitation.strip()):
                failures.append(
                    f"series/ledgers/world_facts.yaml: fact_id={fact.get('fact_id')} "
                    f"kind={fact.get('kind')} 缺 limitation——原文取不到真值时按回填协议"
                    "填显式待定语句（消费方 import 按非空硬校验，留空必拒收）"
                )
    return failures


def check_worldbook_consistency(work_dir: Path) -> list[str]:
    """worldbook 注册一致性：index.yaml 存在时 section_id 唯一、mutability 合法、
    注册的分册文件必须存在（FAIL）；worldbook/ 或 index 缺失、genre_profile.yaml
    缺失 → 可选交付件按降级解释，仅 stderr WARN 不计 failure（新拆解应产出）。"""
    failures: list[str] = []
    if not (work_dir / "series" / "genre_profile.yaml").is_file():
        print(
            "[export_gate][worldbook-consistency][WARN] series/genre_profile.yaml 缺失"
            "——可选交付件，消费方按通用缺省降级；新拆解应在序列⓪产出",
            file=sys.stderr,
        )
    wb_dir = work_dir / "series" / "worldbook"
    index = load_yaml_or_none(wb_dir / "index.yaml")
    if index is None:
        print(
            "[export_gate][worldbook-consistency][WARN] series/worldbook/index.yaml 缺失"
            "——可选交付件，消费方按'无分域设定集'降级；新拆解应在序列④产出",
            file=sys.stderr,
        )
        return failures
    if not isinstance(index, dict):
        return failures
    seen: set[str] = set()
    for s in index.get("sections") or []:
        if not isinstance(s, dict):
            continue
        sid = s.get("section_id")
        if not sid:
            failures.append("series/worldbook/index.yaml: sections 条目缺 section_id")
            continue
        if sid in seen:
            failures.append(f"series/worldbook/index.yaml: section_id={sid} 重复注册")
        seen.add(sid)
        if s.get("mutability") not in ("axiom", "append"):
            failures.append(
                f"series/worldbook/index.yaml: {sid} mutability={s.get('mutability')!r} "
                "非法（axiom|append）"
            )
        fname = s.get("file") or f"{sid}.md"
        if not (wb_dir / fname).is_file():
            failures.append(
                f"series/worldbook/{fname} 缺失（index 已注册 {sid}）——注册与分册文件必须一致"
            )
    return failures


CHECK_FUNCS = {
    "required-files": check_required_files,
    "schema-version": check_schema_version,
    "manifest-match": check_manifest_match,
    "cursor-valid": check_cursor_valid,
    "thread-closure": check_thread_closure,
    "limitation-filled": check_limitation_filled,
    "worldbook-consistency": check_worldbook_consistency,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="出口 B 交换格式契约校验（export gate）")
    parser.add_argument("--work-dir", required=True, type=Path, help="交付根路径")
    args = parser.parse_args()

    work_dir: Path = args.work_dir
    if not work_dir.is_dir():
        print(f"[export_gate] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 1

    failures: list[str] = []
    try:
        for name in CHECK_NAMES:
            check_failures = CHECK_FUNCS[name](work_dir)
            for msg in check_failures:
                print(f"[export_gate][{name}] {msg}", file=sys.stderr)
            failures.extend(check_failures)
    except DataError as exc:
        print(f"[export_gate] {exc}", file=sys.stderr)
        return 1

    print(f"checks={len(CHECK_NAMES)} failures={len(failures)}")
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
