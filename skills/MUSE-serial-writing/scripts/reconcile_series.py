#!/usr/bin/env python3
"""reconcile_series.py — 恢复矩阵对账 + 单写者接管

入会机器对账：按产物存在性（不单信 `series_state.yaml` 的 `cursor.stage`）推导每章
发布事务断在哪一步，输出 serial-outline references/workspace-schema.md 恢复矩阵一节
定义的判定（含矩阵作用域）；`--claim-session` 额外提供单写者 marker 的原子接管。

四列判据（候选章 = 已物化 workspace / manifest 登记 / published 文件反查 /
buffer·cursor 引用四来源并集）：
  recap 存在      — 章 workspace 下 `recap.yaml` 是否存在
  台账已转正      — `recap.yaml.deltas` 里 fact_deltas/character_deltas/thread_events
                    的每一项，在 world_facts.yaml / 对应角色 biography.yaml /
                    threads.yaml 中是否存在 `source: {chapter_id, index}` 命中条目；
                    三类合计零项（deltas 本身为空）视为"转正完成"（vacuous true）
  published 文件  — `published/` 下能否按 `<volume_id><chapter_id>.md` 或章号后缀
                    匹配到对应文件
  manifest 条目   — `published/manifest.yaml` 的 `entries[]` 是否含该 chapter_id

判定作用域：恢复矩阵只评估事务窗口内的章——已物化章 workspace 的章，或在
`buffer.drafted_unpublished` / `cursor.working_chapter` 内的章。窗口内：
  - manifest 缺席时按台账转正状态与 published 文件存在与否分四种 pending 断点；
  - recap/published/manifest 三无 → `in_progress`（在写常态，无需动作，不 hard_fail）；
  - manifest 已登记但链路残缺 → hard_fail（发布是"manifest 登记即最后一步"的事务，
    manifest 可见即应链路完整，否则停下请求人工确认，不允许调用方继续写）。
窗口外：manifest 已登记但章 workspace 整体不存在 → `published_archived`（接管导入
或发布后归档的正常形态，不 hard_fail）；仅 published/ 有孤立文件 → anomaly hard_fail。

`--release-session <id>`：仅释放同 ID 的 marker；空 marker 幂等成功，他人持有返回 3。

`--claim-session <id>`：`series_state.yaml` 的 `active_session` 为空或
`session_id` 与 `<id>` 相同 → 原子写入 marker（`session_id` + `started_at`），
exit 0；`session_id` 是他人且未释放 → exit 3（区别于常规 0/1/2 语义，供调用方
识别为"需人工确认接管"信号，停下转 pending_human，不静默抢占）。

用法：
    python3 reconcile_series.py --work-dir <works/<slug>/ 工作区根>
    python3 reconcile_series.py --work-dir <works/<slug>/ 工作区根> --claim-session <session_id>

输出（无 --claim-session 时）：stdout 一份 YAML
    {chapters: [{chapter_id, state, action, note?}], hard_fail: bool}

退出码：
    0 — 对账完成且 hard_fail 为 false；或 --claim-session 接管成功
    1 — 数据错：既有 YAML 解析失败
    2 — 阻断：--work-dir 不存在；或对账 hard_fail 为 true
    3 — 仅 --claim-session：他人 active_session marker 未释放
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

CHAPTER_RE = re.compile(r"^C\d{4}$")
PUBLISHED_FILE_RE = re.compile(r"(C\d{4})\.md$")


class UsageError(Exception):
    """阻断性前置条件不满足：--work-dir 非法、series_state.yaml 不存在等。"""


class DataError(Exception):
    """既有 YAML 内容解析失败。"""


# ---------------------------------------------------------------------------
# 通用 IO（自含，风格仿 ledger_tools.py / serial_lint.py）
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


def atomic_write_yaml(path: Path, data: Any) -> None:
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    atomic_write_text(path, content)


def load_yaml_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def _has_source(items: list, chapter_id: str, index: int) -> bool:
    target = {"chapter_id": chapter_id, "index": index}
    return any(isinstance(it, dict) and it.get("source") == target for it in items)


# ---------------------------------------------------------------------------
# 台账转正状态判定
# ---------------------------------------------------------------------------


def compute_promote_state(work_dir: Path, chapter_id: str, recap: dict | None) -> tuple[str, bool]:
    """返回 (state, vacuous)；state ∈ {none, partial, full}。"""
    deltas = (recap or {}).get("deltas") or {}
    fact_deltas = deltas.get("fact_deltas") or []
    character_deltas = deltas.get("character_deltas") or []
    thread_events = deltas.get("thread_events") or []

    total = len(fact_deltas) + len(character_deltas) + len(thread_events)
    if total == 0:
        return "full", True

    matched = 0

    facts_data = load_yaml_or_none(work_dir / "series" / "ledgers" / "world_facts.yaml") or {}
    facts = facts_data.get("facts") or []
    for i in range(len(fact_deltas)):
        if _has_source(facts, chapter_id, i):
            matched += 1

    for i, delta in enumerate(character_deltas):
        char_id = (delta or {}).get("char_id") if isinstance(delta, dict) else None
        if not char_id:
            continue
        bio = load_yaml_or_none(
            work_dir / "series" / "ledgers" / "characters" / char_id / "biography.yaml"
        ) or {}
        milestones = bio.get("milestones") or []
        if _has_source(milestones, chapter_id, i):
            matched += 1

    threads_data = load_yaml_or_none(work_dir / "series" / "ledgers" / "threads.yaml") or {}
    threads = threads_data.get("threads") or []
    for i, delta in enumerate(thread_events):
        kind = (delta or {}).get("kind") if isinstance(delta, dict) else None
        if kind == "open":
            if _has_source(threads, chapter_id, i):
                matched += 1
        else:
            if any(
                isinstance(t, dict) and _has_source(t.get("events") or [], chapter_id, i)
                for t in threads
            ):
                matched += 1

    if matched == 0:
        return "none", False
    if matched == total:
        return "full", False
    return "partial", False


# ---------------------------------------------------------------------------
# 恢复矩阵判定
# ---------------------------------------------------------------------------


def classify(
    recap_present: bool, promote_state: str, published_present: bool, manifest_present: bool,
) -> tuple[str, str, bool]:
    """返回 (state, action, hard_fail)。"""
    if manifest_present:
        if recap_present and promote_state == "full" and published_present:
            return "published", "已完整发布，无需动作", False
        return (
            "hard_fail",
            "manifest.yaml 已登记但链路残缺（recap/台账转正/published 文件之一缺失）："
            "停下请求用户确认，禁止继续写",
            True,
        )

    if recap_present and promote_state == "full" and published_present:
        return "pending_manifest_registration", "发布事务死于登记步：只补 manifest.yaml 登记", False
    if recap_present and promote_state == "full" and not published_present:
        return "pending_copy_and_registration", "死于拷入 published/ 之前：补拷入 + 登记两步", False
    if recap_present and promote_state == "none" and not published_present:
        return "pending_full_rerun", "死于台账转正之前：从校验转正步整段重跑", False
    if recap_present and promote_state == "partial" and not published_present:
        return (
            "pending_partial_resume",
            "死于台账转正过程中：按幂等续跑转正 + 拷入 + 登记（source 判重跳过已转正条目）",
            False,
        )
    if not recap_present and not published_present:
        return (
            "in_progress",
            "在写常态：章 workspace 已物化但发布事务尚未开始，无需恢复动作",
            False,
        )
    if recap_present and published_present and promote_state in ("none", "partial"):
        return (
            "anomaly",
            "published 文件已存在但台账转正未完成，事务顺序异常，需人工核查",
            True,
        )
    return (
        "anomaly",
        "未覆盖的产物组合（"
        f"recap.yaml {'存在' if recap_present else '缺失'} / "
        f"台账转正 {promote_state} / "
        f"published 文件{'存在' if published_present else '缺失'} / "
        f"manifest 条目{'存在' if manifest_present else '缺失'}"
        "），不在恢复矩阵内，需人工核查",
        True,
    )


def gather_candidate_chapters(
    work_dir: Path,
) -> tuple[dict[str, Path], set[str], set[str]]:
    """候选章号三来源：已物化 workspace 路径表 / manifest.entries 命中集 /
    published/*.md 文件名反查命中集。返回并集范围内各章的原始判据集合，供
    do_reconcile 逐章分类，避免重复扫描 manifest/published 两次。"""
    chapter_paths: dict[str, Path] = {}
    chapters_root = work_dir / "chapters"
    if chapters_root.is_dir():
        for p in sorted(chapters_root.glob("*/*")):
            if p.is_dir() and CHAPTER_RE.match(p.name):
                chapter_paths[p.name] = p

    manifest = load_yaml_or_none(work_dir / "published" / "manifest.yaml") or {}
    manifest_ids = {
        e.get("chapter_id") for e in manifest.get("entries") or []
        if isinstance(e, dict) and e.get("chapter_id")
    }

    published_ids: set[str] = set()
    published_dir = work_dir / "published"
    if published_dir.is_dir():
        for f in published_dir.glob("*.md"):
            m = PUBLISHED_FILE_RE.search(f.name)
            if m:
                published_ids.add(m.group(1))

    return chapter_paths, manifest_ids, published_ids


