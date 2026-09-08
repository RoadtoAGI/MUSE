#!/usr/bin/env python3
"""publish_chapter.py — 章发布四步事务

按 serial-outline references/workspace-schema.md manifest 一节的发布事务顺序执行，
任一步失败即停在该步，不推进后续步骤（`manifest.yaml` 登记永远是最后一步）：

  ① gate 预检：
     - hard require：`pipeline/phase6_development.yaml` 存在，或
       `pipeline/audit/skip_review.yaml` 有效（reason 非空洞 + risk_acknowledged: true，
       判据同 verify_review_complete.py）——两者皆缺，直接阻断。verify_review_complete.py
       本身对缺 phase6_development.yaml 静默 exit 0（"不该 phase 7 该管"语义），
       此处补上硬性下限，防止绕过审阅直接发布。
     - 子进程调 verify_review_complete.py <章 workspace>（§1.5 场景审阅完整性 +
       escape hatch 语义沿用）
     - recap.yaml 的 deltas 结构 schema 校验（causal_edges/character_deltas/
       fact_deltas/thread_events 各字段齐全）
     - serial_lint.py --check thread-closure --pending-chapter（现台账 + 当前 recap
       只读投影与已发生章/本章卷纲闭合；未来计划不要求先入账）
     - AIGC 防治放行凭据核验：pipeline/aigc_clearance.yaml 存在时，其
       draft_sha256 必须与 draft.md 当前内容 SHA-256 一致（凭据签发后任何改文
       即失效——重签走防治 verify_only 复检），verdict 必须是放行值；凭据缺失
       按防治链未接管的工作区降级 WARN 放行
  ② 子进程调 ledger_tools.py promote --chapter <chapter_id>（幂等，已转正条目
     重跑自动跳过）
  ③ 拷 draft.md → published/<volume_id><chapter_id>.md（卷号从章所在卷纲反查；
     展示态文件名）
  ④ 卷纲条目 status: published → series_state.yaml buffer.drafted_unpublished
     移除该章 → manifest.yaml append {chapter_id, file, published_seq(单调递增), ts}
     ——manifest 登记是事务内最后一个写，任何前步失败都不产生 manifest 条目

幂等：manifest.yaml 已存在该 chapter_id 条目时，视为发布事务已完整落盘，跳过
①-③与 manifest 登记（不重复拷贝 published/ 文件、不重复 append）；返回 0 前重放
卷纲 status 与 buffer 移除两个幂等写——若存在"manifest 已登记但卷纲 status/buffer
未拉齐"的漂移，重跑即治愈。

用法：
    python3 publish_chapter.py --work-dir <works/<slug>/ 工作区根> --chapter C0001

退出码：
    0 — 完成（含幂等重跑）
    1 — 数据错：既有 YAML 解析失败 / 章所在卷目录名不匹配 V\\d{2}
    2 — 阻断：--work-dir 不存在 / --chapter 格式非法 / 章 workspace 不存在 /
        gate 预检未通过 / 前序子进程（verify_review_complete / serial_lint /
        ledger_tools promote）非 0 退出
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

CHAPTER_RE = re.compile(r"^C\d{4}$")
VOLUME_RE = re.compile(r"^V\d{2}$")
EMPTY_REASONS = {"", "skip", "manual_choice", "none", "n/a", "todo", "tbd"}


class UsageError(Exception):
    """阻断性前置条件不满足：workspace/参数非法、gate 预检未通过、子进程阻断。"""


class DataError(Exception):
    """既有 YAML 内容解析失败。"""


# ---------------------------------------------------------------------------
# 通用 IO（自含，不跨脚本 import，保持子进程调用式解耦；风格仿 ledger_tools.py）
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
    """文件不存在 → None（调用方按空结构解释）；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return bool(value)


