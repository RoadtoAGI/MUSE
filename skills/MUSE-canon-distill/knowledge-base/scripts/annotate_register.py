#!/usr/bin/env python3
"""场景人称、语域与对白占比标注（零 API）：算完写回每作品权威索引。

字段（设计 §4.1）：
- original_lang：作品原作语言，取自 style_card.yaml 的 `original_lang`；没有 style_card 的戏剧取
  work-meta.yaml 的 `original_language`。`--prefill-original-lang` 按文本语言与作者表为缺值的
  style_card 预填，逐部打印决定，由作者核对。
- narrative_person：first / third / mixed。中文数引号外"我"每千字，英文数引号外
  I/me/my/mine/myself 每千词；密度够 first 的场景再看第一人称段落的占比，第三人称叙述里嵌书信的
  记 mixed。对白不加引号、或大量不加引号的内心独白的作品由 style_card 的
  `narrative_person_override` 指定。戏剧没有叙述者，记 null。
- register：colloquial / literary / mixed。中文小说由口语标记每千字、对白占比、平均句长三项合成，
  权重与阈值见下方常量，按 14 部中文原作标定。英文阈值等第一批英文原著入库后标定，
  标定前记 null（`REGISTER_LANGS` 之外的语言都如此）；戏剧通篇是台词，这套阈值不适用，也记 null。
- dialogue_ratio：引号内字数占正文字数的比例；戏剧取有角色名前缀的台词行占比。

用法::

    python3 annotate_register.py --all
    python3 annotate_register.py --work 白鹿原 --work 长路
    python3 annotate_register.py --prefill-original-lang

写回后运行 merge_scene_index.py，字段才进入检索用的聚合索引。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    from . import kb_index
    from .paragraph_density import _is_metadata_block
except ImportError:
    import kb_index
    from paragraph_density import _is_metadata_block

KB_ROOT = Path(__file__).resolve().parent.parent

FIELDS = ("original_lang", "narrative_person", "register", "dialogue_ratio")

# narrative_person：引号外第一人称代词密度。中文按每千个汉字计"我"（含"我们"），
# 英文按每千词计 I/me/my/mine/myself。达到 FIRST 判 first，低于 THIRD 判 third，之间判 mixed。
ZH_FIRST_PER_1K = 8.0
ZH_THIRD_BELOW_PER_1K = 2.0
EN_FIRST_PER_1K = 15.0
EN_THIRD_BELOW_PER_1K = 4.0
# 密度达到 first 的场景再看段落：引号外有第一人称的段落占"有人称段落"的比例低于此值记 mixed。
# 第三人称叙述里嵌一封第一人称书信（I Am Legend S10 0.38、信 S21 0.19、红与黑 S27 0.41）会被整场密度
# 判成 first，段落占比能把它们分出来；真正的第一人称叙述（挪威的森林、简·爱、流浪地球）最低 0.6，
# 旁观者叙述（月亮与六便士 S07）0.48，2026-10-15 按现库标定。有人称段落少于 MIN 段时不看占比。
FIRST_PARAGRAPH_SHARE = 0.45
FIRST_PARAGRAPH_MIN = 6

# register 合成：每项先截断到 [low, high] 线性映射为 0–1（句长取反向），再加权求和；
# 合成分 ≥ COLLOQUIAL_AT 判 colloquial，≤ LITERARY_AT 判 literary，之间判 mixed。
# 口语标记只数引号外的叙述：对白另由 dialogue_ratio 计入，金庸、三体这类对白多的场景
# 若连对白里的"呢""吧"一起数，叙述再书面也会被推成口语。句长按"。！？"切，口语独白常是
# 逗号连缀的长句（穿越东汉末年中位约 40 字），区分力弱，权重最低。
# 2026-10-15 按 14 部中文原作 442 场标定：现库 first/colloquial 约 6 场、first/literary 36、
# third/colloquial 25、third/literary 216，与设计 §5.2 的估算同量级；穿越东汉末年全文按
# 50 行一段切块，41 块里 39 块判 colloquial。
REGISTER_LANGS = {"zh"}
ZH_COLLOQUIAL_CHARS = "呢吧嘛啦呀啊哎呗咯喽噢哇哟嗯啥咋俺咱甭瞅"
ZH_COLLOQUIAL_WORDS = ("反正", "然后", "玩意", "这块", "那块", "说白了", "一块儿")
MARKER_RANGE = (1.0, 8.0)          # 叙述里每千字口语标记
DIALOGUE_RANGE = (0.10, 0.50)
SENTENCE_LEN_RANGE = (18.0, 40.0)  # 平均句长（汉字）；越短越口语
REGISTER_WEIGHTS = {"markers": 0.6, "dialogue": 0.25, "sentence": 0.15}
COLLOQUIAL_AT = 0.45
LITERARY_AT = 0.25

QUOTE_SPAN = re.compile(
    r"“[^“”]{0,1500}”|「[^「」]{0,1500}」|『[^『』]{0,1500}』|\"[^\"\n]{0,1500}\""
)
HAN =re.compile(r"[㐀-鿿豈-﫿]")
EN_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
EN_FIRST = re.compile(r"\b(?:I|me|my|mine|myself|Me|My|Mine|Myself)\b")
EN_THIRD = re.compile(r"\b(?:he|she|him|her|his|hers|He|She|Him|Her|His|Hers)\b")
SENTENCE_END = re.compile(r"[。！？!?…]+|\n+")
SPEAKER_LINE = re.compile(r"^[\s　]*[^\s　：:（(]{1,12}[\s　]*[：:　]")

# 作者 → 原作语言，供 --prefill-original-lang 判断译本；表外作者的 zh 文本按中文原作预填并提示核对。
AUTHOR_ORIGINAL_LANG = {
    "罗贝托·波拉尼奥": "es",
    "东野圭吾": "ja",
    "乔治·R·R·马丁": "en",
    "J.R.R.托尔金": "en",
    "村上春树": "ja",
    "约翰·威廉斯": "en",
    "毛姆": "en",
    "汉斯·克里斯蒂安·安徒生": "da",
    "科马克·麦卡锡": "en",
    "威廉·莎士比亚": "en",
    "William Shakespeare": "en",
    "Richard Matheson": "en",
    "司汤达": "fr",
    "夏洛蒂·勃朗特": "en",
}


@dataclass
class SceneFeatures:
    lang: str
    body_units: int          # 中文为汉字数，英文为词数
    narration_units: int
    first_person_per_1k: float   # 引号外，每千字（词）
    first_paragraphs: int        # 引号外有第一人称的段落数
    third_paragraphs: int        # 引号外只有第三人称、没有第一人称的段落数
    dialogue_ratio: float
    markers_per_1k: float        # 引号外口语标记，每千字
    mean_sentence_len: float


def body_text(text: str) -> str:
    """去掉场景文件头部与分隔行（注释、标题、出处行、---），只留正文。"""
    kept = [line for line in text.splitlines() if line.strip() and not _is_metadata_block(line)]
    return "\n".join(kept)


def split_quoted(text: str) -> tuple[str, str]:
    """返回 (引号外文字, 引号内文字)。

    中文引号按成对匹配，可跨行（有的译本逐句断行，一句对白跨两三行）；跨段多段对白只有末段
    闭合，前几段按引号外计，宁可少算对白也不让一处未闭合吞掉整场。英文直引号只在同一行内配对。
    """
    inside = [m.group(0)[1:-1] for m in QUOTE_SPAN.finditer(text)]
    return QUOTE_SPAN.sub("\n", text), "".join(inside)


def _units(text: str, lang: str) -> int:
    return len(EN_WORD.findall(text)) if lang == "en" else len(HAN.findall(text))


def _per_1k(count: int, units: int) -> float:
    return round(count * 1000 / units, 2) if units else 0.0


def _mean_sentence_len(text: str, lang: str) -> float:
    sentences = [s for s in SENTENCE_END.split(text) if s.strip()]
    lengths = [_units(s, lang) for s in sentences]
    lengths = [n for n in lengths if n > 0]
    return round(sum(lengths) / len(lengths), 2) if lengths else 0.0


def paragraph_person(paragraph: str, lang: str) -> str | None:
    """单段叙述的人称：引号外有第一人称为 first，只有第三人称为 third，都没有为 None。"""
    narration, _ = split_quoted(paragraph)
    if lang == "en":
        if EN_FIRST.search(narration):
            return "first"
        return "third" if EN_THIRD.search(narration) else None
    if "我" in narration:
        return "first"
    return "third" if ("他" in narration or "她" in narration) else None


def features(text: str, lang: str, *, drama: bool = False) -> SceneFeatures:
    body = body_text(text)
    lang = "en" if lang == "en" else "zh"
    if drama:
        lines = [line for line in body.split("\n") if line.strip()]
        spoken = [line for line in lines if SPEAKER_LINE.match(line)]
        total = sum(_units(line, lang) for line in lines)
        dialogue_units = sum(_units(line, lang) for line in spoken)
        narration, quoted = body, ""
    else:
        narration, quoted = split_quoted(body)
        total = _units(body, lang)
        dialogue_units = _units(quoted, lang)
    narration_units = _units(narration, lang)
    if lang == "en":
        first = len(EN_FIRST.findall(narration))
        markers = 0
    else:
        first = narration.count("我")
        markers = (sum(narration.count(ch) for ch in ZH_COLLOQUIAL_CHARS)
                   + sum(narration.count(word) for word in ZH_COLLOQUIAL_WORDS))
    persons = [] if drama else [paragraph_person(p, lang) for p in body.split("\n") if p.strip()]
    return SceneFeatures(
        lang=lang,
        body_units=total,
        narration_units=narration_units,
        first_person_per_1k=_per_1k(first, narration_units),
        first_paragraphs=persons.count("first"),
        third_paragraphs=persons.count("third"),
        dialogue_ratio=round(dialogue_units / total, 3) if total else 0.0,
        markers_per_1k=_per_1k(markers, narration_units),
        mean_sentence_len=_mean_sentence_len(body, lang),
    )


def classify_person(feat: SceneFeatures) -> str:
    first_at, third_below = (
        (EN_FIRST_PER_1K, EN_THIRD_BELOW_PER_1K) if feat.lang == "en"
        else (ZH_FIRST_PER_1K, ZH_THIRD_BELOW_PER_1K)
    )
    if feat.first_person_per_1k >= first_at:
        voiced = feat.first_paragraphs + feat.third_paragraphs
        if voiced >= FIRST_PARAGRAPH_MIN and feat.first_paragraphs / voiced < FIRST_PARAGRAPH_SHARE:
            return "mixed"  # 第三人称叙述里嵌了第一人称书信或独白
        return "first"
    if feat.first_person_per_1k < third_below:
        return "third"
    return "mixed"


def _scale(value: float, low: float, high: float) -> float:
    return min(max((value - low) / (high - low), 0.0), 1.0)


def register_score(feat: SceneFeatures) -> float:
    parts = {
        "markers": _scale(feat.markers_per_1k, *MARKER_RANGE),
        "dialogue": _scale(feat.dialogue_ratio, *DIALOGUE_RANGE),
        "sentence": 1.0 - _scale(feat.mean_sentence_len, *SENTENCE_LEN_RANGE),
    }
    return round(sum(REGISTER_WEIGHTS[k] * v for k, v in parts.items()), 3)


def classify_register(feat: SceneFeatures) -> str | None:
    if feat.lang not in REGISTER_LANGS:
        return None
    score = register_score(feat)
    if score >= COLLOQUIAL_AT:
        return "colloquial"
    if score <= LITERARY_AT:
        return "literary"
    return "mixed"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[register] 无法读取 {path}: {exc}", file=sys.stderr)
        return {}
    return value if isinstance(value, dict) else {}


def work_profile(work_dir: Path) -> dict:
    """作品级输入：原作语言、文本语言与人称覆盖。style_card 优先，戏剧缺卡时读 work-meta。"""
    card = _read_yaml(work_dir / "style_card.yaml")
    meta = _read_yaml(work_dir / "work-meta.yaml")
    override = card.get("narrative_person_override")
    return {
        "original_lang": card.get("original_lang") or meta.get("original_language"),
        "text_lang": card.get("lang") or card.get("language") or meta.get("language"),
        "person_override": override if override in {"first", "third", "mixed"} else None,
    }


def annotate_work(index_path: Path, *, dry_run: bool = False) -> list[dict]:
    work_dir = index_path.parent
    drama = kb_index.medium_of(index_path) == "drama"
    profile = work_profile(work_dir)
    entries = kb_index.load_index(index_path)
    for entry in entries:
        scene_path = work_dir / entry.get("file", "")
        if not entry.get("file") or not scene_path.is_file():
            print(f"[register] {work_dir.name}·{entry.get('scene_id')}: 场景文件缺失，跳过", file=sys.stderr)
            continue
        lang = entry.get("lang") or entry.get("language") or profile["text_lang"] or "zh"
        feat = features(scene_path.read_text(encoding="utf-8"), lang, drama=drama)
        if drama:
            person = None
        else:
            person = profile["person_override"] or classify_person(feat)
        entry["original_lang"] = profile["original_lang"]
        entry["narrative_person"] = person
        entry["register"] = None if drama else classify_register(feat)
        entry["dialogue_ratio"] = feat.dialogue_ratio
    if not dry_run:
        kb_index.save_index(index_path, entries)
    return entries


def prefill_decision(card: dict) -> tuple[str | None, str]:
    """返回 (原作语言, 依据)；判断不了时返回 (None, 原因)。"""
    text_lang = card.get("lang") or card.get("language")
    author = str(card.get("author") or "").strip()
    if author in AUTHOR_ORIGINAL_LANG:
        return AUTHOR_ORIGINAL_LANG[author], f"作者表：{author}"
    if text_lang == "zh" and not card.get("translator"):
        return "zh", f"中文文本、作者 {author or '未写'} 不在译本作者表、无译者"
    if text_lang and text_lang != "zh":
        return text_lang, f"文本语言 {text_lang}，按原文预填"
    return None, f"文本语言 {text_lang!r}、作者 {author!r}、译者 {card.get('translator')!r}，无法判断"


def _insert_original_lang(text: str, value: str) -> str:
    """在 lang/language 行后插入一行，保留文件其余排版；找不到则追加在末尾。"""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.match(r"^(lang|language):", line):
            lines.insert(i + 1, f"original_lang: {value}\n")
            return "".join(lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return "".join(lines) + f"original_lang: {value}\n"


def prefill_original_lang(kb_root: Path, *, dry_run: bool = False) -> int:
    unresolved = 0
    for container in kb_index.CONTAINER_DIRS:
        base = kb_root / container
        if not base.is_dir():
            continue
        for work_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            card_path = work_dir / "style_card.yaml"
            if not card_path.exists():
                continue
            card = _read_yaml(card_path)
            if card.get("original_lang"):
                print(f"  = {container}/{work_dir.name}: 已有 original_lang={card['original_lang']}")
                continue
            value, reason = prefill_decision(card)
            if value is None:
                unresolved += 1
                print(f"  ? {container}/{work_dir.name}: {reason}", file=sys.stderr)
                continue
            print(f"  + {container}/{work_dir.name}: original_lang={value}（{reason}）")
            if not dry_run:
                card_path.write_text(
                    _insert_original_lang(card_path.read_text(encoding="utf-8"), value), encoding="utf-8")
    return 1 if unresolved else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="场景人称、语域与对白占比标注（零 API）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true", help="标注全库作品")
    mode.add_argument("--work", action="append", help="按作品目录名标注，可重复")
    mode.add_argument("--prefill-original-lang", action="store_true",
                      help="为缺 original_lang 的 style_card 预填并打印依据，供作者核对")
    parser.add_argument("--kb", default=str(KB_ROOT))
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写回")
    args = parser.parse_args(argv)

    kb_root = Path(args.kb)
    if args.prefill_original_lang:
        return prefill_original_lang(kb_root, dry_run=args.dry_run)

    if args.all:
        paths = kb_index.iter_work_indexes(kb_root)
    else:
        paths = []
        for work in args.work:
            path = kb_index.find_index_path(kb_root, work)
            if path is None:
                print(f"[register] 找不到作品索引: {work}", file=sys.stderr)
                return 2
            paths.append(path)

    missing_lang: list[str] = []
    for path in paths:
        entries = annotate_work(path, dry_run=args.dry_run)
        if entries and not entries[0].get("original_lang"):
            missing_lang.append(path.parent.name)
        counts: dict[tuple, int] = {}
        for e in entries:
            key = (e.get("narrative_person"), e.get("register"))
            counts[key] = counts.get(key, 0) + 1
        summary = "、".join(f"{p or '-'}/{r or '-'}×{n}" for (p, r), n in sorted(counts.items(), key=str))
        print(f"  {path.parent.parent.name}/{path.parent.name}: {len(entries)} 场 {summary}")
    if missing_lang:
        print(f"[register] 缺 original_lang（先补 style_card）：{'、'.join(missing_lang)}", file=sys.stderr)
    if not args.dry_run:
        print("[register] 已写回每作品索引；运行 merge_scene_index.py 同步聚合索引")
    return 1 if missing_lang else 0


if __name__ == "__main__":
    raise SystemExit(main())
