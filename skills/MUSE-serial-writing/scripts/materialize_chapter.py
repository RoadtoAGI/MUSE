#!/usr/bin/env python3
"""materialize_chapter.py — 物化：卷纲条目 → 章 workspace

从 `series/volumes/V0N.yaml` 的 `chapters[]` 一条卷纲条目展开出一个章
workspace（`chapters/V0N/C####/`），供后续 writer/reviser mini-run 消费。

动作序列：
    1. 校验卷纲条目存在且 `status: outline`；`prev_chapter` 推导——卷内非
       首项取该条目在列表中的前一项 chapter_id；卷内首项（idx==0）取**上
       一卷**（按卷号数字序，V01<V02<...）卷纲 `chapters[]` 列表**末项**
       chapter_id，仅当不存在上一卷（全作品第一章）才为 null——prev 链跨
       卷连续。`prev_chapter` 非 null 时校验前章 `recap.yaml` 已产出（前章
       可能在其他卷——按全部卷纲反查其卷号）；缺且已有该章工作区 → 阻断（exit 2），不建任何目录。接管章无历史
       工作区、但 manifest 登记原文存在时，使用发布原文与卷纲摘要。
    2. 建 `pipeline/{scenes,characters,staging,references,review/lint,audit}`
       骨架（目录段名保 hooks 触发契约）；确保系列级 `series/character-skills/`
       存在并创建符号链接 `pipeline/story-character-skills` 指向它（章 mini-run
       内单篇相对路径契约由链接兑现）。系列根目录已有
       `pipeline/inspiration_ledger.yaml` 时，同步链接到章内同名路径，
       供 Phase 5 沿用已有的参考账本契约。
    3. 从卷纲条目展开 `chapter_card.yaml`：chapter_id/prev_chapter/next_chapter
       走链式填充；`hook.type` 预填卷纲 `hook_type`，`hook.design` 留 null
       待编排展开；`recap_inputs.threads` 预填卷纲条目 `opened`+`closed`
       （去重），`characters`/`locations`/`items`/`worldbook_sections` 与 `pov`
       留空；编排前按本章意图选材填写后重跑 assemble_serial_context.py，
       编排中改变人物与实体范围后刷新（重装配义务，
       见 workspace-schema 章卡一节）。
    4. `prev_chapter` 存在 → 子进程调 extract_draft_tail.py 章级模式，从前章
       `draft.md`（接管历史章用 manifest 定位的发布原文）产 `pipeline/prev_chapter_tail.md`。
    5. 子进程调 assemble_serial_context.py 产初始通用 `pipeline/serial_context.md`；
       人物与实体材料在上述选材后进入该文件。
    6. 回写前章 `chapter_card.yaml` 的 `next_chapter` 为本章号（原子写；前章
       `chapter_card.yaml` 不存在 → stderr WARN 并跳过回写，不写残缺卡）；
       卷纲条目 `status` 转 `drafted` 由发布/审阅环节负责，本脚本不动。

用法：
    python3 materialize_chapter.py --work-dir <works/<slug>/ 工作区根> \
        --volume V01 --chapter C0001

失败语义：
    0 — 完成，stdout 末行（且唯一一行）= 章 workspace 绝对路径
    1 — 数据错：既有 YAML 解析失败 / 子进程数据错传导
    2 — 阻断：--work-dir 不存在 / --volume、--chapter 格式非法 / 卷纲条目不存在
        或 status 非 outline / 前章 recap 未产出

本脚本不调 LLM（纯机械字段展开 + 目录骨架 + 子进程编排）。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

VOL_RE = re.compile(r"^V\d+$")
CHAPTER_RE = re.compile(r"^C\d{4}$")

# 章 workspace 骨架（去掉 derivative
# 专属子目录），"pipeline/scenes" 目录段名是场景类 hook 触发契约，不可改名。
SUBDIRS = [
    "pipeline/scenes",
    "pipeline/characters",
    "pipeline/staging",
    "pipeline/references",
    "pipeline/review/lint",
    "pipeline/audit",
]


class BlockingError(Exception):
    """阻断性前置条件不满足：卷纲/参数非法、前章 recap 未产出。"""


class DataError(Exception):
    """既有 YAML 内容解析失败。"""


class SubprocessError(Exception):
    """前序脚本（extract_draft_tail / assemble_serial_context）子进程失败。"""

    def __init__(self, label: str, returncode: int, output: str):
        super().__init__(f"{label} 子进程失败（exit {returncode}）：{output.strip()}")
        self.returncode = returncode


# ---------------------------------------------------------------------------
# 通用 IO（自含，不跨脚本 import，保持子进程调用式解耦）
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


def atomic_write_yaml(path: Path, data: dict) -> None:
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


def find_chapter_volume(work_dir: Path, chapter_id: str) -> str | None:
    """扫描 series/volumes/*.yaml 反查 chapter_id 所属卷号（前章可能不在
    当前 --volume 指定的卷内，需要按全部卷纲反查）。"""
    volumes_dir = work_dir / "series" / "volumes"
    if not volumes_dir.is_dir():
        return None
    for vol_path in sorted(volumes_dir.glob("V*.yaml")):
        data = load_yaml_or_none(vol_path) or {}
        vol_id = data.get("volume_id") or vol_path.stem
        for entry in data.get("chapters") or []:
            if isinstance(entry, dict) and entry.get("chapter_id") == chapter_id:
                return vol_id
    return None


def _volume_number(vol_id: str) -> int | None:
    m = re.match(r"^V(\d+)$", vol_id)
    return int(m.group(1)) if m else None


def find_prev_volume_last_chapter(work_dir: Path, volume_id: str) -> str | None:
    """跨卷 prev_chapter 推导：卷内首项（idx==0）时，取按卷号数字序
    （V01<V02<...）紧邻的上一卷卷纲 `chapters[]` 列表末项 chapter_id。
    不存在上一卷（全作品第一章）或上一卷卷纲 `chapters[]` 为空 → None。"""
    volumes_dir = work_dir / "series" / "volumes"
    if not volumes_dir.is_dir():
        return None
    current_num = _volume_number(volume_id)
    if current_num is None:
        return None
    best_num = None
    best_path = None
    for vol_path in volumes_dir.glob("V*.yaml"):
        num = _volume_number(vol_path.stem)
        if num is None or num >= current_num:
            continue
        if best_num is None or num > best_num:
            best_num, best_path = num, vol_path
    if best_path is None:
        return None
    data = load_yaml_or_none(best_path) or {}
    prev_chapters = data.get("chapters") or []
    if not prev_chapters or not isinstance(prev_chapters[-1], dict):
        return None
    return prev_chapters[-1].get("chapter_id")


def run_subprocess(cmd: list[str], label: str) -> None:
    """跑前序脚本子进程；其自身 stdout/stderr 一律转发到本脚本 stderr（保持
    本脚本 stdout 只有末行章路径这一条契约）。失败抛 SubprocessError 携带
    子进程原始退出码，供 main() 透传。"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    for stream in (result.stdout, result.stderr):
        if stream:
            sys.stderr.write(stream if stream.endswith("\n") else stream + "\n")
    if result.returncode != 0:
        raise SubprocessError(label, result.returncode, result.stderr or result.stdout)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run(work_dir: Path, volume_id: str, chapter_id: str, script_dir: Path) -> Path:
    volume_path = work_dir / "series" / "volumes" / f"{volume_id}.yaml"
    if not volume_path.is_file():
        raise BlockingError(f"卷纲文件不存在: {volume_path}")

    volume_data = load_yaml_or_none(volume_path) or {}
    chapters = volume_data.get("chapters") or []

    idx = None
    entry = None
    for i, e in enumerate(chapters):
        if isinstance(e, dict) and e.get("chapter_id") == chapter_id:
            idx, entry = i, e
            break
    if entry is None:
        raise BlockingError(
            f"卷纲条目不存在：{chapter_id} 未出现在 {volume_path} 的 chapters[] 列表中"
        )
    if entry.get("status") != "outline":
        raise BlockingError(
            f"卷纲条目 {chapter_id} 的 status={entry.get('status')!r}，物化要求 status: outline"
        )

    if idx > 0:
        prev_chapter = chapters[idx - 1].get("chapter_id")
    else:
        prev_chapter = find_prev_volume_last_chapter(work_dir, volume_id)

    # ---- 前章 recap gate（阻断性前置，§6.3）----
    prev_vol = None
    prev_published = None
    if prev_chapter is not None:
        prev_vol = find_chapter_volume(work_dir, prev_chapter)
        if prev_vol is None:
            raise BlockingError(
                f"前章 recap 未产出：前章 {prev_chapter} 未出现在任何 "
                f"series/volumes/*.yaml，无法反查其所属卷以定位 recap.yaml"
            )
        prev_recap_path = work_dir / "chapters" / prev_vol / prev_chapter / "recap.yaml"
        if not prev_recap_path.is_file() and not prev_recap_path.parent.exists():
            manifest = load_yaml_or_none(work_dir / "published" / "manifest.yaml") or {}
            matches = [e for e in manifest.get("entries") or []
                       if isinstance(e, dict) and e.get("chapter_id") == prev_chapter]
            if len(matches) == 1:
                source = work_dir / "published" / (matches[0].get("file") or "")
                if source.is_file():
                    prev_published = source
        if not prev_recap_path.is_file() and prev_published is None:
            raise BlockingError(
                f"前章 recap 未产出：{prev_recap_path} 不存在，阻断 {chapter_id} 物化"
            )

    # ---- 建章 workspace 骨架 ----
    chapter_dir = work_dir / "chapters" / volume_id / chapter_id
    is_new_work = not chapter_dir.exists()
    for sub in SUBDIRS:
        (chapter_dir / sub).mkdir(parents=True, exist_ok=True)
    if is_new_work and os.environ.get("MUSE_NEW_WORK_TEMPLATE"):
        from muse_runtime.bootstrap import initialize_new_work
        initialize_new_work(chapter_dir)

    # ---- 角色 runtime skill 包：系列级家目录 + 章内符号链接 ----
    series_char_skills = work_dir / "series" / "character-skills"
    series_char_skills.mkdir(parents=True, exist_ok=True)
    link_path = chapter_dir / "pipeline" / "story-character-skills"
    if not link_path.exists() and not link_path.is_symlink():
        link_path.symlink_to(
            os.path.relpath(series_char_skills, link_path.parent),
            target_is_directory=True,
        )

    # ---- 系列级 inspiration ledger：章内沿用 Phase 5 的 sibling 读取路径 ----
    series_ledger = work_dir / "pipeline" / "inspiration_ledger.yaml"
    chapter_ledger = chapter_dir / "pipeline" / "inspiration_ledger.yaml"
    if series_ledger.is_file() and not chapter_ledger.exists() and not chapter_ledger.is_symlink():
        chapter_ledger.symlink_to(os.path.relpath(series_ledger, chapter_ledger.parent))

    # ---- 生成 chapter_card.yaml ----
    threads = list(dict.fromkeys((entry.get("opened") or []) + (entry.get("closed") or [])))
    chapter_card = {
        "schema_version": 1,
        "chapter_id": chapter_id,
        "prev_chapter": prev_chapter,
        "next_chapter": None,
        "pov": None,
        "hook": {
            "type": entry.get("hook_type"),
            "design": None,
        },
        "recap_inputs": {
            "characters": [],
            "locations": [],
            "items": [],
            "threads": threads,
            "worldbook_sections": [],
        },
    }
    atomic_write_yaml(chapter_dir / "chapter_card.yaml", chapter_card)

    # ---- 前章尾窗（子进程调 extract_draft_tail 章级模式）----
    if prev_chapter is not None:
        prev_draft = prev_published or work_dir / "chapters" / prev_vol / prev_chapter / "draft.md"
        prev_tail_output = chapter_dir / "pipeline" / "prev_chapter_tail.md"
        run_subprocess(
            [
                sys.executable, str(script_dir / "extract_draft_tail.py"),
                "--chapter-file", str(prev_draft),
                "--output", str(prev_tail_output),
            ],
            "extract_draft_tail",
        )

    # ---- 初始作者侧上下文（人物与实体选材后由编排入口刷新）----
    run_subprocess(
        [
            sys.executable, str(script_dir / "assemble_serial_context.py"),
            "--work-dir", str(work_dir),
            "--chapter", chapter_id,
        ],
        "assemble_serial_context",
    )

    # ---- 回写前章 chapter_card.yaml 的 next_chapter ----
    if prev_chapter is not None:
        prev_card_path = work_dir / "chapters" / prev_vol / prev_chapter / "chapter_card.yaml"
        if not prev_card_path.is_file():
            print(
                f"[materialize_chapter WARN] 前章 chapter_card 不存在，跳过 "
                f"next_chapter 回写: {prev_card_path}",
                file=sys.stderr,
            )
        else:
            prev_card = load_yaml_or_none(prev_card_path) or {}
            prev_card["next_chapter"] = chapter_id
            atomic_write_yaml(prev_card_path, prev_card)

    return chapter_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    parser.add_argument("--volume", required=True, help="卷号，如 V01")
    parser.add_argument("--chapter", required=True, help="裸章号，如 C0001")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[materialize_chapter ERROR] --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    if not VOL_RE.match(args.volume):
        print(f"[materialize_chapter ERROR] --volume 必须匹配 V\\d+，实为 {args.volume!r}", file=sys.stderr)
        return 2

    if not CHAPTER_RE.match(args.chapter):
        print(f"[materialize_chapter ERROR] --chapter 必须匹配 C\\d{{4}}，实为 {args.chapter!r}", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent

    try:
        chapter_dir = run(work_dir, args.volume, args.chapter, script_dir)
    except BlockingError as exc:
        print(f"[materialize_chapter ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[materialize_chapter ERROR] {exc}", file=sys.stderr)
        return 1
    except SubprocessError as exc:
        print(f"[materialize_chapter ERROR] {exc}", file=sys.stderr)
        return exc.returncode if exc.returncode in (1, 2) else 1

    print(f"[materialize_chapter] chapter workspace: {chapter_dir}", file=sys.stderr)
    print(chapter_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
