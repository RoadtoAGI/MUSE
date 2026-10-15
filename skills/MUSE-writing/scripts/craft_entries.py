#!/usr/bin/env python3
"""按锚点从本包 references 取条目（设计 §8.2）。

引用写作 `<技能目录>/references/<文件>.md#<锚点>`，路径相对本包 skills/。锚点两种：

- 标题锚点：任一级 Markdown 标题，文字去掉标点与空白后等于锚点，或标题括号里的英文 id 等于锚点
  （如“规划痕迹外泄（planning_trace_leakage）”）。条目是标题下直到同级或更高一级标题前的段落。
- 表格行锚点：表格首列含该锚点的一行，如 ai-cliche-patterns 的“narrator_self_corrects /
  emotion_naming_under_face_loss”。条目首段是第二列的完整说法，第三列按表头名称附在其后。

取条目按整段累加到字数上限，不截段落；首段本身超限时只取首段。标题下先引原典的条目，
取出时把第一段说法放在引文前。

用法::

    python3 craft_entries.py prose-craft/references/prose-rules.md#因果可恢复
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_shortform_contract import brief_units  # noqa: E402

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
ENTRY_CAP = 300
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Entry:
    ref: str
    title: str
    paragraphs: list[str]

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)

    @property
    def units(self) -> int:
        return brief_units(self.text)


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).casefold()


def _heading_matches(title: str, anchor: str) -> bool:
    if _norm(title) == _norm(anchor):
        return True
    ids = re.findall(r"[（(]([A-Za-z0-9_ /]+)[）)]", title)
    return any(_norm(anchor) == _norm(part) for chunk in ids for part in chunk.split("/"))


def _paragraphs(lines: list[str]) -> list[str]:
    paras: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.rstrip())
        elif current:
            paras.append("\n".join(current))
            current = []
    if current:
        paras.append("\n".join(current))
    return paras


def _from_heading(lines: list[str], anchor: str) -> tuple[str, list[str]] | None:
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if not m or not _heading_matches(m.group(2), anchor):
            continue
        level = len(m.group(1))
        body: list[str] = []
        for nxt in lines[i + 1:]:
            h = HEADING.match(nxt)
            if h and len(h.group(1)) <= level:
                break
            body.append(nxt)
        return m.group(2), _paragraphs(body)
    return None


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _from_table(lines: list[str], anchor: str) -> tuple[str, list[str]] | None:
    header: list[str] | None = None
    for line in lines:
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            header = cells
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        first = cells[0]
        names = [p.strip() for p in re.split(r"[/、,，]", first)]
        if _norm(anchor) in {_norm(n) for n in names} or _norm(first) == _norm(anchor):
            paras = [cells[1]] if len(cells) > 1 else []
            for name, value in zip(header[2:], cells[2:]):
                if value:
                    paras.append(f"{name}：{value}")
            return first, paras
    return None


def resolve(ref: str, *, cap: int = ENTRY_CAP, skills_root: Path = SKILLS_ROOT) -> Entry:
    """取一个条目；找不到文件或锚点时抛 KeyError。"""
    path_part, _, anchor = ref.partition("#")
    path = skills_root / path_part
    if not anchor or not path.is_file():
        raise KeyError(f"条目引用无效：{ref}")
    lines = path.read_text(encoding="utf-8").splitlines()
    found = _from_heading(lines, anchor) or _from_table(lines, anchor)
    if found is None or not found[1]:
        raise KeyError(f"锚点不存在或下面没有正文：{ref}")
    title, paras = found
    # 标题下先引原典再给说法的条目（如“潜文本的适用条件”），取条目时把说法放到首段，引文随后
    lead = next((i for i, p in enumerate(paras) if not p.startswith(">")), 0)
    paras = paras[lead:lead + 1] + paras[:lead] + paras[lead + 1:]
    kept: list[str] = []
    for para in paras:
        if kept and brief_units("\n\n".join(kept + [para])) > cap:
            break
        kept.append(para)
    return Entry(ref=ref, title=title, paragraphs=kept)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("用法: craft_entries.py <技能目录/references/文件.md#锚点>", file=sys.stderr)
        return 2
    try:
        entry = resolve(args[0])
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"## {entry.title}（{entry.units} 字）\n\n{entry.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
