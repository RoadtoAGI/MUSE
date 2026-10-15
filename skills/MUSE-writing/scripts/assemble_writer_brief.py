#!/usr/bin/env python3
"""写作简报装配（设计 §3.1–§3.4、§6、§8.3）：写作者只读这一份文件。

本版实现短篇链（--shortform），在 pipeline/shortform/ 下写三份文件：

- writer_brief.md：简报。各节依次为 作者要求 → 构想 → 人物 → 事件 → 范文 → 条目 → 指令。
  作者要求（requirements 全部条目与 reference_materials）原样进入，不计上限、不裁；
  构想、人物、事件的字数上限由 validate_shortform_contract.py 在设计阶段卡住，装配时不裁。
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
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import craft_entries  # noqa: E402
from reuse_overlap import WINDOW_RE  # noqa: E402
from validate_shortform_contract import brief_units  # noqa: E402

RULES_PATH = Path(__file__).resolve().parent / "brief_rules.yaml"
REVIEW_RE = re.compile(r"^short_story_review\.r(\d+)\.yaml$")
EXEMPLAR_EMPTY_RE = re.compile(r"^results:\s*0\s*—\s*(.+)$", re.M)
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
SECTIONS = ("作者要求", "构想", "人物", "事件", "范文", "条目", "指令")
FACT_SECTIONS = ("构想", "人物", "事件")


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


def is_english(conception: dict) -> bool:
    text = " ".join(str(conception.get(k) or "") for k in ("premise", "core_value"))
    text += " ".join(map(str, conception.get("requirements") or []))
    return len(re.findall(r"[A-Za-z]+", text)) > len(re.findall(r"[㐀-鿿]", text))


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
    lab = LABELS["en" if english else "zh"]
    mechanisms = mechanisms or {}
    sep = ", " if english else "、"
    lines: list[str] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        pov = str(scene.get("pov") or "")
        viewer = pov.removeprefix("narrator:").strip() if pov.startswith("narrator:") else names.get(pov, pov)
        present = sep.join(names.get(p, p) for p in scene.get("participants") or [])
        head = f"{scene.get('scene_id', '')}｜{scene.get('location_time', '')}｜" + lab["pov"].format(
            viewer=viewer, present=present)
        body = [_end(scene.get("conflict", ""), english)]
        if scene.get("value_start") or scene.get("value_end"):
            body.append(_end(lab["arc"].format(start=str(scene.get("value_start", "")).rstrip("。. "),
                                               end=str(scene.get("value_end", "")).rstrip("。. ")), english))
        body.append(_end(scene.get("task", ""), english))
        if scene.get("handoff"):
            body.append(_end(lab["handoff"].format(text=scene["handoff"]), english))
        for ref in scene.get("inspiration_refs") or []:
            if mechanisms.get(ref):
                body.append(_end(lab["borrowed"].format(text=mechanisms[ref]), english))
        joiner = " " if english else ""
        lines.append(f"- {head}{joiner.join(b.strip() for b in body if b)}".rstrip())
    return "\n".join(lines)


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


def section_entries(state: dict, cap_each: int, cap_total: int) -> tuple[str, list[dict]]:
    active = [s for s in state["unlocked"] if s.get("active")]
    active.sort(key=lambda s: (-int(s["last_seen"].lstrip("r")), -len(s["history"])))
    blocks: list[str] = []
    record: list[dict] = []
    total = 0
    for item in active:
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


def reuse_authorized(conception: dict) -> bool:
    profile = conception.get("canon_reference_profile")
    materials = profile.get("user_reference_materials") if isinstance(profile, dict) else None
    return any(isinstance(m, dict) and m.get("reuse_mode") == "maximize_apt_reuse" for m in materials or [])


def section_instruction(has_exemplar: bool, usage: str | None, has_full: bool, reuse: bool = False) -> str:
    lines = ["写全文。只读本简报，写到工作目录根部 story.md。"]
    if has_exemplar:
        exception = "（作者授权复用的来源按“作者要求”与设计使用）" if reuse else ""
        lines.append("用“范文”一节的口吻写：句子长短、用词、对白的写法、叙述者与人物说话的距离都跟范文走；"
                     f"范文的人物、情节、专名和连续原句一律不用{exception}。")
        lines.append(f"本篇可以怎样用：{usage.strip() if usage else '见派发。'}")
    else:
        lines.append("本篇无范文，按人物声音与示范句写。")
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
    entries_text, entries_record = section_entries(state, rules["entry_cap"], rules["entries_cap"])
    has_full = any(r.get("attached") and r.get("rung") == "full" for r in entries_record)
    sections = {
        "作者要求": section_requirements(conception),
        "构想": section_conception(conception, english),
        "人物": char_text or "无",
        "事件": section_events(outline.get("scenes") or [], names, english, adopted_mechanisms(shortform)),
        "范文": "\n\n".join(windows) if windows else f"本篇无范文：{none_reason}",
        "条目": entries_text,
        "指令": section_instruction(bool(windows), usage, has_full, reuse_authorized(conception)),
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
    args = ["--lang", "en" if is_english(conception) else "zh"]
    if rules.get("original_only"):
        args.append("--original-only")
    person = conception.get(rules.get("person_from", "narration_person"))
    if person in PERSON_LABEL:
        args += ["--person", person]
    args += ["--budget-chars", str(rules["budget_chars"]), "--render", "exemplar", "--shortform-pack",
             "--output-dir", str(shortform)]
    return " ".join(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写作简报装配")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--shortform", action="store_true", help="短篇链：pipeline/shortform/writer_brief.md")
    scope.add_argument("--scene-id", help="完整链按场装配（设计 §3.1，尚未提供）")
    scope.add_argument("--serial", action="store_true", help="连载按场装配（设计 §7.3，尚未提供）")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--usage", help="主控写的“本篇可以怎样用”，两行以内")
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
