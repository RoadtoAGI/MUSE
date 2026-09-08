#!/usr/bin/env python3
r"""split_chapters.py — 连载原文 → 章节切分 + published/manifest.yaml 落盘

按章节标题正则把整本原文（单文件或目录）切成逐章 markdown，产出出口 B 交付根下的
`published/` 层：

  <out>/published/V0NC####.md   —— 每章一文件，内容 = 标题行 + 该章正文
  <out>/published/manifest.yaml —— {schema_version: 1, entries: [...], revisions: []}
                                    entries 字段形态与 muse-serial-writing 的
                                    publish_chapter.py 产出对齐：
                                    {chapter_id, file, published_seq, ts}

默认识别第×章/回、Chapter、序章/楔子/引子，允许前置 Markdown 标记。
普通 Markdown 小标题不分章；其他作品标题形式用 --pattern 明确指定。
目录按文件名自然序（2 在 10 前）读取，实际卷序须由调用方确认。

章序号只按文本序分配（C0001 起），与标题里的中文数字/阿拉伯数字无关——标题只是
切分锚，不解析数字。文首标题前若有非空前言文本，不独立成章，并入第一章文件的
标题行之前；stdout 打印一行 WARN 提示。

卷边界默认单卷 V01；`--volume-breaks C0003,C0007` 显式指定各卷（V02 起）的首章
chapter_id，逗号分隔、必须严格递增、必须落在实际章号范围内。

用法：
    python3 split_chapters.py --input <文本文件或目录> --out <交付根>
    python3 split_chapters.py --input raw.md --out works/demo --volume-breaks C0003,C0007
    python3 split_chapters.py --input raw.md --out works/demo --pattern '^Chapter \d+'
    python3 split_chapters.py --input works/demo --out works/demo --force

退出码：
    0 — 成功
    1 — 数据错：--input 不存在 / 无章可切（未匹配到任何标题）/
        --out 下 published/ 已有产物且未加 --force
    2 — 用法错：CLI 参数缺失或格式非法（argparse 内置）、--pattern 正则语法错、
        --volume-breaks 条目格式非法 / 越界 / 非严格递增
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

CHAPTER_ID_RE = re.compile(r"^C\d{4}$")

DEFAULT_PATTERNS = [
    r"^(?:#+\s*)?第[零〇一二两三四五六七八九十百千0-9]+[章回]",
    r"^(?:#+\s*)?Chapter\s+\d+",
    r"^(?:#+\s*)?(?:序章|楔子|引子)(?:\s|[:：]|$)",
]


class UsageError(Exception):
    """CLI 参数 / 用法问题：exit 2。"""


class DataError(Exception):
    """输入数据问题（不存在 / 无章可切 / 已有产物未加 --force）：exit 1。"""


# ---------------------------------------------------------------------------
# 通用 IO（自含，风格仿 muse-serial-writing/scripts/publish_chapter.py，不跨脚本 import）
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


# ---------------------------------------------------------------------------
# 输入读取
# ---------------------------------------------------------------------------


def read_input_text(input_path: Path) -> str:
    if input_path.is_dir():
        files = sorted(
            (p for p in input_path.iterdir()
             if p.is_file() and p.suffix.lower() in (".md", ".txt")),
            key=lambda p: [(0, int(part)) if part.isdigit() else (1, part.lower())
                           for part in re.split(r"(\d+)", p.name)],
        )
        if not files:
            raise DataError(f"--input 目录下无 .md/.txt 文件: {input_path}")
        parts = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            if not text.endswith("\n"):
                text += "\n"
            parts.append(text)
        return "".join(parts)
    return input_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 切分
# ---------------------------------------------------------------------------


def compile_title_matcher(pattern_override: str | None) -> re.Pattern:
    if pattern_override:
        try:
            return re.compile(pattern_override)
        except re.error as exc:
            raise UsageError(f"--pattern 非法正则: {exc}") from exc
    return re.compile("|".join(f"(?:{p})" for p in DEFAULT_PATTERNS))


def split_into_chapters(text: str, matcher: re.Pattern) -> tuple[list[str], bool]:
    """返回 (chapters, has_preface)。chapters[i] 为第 i+1 章完整文本（含标题行；
    第 0 章若有前言，前言原样并入其标题行之前）。"""
    lines = text.splitlines()
    title_indices = [i for i, line in enumerate(lines) if matcher.match(line)]
    if not title_indices:
        raise DataError("--input 未匹配到任何章节标题，无章可切")

    has_preface = any(line.strip() for line in lines[: title_indices[0]])

    chapters: list[str] = []
    for idx, start in enumerate(title_indices):
        end = title_indices[idx + 1] if idx + 1 < len(title_indices) else len(lines)
        chunk = lines[start:end]
        if idx == 0 and has_preface:
            chunk = lines[:start] + chunk
        content = "\n".join(chunk)
        if not content.endswith("\n"):
            content += "\n"
        chapters.append(content)
    return chapters, has_preface


# ---------------------------------------------------------------------------
# 卷边界
# ---------------------------------------------------------------------------


def parse_volume_breaks(raw: str | None, total_chapters: int) -> list[int]:
    """返回排序后的卷起始章号（int）；空/None → 单卷（[]）。"""
    if not raw:
        return []
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    nums = []
    for cid in ids:
        if not CHAPTER_ID_RE.match(cid):
            raise UsageError(f"--volume-breaks 条目格式非法（须 C####): {cid!r}")
        n = int(cid[1:])
        if n < 2 or n > total_chapters:
            raise UsageError(
                f"--volume-breaks 条目 {cid} 超出实际章号范围（实际章数={total_chapters}）"
            )
        nums.append(n)
    if nums != sorted(nums) or len(set(nums)) != len(nums):
        raise UsageError(f"--volume-breaks 必须严格递增且不重复: {raw!r}")
    return nums


def volume_for(chapter_num: int, breaks: list[int]) -> int:
    return 1 + sum(1 for b in breaks if b <= chapter_num)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    input_path: Path = args.input
    if not input_path.exists():
        raise DataError(f"--input 不存在: {input_path}")

    text = read_input_text(input_path)
    matcher = compile_title_matcher(args.pattern)
    chapters, has_preface = split_into_chapters(text, matcher)

    breaks = parse_volume_breaks(args.volume_breaks, len(chapters))

    out_root: Path = args.out
    published_dir = out_root / "published"
    if published_dir.exists() and any(published_dir.iterdir()):
        if not args.force:
            raise DataError(
                f"{published_dir} 已有产物，默认拒绝覆盖；如需重建请加 --force"
            )
        shutil.rmtree(published_dir)

    ts = datetime.now().isoformat(timespec="seconds")
    entries = []
    for i, content in enumerate(chapters, start=1):
        chapter_id = f"C{i:04d}"
        volume_id = f"V{volume_for(i, breaks):02d}"
        file_name = f"{volume_id}{chapter_id}.md"
        atomic_write_text(published_dir / file_name, content)
        entries.append({
            "chapter_id": chapter_id,
            "file": file_name,
            "published_seq": i,
            "ts": ts,
        })

    manifest = {"schema_version": 1, "entries": entries, "revisions": []}
    atomic_write_yaml(published_dir / "manifest.yaml", manifest)

    if has_preface:
        print(
            f"[split_chapters WARN] 文首前言文本未独立成章，已并入 {entries[0]['file']} 标题行之前"
        )

    volumes_count = 1 + len(breaks)
    print(f"chapters={len(chapters)} volumes={volumes_count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, type=Path, help="文本文件或目录（目录时按文件名字典序拼接 .md/.txt）")
    parser.add_argument("--out", required=True, type=Path, help="交付根目录（产出落 <out>/published/）")
    parser.add_argument("--pattern", default=None, help="覆盖默认三族标题正则，改用单一正则")
    parser.add_argument("--volume-breaks", default=None, help="逗号分隔的各卷（V02 起）首章 chapter_id，如 C0003,C0007")
    parser.add_argument("--force", action="store_true", help="--out/published 已有产物时清空重建")
    args = parser.parse_args()

    try:
        return run(args)
    except UsageError as exc:
        print(f"[split_chapters ERROR] {exc}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"[split_chapters ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
