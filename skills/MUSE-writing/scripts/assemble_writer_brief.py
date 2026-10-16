#!/usr/bin/env python3
"""写作简报装配（设计 §3.1–§3.4、§6、§8.3）：写作者只读这一份文件。

本版实现短篇链（--shortform），在 pipeline/shortform/ 下写三份文件：

- writer_brief.md：简报。各节依次为 作者要求 → 构想 → 人物 → 事件 → 范文 → 手法导航 → 条目 → 指令。
  “条目”节先附条件表 always_entries 列出的固定条目（口癖的改法），再附审阅解锁的条目。
  作者要求（requirements 全部条目与 reference_materials）原样进入，不计上限、不裁；
  构想、人物、事件按设计文字投影，装配时不裁。事件节的 task 与 handoff 承载一致性事实（谁知道什么、
  数字、物件去向、时间），逐行保留原文，各占一行，不与其他字段并句。
- brief_meta.yaml：各节字数、范文占比，以及 exemplar_short / exemplar: none / facts_over_budget 标记。
  只记录，不拦派发。
- disclosure_state.yaml：审阅解锁的条目。每次运行从 pipeline/shortform/review/ 的审阅文件重算，
  主控不写。某个 finding 键首次报出后附条目（rung: entry），后一轮再报出改附全文（rung: full）。

条件表与 finding → 条目对照在同目录 brief_rules.yaml。完整链（--scene-id）与连载（--serial）
按设计 §3.1 预留参数，尚未提供。

用法::

    python3 assemble_writer_brief.py --shortform --work-dir <run> [--usage "本篇可以怎样用"]
    python3 assemble_writer_brief.py --shortform --work-dir <run> --retrieval-args

退出码：0 已写出；2 输入错误（缺 conception / characters / outline 或参数不支持）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shlex
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import craft_entries  # noqa: E402
from validate_shortform_contract import brief_units  # noqa: E402

RULES_PATH = Path(__file__).resolve().parent / "brief_rules.yaml"
REVIEW_RE = re.compile(r"^short_story_review\.r(\d+)\.yaml$")
EXEMPLAR_EMPTY_RE = re.compile(r"^results:\s*0\s*—\s*(.+)$", re.M)
WINDOW_RE = re.compile(r"<exemplar_window\b[^>]*>\n?(.*?)</exemplar_window>", re.S)
PERSON_LABEL = {"first": "第一人称", "third": "第三人称"}
# 投影用的连接词随交付语言，避免英文设计文字夹中文连接词
LABELS = {
    "zh": {"experience": "主要经验：", "genre": "类型：", "person": "叙述人称：", "length": "篇幅：约 {n} 字",
           "style": "风格：", "pressure": "处境：", "desire": "追求：", "voice": "声音：", "boundary": "表达边界：",
           "samples": "示范句：", "with": "与{name}：", "pov": "{viewer}视角，在场：{present}。",
           "arc": "开场时{start}，场末{end}", "handoff": "后文承接：{text}", "borrowed": "借用机制：{text}",
           "persons": {"first": "第一人称", "third": "第三人称"}, "no_person": "构想未写叙述人称"},
    "en": {"experience": "Core experience: ", "genre": "Genre: ", "person": "Narration: ",
           "length": "Length: about {n} words", "style": "Style:", "pressure": "Situation: ", "desire": "Wants: ",
           "voice": "Voice: ", "boundary": "Boundary: ", "samples": "Sample lines: ", "with": "With {name}: ",
           "pov": "POV {viewer}; present: {present}. ", "arc": "Opens with {start}; ends with {end}",
           "handoff": "Carries forward: {text}", "borrowed": "Borrowed mechanism: {text}",
           "persons": {"first": "first person", "third": "third person"}, "no_person": "not set in conception"},
}
SECTIONS = ("作者要求", "构想", "人物", "事件", "范文", "手法导航", "条目", "指令")
FACT_SECTIONS = ("构想", "人物", "事件")
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
NAV_SKILLS = (("prose-craft", "叙述"), ("dialogue-craft", "人物声音与对白"))
NAV_ENTRY_FILES = "prose-craft/references/prose-rules.md、dialogue-craft/references/voice-and-dialogue.md"
NAV_PATTERN_LIBRARY = "prose-craft/references/ai-cliche-patterns.md"
NAV_SKIP_PREFIXES = ("- 案例与全文", "- 规则与案例")  # 整份参考的清单，条目与全文由审阅解锁后附上
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
DOMAIN_LABELS = {"world_rule": "世界规则", "reveal_structure": "揭示结构", "protagonist_archetype": "主角原型",
                 "scene_carrier": "场景载体", "prose_style_imitation": "文风模仿"}


def _load(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _end(text: str, english: bool = False) -> str:
    text = str(text).strip()
    if not text or text[-1] in "。！？!?.…」”）)\"'":
        return text
    return text + (". " if english else "。")


def delivery_language(conception: dict) -> tuple[str, bool]:
    """返回 (交付语言, 是否由文字推断)。以 conception 的 language 为准：中文讨论、英文交付是常态，
    按设计文字的语种推断会取到中文范文。只有缺字段的旧构想才推断，并在 meta 里记警告。"""
    lang = conception.get("language")
    if isinstance(lang, str) and re.fullmatch(r"[a-z]{2}", lang):
        return lang, False
    text = " ".join(str(conception.get(k) or "") for k in ("premise", "core_value"))
    text += " ".join(map(str, conception.get("requirements") or []))
    return ("en" if len(re.findall(r"[A-Za-z]+", text)) > len(re.findall(r"[㐀-鿿]", text)) else "zh"), True


def is_english(conception: dict) -> bool:
    return delivery_language(conception)[0] == "en"


# ---------- 各节 ----------

def section_requirements(conception: dict) -> str:
    parts: list[str] = []
    requirements = conception.get("requirements") or []
    if requirements:
        parts.append("以下要求逐条落实：")
        parts.extend(f"- {item}" for item in requirements)
    materials = conception.get("reference_materials")
    if materials:
        if parts:
            parts.append("")
        parts.append("用户素材（原样，事实与授权原文照用）：")
        parts.append("<user_materials>")
        parts.append(str(materials).rstrip("\n"))
        parts.append("</user_materials>")
    return "\n".join(parts) if parts else "无"


def section_conception(conception: dict, english: bool) -> str:
    lab = LABELS["en" if english else "zh"]
    person = lab["persons"].get(conception.get("narration_person"), lab["no_person"])
    lines = [_end(conception.get("premise", ""), english)]
    if conception.get("core_value"):
        lines.append(lab["experience"] + str(conception["core_value"]))
    if conception.get("genre"):
        lines.append(lab["genre"] + str(conception["genre"]))
    lines.append(lab["person"] + person)
    if conception.get("target_length"):
        lines.append(lab["length"].format(n=conception["target_length"]))
    directives = conception.get("style_directives") or []
    if directives:
        lines.append(lab["style"])
        lines.extend(f"- {item}" for item in directives)
    return "\n".join(lines)


def section_characters(characters: list[dict], english: bool = False) -> tuple[str, dict[str, str]]:
    lab = LABELS["en" if english else "zh"]
    names = {c["id"]: c.get("name") or c["id"] for c in characters if isinstance(c, dict) and c.get("id")}
    blocks: list[str] = []
    for char in characters:
        if not isinstance(char, dict):
            continue
        lines = [f"### {char.get('name') or char.get('id')}"]
        for key in ("pressure", "desire", "voice"):
            if char.get(key):
                lines.append(lab[key] + str(char[key]))
        for item in char.get("voice_boundaries") or []:
            lines.append(lab["boundary"] + str(item))
        samples = char.get("voice_samples") or []
        if samples:
            quoted = " ".join(f"\"{s}\"" if english else f"「{s}」" for s in samples)
            lines.append(lab["samples"] + quoted)
        for rel in char.get("relationships") or []:
            if isinstance(rel, dict) and rel.get("with"):
                lines.append(lab["with"].format(name=names.get(rel["with"], rel["with"])) + str(rel.get("nature", "")))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks), names


def adopted_mechanisms(shortform: Path) -> dict[str, str]:
    """inspiration_ledger 中 adopted 条目的 project_encoding，供事件节附在引用它的场后。"""
    ledger = _load(shortform / "inspiration_ledger.yaml")
    items = ledger.get("inspirations") if isinstance(ledger, dict) else None
    return {i["id"]: str(i.get("project_encoding", "")) for i in items or []
            if isinstance(i, dict) and i.get("status") == "adopted" and i.get("id")}


def section_events(scenes: list[dict], names: dict[str, str], english: bool = False,
                   mechanisms: dict[str, str] | None = None) -> str:
    """每场一条：首行场次、时地与视角，其下冲突与起止状态、task、handoff、借用机制各起一行，
    多行的值逐行保留。"""
    lab = LABELS["en" if english else "zh"]
    mechanisms = mechanisms or {}
    sep = ", " if english else "、"
    joiner = " " if english else ""
    blocks: list[str] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        pov = str(scene.get("pov") or "")
        viewer = pov.removeprefix("narrator:").strip() if pov.startswith("narrator:") else names.get(pov, pov)
        present = sep.join(names.get(p, p) for p in scene.get("participants") or [])
        head = f"{scene.get('scene_id', '')}｜{scene.get('location_time', '')}｜" + lab["pov"].format(
            viewer=viewer, present=present)
        situation = [_end(scene.get("conflict", ""), english)]
        if scene.get("value_start") or scene.get("value_end"):
            situation.append(_end(lab["arc"].format(start=str(scene.get("value_start", "")).rstrip("。. "),
                                                    end=str(scene.get("value_end", "")).rstrip("。. ")), english))
        items = [joiner.join(s.strip() for s in situation if s.strip()), _end(scene.get("task", ""), english)]
        if scene.get("handoff"):
            items.append(_end(lab["handoff"].format(text=scene["handoff"]), english))
        for ref in scene.get("inspiration_refs") or []:
            if mechanisms.get(ref):
                items.append(_end(lab["borrowed"].format(text=mechanisms[ref]), english))
        lines = [f"- {head}".rstrip()]
        lines += [f"  {line.strip()}" for item in items for line in item.splitlines() if line.strip()]
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def read_exemplar(path: Path) -> tuple[list[str], str | None]:
    """返回 (窗口块原文, 无范文原因)。"""
    if not path.is_file():
        return [], f"未取范文（{path.name} 不存在）"
    raw = path.read_text(encoding="utf-8")
    windows = [m.group(0).strip() for m in WINDOW_RE.finditer(raw)]
    if windows:
        return windows, None
    if m := EXEMPLAR_EMPTY_RE.search(raw):
        return [], f"检索无结果：{m.group(1).strip()}"
    return [], f"{path.name} 不是范文窗口渲染（kb_query --render exemplar）"


# ---------- 披露梯 ----------

def compute_disclosure(review_dir: Path, findings_rules: dict) -> dict:
    """从各轮审阅文件重算解锁项。since 是开始附条目的轮次：r1 报出，r2 的写作或修订起附。"""
    rounds = []
    if review_dir.is_dir():
        for path in review_dir.iterdir():
            if m := REVIEW_RE.match(path.name):
                rounds.append((int(m.group(1)), path))
    items: dict[str, dict] = {}
    for n, path in sorted(rounds):
        report = _load(path) or {}
        seen: dict[str, str] = {}
        for finding in report.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            dim, sub = finding.get("dimension"), finding.get("subkind")
            key = f"{dim}/{sub}" if sub else str(dim)
            rule = findings_rules.get(key) or (findings_rules.get(str(dim)) if sub else None)
            if rule:
                seen.setdefault(rule["entry"], key)
        for entry, key in seen.items():
            rule = findings_rules.get(key) or findings_rules.get(key.split("/")[0])
            state = items.get(entry)
            if state is None:
                items[entry] = {
                    "item": entry, "rung": "entry", "active": True,
                    "reason": f"{key} 在 r{n} 报出", "since": f"r{n + 1}", "last_seen": f"r{n}",
                    "history": [{"enter": f"r{n + 1}"}], "full": rule["full"], "keys": [key],
                }
                continue
            state["last_seen"] = f"r{n}"
            if key not in state["keys"]:
                state["keys"].append(key)
            if state["rung"] == "entry":
                state["rung"] = "full"
                state["reason"] += f"；r{n} 再报，附全文"
                state["history"].append({"full": f"r{n + 1}"})
    return {"rounds": [n for n, _ in sorted(rounds)], "unlocked": list(items.values())}


def section_entries(state: dict, cap_each: int, cap_total: int,
                    always: tuple[str, ...] | list[str] = ()) -> tuple[str, list[dict]]:
    """固定条目不等审阅、先计入合计；审阅解锁的同一条目不重复附，第二次报出时在固定条目后补全文位置。"""
    active = [s for s in state["unlocked"] if s.get("active")]
    active.sort(key=lambda s: (-int(s["last_seen"].lstrip("r")), -len(s["history"])))
    blocks: list[str] = []
    record: list[dict] = []
    total = 0
    fixed: dict[str, int] = {}
    for ref in always:
        try:
            entry = craft_entries.resolve(ref, cap=cap_each)
        except KeyError as exc:
            record.append({"item": ref, "attached": False, "reason": str(exc), "rung": "always"})
            continue
        fixed[ref] = len(blocks)
        blocks.append(f"### {entry.title}\n\n{entry.text}")
        total += entry.units
        record.append({"item": ref, "attached": True, "units": entry.units, "rung": "always"})
    for item in active:
        if item["item"] in fixed:
            if item["rung"] == "full":
                blocks[fixed[item["item"]]] += f"\n\n全文：{item['full']}（同类问题第二次报出，动笔或修订前读这一处）"
            record.append({"item": item["item"], "attached": True, "rung": item["rung"], "merged": "always"})
            continue
        try:
            entry = craft_entries.resolve(item["item"], cap=cap_each)
        except KeyError as exc:
            record.append({"item": item["item"], "attached": False, "reason": str(exc)})
            continue
        text = f"### {entry.title}\n\n{entry.text}"
        if item["rung"] == "full":
            text += f"\n\n全文：{item['full']}（同类问题第二次报出，动笔或修订前读这一处）"
        if total + entry.units > cap_total and blocks:
            record.append({"item": item["item"], "attached": False, "units": entry.units, "reason": "超过条目节上限"})
            continue
        blocks.append(text)
        total += entry.units
        record.append({"item": item["item"], "attached": True, "units": entry.units, "rung": item["rung"]})
    return ("\n\n".join(blocks) if blocks else "无"), record


def section_navigation() -> str:
    """prose-craft、dialogue-craft 的手法导航，原样附进简报：写作者先知道有哪些手法、何时用。
    两次真实运行里写作者都没有自己去加载导航（设计 §3.1）。链接只留名称，整份参考的清单不附。"""
    blocks: list[str] = []
    for skill, label in NAV_SKILLS:
        path = SKILLS_DIR / skill / "SKILL.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            text = text.split("---", 2)[2]
        lines = [f"### {label}"]
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("# ") or stripped.startswith("手法导航："):
                continue
            if stripped.startswith(NAV_SKIP_PREFIXES):
                continue
            if stripped.startswith("## "):
                lines.append(stripped[3:])
                continue
            lines.append(MARKDOWN_LINK.sub(r"\1", stripped))
        blocks.append("\n".join(lines))
    if not blocks:
        return "无"
    blocks.append(f"条目全文在 {NAV_ENTRY_FILES}（路径相对本包 skills/），按条目标题查；口癖四个机制的判据与例子在 "
                  f"{NAV_PATTERN_LIBRARY}。需要时读，回执写明读了哪些。")
    return "\n\n".join(blocks)


def author_sources(conception: dict) -> list[dict]:
    """作者在 canon_reference_profile 里写了复用方式的来源：作品名、方式（maximize_apt_reuse 或
    style_only）、用途领域，以及作品级不用的领域。"""
    profile = conception.get("canon_reference_profile")
    if not isinstance(profile, dict):
        return []
    avoid = [d for d in profile.get("avoid_domains") or [] if isinstance(d, str)]
    return [{"work": str(m["work"]), "mode": m["reuse_mode"],
             "domains": [d for d in m.get("intended_domains") or [] if isinstance(d, str)], "avoid": avoid}
            for m in profile.get("user_reference_materials") or []
            if isinstance(m, dict) and m.get("reuse_mode") in ("maximize_apt_reuse", "style_only") and m.get("work")]


def _domains(codes: list[str]) -> str:
    return "、".join(DOMAIN_LABELS.get(c, c) for c in codes)


def section_instruction(has_exemplar: bool, usage: str | None, has_full: bool,
                        sources: list[dict] | None = None) -> str:
    lines = ["写全文。只读本简报，写到工作目录根部 story.md。"]
    if has_exemplar:
        lines.append("用“范文”一节的口吻写：句子长短、用词、对白的节奏与归属方式、叙述者与人物说话的距离都跟范文走；"
                     "引号等标点按本篇语言的通行写法，作者要求或下面一两句另有说明的除外。"
                     "不偏离本篇情节走向和人物设定的前提下，越像范文越好：范文里的原句、专名、人物和情节，合适就直接用。")
        lines.append(f"本篇可以怎样用：{usage.strip() if usage else '见派发。'}")
    else:
        lines.append("本篇无范文，按人物声音与示范句写。")
    for source in sources or []:
        if source["mode"] == "style_only":
            lines.append(f"《{source['work']}》作者定为只借文风。")
            continue
        scope = f"，用于{_domains(source['domains'])}" if source["domains"] else ""
        avoid = f"，不用于{_domains(source['avoid'])}" if source["avoid"] else ""
        lines.append(f"作者要求尽量复用《{source['work']}》的原文{scope}{avoid}。")
    if has_full:
        lines.append("条目注明“全文”的，动笔前读那一处。")
    return "\n".join(lines)


# ---------- 装配 ----------

def assemble_shortform(work_dir: Path, *, usage: str | None = None, exemplar_path: Path | None = None) -> dict:
    rules = (_load(RULES_PATH) or {})["shortform"]
    shortform = work_dir / "pipeline" / "shortform"
    conception = _load(shortform / "conception.yaml")
    characters = _load(shortform / "characters.yaml")
    outline = _load(shortform / "outline.yaml")
    for name, data in (("conception", conception), ("characters", characters), ("outline", outline)):
        if not isinstance(data, dict):
            raise ValueError(f"pipeline/shortform/{name}.yaml 缺失或不可解析")
    english = is_english(conception)
    exemplar_path = exemplar_path or shortform / "reference_pack.md"
    windows, none_reason = read_exemplar(exemplar_path)
    state = compute_disclosure(shortform / "review", rules["findings"])

    char_text, names = section_characters(characters.get("characters") or [], english)
    entries_text, entries_record = section_entries(state, rules["entry_cap"], rules["entries_cap"],
                                                   rules.get("always_entries") or ())
    has_full = any(r.get("attached") and r.get("rung") == "full" for r in entries_record)
    sections = {
        "作者要求": section_requirements(conception),
        "构想": section_conception(conception, english),
        "人物": char_text or "无",
        "事件": section_events(outline.get("scenes") or [], names, english, adopted_mechanisms(shortform)),
        "范文": "\n\n".join(windows) if windows else f"本篇无范文：{none_reason}",
        "手法导航": section_navigation(),
        "条目": entries_text,
        "指令": section_instruction(bool(windows), usage, has_full, author_sources(conception)),
    }
    brief = "# 写作简报\n\n" + "\n\n".join(f"## {name}\n\n{sections[name]}" for name in SECTIONS) + "\n"
    (shortform / "writer_brief.md").write_text(brief, encoding="utf-8")

    counts = {name: brief_units(sections[name]) for name in SECTIONS}
    total = sum(counts.values())
    exemplar_units = counts["范文"] if windows else 0
    ratio = round(exemplar_units / total, 3) if total else 0.0
    meta: dict = {
        "brief": "pipeline/shortform/writer_brief.md",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "unit": "字（汉字；英文按 1 汉字约 0.6 词折算）",
        "sections": counts,
        "total": total,
        "exemplar": "windows" if windows else "none",
        "exemplar_windows": len(windows),
        "exemplar_ratio": ratio,
        "exemplar_short": bool(windows) and ratio < rules["exemplar_min_ratio"],
        "facts_over_budget": sum(counts[s] for s in FACT_SECTIONS) > exemplar_units,
        "review_rounds": state["rounds"],
        "entries": entries_record,
        "inputs": {
            name: _sha(shortform / f"{name}.yaml") for name in ("conception", "characters", "outline")
        } | {"exemplar": _sha(exemplar_path)},
    }
    if not windows:
        meta["exemplar_reason"] = none_reason
    elif meta["exemplar_short"]:
        meta["exemplar_short_reason"] = (
            f"范文 {exemplar_units} 字占简报 {ratio:.0%}，低于 {rules['exemplar_min_ratio']:.0%}；"
            f"作者要求 {counts['作者要求']} 字不裁")
    if conception.get("narration_person") not in PERSON_LABEL:
        meta["warnings"] = ["conception 缺 narration_person（旧构想）；取范文时 --person 需主控判断"]
    if exemplar_path.is_file() and (shortform / "conception.yaml").stat().st_mtime > exemplar_path.stat().st_mtime:
        stale = "conception 在取范文之后改过；人称、语言或风格指令变了时按 short-phase0-conception 的“取本篇范文”重取"
        meta.setdefault("warnings", []).append(stale)
        print(f"[brief] {stale}", file=sys.stderr)
    lang, inferred = delivery_language(conception)
    meta["language"] = lang
    if inferred:
        meta.setdefault("warnings", []).append(
            f"conception 缺 language（旧构想），交付语言按设计文字推断为 {lang}；作者要求另有说明时以要求为准")
    if counts["指令"] > rules["instruction_cap"]:
        meta.setdefault("warnings", []).append(f"指令节 {counts['指令']} 字，超过 {rules['instruction_cap']}")
    (shortform / "brief_meta.yaml").write_text(
        "# 由 assemble_writer_brief.py 生成，不手工编辑\n"
        + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (shortform / "disclosure_state.yaml").write_text(
        "# 由 assemble_writer_brief.py 从审阅文件重算，主控不维护。\n"
        "# rung: entry 附条目；full 附全文位置。since / last_seen 是审阅轮次（r1 报出，r2 起附）。\n"
        + yaml.safe_dump({"unlocked": state["unlocked"]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return meta


def retrieval_args(work_dir: Path) -> str:
    """成稿前取范文的确定参数（条件表 shortform.retrieval）；--query 与 --register 由主控写。"""
    rules = (_load(RULES_PATH) or {})["shortform"]["retrieval"]
    shortform = work_dir / "pipeline" / "shortform"
    conception = _load(shortform / "conception.yaml")
    if not isinstance(conception, dict):
        raise ValueError("pipeline/shortform/conception.yaml 缺失或不可解析")
    lang, inferred = delivery_language(conception)
    if inferred:
        print(f"[brief] conception 缺 language，交付语言按设计文字推断为 {lang}；请在构想里写明", file=sys.stderr)
    args = ["--lang", lang]
    if rules.get("original_only"):
        args.append("--original-only")
    person = conception.get(rules.get("person_from", "narration_person"))
    if person in PERSON_LABEL:
        args += ["--person", person]
    args += ["--budget-chars", str(rules["budget_chars"]), "--render", "exemplar", "--shortform-pack",
             "--output-dir", shlex.quote(str(shortform))]
    if isinstance(conception.get("canon_reference_profile"), dict):
        args += ["--canon-reference-profile", shlex.quote(str(shortform / "conception.yaml"))]
    args += ["--style-hint", shlex.quote(style_hint(conception, lang))]
    return " ".join(args)


def style_hint(conception: dict, lang: str) -> str:
    """选范文作品用的 style hint（设计 §4.2）：叙述人称、作品风格指令与类型，主控可改。"""
    english = lang == "en"
    lab = LABELS["en" if english else "zh"]
    parts = [lab["persons"].get(conception.get("narration_person"), "")]
    parts += [str(d) for d in conception.get("style_directives") or []]
    if conception.get("genre"):
        parts.append(lab["genre"] + str(conception["genre"]))
    return ("; " if english else "；").join(p.strip() for p in parts if p and p.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写作简报装配")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--shortform", action="store_true", help="短篇链：pipeline/shortform/writer_brief.md")
    scope.add_argument("--scene-id", help="完整链按场装配（设计 §3.1，尚未提供）")
    scope.add_argument("--serial", action="store_true", help="连载按场装配（设计 §7.3，尚未提供）")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--usage", help="主控写的“本篇可以怎样用”，一两句")
    parser.add_argument("--exemplar", type=Path, help="范文窗口文件；默认 pipeline/shortform/reference_pack.md")
    parser.add_argument("--retrieval-args", action="store_true", help="只打印成稿前取范文的确定参数")
    args = parser.parse_args(argv)

    if not args.shortform:
        print("[brief] 完整链与连载的简报装配尚未提供，本版只支持 --shortform", file=sys.stderr)
        return 2
    work_dir = args.work_dir.resolve()
    try:
        if args.retrieval_args:
            print(retrieval_args(work_dir))
            return 0
        meta = assemble_shortform(work_dir, usage=args.usage, exemplar_path=args.exemplar)
    except ValueError as exc:
        print(f"[brief] {exc}", file=sys.stderr)
        return 2
    flags = [k for k in ("exemplar_short", "facts_over_budget") if meta.get(k)]
    if meta["exemplar"] == "none":
        flags.append(f"exemplar: none（{meta['exemplar_reason']}）")
    print(f"[brief] 已写 {meta['brief']}：共 {meta['total']} 字，范文占 {meta['exemplar_ratio']:.0%}"
          + (f"；{'；'.join(flags)}" if flags else ""))
    attached = [e["item"] for e in meta["entries"] if e.get("attached")]
    if attached:
        print(f"[brief] 本轮附条目：{'、'.join(attached)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
