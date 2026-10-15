#!/usr/bin/env python3
"""短篇正文写入后的守卫（设计 §3.6、§6、§10.2），由 hooks/check-design-token-leak.sh 分派。

只检查短链正文：工作目录根部的 story.md，且同目录有 pipeline/shortform/conception.yaml。
四项，任一不满足 exit 2 并逐条给出位置，写作者在同一会话修改：

1. 格式：无 YAML frontmatter、无 HTML 注释。
2. 设计用词泄漏：大纲与构想字段名、设计标记、排练标题、场景卡投影标签、灵感账 ID、YAML 键行。
3. 与范文的连续重合：对照写作简报“范文”一节的窗口，口径见 reuse_overlap.py；
   人物名不计；conception 的手选名著写明 maximize_apt_reuse（作者授权复用原文）的那部作品的窗口
   不查，其他窗口照查。
4. 字数：超出 conception.target_length ±30% 才拦；更小的偏差不拦，字数是软约束。

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reuse_overlap  # noqa: E402

LENGTH_TOLERANCE = 0.30

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
    words = len(reuse_overlap.EN_WORD.findall(text))
    han = len(reuse_overlap.HAN.findall(text))
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


WINDOW_WITH_ATTRS = re.compile(r"<exemplar_window\b([^>]*)>\n?(.*?)</exemplar_window>", re.S)
NOVEL_ATTR = re.compile(r'\bnovel="([^"]*)"')


def authorized_works(conception: dict) -> list[str]:
    """作者在 canon_reference_profile 里授权复用原文（maximize_apt_reuse）的作品名。"""
    profile = conception.get("canon_reference_profile") or {}
    materials = profile.get("user_reference_materials") if isinstance(profile, dict) else None
    return [str(m["work"]) for m in materials or []
            if isinstance(m, dict) and m.get("reuse_mode") == "maximize_apt_reuse" and m.get("work")]


def _same_work(a: str, b: str) -> bool:
    a, b = a.strip(), b.strip()
    return bool(a and b) and (a in b or b in a)


def checked_exemplar(raw: str, authorized: list[str]) -> str:
    """要查重合的范文原文：作者授权复用的那几部作品的窗口不查，其余窗口照查。"""
    kept = []
    for attrs, body in WINDOW_WITH_ATTRS.findall(raw):
        novel = NOVEL_ATTR.search(attrs)
        if novel and any(_same_work(novel.group(1), work) for work in authorized):
            continue
        kept.append(body)
    return "\n".join(kept)


def _character_names(shortform: Path) -> list[str]:
    chars = _load_yaml(shortform / "characters.yaml").get("characters") or []
    return [c["name"] for c in chars if isinstance(c, dict) and isinstance(c.get("name"), str)]


def overlap_problems(text: str, shortform: Path, conception: dict) -> list[str]:
    brief = shortform / "writer_brief.md"
    raw = brief.read_text(encoding="utf-8") if brief.exists() else ""
    exemplar = checked_exemplar(raw, authorized_works(conception))
    if not exemplar.strip():  # 没有简报、简报无范文，或范文全是授权复用的作品
        return []
    result = reuse_overlap.measure(text, exemplar, _character_names(shortform))
    if not result.violated:
        return []
    unit = result.unit
    problems = [f"与范文最长连续重合 {result.longest} {unit}（上限 {reuse_overlap.MAX_COMMON_RUN}），"
                f"≥{reuse_overlap.FRAGMENT_MIN}{unit}的共同片段覆盖正文 {result.coverage:.2%}"
                f"（上限 {reuse_overlap.MAX_FRAGMENT_COVERAGE:.0%}）"]
    problems += [f"{span['line']}: 与范文连续重合 {span['length']} {unit}：{span['text']}"
                 for span in result.spans[:10]]
    return problems


def length_problems(text: str, conception: dict) -> list[str]:
    target = conception.get("target_length")
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        return []
    count, unit = count_units(text)
    low, high = round(target * (1 - LENGTH_TOLERANCE)), round(target * (1 + LENGTH_TOLERANCE))
    if low <= count <= high:
        return []
    return [f"全文 {count} {unit}，target_length {target} 的 ±30% 是 {low}–{high}；"
            "仍在续写时写完再看，写完仍不在区间时按全文需要增删"]


def check(story: Path) -> list[str]:
    shortform = story.parent / "pipeline" / "shortform"
    conception = _load_yaml(shortform / "conception.yaml")
    text = story.read_text(encoding="utf-8")
    sections = [
        ("格式", format_problems(text)),
        ("设计用词", token_problems(text)),
        ("范文重合", overlap_problems(text, shortform, conception)),
        ("字数", length_problems(text, conception)),
    ]
    out = []
    for name, problems in sections:
        for problem in problems:
            out.append(f"[{name}] {story}:{problem}" if re.match(r"\d+:", problem) else f"[{name}] {problem}")
    return out


def in_scope(story: Path) -> bool:
    return story.name == "story.md" and (story.parent / "pipeline" / "shortform" / "conception.yaml").is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="短篇正文写入后的守卫")
    parser.add_argument("--story", required=True, type=Path)
    args = parser.parse_args(argv)
    story = args.story
    if not story.is_file() or not in_scope(story):
        return 0
    problems = check(story)
    if not problems:
        return 0
    print("[shortform-story] 正文需修改（位置为 文件:行号）：", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("设计用词换成作品内的说法；与范文重合处改用自己的句子，只学口吻；格式问题删去非作品文本。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