def run_subprocess(cmd: list[str], label: str) -> int:
    """跑前序脚本子进程；其 stdout/stderr 转发到本脚本 stderr，返回子进程退出码。"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    for stream in (result.stdout, result.stderr):
        if stream:
            sys.stderr.write(f"[{label}] " + (stream if stream.endswith("\n") else stream + "\n"))
    return result.returncode


# ---------------------------------------------------------------------------
# ① gate 预检
# ---------------------------------------------------------------------------


def _skip_review_valid(skip_yaml_path: Path) -> bool:
    if not skip_yaml_path.exists():
        return False
    data = load_yaml_or_none(skip_yaml_path) or {}
    if not isinstance(data, dict):
        return False
    reason = data.get("reason")
    return (isinstance(reason, str) and reason.strip().lower() not in EMPTY_REASONS
            and data.get("risk_acknowledged") is True)


def check_hard_require(chapter_dir: Path) -> None:
    dev_yaml = chapter_dir / "pipeline" / "phase6_development.yaml"
    skip_yaml = chapter_dir / "pipeline" / "audit" / "skip_review.yaml"
    if dev_yaml.exists():
        return
    if _skip_review_valid(skip_yaml):
        return
    raise UsageError(
        f"发布 gate 硬性下限未满足：{dev_yaml} 不存在，且 {skip_yaml} 缺失或无效"
        "（reason 空洞或 risk_acknowledged 非 true）——拒绝发布"
    )


def validate_recap_schema(recap: dict, chapter_id: str, recap_path: Path) -> None:
    if not isinstance(recap, dict):
        raise UsageError(f"{recap_path}: 顶层必须是字典")
    if recap.get("schema_version") != 1:
        raise UsageError(f"{recap_path}: schema_version 必须为 1，实为 {recap.get('schema_version')!r}")
    if recap.get("chapter_id") != chapter_id:
        raise UsageError(
            f"{recap_path}: chapter_id={recap.get('chapter_id')!r} 与目标 {chapter_id!r} 不一致"
        )
    if not _non_empty(recap.get("summary")):
        raise UsageError(f"{recap_path}: summary 不能为空")

    deltas = recap.get("deltas")
    if not isinstance(deltas, dict):
        raise UsageError(f"{recap_path}: deltas 必须是字典")
    for field in ("causal_edges", "character_deltas", "fact_deltas", "thread_events"):
        if field in deltas and not isinstance(deltas[field], list):
            raise UsageError(f"{recap_path}: {field} 必须是列表")

    for i, edge in enumerate(deltas.get("causal_edges") or []):
        if not isinstance(edge, dict) or not _non_empty(edge.get("cause")) or not _non_empty(edge.get("note")):
            raise UsageError(f"{recap_path}: causal_edges[{i}] 缺 cause/note")

    for i, cd in enumerate(deltas.get("character_deltas") or []):
        if not isinstance(cd, dict):
            raise UsageError(f"{recap_path}: character_deltas[{i}] 不是字典")
        missing = [f for f in ("char_id", "at", "kind", "before", "after", "evidence") if not _non_empty(cd.get(f))]
        if missing:
            raise UsageError(f"{recap_path}: character_deltas[{i}] 缺字段: {missing}")

    for i, fd in enumerate(deltas.get("fact_deltas") or []):
        if not isinstance(fd, dict):
            raise UsageError(f"{recap_path}: fact_deltas[{i}] 不是字典")
        missing = [f for f in ("entity", "kind", "attribute", "value", "established_at") if not _non_empty(fd.get(f))]
        if missing:
            raise UsageError(f"{recap_path}: fact_deltas[{i}] 缺字段: {missing}")
        if fd.get("kind") in ("ability", "rule") and not _non_empty(fd.get("limitation")):
            raise UsageError(f"{recap_path}: fact_deltas[{i}] kind={fd.get('kind')} 缺 limitation")

    for i, te in enumerate(deltas.get("thread_events") or []):
        if not isinstance(te, dict):
            raise UsageError(f"{recap_path}: thread_events[{i}] 不是字典")
        kind = te.get("kind")
        if kind == "open":
            if not _non_empty(te.get("thread_id")):
                raise UsageError(f"{recap_path}: thread_events[{i}] kind=open 缺 thread_id")
            if not _non_empty(te.get("statement")):
                raise UsageError(f"{recap_path}: thread_events[{i}] kind=open 缺 statement")
            payoff = te.get("intended_payoff") or {}
            if not isinstance(payoff, dict) or not _non_empty(payoff.get("horizon")):
                raise UsageError(f"{recap_path}: thread_events[{i}] kind=open 缺 intended_payoff.horizon")
        elif kind in ("advance", "payoff"):
            if not _non_empty(te.get("thread_id")):
                raise UsageError(f"{recap_path}: thread_events[{i}] kind={kind} 缺 thread_id")
            if not _non_empty(te.get("note")):
                raise UsageError(f"{recap_path}: thread_events[{i}] kind={kind} 缺 note")
        else:
            raise UsageError(f"{recap_path}: thread_events[{i}] 未知 kind={kind!r}（合法值 open|advance|payoff）")


def check_aigc_clearance(chapter_dir: Path, chapter_id: str) -> None:
    """AIGC 防治放行凭据核验：凭据存在时绑定 hash 必须与 draft.md 当前内容一致
    （签发后任何改文即失效，重签走防治 verify_only 复检）；凭据缺失按防治链未
    接管的工作区降级 WARN，不阻断。"""
    clearance_path = chapter_dir / "pipeline" / "aigc_clearance.yaml"
    clearance = load_yaml_or_none(clearance_path)
    if clearance is None:
        print(
            f"[publish_chapter WARN] AIGC 防治放行凭据缺失（{clearance_path}），"
            "降级放行——发布前应过 AIGC 防治并签发凭据",
            file=sys.stderr,
        )
        return

    if clearance.get("chapter_id") != chapter_id:
        raise UsageError(
            f"{clearance_path}: chapter_id={clearance.get('chapter_id')!r} "
            f"与目标 {chapter_id!r} 不一致"
        )
    verdict = clearance.get("verdict")
    if verdict not in ("pass", "pass_with_notes"):
        raise UsageError(
            f"{clearance_path}: verdict={verdict!r} 非放行值（pass|pass_with_notes）"
            "——防治未通过不得发布"
        )
    expected = str(clearance.get("draft_sha256") or "").strip().lower()
    if not expected:
        raise UsageError(f"{clearance_path}: 缺 draft_sha256——凭据未绑定正文，无效")

    draft_path = chapter_dir / "draft.md"
    if not draft_path.is_file():
        raise UsageError(f"draft.md 不存在: {draft_path}")
    actual = hashlib.sha256(draft_path.read_bytes()).hexdigest()
    if actual != expected:
        raise UsageError(
            f"AIGC 放行凭据已失效：draft.md 当前 SHA-256 {actual[:12]}… 与凭据 "
            f"{expected[:12]}… 不一致（凭据签发后正文被改动）——重跑 AIGC 防治 "
            "verify_only 复检重签后再发布"
        )


def run_gate_precheck(work_dir: Path, chapter_dir: Path, chapter_id: str, script_dir: Path) -> None:
    check_hard_require(chapter_dir)

    recap_path = chapter_dir / "recap.yaml"
    recap = load_yaml_or_none(recap_path)
    if recap is None:
        raise UsageError(f"recap.yaml 不存在: {recap_path}")
    validate_recap_schema(recap, chapter_id, recap_path)
    facts_data = load_yaml_or_none(work_dir / "series" / "ledgers" / "world_facts.yaml") or {}
    fact_ids = {f.get("fact_id") for f in facts_data.get("facts") or []
                if isinstance(f, dict) and isinstance(f.get("fact_id"), str)}
    for i, delta in enumerate(recap["deltas"].get("fact_deltas", [])):
        previous = delta.get("supersedes")
        if previous is not None and (not isinstance(previous, str) or previous not in fact_ids):
            raise UsageError(f"{recap_path}: fact_deltas[{i}].supersedes 未指向已转正事实: {previous!r}")

    rc = run_subprocess(
        [sys.executable, str(script_dir / "verify_review_complete.py"), str(chapter_dir)],
        "verify_review_complete",
    )
    if rc != 0:
        raise UsageError(f"verify_review_complete.py 未通过（exit {rc}）")

    rc = run_subprocess(
        [sys.executable, str(script_dir / "serial_lint.py"),
         "--work-dir", str(work_dir), "--check", "thread-closure",
         "--pending-chapter", chapter_id],
        "serial_lint",
    )
    if rc == 1:
        raise DataError("serial_lint --check thread-closure 数据错（exit 1）")
    if rc != 0:
        raise UsageError(f"serial_lint --check thread-closure 未通过（exit {rc}）")

    check_aigc_clearance(chapter_dir, chapter_id)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def find_chapter_dir(work_dir: Path, chapter_id: str) -> Path:
    matches = sorted(p for p in work_dir.glob(f"chapters/*/{chapter_id}") if p.is_dir())
    if not matches:
        raise UsageError(f"章 workspace 不存在: chapters/*/{chapter_id}")
    if len(matches) > 1:
        raise DataError(f"chapter_id={chapter_id} 命中多个章 workspace，工作区结构异常: {matches}")
    return matches[0]


def already_published(work_dir: Path, chapter_id: str) -> bool:
    manifest = load_yaml_or_none(work_dir / "published" / "manifest.yaml") or {}
    return any(
        isinstance(e, dict) and e.get("chapter_id") == chapter_id
        for e in manifest.get("entries") or []
    )


def apply_volume_status(work_dir: Path, chapter_id: str) -> None:
    """卷纲对应条目 status → published（幂等：已是 published 不重写；卷纲缺失或
    条目未命中 → stderr WARN 不阻断，manifest 才是发布真值）。按 chapter_id（全局
    裸章号）扫描 series/volumes/*.yaml 命中，不依赖章 workspace 仍存在。"""
    volumes_dir = work_dir / "series" / "volumes"
    volume_paths = sorted(volumes_dir.glob("*.yaml")) if volumes_dir.is_dir() else []
    for volume_path in volume_paths:
        vol_data = load_yaml_or_none(volume_path)
        if not isinstance(vol_data, dict):
            continue
        for entry in vol_data.get("chapters") or []:
            if isinstance(entry, dict) and entry.get("chapter_id") == chapter_id:
                if entry.get("status") != "published":
                    entry["status"] = "published"
                    atomic_write_yaml(volume_path, vol_data)
                return
    print(
        f"[publish_chapter WARN] 卷纲未找到 chapter_id={chapter_id} 条目，跳过 status 回写"
        f"（查找范围: {volumes_dir}/*.yaml）",
        file=sys.stderr,
    )


def apply_buffer_removal(work_dir: Path, chapter_id: str) -> None:
    """series_state.yaml buffer.drafted_unpublished 移除该章（幂等：不在列表即不写）。"""
    state_path = work_dir / "series" / "series_state.yaml"
    state = load_yaml_or_none(state_path)
    if state is None:
        return
    buffer = state.get("buffer") or {}
    drafted = buffer.get("drafted_unpublished") or []
    if chapter_id in drafted:
        buffer["drafted_unpublished"] = [c for c in drafted if c != chapter_id]
        state["buffer"] = buffer
        atomic_write_yaml(state_path, state)


def run(work_dir: Path, chapter_id: str, script_dir: Path) -> int:
    # 幂等短路：manifest 已登记即视为发布事务完整落盘，不要求章 workspace 仍存在
    # （工作区可能在发布后被归档/清理），跳过 ①-③ 与 manifest 登记。返回 0 前重放
    # 卷纲 status + buffer 移除两个幂等写，治愈"manifest 已登记但卷纲/buffer 未拉齐"
    # 的漂移。
    if already_published(work_dir, chapter_id):
        apply_volume_status(work_dir, chapter_id)
        apply_buffer_removal(work_dir, chapter_id)
        print(
            f"[publish_chapter] chapter_id={chapter_id} 已在 manifest.yaml 登记，幂等跳过"
            "（卷纲 status / buffer 两个幂等写已重放拉齐）",
            file=sys.stderr,
        )
        return 0

    chapter_dir = find_chapter_dir(work_dir, chapter_id)
    volume_id = chapter_dir.parent.name
    if not VOLUME_RE.match(volume_id):
        raise DataError(
            f"章 workspace 所在卷目录名 {volume_id!r} 不匹配 V\\d{{2}}，"
            f"工作区结构异常: {chapter_dir}"
        )

    # ① gate 预检
    run_gate_precheck(work_dir, chapter_dir, chapter_id, script_dir)

    # ② promote（幂等）
    rc = run_subprocess(
        [sys.executable, str(script_dir / "ledger_tools.py"),
         "promote", "--work-dir", str(work_dir), "--chapter", chapter_id],
        "ledger_tools",
    )
    if rc == 1:
        raise DataError("ledger_tools promote 数据错（exit 1）")
    if rc != 0:
        raise UsageError(f"ledger_tools promote 未通过（exit {rc}）")

    # ③ 拷 draft.md → published/<volume_id><chapter_id>.md
    draft_path = chapter_dir / "draft.md"
    if not draft_path.is_file():
        raise UsageError(f"draft.md 不存在: {draft_path}")
    display_name = f"{volume_id}{chapter_id}.md"
    dest_path = work_dir / "published" / display_name
    atomic_write_text(dest_path, draft_path.read_text(encoding="utf-8"))

    # ④ 卷纲 status → buffer 移除 → manifest 登记（manifest 是事务最后一个写，
    #    死于 manifest 前的任何位置都留下"manifest 未登记"的可恢复断点）
    apply_volume_status(work_dir, chapter_id)
    apply_buffer_removal(work_dir, chapter_id)

    manifest_path = work_dir / "published" / "manifest.yaml"
    manifest = load_yaml_or_none(manifest_path) or {"schema_version": 1, "entries": [], "revisions": []}
    entries = manifest.get("entries") or []
    next_seq = max(
        (e.get("published_seq", 0) for e in entries if isinstance(e, dict)), default=0
    ) + 1
    entries.append({
        "chapter_id": chapter_id,
        "file": display_name,
        "published_seq": next_seq,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    manifest["entries"] = entries
    manifest.setdefault("schema_version", 1)
    manifest.setdefault("revisions", [])
    atomic_write_yaml(manifest_path, manifest)

    print(
        f"[publish_chapter] chapter_id={chapter_id} 已发布: {dest_path}"
        f"（published_seq={next_seq}）",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    parser.add_argument("--chapter", required=True, help="裸章号，如 C0001")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[publish_chapter ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    if not CHAPTER_RE.match(args.chapter):
        print(f"[publish_chapter ERROR] --chapter 必须匹配 C\\d{{4}}，实为 {args.chapter!r}", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent

    try:
        return run(work_dir, args.chapter, script_dir)
    except UsageError as exc:
        print(f"[publish_chapter ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[publish_chapter ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