def get_window_extra_ids(work_dir: Path) -> set[str]:
    """buffer.drafted_unpublished 与 cursor.working_chapter 引用的章号——与已物化
    workspace 一起构成事务窗口成员。"""
    state = load_yaml_or_none(work_dir / "series" / "series_state.yaml") or {}
    buffer = state.get("buffer") or {}
    ids = {
        c for c in (buffer.get("drafted_unpublished") or [])
        if isinstance(c, str) and CHAPTER_RE.match(c)
    }
    cursor = state.get("cursor") or {}
    working = cursor.get("working_chapter")
    if isinstance(working, str) and CHAPTER_RE.match(working):
        ids.add(working)
    return ids


def do_reconcile(work_dir: Path) -> int:
    chapter_paths, manifest_ids, published_ids = gather_candidate_chapters(work_dir)
    window_extra = get_window_extra_ids(work_dir)
    ids = set(chapter_paths) | manifest_ids | published_ids | window_extra

    chapters_out: list[dict] = []
    any_hard_fail = False

    for chapter_id in sorted(ids, key=lambda cid: int(cid[1:])):
        chapter_dir = chapter_paths.get(chapter_id)
        published_present = chapter_id in published_ids
        manifest_present = chapter_id in manifest_ids
        in_window = chapter_dir is not None or chapter_id in window_extra

        if chapter_dir is None and manifest_present:
            # 章 workspace 整体不存在但 manifest 已登记：接管导入或发布后归档清理的
            # 正常形态，不进入事务矩阵评估
            chapters_out.append({
                "chapter_id": chapter_id,
                "state": "published_archived",
                "action": "已发布且章 workspace 不存在（接管导入或发布后归档），无需动作",
            })
            continue

        if not in_window:
            # 无 workspace、不在 buffer/cursor、manifest 未登记，却在 published/
            # 有文件——孤立发布文件
            chapters_out.append({
                "chapter_id": chapter_id,
                "state": "anomaly",
                "action": "published/ 有该章文件但 manifest.yaml 未登记、"
                          "章 workspace 亦不存在——孤立发布文件，需人工核查",
            })
            any_hard_fail = True
            continue

        recap_path = chapter_dir / "recap.yaml" if chapter_dir else None
        recap_present = bool(recap_path and recap_path.is_file())
        recap = load_yaml_or_none(recap_path) if recap_present else None

        if recap_present:
            promote_state, vacuous = compute_promote_state(work_dir, chapter_id, recap)
        else:
            promote_state, vacuous = "none", False

        state, action, hard_fail = classify(
            recap_present, promote_state, published_present, manifest_present
        )
        entry = {"chapter_id": chapter_id, "state": state, "action": action}
        if vacuous:
            entry["note"] = "deltas 为空，视为转正完成（vacuous true）"
        chapters_out.append(entry)
        any_hard_fail = any_hard_fail or hard_fail

    payload = {"chapters": chapters_out, "hard_fail": any_hard_fail}
    yaml.safe_dump(payload, sys.stdout, allow_unicode=True, sort_keys=False)

    return 2 if any_hard_fail else 0


