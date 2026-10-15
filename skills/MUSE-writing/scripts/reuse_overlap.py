#!/usr/bin/env python3
"""正文与范文的连续重合检查（设计 §10.2）。

口径沿 2026-07-10 复用对照试验：中文去掉标点与空白后比较连续字串，英文按小写词序列比较。
两项上限：最长公共子串 ≤ 12 字（英文 12 词），长度 ≥ 10 的共同片段覆盖正文 ≤ 1%。
专名（--allow）先遮蔽再比较，人物名、地名不算抄写。只设上限，不要求复用。

范文文件含 `<exemplar_window ...>` 块时只比较块内原文（写作简报与 kb_query --render exemplar
的输出都是这种格式），否则比较整个文件。

用法::

    python3 reuse_overlap.py --draft story.md --exemplar pipeline/shortform/writer_brief.md \
        --allow 许诚 --allow 废城

退出码：0 未超限；1 超限；2 输入错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_COMMON_RUN = 12
FRAGMENT_MIN = 10
MAX_FRAGMENT_COVERAGE = 0.01

WINDOW_RE = re.compile(r"<exemplar_window\b[^>]*>\n?(.*?)</exemplar_window>", re.S)
HAN = re.compile(r"[㐀-鿿豈-﫿]")
EN_WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
DRAFT_MASK, EXEMPLAR_MASK = "\x01", "\x02"  # 遮蔽专名用的两种占位，彼此不相等，不会凑成重合


@dataclass
class Overlap:
    unit: str                    # "字" 或 "词"
    draft_units: int
    longest: int = 0
    coverage: float = 0.0
    spans: list[dict] = field(default_factory=list)   # 超过上限的连续重合

    @property
    def violated(self) -> bool:
        return self.longest > MAX_COMMON_RUN or self.coverage > MAX_FRAGMENT_COVERAGE


def exemplar_text(raw: str) -> str:
    windows = WINDOW_RE.findall(raw)
    return "\n".join(windows) if windows else raw


def is_english(text: str) -> bool:
    return len(EN_WORD.findall(text)) > len(HAN.findall(text))


def _mask(text: str, allow: list[str], token: str) -> str:
    for term in sorted({t for t in allow if t and t.strip()}, key=len, reverse=True):
        text = text.replace(term, token)
    return text


def _tokens(text: str, english: bool) -> tuple[list[str], list[int]]:
    """返回 (比较单位序列, 每个单位所在的原文行号)。中文按字，英文按小写词；标点与空白丢弃。"""
    units: list[str] = []
    lines: list[int] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if english:
            for m in re.finditer(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?|[\x01\x02]", line):
                units.append(m.group(0).lower())
                lines.append(line_no)
        else:
            for ch in line:
                if ch.isalnum() or ch in (DRAFT_MASK, EXEMPLAR_MASK):
                    units.append(ch)
                    lines.append(line_no)
    return units, lines


def measure(draft: str, exemplar: str, allow: list[str] | None = None) -> Overlap:
    allow = allow or []
    english = is_english(draft)
    d_units, d_lines = _tokens(_mask(draft, allow, DRAFT_MASK), english)
    e_units, _ = _tokens(_mask(exemplar, allow, EXEMPLAR_MASK), english)
    result = Overlap(unit="词" if english else "字", draft_units=len(d_units))
    if not d_units or len(e_units) < FRAGMENT_MIN:
        return result

    sep = " " if english else ""
    e_joined = sep + sep.join(e_units) + sep if english else "".join(e_units)
    seeds = {tuple(e_units[i:i + FRAGMENT_MIN]) for i in range(len(e_units) - FRAGMENT_MIN + 1)}

    def occurs(start: int, length: int) -> bool:
        piece = d_units[start:start + length]
        if english:
            return (" " + " ".join(piece) + " ") in e_joined
        return "".join(piece) in e_joined

    covered = [False] * len(d_units)
    last_end = 0  # 上一段最长重合的结束位置；其内部位置的重合必然更短或同终点
    for i in range(len(d_units) - FRAGMENT_MIN + 1):
        if tuple(d_units[i:i + FRAGMENT_MIN]) not in seeds:
            continue
        length = max(FRAGMENT_MIN, last_end - i)
        while i + length < len(d_units) and occurs(i, length + 1):
            length += 1
        for k in range(i, i + length):
            covered[k] = True
        result.longest = max(result.longest, length)
        if length > MAX_COMMON_RUN and i + length > last_end:
            result.spans.append({
                "length": length,
                "line": d_lines[i],
                "text": sep.join(d_units[i:i + length]),
            })
        last_end = max(last_end, i + length)
    result.coverage = round(sum(covered) / len(d_units), 4)
    return result


def report_lines(result: Overlap, draft_name: str) -> list[str]:
    lines = [
        f"最长连续重合 {result.longest} {result.unit}（上限 {MAX_COMMON_RUN}）；"
        f"≥{FRAGMENT_MIN}{result.unit}的共同片段覆盖正文 {result.coverage:.2%}（上限 {MAX_FRAGMENT_COVERAGE:.0%}）"
    ]
    for span in result.spans[:10]:
        lines.append(f"{draft_name}:{span['line']}: 与范文连续重合 {span['length']} {result.unit}：{span['text']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="正文与范文的连续重合检查")
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--exemplar", required=True, type=Path, action="append",
                        help="范文文件，可重复；含 <exemplar_window> 块时只比较块内原文")
    parser.add_argument("--allow", action="append", default=[], help="不计重合的专名，可重复")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        draft = args.draft.read_text(encoding="utf-8")
        exemplar = "\n".join(exemplar_text(p.read_text(encoding="utf-8")) for p in args.exemplar)
    except OSError as exc:
        print(f"[reuse-overlap] 读取失败: {exc}", file=sys.stderr)
        return 2
    result = measure(draft, exemplar, args.allow)
    if args.json:
        print(json.dumps({"unit": result.unit, "draft_units": result.draft_units, "longest": result.longest,
                          "coverage": result.coverage, "violated": result.violated, "spans": result.spans},
                         ensure_ascii=False, indent=2))
    else:
        print("\n".join(report_lines(result, args.draft.name)))
    return 1 if result.violated else 0


if __name__ == "__main__":
    raise SystemExit(main())
