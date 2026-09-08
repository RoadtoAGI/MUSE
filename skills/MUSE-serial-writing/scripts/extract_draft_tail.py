#!/usr/bin/env python3
"""
extract_draft_tail.py — 从场景或前章提取尾部 ~100 字

场景模式（--scene-id + --work-dir）：
    从 pipeline/scenes/scene_{id}.md 提取尾窗，写入 pipeline/scene_{id}/draft_tail.md

章级模式（--chapter-file + --output）：
    从给定前章 draft.md 全文提取尾窗，写到指定输出路径

按中文句末标点（。！？"'）做边界，不切半句；若 100 字内无句末标点则放宽到
完整末段（通常 ≤ 200 字）。

用法：
    python3 extract_draft_tail.py --scene-id S01 --work-dir <含 pipeline/ 的章工作区根目录>
    python3 extract_draft_tail.py --chapter-file <path> --output <path>

失败：
    - 文件不存在 → stderr + exit 1
    - 模式参数错（同时给两模式 / 都不给）→ exit 2

本脚本不调 LLM（纯文本截断）。
"""

import argparse
import sys
import tempfile
from pathlib import Path


# 中文句末标点（含中英文）
SENTENCE_END = set("。！？!?…")

TARGET_MIN = 80
TARGET_MAX = 150
HARD_CAP = 250


def count_chars(text: str) -> int:
    """与 writer 的"字数"语义对齐：中文按字 + 英文按词，简化为 len()。
    tail 截断只需字符计数作粗估，不求精确——writer 不读 tail_length 作决策。"""
    return len(text)


def extract_tail(draft_text: str) -> str:
    """从尾部倒扫找合适的截断边界。

    策略：
    1. 从末尾向前数字符，找到至少 TARGET_MIN 字 + 句末标点结束的窗口
    2. 窗口长度尽量落在 [TARGET_MIN, TARGET_MAX]；超 TARGET_MAX 时放宽到 HARD_CAP
    3. 找不到句末标点则直接给末尾 TARGET_MAX 字（writer 能处理段中断）
    """
    text = draft_text.rstrip()
    if not text:
        return ""

    n = len(text)
    if n <= TARGET_MAX:
        return text

    # 向前扫描找句末标点
    # 先在 [n - TARGET_MAX, n - TARGET_MIN] 区间找最后一个句末
    lo = max(0, n - HARD_CAP)
    # 优先在 [n - TARGET_MAX, n] 找
    best_cut: int | None = None
    for i in range(n - 1, max(lo, n - TARGET_MAX) - 1, -1):
        if text[i] in SENTENCE_END:
            # 切到 i+1（含标点）
            candidate_len = n - (i + 1)
            if TARGET_MIN <= candidate_len:
                best_cut = i + 1
                break

    # 若第一轮没找到，在 [n - HARD_CAP, n - TARGET_MAX] 继续找（放宽窗口）
    if best_cut is None:
        for i in range(n - 1 - TARGET_MAX, lo - 1, -1):
            if text[i] in SENTENCE_END:
                best_cut = i + 1
                break

    if best_cut is not None:
        return text[best_cut:].lstrip()

    # 最后兜底：从尾截 TARGET_MAX 字
    return text[-TARGET_MAX:].lstrip()


def atomic_write(path: Path, content: str) -> None:
    """内容相同则保留旧文件不刷 mtime；不同才原子写。

    幂等性保护下游 writer audit：184 实战中 PATCH 后重抽 tail 只刷 mtime
    不变内容会让前序场景 audit 物理校验 fail（mtime > dispatch_at）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                return
        except OSError:
            pass
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "",
    )

    parser.add_argument("--scene-id", help="e.g. S01 (scene mode)")
    parser.add_argument("--work-dir", type=Path, help="章工作区根目录，其下含 pipeline/ (scene mode)")
    parser.add_argument("--chapter-file", type=Path, help="前章 draft.md 路径 (chapter mode)")
    parser.add_argument("--output", type=Path, help="输出路径 (chapter mode)")

    args = parser.parse_args()

    # 验证互斥性：需要恰好一种模式
    scene_mode_specified = args.scene_id is not None or args.work_dir is not None
    chapter_mode_specified = args.chapter_file is not None or args.output is not None

    if scene_mode_specified and chapter_mode_specified:
        print("[extract_draft_tail] ERROR: cannot mix --scene-id/--work-dir with --chapter-file/--output",
              file=sys.stderr)
        return 2

    if not scene_mode_specified and not chapter_mode_specified:
        print("[extract_draft_tail] ERROR: must specify either (--scene-id + --work-dir) or (--chapter-file + --output)",
              file=sys.stderr)
        return 2

    # 验证场景模式参数完整性
    if scene_mode_specified:
        if args.scene_id is None or args.work_dir is None:
            print("[extract_draft_tail] ERROR: scene mode requires both --scene-id and --work-dir",
                  file=sys.stderr)
            return 2
        return handle_scene_mode(args.scene_id, args.work_dir)

    # 验证章级模式参数完整性
    if chapter_mode_specified:
        if args.chapter_file is None or args.output is None:
            print("[extract_draft_tail] ERROR: chapter mode requires both --chapter-file and --output",
                  file=sys.stderr)
            return 2
        return handle_chapter_mode(args.chapter_file, args.output)

    return 2


def handle_scene_mode(scene_id: str, work_dir: Path) -> int:
    """处理场景模式（既有行为）"""
    work_dir = work_dir.resolve()
    scene_dir = work_dir / "pipeline" / f"scene_{scene_id}"
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    tail_path = scene_dir / "draft_tail.md"

    if not scene_path.exists():
        print(f"[extract_draft_tail] ERROR: {scene_path} not found", file=sys.stderr)
        return 1

    draft_text = scene_path.read_text(encoding="utf-8")
    tail = extract_tail(draft_text)

    if not tail:
        print(f"[extract_draft_tail] WARNING: {scene_path} empty; writing empty tail",
              file=sys.stderr)

    atomic_write(tail_path, tail)
    print(f"✅ draft_tail written: {tail_path} ({count_chars(tail)} chars)")
    return 0


def handle_chapter_mode(chapter_file: Path, output: Path) -> int:
    """处理章级模式"""
    chapter_file = chapter_file.resolve()
    output = output.resolve()

    if not chapter_file.exists():
        print(f"[extract_draft_tail] ERROR: {chapter_file} not found", file=sys.stderr)
        return 1

    draft_text = chapter_file.read_text(encoding="utf-8")
    tail = extract_tail(draft_text)

    if not tail:
        print(f"[extract_draft_tail] WARNING: {chapter_file} empty; writing empty tail",
              file=sys.stderr)

    atomic_write(output, tail)
    print(f"✅ draft_tail written: {output} ({count_chars(tail)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
