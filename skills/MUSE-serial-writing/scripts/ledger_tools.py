#!/usr/bin/env python3
"""ledger_tools.py — 连载工作区三台账写入 / retract / facts_current 派生视图重建

三个子命令，字段契约见 serial-outline workspace-schema.md 的
threads.yaml / world_facts.yaml / biography.yaml / facts_current.yaml 各节：

  promote        读 chapters/*/<chapter_id>/recap.yaml 的 deltas，转正 append 进
                 三台账（world_facts.yaml facts / 各角色 biography.yaml milestones /
                 threads.yaml threads-events）。完成后自动重建 facts_current.yaml。
  retract        目标 fact 条目原地追加 status:retracted + retracted_by +
                 retraction_reason（不删除原条目），重建 facts_current.yaml。
  rebuild-current 按三步算法从 world_facts.yaml 重算 facts_current.yaml：
                 ① 取 status:active 行为 active_rows
                 ② 仅从 active_rows 的 supersedes 收集 suppressed_ids
                 ③ 输出 active_rows − suppressed_ids

幂等：promote 写入的每条台账条目（fact / milestone / thread 创建 / thread 事件）都携带
`source: {chapter_id, index}`；重跑同一章 promote 时，已存在同 source 的条目直接跳过，
不产生重复写入。`index` 是该条目在其所属 deltas 子列表（fact_deltas / character_deltas /
thread_events）内的位置序号，各子列表独立编号。

thread_events 支持三种 kind：
  open     新开一条伏笔——从 delta 的 statement / intended_payoff 构造新 threads 条目，
           opened_at 设为本章号；thread_id 缺省时按序号自动分配。
  advance  在已存在的 thread_id 条目 events 追加一条 advance 事件，thread 顶层
           status 推进为 advanced（若已是 paid 则不回退）。
  payoff   同 advance，但 status 推进为 paid（终态）。

fact_deltas 若带 source_reveal_id（非 null），回写该章所属卷纲
`series/volumes/V0N.yaml` 对应 world_reveal_plan 条目为 status:fulfilled，
并附上新分配的 fact_id 与本章号；卷号从 chapter 所属物理路径 chapters/V0N/<chapter_id>/
反查，不需要单独的命令行参数。回指目标缺失时打印 stderr 提示并跳过（不阻断本次
promote 的其余部分）。

用法：
    python3 ledger_tools.py promote --work-dir <工作区根> --chapter C0005
    python3 ledger_tools.py retract --work-dir <工作区根> --fact F-0002 --by D-0001 --reason "误入账"
    python3 ledger_tools.py rebuild-current --work-dir <工作区根> [--chapter C0005]

退出码：
    0 — 完成
    1 — 数据错：既有 YAML 解析失败 / delta 内容结构非法（如未知 kind、advance 引用
        不存在的 thread_id、kind=open 缺 statement 或 intended_payoff.horizon）
    2 — 阻断：--work-dir 不存在 / --chapter 格式非法 / 待处理的 recap.yaml 或
        fact_id 不存在（目标资源缺失，无法执行请求的动作）
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

CHAPTER_RE = re.compile(r"^C\d{4}$")
FACT_ID_RE = re.compile(r"^F-(\d{4})$")
THREAD_ID_RE = re.compile(r"^T-(\d{4})$")

FACTS_CURRENT_HEADER = (
    "# series/ledgers/facts_current.yaml —— 派生视图非真值源\n"
    "# 由 ledger_tools.py 从 world_facts.yaml 重算生成，可随时丢弃重建，不手工编辑\n"
)


class UsageError(Exception):
    """阻断性前置条件不满足：目标资源不存在，或输入格式非法。"""


class DataError(Exception):
    """既有 YAML 内容解析失败，或 delta 内容结构不合法。"""


# ---------------------------------------------------------------------------
# 通用 IO
# ---------------------------------------------------------------------------


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_yaml(path: Path, data: Any, header: str | None = None) -> None:
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    if header:
        content = header + content
    atomic_write_text(path, content)


def load_yaml_or_none(path: Path) -> dict | None:
    """文件不存在 → None（调用方按空结构解释）；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def _chapter_num(chapter_id: str) -> int:
    return int(chapter_id[1:])


