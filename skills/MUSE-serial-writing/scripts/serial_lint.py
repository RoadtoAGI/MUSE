#!/usr/bin/env python3
"""serial_lint.py — 连载工作区结构性 lint 族

对 works/<slug>/ 工作区（字段契约见 serial-outline references/workspace-schema.md）
做十项结构性校验，机械判据，不调 LLM：

  hook-fields        卷纲 status≠outline 条目 hook_type 非空；章卡 hook.type/design 非空
  thread-closure     已发布章与台账双向闭合；--pending-chapter 加入待发布 recap 的只读投影
  frozen-protect     story_bible.yaml frozen 区较 git HEAD 有 diff 时，要求存在
                     kind=frozen_amendment 且 consumed_by 含 "bible:frozen" 的决策档案
  published-protect  published/*.md 较 git HEAD 有 diff 时，要求 manifest.revisions[]
                     存在对应 {chapter_id, reason} 记录
  limitation         world_facts.yaml 中 kind ∈ {ability,rule} 条目 limitation 非空
  stale-decisions    consumed_by 为空且 scope.volume_id 所指卷已 closed 的决策档案
  genre-profile      genre_profile.yaml 必填枚举校验 + 写保护（凭据 profile:genre）+
                     台账/卷纲枚举值 ∈ 通用核心 ∪ genre-pack 扩展词表（越界仅 WARN）
  worldbook-protect  worldbook/index.yaml 分册注册一致性（file 存在 / mutability 合法 /
                     section_id 唯一）+ axiom 册写保护（凭据 worldbook:<section_id>）
  volume-frozen      HEAD 版本 status=closed 的卷纲有 diff 时，要求凭据 volume:<V##>
  consumer-fields    已有传记 milestones 与卷纲 tentpoles 的消费必需字段及章锚

  缺 genre_profile.yaml / worldbook/（V1 既有工作区）按通用缺省 WARN 通过，不阻断。

frozen-protect / published-protect 用 `git show HEAD:<path>` 取基线；工作区未纳入 git、
文件未提交、或取基线失败的任何情况，一律 WARN（打到 stderr）+ 该条目视为通过，不计入
failures（无基线无法比对，不构成阻断依据）。

用法：
    python3 serial_lint.py --work-dir <工作区根> [--check all] [--file <path>]

    --check 接受逗号分隔与重复 flag 两种写法，等价：
        --check hook-fields,limitation
        --check hook-fields --check limitation
    默认 --check all（等价于全部十项）；split+strip 后为空列表（如 --check ""）视为
    非法用法，报错退出，不静默当作零检查全绿。

    --file 可选：单文件模式，只保留 file 字段命中该路径的 failures（供 hook 用，
    只关心刚写入的这一个文件相关的违规）。--file 必须落在 --work-dir 之内（两侧
    resolve 后按绝对路径比较），否则报错退出。

输出：stdout 一份 YAML `{status: PASS|FAIL, failures: [...]}`。

退出码：
    0 — 全部校验通过（含仅 WARN 视为通过的情形）
    1 — 数据错：--work-dir 不存在 / --check 值非法 / 相关 YAML 解析失败
    2 — 阻断：failures 非空
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from consumer_contract import load_chapter_anchors, validate_milestones, validate_tentpoles
from ledger_tools import project_thread_events, DataError as LedgerDataError

ALL_CHECKS = [
    "hook-fields",
    "thread-closure",
    "frozen-protect",
    "published-protect",
    "limitation",
    "stale-decisions",
    "genre-profile",
    "worldbook-protect",
    "volume-frozen",
    "consumer-fields",
]

# 通用核心枚举（workspace-schema 权威）；genre-pack enum_extensions 在其上追加
GENRE_CORE_ENUMS = {
    "world_facts_kind": {"item", "rule", "state", "geo", "org", "ability", "secret", "relation"},
    "milestone_kind": {"认知转变", "能力获得", "关系变化", "创伤", "誓言", "退场"},
    "thread_kind": {"伏笔", "悬线", "承诺", "谜团"},
    "hook_type": {"悬念", "反转", "情绪炸弹", "信息投放"},
}
PACING_VALUES = {"免费快节奏", "付费标准", "慢热精品"}


class UsageError(Exception):
    """--check 值非法等 CLI 层输入错误。"""


class DataError(Exception):
    """相关 YAML 文件存在但解析失败（区别于文件缺失——缺失按空结构处理）。"""


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return bool(value)


def _rel(path: Path, work_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(work_dir.resolve()))
    except ValueError:
        return str(path)


def load_yaml_or_none(path: Path) -> dict | None:
    """文件不存在 → None（调用方按空结构解释）；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def git_show_head(path: Path) -> tuple[bool, str | None]:
    """取 path 在 git HEAD 的版本内容。

    工作区未纳入任何 git 仓库、文件尚未提交（未跟踪/被 gitignore）、或 git 不可用等
    任何原因导致取不到基线，统一返回 (False, None)——调用方按 WARN + 视为通过处理。
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return False, None
    if top.returncode != 0:
        return False, None
    root = Path(top.stdout.strip())
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False, None
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{rel.as_posix()}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, None
    return True, result.stdout


# ---------------------------------------------------------------------------
# hook-fields
# ---------------------------------------------------------------------------


def check_hook_fields(work_dir: Path) -> tuple[list[dict], list[str]]:
    failures: list[dict] = []
    warnings: list[str] = []

    volumes_dir = work_dir / "series" / "volumes"
    for vol_path in sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []:
        data = load_yaml_or_none(vol_path) or {}
        vol_id = data.get("volume_id") or vol_path.stem
        for chap in data.get("chapters") or []:
            if not isinstance(chap, dict):
                continue
            if "status" not in chap or chap.get("status") is None:
                warnings.append(
                    f"[serial_lint WARN] {vol_id}.chapters[{chap.get('chapter_id')}] 缺 status 字段"
                )
                continue
            status = chap.get("status")
            if status == "outline":
                continue
            if not _non_empty(chap.get("hook_type")):
                failures.append({
                    "check": "hook-fields",
                    "file": _rel(vol_path, work_dir),
                    "chapter_id": chap.get("chapter_id"),
                    "message": f"chapter_id={chap.get('chapter_id')} status={status} 缺 hook_type",
                })

    chapters_root = work_dir / "chapters"
    for card_path in sorted(chapters_root.glob("*/*/chapter_card.yaml")) if chapters_root.is_dir() else []:
        data = load_yaml_or_none(card_path) or {}
        hook = data.get("hook") or {}
        missing = [f for f in ("type", "design") if not _non_empty(hook.get(f))]
        if missing:
            failures.append({
                "check": "hook-fields",
                "file": _rel(card_path, work_dir),
                "chapter_id": data.get("chapter_id"),
                "message": f"章卡缺字段: {', '.join('hook.' + m for m in missing)}",
            })

    return failures, warnings


# ---------------------------------------------------------------------------
# thread-closure
# ---------------------------------------------------------------------------


def check_thread_closure(work_dir: Path, pending_chapter: str | None = None) -> tuple[list[dict], list[str]]:
    failures: list[dict] = []

    volumes_dir = work_dir / "series" / "volumes"
    chapter_entries: list[dict] = []
    for vol_path in sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []:
        data = load_yaml_or_none(vol_path) or {}
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
    threads_data = load_yaml_or_none(threads_path) or {}
    threads = threads_data.get("threads") or []
    manifest = load_yaml_or_none(work_dir / "published" / "manifest.yaml") or {}
    checked_chapters = {
        entry.get("chapter_id") for entry in manifest.get("entries") or []
        if isinstance(entry, dict) and entry.get("chapter_id")
    }
    if pending_chapter:
        matches = list(work_dir.glob(f"chapters/*/{pending_chapter}/recap.yaml"))
        if len(matches) != 1 or pending_chapter not in chapter_by_id:
            raise DataError(f"待发布章 {pending_chapter} 需要唯一 recap.yaml 和卷纲条目")
        recap = load_yaml_or_none(matches[0]) or {}
        deltas = recap.get("deltas")
        if recap.get("chapter_id") != pending_chapter or not isinstance(deltas, dict):
            raise DataError(f"{matches[0]}: chapter_id 或 deltas 无效")
        try:
            threads, _, _ = project_thread_events(
                threads, pending_chapter, deltas.get("thread_events", []),
            )
        except LedgerDataError as exc:
            raise DataError(str(exc)) from exc
        checked_chapters.add(pending_chapter)
    threads_by_id = {
        t.get("thread_id"): t
        for t in threads
        if isinstance(t, dict) and t.get("thread_id")
    }

    # 方向 A：已发生/待发布章的设计义务 → 台账或当前 recap 投影。
    # 后续 outline 仅是计划，不能要求它已经发生并转正。
    for entry in chapter_entries:
        if entry["chapter_id"] not in checked_chapters:
            continue
        for tid in entry["opened"]:
            thread = threads_by_id.get(tid)
            if thread is None or thread.get("opened_at") != entry["chapter_id"]:
                failures.append({
                    "check": "thread-closure",
                    "file": _rel(entry["vol_path"], work_dir),
                    "chapter_id": entry["chapter_id"],
                    "thread_id": tid,
                    "message": (
                        f"chapter_id={entry['chapter_id']} opened 列出 {tid}，"
                        "threads.yaml 无对应 opened_at 一致的条目"
                    ),
                })
        for tid in entry["closed"]:
            thread = threads_by_id.get(tid)
            has_payoff = bool(thread) and any(
                isinstance(ev, dict) and ev.get("kind") == "payoff" and ev.get("at") == entry["chapter_id"]
                for ev in (thread.get("events") or [])
            )
            if not has_payoff:
                failures.append({
                    "check": "thread-closure",
                    "file": _rel(entry["vol_path"], work_dir),
                    "chapter_id": entry["chapter_id"],
                    "thread_id": tid,
                    "message": (
                        f"chapter_id={entry['chapter_id']} closed 列出 {tid}，"
                        "threads.yaml 无对应 payoff 事件（kind=payoff, at 一致）"
                    ),
                })

    # 方向 B：threads.yaml → 卷纲 opened/closed
    for tid, thread in threads_by_id.items():
        opened_at = thread.get("opened_at")
        if opened_at is not None:
            chap = chapter_by_id.get(opened_at)
            if chap is None or tid not in chap["opened"]:
                failures.append({
                    "check": "thread-closure",
                    "file": _rel(threads_path, work_dir),
                    "chapter_id": opened_at,
                    "thread_id": tid,
                    "message": (
                        f"threads.yaml {tid} opened_at={opened_at}，"
                        "对应卷纲章条目 opened 未列出该 thread_id（或该章不存在）"
                    ),
                })
        for ev in thread.get("events") or []:
            if not isinstance(ev, dict) or ev.get("kind") != "payoff":
                continue
            at = ev.get("at")
            chap = chapter_by_id.get(at)
            if chap is None or tid not in chap["closed"]:
                failures.append({
                    "check": "thread-closure",
                    "file": _rel(threads_path, work_dir),
                    "chapter_id": at,
                    "thread_id": tid,
                    "message": (
                        f"threads.yaml {tid} payoff 事件 at={at}，"
                        "对应卷纲章条目 closed 未列出该 thread_id（或该章不存在）"
                    ),
                })

    return failures, []


# ---------------------------------------------------------------------------
# frozen-protect
# ---------------------------------------------------------------------------


def _has_amendment(work_dir: Path, token: str) -> bool:
    """是否存在 kind=frozen_amendment 且 consumed_by 含指定凭据 token 的决策档案。"""
    decisions_dir = work_dir / "series" / "decisions"
    if not decisions_dir.is_dir():
        return False
    for dec_path in decisions_dir.glob("*.yaml"):
        data = load_yaml_or_none(dec_path) or {}
        if data.get("kind") == "frozen_amendment" and token in (data.get("consumed_by") or []):
            return True
    return False


def _has_frozen_amendment(work_dir: Path) -> bool:
    return _has_amendment(work_dir, "bible:frozen")


def check_frozen_protect(work_dir: Path) -> tuple[list[dict], list[str]]:
    path = work_dir / "series" / "story_bible.yaml"
    if not path.exists():
        return [], []

    current = load_yaml_or_none(path) or {}
    ok, head_text = git_show_head(path)
    if not ok:
        return [], [f"[WARN] frozen-protect: {path} 无 git HEAD 基线可比对，视为通过"]

    try:
        head_data = yaml.safe_load(head_text) or {}
    except yaml.YAMLError:
        return [], [f"[WARN] frozen-protect: {path} HEAD 版本 YAML 解析失败，视为通过"]

    if current.get("frozen") == head_data.get("frozen"):
        return [], []

    if _has_frozen_amendment(work_dir):
        return [], []

    return [{
        "check": "frozen-protect",
        "file": _rel(path, work_dir),
        "message": (
            "story_bible.yaml frozen 区与 HEAD 版本不一致，且未找到 "
            "kind=frozen_amendment 且 consumed_by 含 bible:frozen 的决策档案"
        ),
    }], []


# ---------------------------------------------------------------------------
# published-protect
# ---------------------------------------------------------------------------


def check_published_protect(work_dir: Path) -> tuple[list[dict], list[str]]:
    published_dir = work_dir / "published"
    if not published_dir.is_dir():
        return [], []

    manifest = load_yaml_or_none(published_dir / "manifest.yaml") or {}
    entries = manifest.get("entries") or []
    revisions = manifest.get("revisions") or []
    file_to_chapter = {
        e.get("file"): e.get("chapter_id")
        for e in entries if isinstance(e, dict)
    }
    revised_chapters = {
        r.get("chapter_id") for r in revisions
        if isinstance(r, dict) and r.get("chapter_id") and _non_empty(r.get("reason"))
    }

    failures: list[dict] = []
    warnings: list[str] = []
    for md_path in sorted(published_dir.glob("*.md")):
        ok, head_text = git_show_head(md_path)
        if not ok:
            warnings.append(f"[WARN] published-protect: {md_path} 无 git HEAD 基线可比对，视为通过")
            continue
        if md_path.read_text(encoding="utf-8") == head_text:
            continue
        chapter_id = file_to_chapter.get(md_path.name)
        if chapter_id is None or chapter_id not in revised_chapters:
            failures.append({
                "check": "published-protect",
                "file": _rel(md_path, work_dir),
                "chapter_id": chapter_id,
                "message": (
                    f"{md_path.name} 与 HEAD 版本不一致，manifest.revisions[] 未找到 "
                    f"对应 chapter_id={chapter_id} 且 reason 非空的记录"
                ),
            })

    return failures, warnings


# ---------------------------------------------------------------------------
# limitation
# ---------------------------------------------------------------------------


def check_limitation(work_dir: Path) -> tuple[list[dict], list[str]]:
    path = work_dir / "series" / "ledgers" / "world_facts.yaml"
    data = load_yaml_or_none(path) or {}
    failures: list[dict] = []
    for fact in data.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if fact.get("kind") in ("ability", "rule") and not _non_empty(fact.get("limitation")):
            failures.append({
                "check": "limitation",
                "file": _rel(path, work_dir),
                "fact_id": fact.get("fact_id"),
                "message": f"fact_id={fact.get('fact_id')} kind={fact.get('kind')} 缺 limitation",
            })
    return failures, []


# ---------------------------------------------------------------------------
# stale-decisions
# ---------------------------------------------------------------------------


def check_stale_decisions(work_dir: Path) -> tuple[list[dict], list[str]]:
    decisions_dir = work_dir / "series" / "decisions"
    if not decisions_dir.is_dir():
        return [], []

    volumes_dir = work_dir / "series" / "volumes"
    volume_status: dict[str, Any] = {}
    for vol_path in sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []:
        data = load_yaml_or_none(vol_path) or {}
        vid = data.get("volume_id") or vol_path.stem
        volume_status[vid] = data.get("status")

    failures: list[dict] = []
    for dec_path in sorted(decisions_dir.glob("*.yaml")):
        data = load_yaml_or_none(dec_path) or {}
        if data.get("consumed_by"):
            continue  # 非空即已消费
        scope = data.get("scope") or {}
        volume_id = scope.get("volume_id")
        if volume_id and volume_status.get(volume_id) == "closed":
            failures.append({
                "check": "stale-decisions",
                "file": _rel(dec_path, work_dir),
                "decision_id": data.get("decision_id"),
                "message": (
                    f"decision_id={data.get('decision_id')} consumed_by 为空，"
                    f"所属卷 {volume_id} 已 closed"
                ),
            })
    return failures, []


# ---------------------------------------------------------------------------
# genre-profile / worldbook-protect / volume-frozen
# ---------------------------------------------------------------------------


def _find_genre_pack(substrate: str) -> dict | None:
    """定位包内 genre-pack 契约文件（plugin 安装态优先，开发态脚本相对回溯）。"""
    candidates = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "skills" / "serial-outline" / "references" / "genre-packs" / f"{substrate}.yaml")
    here = Path(__file__).resolve().parents[1]
    candidates.append(here / "skills" / "serial-outline" / "references" / "genre-packs" / f"{substrate}.yaml")
    for c in candidates:
        if c.is_file():
            try:
                return yaml.safe_load(c.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                return None
    return None


def check_genre_profile(work_dir: Path) -> tuple[list[dict], list[str]]:
    failures: list[dict] = []
    warnings: list[str] = []
    path = work_dir / "series" / "genre_profile.yaml"
    data = load_yaml_or_none(path)
    if data is None:
        return [], ["[WARN] genre-profile: genre_profile.yaml 缺失，按通用缺省（substrate=generic）运行"]

    substrate = data.get("substrate")
    if not _non_empty(substrate):
        return [], ["[WARN] genre-profile: substrate 未判定（大纲 S1 前合法），跳过枚举与词表校验"]

    if not _non_empty((data.get("engine") or {}).get("primary")):
        failures.append({
            "check": "genre-profile", "file": _rel(path, work_dir),
            "message": "engine.primary 为空——类型判定后爽点引擎主槽必填",
        })
    pacing = data.get("pacing_contract")
    if pacing is not None and pacing not in PACING_VALUES:
        failures.append({
            "check": "genre-profile", "file": _rel(path, work_dir),
            "message": f"pacing_contract={pacing!r} 不在三档值域 {sorted(PACING_VALUES)}",
        })

    # 写保护：判定后冻结，改动须 frozen_amendment 凭据 profile:genre
    ok, head_text = git_show_head(path)
    if not ok:
        warnings.append(f"[WARN] genre-profile: {path} 无 git HEAD 基线可比对，写保护视为通过")
    else:
        try:
            head_data = yaml.safe_load(head_text) or {}
        except yaml.YAMLError:
            head_data = None
        # HEAD 时仍未判定（substrate 空）→ 本次是首次判定写入，不算改动
        if head_data is not None and _non_empty(head_data.get("substrate")) and head_data != data                 and not _has_amendment(work_dir, "profile:genre"):
            failures.append({
                "check": "genre-profile", "file": _rel(path, work_dir),
                "message": "genre_profile.yaml 与 HEAD 不一致，且无 frozen_amendment 决策（consumed_by 含 profile:genre）",
            })

    # 枚举联合词表（通用核心 ∪ pack 扩展）——越界仅 WARN，不阻断（反僵化：词表演进走 pack 更新）
    pack = _find_genre_pack(str(substrate)) if substrate != "generic" else {}
    if pack is None or (substrate != "generic" and not pack):
        warnings.append(f"[WARN] genre-profile: 未找到 genre-pack '{substrate}'，扩展词表按空处理")
        pack = {}
    ext = pack.get("enum_extensions") or {}
    allowed = {k: set(v) | set(ext.get(k) or []) for k, v in GENRE_CORE_ENUMS.items()}

    wf = load_yaml_or_none(work_dir / "series" / "ledgers" / "world_facts.yaml") or {}
    for fact in wf.get("facts") or []:
        if isinstance(fact, dict) and fact.get("kind") not in allowed["world_facts_kind"]:
            warnings.append(f"[WARN] genre-profile: world_facts fact_id={fact.get('fact_id')} kind={fact.get('kind')!r} 不在联合词表")
    chars_dir = work_dir / "series" / "ledgers" / "characters"
    for bio_path in sorted(chars_dir.glob("*/biography.yaml")) if chars_dir.is_dir() else []:
        bio = load_yaml_or_none(bio_path) or {}
        if not isinstance(bio, dict):
            raise DataError(f"{bio_path}: 顶层必须为映射")
        milestones = bio.get("milestones")
        # consumer-fields reports malformed containers and field types as failures.
        for ms in milestones if isinstance(milestones, list) else []:
            if isinstance(ms, dict) and isinstance(ms.get("kind"), str) and ms["kind"] not in allowed["milestone_kind"]:
                warnings.append(f"[WARN] genre-profile: {bio_path.parent.name} milestone at={ms.get('at')} kind={ms.get('kind')!r} 不在联合词表")
    threads = load_yaml_or_none(work_dir / "series" / "ledgers" / "threads.yaml") or {}
    for th in threads.get("threads") or []:
        if isinstance(th, dict) and th.get("kind") not in allowed["thread_kind"]:
            warnings.append(f"[WARN] genre-profile: thread {th.get('thread_id')} kind={th.get('kind')!r} 不在联合词表")
    volumes_dir = work_dir / "series" / "volumes"
    for vol_path in sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []:
        vol = load_yaml_or_none(vol_path) or {}
        for chap in vol.get("chapters") or []:
            if isinstance(chap, dict) and _non_empty(chap.get("hook_type"))                     and chap.get("hook_type") not in allowed["hook_type"]:
                warnings.append(f"[WARN] genre-profile: {vol_path.name} {chap.get('chapter_id')} hook_type={chap.get('hook_type')!r} 不在联合词表")

    return failures, warnings


def check_worldbook_protect(work_dir: Path) -> tuple[list[dict], list[str]]:
    failures: list[dict] = []
    warnings: list[str] = []
    wb_dir = work_dir / "series" / "worldbook"
    index_path = wb_dir / "index.yaml"
    data = load_yaml_or_none(index_path)
    if data is None:
        return [], ["[WARN] worldbook-protect: worldbook/index.yaml 缺失，本作品无分域设定集，跳过"]

    seen_ids: set[str] = set()
    for sec in data.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id")
        if sid in seen_ids:
            failures.append({
                "check": "worldbook-protect", "file": _rel(index_path, work_dir),
                "message": f"section_id={sid} 重复注册",
            })
        seen_ids.add(sid)
        mut = sec.get("mutability")
        if mut not in ("axiom", "append"):
            failures.append({
                "check": "worldbook-protect", "file": _rel(index_path, work_dir),
                "message": f"section_id={sid} mutability={mut!r} 非法（axiom|append）",
            })
            continue
        sec_file = wb_dir / str(sec.get("file") or "")
        if not sec_file.is_file():
            failures.append({
                "check": "worldbook-protect", "file": _rel(index_path, work_dir),
                "message": f"section_id={sid} 注册的分册文件不存在: {sec.get('file')}",
            })
            continue
        if mut == "axiom":
            ok, head_text = git_show_head(sec_file)
            if not ok:
                warnings.append(f"[WARN] worldbook-protect: {sec_file} 无 git HEAD 基线可比对，视为通过")
            elif sec_file.read_text(encoding="utf-8") != head_text                     and not _has_amendment(work_dir, f"worldbook:{sid}"):
                failures.append({
                    "check": "worldbook-protect", "file": _rel(sec_file, work_dir),
                    "message": f"axiom 册 {sid} 与 HEAD 不一致，且无 frozen_amendment 决策（consumed_by 含 worldbook:{sid}）",
                })
    return failures, warnings


def check_volume_frozen(work_dir: Path) -> tuple[list[dict], list[str]]:
    failures: list[dict] = []
    warnings: list[str] = []
    volumes_dir = work_dir / "series" / "volumes"
    for vol_path in sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []:
        ok, head_text = git_show_head(vol_path)
        if not ok:
            warnings.append(f"[WARN] volume-frozen: {vol_path} 无 git HEAD 基线可比对，视为通过")
            continue
        try:
            head_data = yaml.safe_load(head_text) or {}
        except yaml.YAMLError:
            warnings.append(f"[WARN] volume-frozen: {vol_path} HEAD 版本 YAML 解析失败，视为通过")
            continue
        if head_data.get("status") != "closed":
            continue  # 冻结判定以 HEAD 版本 status 为准（含当前把 closed 改回 active 的违规形态）
        if vol_path.read_text(encoding="utf-8") == head_text:
            continue
        vid = head_data.get("volume_id") or vol_path.stem
        if not _has_amendment(work_dir, f"volume:{vid}"):
            failures.append({
                "check": "volume-frozen", "file": _rel(vol_path, work_dir),
                "message": f"closed 卷 {vid} 与 HEAD 不一致，且无 frozen_amendment 决策（consumed_by 含 volume:{vid}）",
            })
    return failures, warnings


def check_consumer_fields(work_dir: Path) -> tuple[list[dict], list[str]]:
    """Validate supplied records; missing old character ledgers remain optional."""
    try:
        anchors = load_chapter_anchors(work_dir)
    except ValueError as exc:
        raise DataError(str(exc)) from exc
    failures: list[dict] = []
    for path in sorted((work_dir / "series" / "volumes").glob("*.yaml")):
        data = load_yaml_or_none(path) or {}
        errors = validate_tentpoles(data.get("tentpoles"), anchors, data.get("volume_id") or path.stem)
        failures.extend({"check": "consumer-fields", "file": _rel(path, work_dir), "message": error}
                        for error in errors)
    for path in sorted((work_dir / "series" / "ledgers" / "characters").glob("*/biography.yaml")):
        data = load_yaml_or_none(path) or {}
        if not isinstance(data, dict):
            raise DataError(f"{path}: 顶层必须为映射")
        errors = validate_milestones(data.get("milestones"), anchors)
        failures.extend({"check": "consumer-fields", "file": _rel(path, work_dir), "message": error}
                        for error in errors)
    return failures, []


CHECK_FUNCS = {
    "hook-fields": check_hook_fields,
    "thread-closure": check_thread_closure,
    "frozen-protect": check_frozen_protect,
    "published-protect": check_published_protect,
    "limitation": check_limitation,
    "stale-decisions": check_stale_decisions,
    "genre-profile": check_genre_profile,
    "worldbook-protect": check_worldbook_protect,
    "volume-frozen": check_volume_frozen,
    "consumer-fields": check_consumer_fields,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_checks(raw_values: list[str] | None) -> list[str]:
    """--check 支持逗号分隔与重复 flag 两种写法，统一 split 后按 ALL_CHECKS 顺序去重。

    出现 "all"（或整体缺省）即等价于全部十项。--check 被显式传入但 split+strip 后
    为空列表（如 --check ""）视为非法用法，报错——不静默当作零检查全绿。
    """
    if not raw_values:
        return list(ALL_CHECKS)

    names: list[str] = []
    for value in raw_values:
        for part in value.split(","):
            part = part.strip()
            if part:
                names.append(part)

    if not names:
        raise UsageError("--check 显式传入但值为空（split+strip 后无有效项），禁止零检查全绿")

    if "all" in names:
        return list(ALL_CHECKS)

    unknown = [n for n in names if n not in ALL_CHECKS]
    if unknown:
        raise UsageError(
            f"未知 --check 值: {unknown}；可选: all, {', '.join(ALL_CHECKS)}"
        )

    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="连载工作区结构性 lint")
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    parser.add_argument(
        "--check", action="append", default=None,
        help="逗号分隔或重复出现均可；默认 all；可选 " + ", ".join(ALL_CHECKS),
    )
    parser.add_argument(
        "--file", default=None,
        help="单文件模式：只保留 file 字段命中该路径的 failures（供 hook 用）；"
             "必须落在 --work-dir 之内，否则报错",
    )
    parser.add_argument("--pending-chapter", default=None,
                        help="thread-closure 只读纳入本章 recap；不写入台账")
    args = parser.parse_args()

    work_dir: Path = args.work_dir
    if not work_dir.is_dir():
        print(f"[serial_lint] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 1

    try:
        checks = parse_checks(args.check)
    except UsageError as exc:
        print(f"[serial_lint] {exc}", file=sys.stderr)
        return 1

    target_rel: str | None = None
    if args.file:
        file_path = Path(args.file).resolve()
        work_root = work_dir.resolve()
        try:
            target_rel = str(file_path.relative_to(work_root))
        except ValueError:
            print(
                f"[serial_lint] --file {args.file} 不在 --work-dir {work_dir} 下",
                file=sys.stderr,
            )
            return 1

    failures: list[dict] = []
    warnings: list[str] = []
    try:
        for name in checks:
            if name == "thread-closure":
                check_failures, check_warnings = check_thread_closure(work_dir, args.pending_chapter)
            else:
                check_failures, check_warnings = CHECK_FUNCS[name](work_dir)
            failures.extend(check_failures)
            warnings.extend(check_warnings)
    except DataError as exc:
        print(f"[serial_lint] {exc}", file=sys.stderr)
        return 1

    if target_rel is not None:
        failures = [f for f in failures if f.get("file") == target_rel]

    for w in warnings:
        print(w, file=sys.stderr)

    payload = {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
    }
    yaml.safe_dump(payload, sys.stdout, allow_unicode=True, sort_keys=False)

    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