# ---------------------------------------------------------------------------
# --claim-session 单写者接管
# ---------------------------------------------------------------------------


def do_claim_session(work_dir: Path, session_id: str) -> int:
    state_path = work_dir / "series" / "series_state.yaml"
    state = load_yaml_or_none(state_path)
    if state is not None and not isinstance(state, dict):
        raise DataError(f"{state_path} 必须为映射")
    if state is None:
        raise UsageError(f"{state_path} 不存在，无法 claim-session")

    active = state.get("active_session")
    if isinstance(active, dict) and active.get("session_id") and active.get("session_id") != session_id:
        print(
            f"[reconcile_series] active_session.session_id={active.get('session_id')!r} 未释放，"
            f"claim-session={session_id!r} 被拒绝——调用方应停下转 pending_human",
            file=sys.stderr,
        )
        return 3

    if isinstance(active, dict) and active.get("session_id") == session_id:
        return 0
    if active is not None and (not isinstance(active, dict) or not isinstance(active.get("session_id"), str) or not active["session_id"].strip()):
        raise DataError(f"{state_path}: active_session 无效")
    if not session_id.strip():
        raise UsageError("session_id 不能为空")
    state["active_session"] = {
        "session_id": session_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    atomic_write_yaml(state_path, state)
    print(f"[reconcile_series] active_session 已接管，session_id={session_id!r}", file=sys.stderr)
    return 0


def do_release_session(work_dir: Path, session_id: str) -> int:
    """仅释放调用者持有的 marker，保留其他状态；重复释放无副作用。"""
    if not session_id.strip():
        raise UsageError("session_id 不能为空")
    state_path = work_dir / "series" / "series_state.yaml"
    state = load_yaml_or_none(state_path)
    if state is None:
        raise UsageError(f"{state_path} 不存在，无法 release-session")
    if not isinstance(state, dict):
        raise DataError(f"{state_path} 必须为映射")
    active = state.get("active_session")
    if active is None:
        return 0
    if not isinstance(active, dict) or not isinstance(active.get("session_id"), str) or not active["session_id"].strip():
        raise DataError(f"{state_path}: active_session 无效")
    if active["session_id"] != session_id:
        print("[reconcile_series] 不能释放其他 session 的 active_session", file=sys.stderr)
        return 3
    state["active_session"] = None
    atomic_write_yaml(state_path, state)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    session_action = parser.add_mutually_exclusive_group()
    session_action.add_argument(
        "--claim-session", default=None, metavar="SESSION_ID",
        help="原子接管 series_state.yaml 的 active_session marker",
    )
    session_action.add_argument("--release-session", default=None, metavar="SESSION_ID",
                                help="释放本会话持有的 active_session marker")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[reconcile_series ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    try:
        if args.claim_session:
            return do_claim_session(work_dir, args.claim_session)
        if args.release_session:
            return do_release_session(work_dir, args.release_session)
        return do_reconcile(work_dir)
    except UsageError as exc:
        print(f"[reconcile_series ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[reconcile_series ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