def _has_source(items: list, chapter_id: str, index: int) -> bool:
    target = {"chapter_id": chapter_id, "index": index}
    return any(isinstance(it, dict) and it.get("source") == target for it in items)


# ---------------------------------------------------------------------------
# ID 生成（扫描既有台账，取同前缀最大编号 + 1；retracted 条目同样占位，不复用其号）
# ---------------------------------------------------------------------------


def next_fact_id(facts: list) -> str:
    max_n = 0
    for f in facts:
        if not isinstance(f, dict):
            continue
        m = FACT_ID_RE.match(str(f.get("fact_id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"F-{max_n + 1:04d}"


def next_thread_id(threads: list) -> str:
    max_n = 0
    for t in threads:
        if not isinstance(t, dict):
            continue
        m = THREAD_ID_RE.match(str(t.get("thread_id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"T-{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# facts_current 派生视图（三步重建算法）
# ---------------------------------------------------------------------------


def active_facts(facts: list[dict]) -> list[dict]:
    """Resolve active supersession edges within the supplied source window."""
    active_rows = [f for f in facts if f.get("status") == "active"]
    suppressed_ids = {f.get("supersedes") for f in active_rows if f.get("supersedes")}
    return [f for f in active_rows if f.get("fact_id") not in suppressed_ids]


def rebuild_facts_current(work_dir: Path, chapter_id: str | None = None) -> dict:
    facts_path = work_dir / "series" / "ledgers" / "world_facts.yaml"
    data = load_yaml_or_none(facts_path) or {}
    output_rows = active_facts([f for f in (data.get("facts") or []) if isinstance(f, dict)])

    current = {
        "schema_version": 1,
        "generated_from_chapter": chapter_id,
        "facts": output_rows,
    }
    out_path = work_dir / "series" / "ledgers" / "facts_current.yaml"
    atomic_write_yaml(out_path, current, header=FACTS_CURRENT_HEADER)
    return current


# ---------------------------------------------------------------------------
# retract
# ---------------------------------------------------------------------------


def do_retract(work_dir: Path, fact_id: str, by: str, reason: str) -> int:
    facts_path = work_dir / "series" / "ledgers" / "world_facts.yaml"
    data = load_yaml_or_none(facts_path)
    if data is None:
        raise UsageError(f"{facts_path} 不存在，无法 retract")
    facts = data.get("facts") or []

    target = None
    for f in facts:
        if isinstance(f, dict) and f.get("fact_id") == fact_id:
            target = f
            break
    if target is None:
        raise UsageError(f"fact_id={fact_id} 在 {facts_path} 中不存在")

    if target.get("status") == "retracted":
        print(
            f"[ledger_tools WARN] fact_id={fact_id} 已处于 retracted 状态，"
            "不重复覆写 retracted_by/retraction_reason（保留原始作废记录）",
            file=sys.stderr,
        )
    else:
        target["status"] = "retracted"
        target["retracted_by"] = by
        target["retraction_reason"] = reason
        data["facts"] = facts
        atomic_write_yaml(facts_path, data)
        print(f"[ledger_tools] fact_id={fact_id} 已 retract（by={by}）", file=sys.stderr)

    rebuild_facts_current(work_dir, chapter_id=None)
    return 0


# ---------------------------------------------------------------------------
# promote：fact_deltas → world_facts.yaml
# ---------------------------------------------------------------------------


def _build_fact_entry(delta: dict, fact_id: str, chapter_id: str, index: int) -> tuple[dict, str | None]:
    """把 recap fact_delta 转成 world_facts.yaml 行。

    source_reveal_id 只是 delta 侧的回指触发器，不进入台账行 schema（world_facts.yaml
    字段表无此字段）——取出后单独返回给调用方去驱动卷纲回写，不持久化到 fact 行本身。
    """
    entry = dict(delta)
    source_reveal_id = entry.pop("source_reveal_id", None)
    entry["fact_id"] = fact_id
    entry.setdefault("origin", "normal")
    entry.setdefault("status", "active")
    if entry["status"] == "retracted":
        entry.setdefault("retracted_by", None)
        entry.setdefault("retraction_reason", None)
    entry["source"] = {"chapter_id": chapter_id, "index": index}
    return entry, source_reveal_id


def _apply_reveal_fulfillments(
    work_dir: Path, volume_dir_name: str, updates: list[tuple[str, str, str]]
) -> None:
    if not updates:
        return
    volume_path = work_dir / "series" / "volumes" / f"{volume_dir_name}.yaml"
    vol_data = load_yaml_or_none(volume_path)
    if vol_data is None:
        for reveal_id, _fact_id, _chapter_id in updates:
            print(
                f"[ledger_tools WARN] source_reveal_id={reveal_id} 无法回写："
                f"卷纲文件不存在 {volume_path}",
                file=sys.stderr,
            )
        return

    reveal_plan = vol_data.get("world_reveal_plan") or []
    by_id = {r.get("reveal_id"): r for r in reveal_plan if isinstance(r, dict)}
    changed = False
    for reveal_id, fact_id, chapter_id in updates:
        reveal = by_id.get(reveal_id)
        if reveal is None:
            print(
                f"[ledger_tools WARN] source_reveal_id={reveal_id} 在 {volume_path} 的 "
                "world_reveal_plan 中未找到对应条目，跳过回写",
                file=sys.stderr,
            )
            continue
        reveal["status"] = "fulfilled"
        reveal["fact_id"] = fact_id
        reveal["chapter_id"] = chapter_id
        changed = True

    if changed:
        atomic_write_yaml(volume_path, vol_data)


# ---------------------------------------------------------------------------
# promote：character_deltas → characters/<char_id>/biography.yaml
# ---------------------------------------------------------------------------


def _promote_character_deltas(work_dir: Path, chapter_id: str, character_deltas: list) -> tuple[int, int]:
    promoted = 0
    skipped = 0

    by_char: dict[str, list[tuple[int, dict]]] = {}
    for i, delta in enumerate(character_deltas):
        if not isinstance(delta, dict):
            raise DataError(f"character_deltas[{i}] 不是合法字典")
        char_id = delta.get("char_id")
        if not char_id:
            raise DataError(f"character_deltas[{i}] 缺 char_id")
        by_char.setdefault(char_id, []).append((i, delta))

    for char_id, items in by_char.items():
        bio_path = work_dir / "series" / "ledgers" / "characters" / char_id / "biography.yaml"
        bio = load_yaml_or_none(bio_path)
        if bio is None:
            # 新角色首次入账：构造纯净结构，不沿用模板里的虚构示例内容
            # （与 init_series.py 对 threads.yaml/world_facts.yaml 的处理口径一致）。
            bio = {
                "schema_version": 1,
                "char_id": char_id,
                "growth_track": [],
                "milestones": [],
                "last_seen": None,
            }
        milestones = bio.get("milestones") or []
        changed = False
        for i, delta in items:
            if _has_source(milestones, chapter_id, i):
                skipped += 1
                continue
            milestone = {
                "at": delta.get("at"),
                "kind": delta.get("kind"),
                "before": delta.get("before"),
                "after": delta.get("after"),
                "evidence": delta.get("evidence"),
                "source": {"chapter_id": chapter_id, "index": i},
            }
            milestones.append(milestone)
            changed = True
            promoted += 1

        if changed:
            bio["milestones"] = milestones
            bio.setdefault("schema_version", 1)
            bio.setdefault("char_id", char_id)
            bio.setdefault("growth_track", [])
            existing_last = bio.get("last_seen")
            if existing_last is None or _chapter_num(chapter_id) > _chapter_num(existing_last):
                bio["last_seen"] = chapter_id
            atomic_write_yaml(bio_path, bio)

    return promoted, skipped


# ---------------------------------------------------------------------------
# promote：thread_events → threads.yaml（open 建新条目 / advance,payoff 追加事件）
# ---------------------------------------------------------------------------


def project_thread_events(threads: list, chapter_id: str, thread_events: list) -> tuple[list, int, int]:
    """Apply candidate events to a copy; precheck and promotion share transition semantics."""
    if not isinstance(threads, list) or not isinstance(thread_events, list):
        raise DataError("threads / thread_events 必须为列表")
    threads = deepcopy(threads)
    by_id = {}
    for thread in threads:
        if not isinstance(thread, dict) or not isinstance(thread.get("thread_id"), str) or not thread["thread_id"]:
            raise DataError("threads 条目需要非空字符串 thread_id")
        if not isinstance(thread.get("events", []), list):
            raise DataError(f"{thread['thread_id']}: events 必须为列表")
        if thread["thread_id"] in by_id:
            raise DataError(f"重复 thread_id={thread['thread_id']}")
        by_id[thread["thread_id"]] = thread

    promoted = 0
    skipped = 0

    for i, delta in enumerate(thread_events):
        if not isinstance(delta, dict):
            raise DataError(f"thread_events[{i}] 不是合法字典")
        kind = delta.get("kind")
        supplied_id = delta.get("thread_id")
        if supplied_id is not None and (not isinstance(supplied_id, str) or not supplied_id.strip()):
            raise DataError(f"thread_events[{i}]: thread_id 必须为非空字符串")

        if kind == "open":
            if _has_source(threads, chapter_id, i):
                skipped += 1
                continue
            statement = delta.get("statement")
            if not statement:
                raise DataError(f"thread_events[{i}] kind=open 缺 statement")
            intended_payoff = delta.get("intended_payoff") or {}
            if not isinstance(intended_payoff, dict) or not intended_payoff.get("horizon"):
                raise DataError(f"thread_events[{i}] kind=open 缺 intended_payoff.horizon")
            thread_id = delta.get("thread_id") or next_thread_id(threads)
            if thread_id in by_id:
                raise DataError(
                    f"thread_events[{i}] kind=open 指定的 thread_id={thread_id} 已存在"
                )
            new_thread = {
                "thread_id": thread_id,
                "kind": delta.get("thread_kind", "伏笔"),
                "opened_at": chapter_id,
                "statement": statement,
                "intended_payoff": intended_payoff,
                "status": "open",
                "events": [],
                "source": {"chapter_id": chapter_id, "index": i},
            }
            threads.append(new_thread)
            by_id[thread_id] = new_thread
            promoted += 1
            continue

        if kind in ("advance", "payoff"):
            thread_id = delta.get("thread_id")
            if not thread_id:
                raise DataError(f"thread_events[{i}] kind={kind} 缺 thread_id")
            thread = by_id.get(thread_id)
            if thread is None:
                raise DataError(
                    f"thread_events[{i}] thread_id={thread_id} 在 threads.yaml 中不存在"
                )
            events = thread.get("events") or []
            if _has_source(events, chapter_id, i):
                skipped += 1
                continue
            note = delta.get("note")
            if not note:
                raise DataError(f"thread_events[{i}] kind={kind} 缺 note")
            events.append({
                "at": chapter_id,
                "kind": kind,
                "note": note,
                "source": {"chapter_id": chapter_id, "index": i},
            })
            thread["events"] = events
            if kind == "payoff":
                thread["status"] = "paid"
            elif thread.get("status") != "paid":
                thread["status"] = "advanced"
            promoted += 1
            continue

        raise DataError(f"thread_events[{i}] 未知 kind={kind!r}（合法值 open|advance|payoff）")

    return threads, promoted, skipped


def _promote_thread_events(work_dir: Path, chapter_id: str, thread_events: list) -> tuple[int, int]:
    threads_path = work_dir / "series" / "ledgers" / "threads.yaml"
    threads_data = load_yaml_or_none(threads_path) or {"schema_version": 1, "threads": []}
    threads, promoted, skipped = project_thread_events(
        threads_data.get("threads") or [], chapter_id, thread_events,
    )
    if promoted:
        threads_data["threads"] = threads
        threads_data.setdefault("schema_version", 1)
        atomic_write_yaml(threads_path, threads_data)

    return promoted, skipped


# ---------------------------------------------------------------------------
# promote 主流程
# ---------------------------------------------------------------------------


def do_promote(work_dir: Path, chapter_id: str) -> int:
    if not CHAPTER_RE.match(chapter_id):
        raise UsageError(f"--chapter 必须匹配 C\\d{{4}}，实为 {chapter_id!r}")

    matches = sorted(work_dir.glob(f"chapters/*/{chapter_id}/recap.yaml"))
    if not matches:
        raise UsageError(
            f"未找到 chapter_id={chapter_id} 对应的 recap.yaml"
            f"（chapters/*/{chapter_id}/recap.yaml）"
        )
    if len(matches) > 1:
        raise DataError(
            f"chapter_id={chapter_id} 命中多个 recap.yaml，工作区结构异常: {matches}"
        )
    recap_path = matches[0]
    volume_dir_name = recap_path.parent.parent.name  # 如 V01，物理路径反查卷号

    recap = load_yaml_or_none(recap_path)
    if recap is None:
        raise UsageError(f"{recap_path} 不存在")
    deltas = recap.get("deltas") or {}
    character_deltas = deltas.get("character_deltas") or []
    fact_deltas = deltas.get("fact_deltas") or []
    thread_events = deltas.get("thread_events") or []

    # ---- fact_deltas → world_facts.yaml ----
    facts_path = work_dir / "series" / "ledgers" / "world_facts.yaml"
    facts_data = load_yaml_or_none(facts_path) or {"schema_version": 1, "facts": []}
    facts = facts_data.get("facts") or []

    fact_promoted = 0
    fact_skipped = 0
    reveal_updates: list[tuple[str, str, str]] = []
    facts_changed = False

    for i, delta in enumerate(fact_deltas):
        if not isinstance(delta, dict):
            raise DataError(f"{recap_path} fact_deltas[{i}] 不是合法字典")
        if _has_source(facts, chapter_id, i):
            fact_skipped += 1
            continue
        new_fact_id = next_fact_id(facts)
        entry, source_reveal_id = _build_fact_entry(delta, new_fact_id, chapter_id, i)
        facts.append(entry)
        facts_changed = True
        fact_promoted += 1
        if source_reveal_id:
            reveal_updates.append((source_reveal_id, new_fact_id, chapter_id))

    if facts_changed:
        facts_data["facts"] = facts
        facts_data.setdefault("schema_version", 1)
        atomic_write_yaml(facts_path, facts_data)

    # ---- character_deltas → biography.yaml ----
    char_promoted, char_skipped = _promote_character_deltas(work_dir, chapter_id, character_deltas)

    # ---- thread_events → threads.yaml ----
    thread_promoted, thread_skipped = _promote_thread_events(work_dir, chapter_id, thread_events)

    # ---- fact_deltas 的 source_reveal_id 回写卷纲 ----
    _apply_reveal_fulfillments(work_dir, volume_dir_name, reveal_updates)

    # ---- facts_current 派生视图收尾 ----
    rebuild_facts_current(work_dir, chapter_id=chapter_id)

    print(
        f"[ledger_tools] promote chapter_id={chapter_id}: "
        f"facts +{fact_promoted}(skip {fact_skipped}), "
        f"milestones +{char_promoted}(skip {char_skipped}), "
        f"thread_events +{thread_promoted}(skip {thread_skipped})",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_promote = sub.add_parser("promote", help="将某章 recap.yaml 的 deltas 转正入三台账")
    p_promote.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    p_promote.add_argument("--chapter", required=True, help="裸章号，如 C0005")

    p_retract = sub.add_parser("retract", help="作废一条 world_facts 条目（不删除原条目）")
    p_retract.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    p_retract.add_argument("--fact", required=True, help="fact_id，如 F-0002")
    p_retract.add_argument("--by", required=True, help="触发作废的 decision/复核事件 ID")
    p_retract.add_argument("--reason", required=True, help="一句话作废理由")

    p_rebuild = sub.add_parser("rebuild-current", help="按三步算法重建 facts_current.yaml")
    p_rebuild.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    p_rebuild.add_argument(
        "--chapter", default=None,
        help="记录本次重建关联的章号，写入 generated_from_chapter（可选，省略则为 null）",
    )

    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[ledger_tools ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    try:
        if args.command == "promote":
            return do_promote(work_dir, args.chapter)
        if args.command == "retract":
            return do_retract(work_dir, args.fact, args.by, args.reason)
        if args.command == "rebuild-current":
            rebuild_facts_current(work_dir, chapter_id=args.chapter)
            out_path = work_dir / "series" / "ledgers" / "facts_current.yaml"
            print(f"[ledger_tools] facts_current.yaml 已重建: {out_path}", file=sys.stderr)
            return 0
    except UsageError as exc:
        print(f"[ledger_tools ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[ledger_tools ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
