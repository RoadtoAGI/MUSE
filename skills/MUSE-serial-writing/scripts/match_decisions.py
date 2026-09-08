#!/usr/bin/env python3
"""match_decisions.py — 决策消费三步协议：机械列出待消费决策 + 回写 consumed_by

字段契约见 serial-outline workspace-schema.md 的 series/decisions/D-<seq>.yaml 节。

两个子命令：

  list      列出 --work-dir 下 series/decisions/D-*.yaml 中 scope 命中且
            consumed_by 为空的决策，stdout 输出 YAML。只考虑 scope.level 与
            --level 相同的决策（typed scope，不同 level 互不干扰）。命中键：
              level=volume   按 volume_id
              level=unit     按 (volume_id, unit_id) 联合键（unit_id 卷内局部，
                             跨卷同名不互相命中）
              level=chapter  按 chapter_id；--volume 仅做一致性校验——chapter_id
                             命中但 scope.volume_id 与传入 --volume 不一致视为
                             工作区数据错误（不是"未命中"，直接阻断退出）

  consume   把 --by 追加进目标决策的 consumed_by（幂等：已含同值不重复追加）。
            --by 值域为规范 artifact token：
              volume:V##  unit:V##-U##  chapter:C####
              bible:frozen  profile:genre  worldbook:<section_id>
            后三种仅 kind: frozen_amendment 决策可用（对应冻结资料的
            写保护凭据）；section_id 沿用设定册的 ASCII kebab-case 标识。

用法：
    python3 match_decisions.py list --work-dir <工作区根> --level unit \
        --volume V01 --unit U01
    python3 match_decisions.py list --work-dir <工作区根> --level chapter \
        --volume V01 --chapter C0005
    python3 match_decisions.py consume --work-dir <工作区根> --decision D-0001 \
        --by unit:V01-U01

退出码：
    0 — 完成
    1 — 数据错：决策 YAML 解析失败 / scope 缺失或结构非法 / level=chapter 命中
        但 scope.volume_id 与传入 --volume 不一致
    2 — 阻断：--work-dir 不存在 / --decision 对应文件不存在 / --by 值域不合规 /
        --by 为冻结资料 token 但决策 kind 不是 frozen_amendment
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

BY_BIBLE_FROZEN = "bible:frozen"
BY_PROFILE_GENRE = "profile:genre"
BY_WORLDBOOK_RE = re.compile(r"worldbook:[a-z0-9]+(?:-[a-z0-9]+)*")
BY_VOLUME_RE = re.compile(r"^volume:V\d{2}$")
BY_UNIT_RE = re.compile(r"^unit:V\d{2}-U\d{2}$")
BY_CHAPTER_RE = re.compile(r"^chapter:C\d{4}$")
DECISION_ID_RE = re.compile(r"^D-[A-Za-z0-9_-]+$")


class UsageError(Exception):
    """阻断性前置条件不满足：资源缺失 / --by 值域不合规。"""


class DataError(Exception):
    """既有决策 YAML 解析失败，或 workspace 内部一致性校验失败。"""


# ---------------------------------------------------------------------------
# 通用 IO（仿 ledger_tools.py：临时文件 + rename 原子写）
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
    """文件不存在 → None；存在但解析失败 → 抛 DataError。"""
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DataError(f"{path}: YAML 解析失败: {exc}") from exc


def _iter_decisions(work_dir: Path):
    decisions_dir = work_dir / "series" / "decisions"
    if not decisions_dir.is_dir():
        return
    for path in sorted(decisions_dir.glob("D-*.yaml")):
        data = load_yaml_or_none(path)
        if data is None:
            continue
        yield path, data


# ---------------------------------------------------------------------------
# list：typed scope 机械命中键 + consumed_by 为空过滤
# ---------------------------------------------------------------------------


def do_list(
    work_dir: Path, level: str, volume: str, unit: str | None, chapter: str | None
) -> int:
    if level == "unit" and not unit:
        raise UsageError("--level unit 需要 --unit")
    if level == "chapter" and not chapter:
        raise UsageError("--level chapter 需要 --chapter")

    hits: list[dict] = []
    for path, data in _iter_decisions(work_dir):
        if data.get("consumed_by"):
            continue  # 非空即已消费，不进入待消费列表

        scope = data.get("scope")
        if not isinstance(scope, dict):
            print(
                f"[match_decisions WARN] {path}: scope 缺失或结构非法，跳过该记录",
                file=sys.stderr,
            )
            continue
        if scope.get("level") != level:
            continue  # typed scope：不同 level 互不干扰

        if level == "volume":
            if scope.get("volume_id") != volume:
                continue
        elif level == "unit":
            if scope.get("volume_id") != volume or scope.get("unit_id") != unit:
                continue
        else:  # level == "chapter"
            if scope.get("chapter_id") != chapter:
                continue
            if scope.get("volume_id") != volume:
                raise DataError(
                    f"{path}: scope.chapter_id={chapter!r} 命中，但 scope.volume_id="
                    f"{scope.get('volume_id')!r} 与传入 --volume={volume!r} 不一致"
                )

        decision_id = data.get("decision_id")
        if not decision_id:
            decision_id = path.stem
            print(
                f"[match_decisions WARN] {path}: decision_id 缺失，使用文件名 {decision_id!r}",
                file=sys.stderr,
            )
        entry = {"decision_id": decision_id}
        entry.update({k: v for k, v in data.items() if k != "decision_id"})
        hits.append(entry)

    result = {
        "level": level,
        "volume": volume,
        "unit": unit,
        "chapter": chapter,
        "count": len(hits),
        "decisions": hits,
    }
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


# ---------------------------------------------------------------------------
# consume：--by 值域校验 + 冻结资料/kind 配对校验 + 幂等回写 consumed_by
# ---------------------------------------------------------------------------


def _validate_by(by: str) -> str:
    """校验 --by artifact token 并返回其类别；不合规抛 UsageError。"""
    if by == BY_BIBLE_FROZEN:
        return "bible"
    if by == BY_PROFILE_GENRE:
        return "profile"
    if BY_WORLDBOOK_RE.fullmatch(by):
        return "worldbook"
    if BY_VOLUME_RE.fullmatch(by):
        return "volume"
    if BY_UNIT_RE.fullmatch(by):
        return "unit"
    if BY_CHAPTER_RE.fullmatch(by):
        return "chapter"
    raise UsageError(
        f"--by 值域不合规：{by!r}（仅接受 volume:V##｜unit:V##-U##｜chapter:C####｜"
        "bible:frozen｜profile:genre｜worldbook:<section_id>）"
    )


def do_consume(work_dir: Path, decision_id: str, by: str) -> int:
    if not DECISION_ID_RE.match(decision_id):
        raise UsageError(
            f"--decision 格式不合规：{decision_id!r}（须匹配 ^D-[A-Za-z0-9_-]+$）"
        )
    dec_path = work_dir / "series" / "decisions" / f"{decision_id}.yaml"
    data = load_yaml_or_none(dec_path)
    if data is None:
        raise UsageError(f"{dec_path} 不存在")

    by_kind = _validate_by(by)
    if by_kind in {"bible", "profile", "worldbook"} and data.get("kind") != "frozen_amendment":
        raise UsageError(
            f"--by={by} 仅 kind: frozen_amendment 决策可用，"
            f"{decision_id} 实为 kind={data.get('kind')!r}"
        )

    consumed_by = data.get("consumed_by") or []
    if by in consumed_by:
        print(
            f"[match_decisions WARN] {decision_id} 已含 consumed_by={by!r}，"
            "跳过重复写入", file=sys.stderr,
        )
        return 0

    consumed_by.append(by)
    data["consumed_by"] = consumed_by
    atomic_write_yaml(dec_path, data)
    print(f"[match_decisions] {decision_id} consumed_by += {by!r}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出 scope 命中且待消费的决策")
    p_list.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    p_list.add_argument("--level", required=True, choices=["volume", "unit", "chapter"])
    p_list.add_argument("--volume", required=True, help="卷号，如 V01")
    p_list.add_argument("--unit", default=None, help="卷内局部单元号；--level unit 时必填")
    p_list.add_argument("--chapter", default=None, help="裸章号；--level chapter 时必填")

    p_consume = sub.add_parser("consume", help="回写 consumed_by")
    p_consume.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    p_consume.add_argument("--decision", required=True, help="决策 ID，如 D-0001")
    p_consume.add_argument(
        "--by", required=True,
        help="volume:V##｜unit:V##-U##｜chapter:C####｜bible:frozen｜profile:genre｜worldbook:<section_id>",
    )

    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[match_decisions ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    try:
        if args.command == "list":
            return do_list(work_dir, args.level, args.volume, args.unit, args.chapter)
        if args.command == "consume":
            return do_consume(work_dir, args.decision, args.by)
    except UsageError as exc:
        print(f"[match_decisions ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[match_decisions ERROR] {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
