#!/usr/bin/env python3
"""
extract_draft_tail.py — 从某场景已产的 pipeline/scenes/scene_{id}.md 提取尾部 ~100 字
写入同场景元数据目录的 draft_tail.md，供下一场景 writer 消费衔接。

按中文句末标点（。！？"'）做边界，不切半句；若 100 字内无句末标点则放宽到
完整末段（通常 ≤ 200 字）。

用法：
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_draft_tail.py --scene-id S01 --work-dir <含 pipeline/ 的 run 根目录>

输入：
    {work_dir}/pipeline/scenes/scene_{scene_id}.md（单路径协议；2026-05-18 plan 起）

输出：
    {work_dir}/pipeline/scene_{scene_id}/draft_tail.md（场景元数据目录，与 scene_card / role_views 同组）

失败：
    - scene_{scene_id}.md 不存在 → stderr + exit 1

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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--scene-id", required=True, help="e.g. S01")
    parser.add_argument("--work-dir", required=True, type=Path, help="run 根目录（其下含 pipeline/）")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    scene_dir = work_dir / "pipeline" / f"scene_{args.scene_id}"
    # 输入：pipeline/scenes/scene_{id}.md（单路径协议）
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{args.scene_id}.md"
    # 输出：场景元数据目录，与 scene_card / role_views 同组
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


if __name__ == "__main__":
    sys.exit(main())
