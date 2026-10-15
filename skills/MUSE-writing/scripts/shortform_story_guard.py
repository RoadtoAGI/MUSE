#!/usr/bin/env python3
"""短篇正文写入后的守卫（设计 §3.6、§6、§10.2），由 hooks/check-design-token-leak.sh 分派。

只检查短链正文：工作目录根部的 story.md，且同目录有 pipeline/shortform/conception.yaml。
两项，任一不满足 exit 2 并逐条给出位置，写作者在同一会话修改：

1. 格式：无 YAML frontmatter、无 HTML 注释。
2. 设计用词泄漏：大纲与构想字段名、设计标记、排练标题、场景卡投影标签、灵感账 ID、YAML 键行。

字数只打印全文字数与 conception 的 target_length，不拦：用户给的字数要求在 requirements 里，
由审阅核销。正文与范文像不像也不在这里查，由审阅判断。

用法::

    python3 shortform_story_guard.py --story <work_dir>/story.md

退出码：0 通过或不在检查范围；2 有需修改的问题。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

HAN = re.compile(r"[㐀-鿿豈-﫿]")
EN_WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")

DESIGN_MARKERS = ("[核心]", "[灵感]", "[惊艳]", "[main]", "[support]", "[atmosphere]")
DESIGN_FIELDS = (
    "spine_statement", "dramatic_question", "ending_pressure", "value_start", "value_end",
    "location_time", "inspiration_refs", "voice_boundaries", "voice_samples", "narration_person",
    "core_value", "target_length", "style_directives", "reference_materials", "canon_reference_profile",
    "scene_tasks", "reader_track", "beat_direction", "craft_carrier", "boldness_guardrails",
    "prose_risk_contract", "scene_id",
)
# 排练标题与场景卡投影标签只按标题、标签形态认：独占一行，或后接冒号。叙述句里的同形词组
# （"这些话他想说但不会直说""他等着她的动作或停顿"）是正常正文，不拦。
REHEARSAL_HEADING = re.compile(
    r"^\s*(?:[#>*\-]+\s*)?[【\[]?\**\s*(想说但不会直说|台词候选|禁用语气|动作或停顿)\s*\**[】\]]?\s*(?:[：:]|$)")
PROJECTION_LABEL = re.compile(
    r"^\s*[#*【\[]*\s*(需成立的叙事工作|目标叙事增量|呈现建议|入场处境|离场结果|关键转折)\s*[】\]*]*\s*[：:]")
LEDGER_ID = re.compile(r"\bINS-\d{3}\b")
YAML_KEY_LINE = re.compile(
    r"^\s*-?\s*(premise|core_value|genre|target_length|scene_id|pov|participants|location_time|conflict|"
    r"value_start|value_end|task|handoff|desire|pressure|voice|relationships|nature|requirements)\s*:\s")


def count_units(text: str) -> tuple[int, str]:
    """正文篇幅：中文数非空白字符，英文数词；返回 (数量, 单位)。"""
    words = len(EN_WORD.findall(text))
    han = len(HAN.findall(text))
    if words > han:
        return words, "词"
    return len(re.sub(r"\s", "", text)), "字"


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def format_problems(text: str) -> list[str]:
    problems = []
    if text.lstrip().startswith("---\n") or text.startswith("---\r\n"):
        problems.append("1: 正文以 YAML frontmatter 开头，story.md 只放作品文本")
    for i, line in enumerate(text.splitlines(), start=1):
        if "<!--" in line:
            problems.append(f"{i}: 含 HTML 注释")
    return problems


def token_problems(text: str) -> list[str]:
    """带下划线的字段名是程序标识，出现即算；handoff 这类普通词只在 YAML 键行里算（"handoff failed"
    可以是正文里的报错文字）；排练标题与投影标签只认标题、标签形态。"""
    problems = []
    for i, line in enumerate(text.splitlines(), start=1):
        hits = [t for t in DESIGN_MARKERS if t in line]
        hits += [f for f in DESIGN_FIELDS if f in line]
        if m := REHEARSAL_HEADING.match(line):
            hits.append(m.group(1))
        if m := PROJECTION_LABEL.match(line):
            hits.append(m.group(1))
        hits += LEDGER_ID.findall(line)
        if m := YAML_KEY_LINE.match(line):
            hits.append(f"{m.group(1)}:")
        if hits:
            problems.append(f"{i}: 设计用词 {'、'.join(dict.fromkeys(hits))}")
    return problems


def length_line(story: Path) -> str:
    """全文字数与构想的 target_length，只供对照。"""
    count, unit = count_units(story.read_text(encoding="utf-8"))
    target = _load_yaml(story.parent / "pipeline" / "shortform" / "conception.yaml").get("target_length")
    return f"[字数] 全文 {count} {unit}" + (f"，target_length {target}" if target else "")


def check(story: Path) -> list[str]:
    text = story.read_text(encoding="utf-8")
    sections = [("格式", format_problems(text)), ("设计用词", token_problems(text))]
    return [f"[{name}] {story}:{problem}" for name, problems in sections for problem in problems]


def in_scope(story: Path) -> bool:
    return story.name == "story.md" and (story.parent / "pipeline" / "shortform" / "conception.yaml").is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="短篇正文写入后的守卫")
    parser.add_argument("--story", required=True, type=Path)
    args = parser.parse_args(argv)
    story = args.story
    if not story.is_file() or not in_scope(story):
        return 0
    print(length_line(story))
    problems = check(story)
    if not problems:
        return 0
    print("[shortform-story] 正文需修改（位置为 文件:行号）：", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("设计用词换成作品内的说法；格式问题删去非作品文本。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
