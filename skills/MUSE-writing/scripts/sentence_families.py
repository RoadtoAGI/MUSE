#!/usr/bin/env python3
"""逐句家族：只看句子表面形态定位口癖，不做语义裁量。

家族的策略（逐句单发，或只做整篇密度）在 ai_policy.py；本文件只给形态定义。
定义取自 AI 口癖治理升级设计 §5.2 的研究脚本，校准记录在 ai_policy.PROMOTION_RECORDS。

计数口径：
- 句：句号、问号、叹号之间的文字；台词去掉引号后照样计入。couplet_fragment 只取引号外的叙述。
- 分句：句内逗号、顿号、分号、冒号、破折号、省略号与空白之间的文字；“她说”“他问”一类说话标签不算分句。
- 长度：只数汉字。
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

CJK_RE = re.compile(r"[一-鿿]")
QUOTE_SPAN_RE = re.compile(r"“[^“”]*”|「[^「」]*」|『[^『』]*』|\"[^\"\n]*\"")
QUOTE_CHARS_RE = re.compile(r"[“”「」『』\"*]")
QUOTE_ANY_RE = re.compile(r"[“”「」『』\"]")
SENTENCE_RE = re.compile(r"[^。！？]*[。！？]+|[^。！？]+$")
CLAUSE_SPLIT_RE = re.compile(r"[，、；：—…\s]+")
SPEECH_TAG_RE = re.compile(r"^[一-鿿]{0,6}(说|问|道|答|喊|应|补了一句|又说)$")


def cjk(text: str) -> int:
    return len(CJK_RE.findall(text))


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int
    text: str  # 去掉引号与星号后的句子


def sentences(text: str, *, narration_only: bool = False) -> list[Sentence]:
    """按句切分并保留原文偏移；跳过 Markdown 标题行。"""
    out: list[Sentence] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        body = line.rstrip("\n")
        if body.lstrip().startswith("#"):
            continue
        segments = [(0, len(body))]
        if narration_only:
            segments, cur = [], 0
            for m in QUOTE_SPAN_RE.finditer(body):
                segments.append((cur, m.start()))
                cur = m.end()
            segments.append((cur, len(body)))
        for seg_start, seg_end in segments:
            for m in SENTENCE_RE.finditer(body[seg_start:seg_end]):
                raw = m.group()
                cleaned = QUOTE_CHARS_RE.sub("", raw).strip()
                if not cjk(cleaned):
                    continue
                lead = len(raw) - len(raw.lstrip(" \t　”」』\"*"))
                start = line_start + seg_start + m.start() + lead
                end = line_start + seg_start + m.end()
                out.append(Sentence(start, end, cleaned))
    return out


def clauses(sentence_text: str) -> list[str]:
    parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(re.sub(r"[。！？]", "", sentence_text)) if cjk(p)]
    return [p for p in parts if not SPEECH_TAG_RE.match(p)]


def _hit(text: str, rule: str, pattern: str, start: int, end: int) -> dict:
    return {
        "rule": rule,
        "pattern": pattern,
        "location": f"L{text.count(chr(10), 0, start) + 1}",
        "snippet": text[start:end][:100],
        "span": text[start:end],
        "start": start,
        "end": end,
        "confidence": "high",
        "severity": "medium",
    }


# ---------- 姿态句 ----------

def detect_couplet_fragment(text: str) -> list[dict]:
    """短对句：叙述里整句不超过 12 字，至少两个分句，末分句不超过 4 字（"是纸，湿的。"）。"""
    hits = []
    for s in sentences(text, narration_only=True):
        parts = clauses(s.text)
        if len(parts) >= 2 and cjk(s.text) <= 12 and cjk(parts[-1]) <= 4:
            hits.append(_hit(text, "couplet_fragment", "short_couplet", s.start, s.end))
    return hits


ECHO_NEGATION_RE = re.compile(r"(没有?人?|不)(接|改口|复述|回答|应声|说话|开口|动|抬头|回头|提)了?。?$")


def detect_echo_negation(text: str) -> list[dict]:
    """回声否定：句末对前一动作作否定回应（"没有人复述。""没有改口。"）。"""
    return [
        _hit(text, "echo_negation", "echo_negation", s.start, s.end)
        for s in sentences(text)
        if ECHO_NEGATION_RE.search(s.text)
    ]


NEGATION_CLAUSE_RE = re.compile(r"(?:^|，)(没有?|不|未)[一-鿿]{1,5}(?=，|。|$)")
# 原 parallel_negation 的否定清单形态，逐 pattern 迁入
NEGATION_LIST_PATTERNS = [
    ("没有A没有B", re.compile(r"没有[^，。]{1,15}，(?:甚至)?没有[^，。]{1,15}")),
    ("不是A不是B", re.compile(r"不是[^，。]{1,15}，不是[^，。]{1,15}")),
]


def detect_negation_list(text: str) -> list[dict]:
    """否定清单：一句里两个以上以没、没有、不、未开头的短分句并列（"没卷，没挪，有人守着。"）。"""
    hits = []
    for s in sentences(text):
        if len(NEGATION_CLAUSE_RE.findall(s.text)) >= 2:
            hits.append(_hit(text, "negation_list", "short_negation_run", s.start, s.end))
            continue
        for label, pattern in NEGATION_LIST_PATTERNS:
            if pattern.search(s.text):
                hits.append(_hit(text, "negation_list", label, s.start, s.end))
                break
    return hits


MIRRORED_PAIR_RE = re.compile(r"([一-鿿])是[^，]{0,3}的\1|([一-鿿]{1,2})没\2")


def detect_mirrored_pair(text: str) -> list[dict]:
    """同字对举："卡是我的卡""取没取，上没上"。"有没有"一类正反问不计。"""
    hits = []
    for s in sentences(text):
        if any(m.group(2) != "有" for m in MIRRORED_PAIR_RE.finditer(s.text)):
            hits.append(_hit(text, "mirrored_pair", "mirrored_pair", s.start, s.end))
    return hits


def detect_single_sentence_paragraph(text: str) -> list[dict]:
    """叙述单句成段：段落只有一句且不超过 12 字，段内没有引语（"石秋准等着。"）。"""
    hits = []
    pos = 0
    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        para = line.strip()
        if not para or para.startswith("#") or QUOTE_ANY_RE.search(para):
            continue
        parts = [x for x in re.split(r"(?<=[。！？])", para) if cjk(x)]
        if len(parts) == 1 and cjk(para) <= 12:
            start = line_start + line.index(para)
            hits.append(_hit(text, "single_sentence_paragraph", "single_sentence_paragraph", start, start + len(para)))
    return hits


NUM = r"[零〇一二两三四五六七八九十百千\d]+"
TIME_RE = re.compile(rf"{NUM}[点时]{NUM}分(?:{NUM}秒)?|{NUM}分{NUM}秒|{NUM}[点时]{NUM}|{NUM}(?:点|时)(?:半|整)?")
MEASURE_RE = re.compile(rf"{NUM}(?:点{NUM})?(?:公斤|克|厘米|毫米|米|度|分钟|秒)")
# 副词与书名里的同形：有一点、一时语塞、一度、《凌晨三点》
NUMBER_NOT_EXPRESSIONS = {"一点", "一时", "一度"}
BOOK_TITLE_RE = re.compile(r"《[^》]*》")
PRECISE_NUMBER_REPEAT_GTE = 3


def detect_precise_number_repeat(text: str) -> list[dict]:
    """精确数字反复：同一时刻或计量表达在一次检查的正文里出现 3 次以上，逐处标记。

    计数范围是传入的整段文本：逐场检查是一场，短篇全文模式是整篇。校准按同一范围计
    （AI 稿按篇、人类小说按约 3,000 字片段），183 与留出稿 02、03 在这一范围下零命中。
    """
    titles = [(m.start(), m.end()) for m in BOOK_TITLE_RE.finditer(text)]
    found: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for pattern in (TIME_RE, MEASURE_RE):
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if m.group() in NUMBER_NOT_EXPRESSIONS:
                continue
            if any(a <= span[0] < b for a, b in titles):
                continue
            if any(span[0] < b and a < span[1] for a, b in occupied):
                continue
            occupied.append(span)
            found.append((m.start(), m.end(), m.group()))
    counts = Counter(expr for _, _, expr in found)
    return [
        _hit(text, "precise_number_repeat", expr, start, end)
        for start, end, expr in sorted(found)
        if counts[expr] >= PRECISE_NUMBER_REPEAT_GTE
    ]


# ---------- 说破 ----------

ABSTRACT_CLASSIFIER_RE = re.compile(r"一种|那种|某种")


def detect_abstract_classifier(text: str) -> list[dict]:
    """抽象框定词：裸词一种、那种、某种（"生出一种卑微的羡慕"）。"""
    return [
        _hit(text, "abstract_classifier", m.group(), m.start(), m.end())
        for m in ABSTRACT_CLASSIFIER_RE.finditer(text)
    ]


# ---------- 填充 ----------

BODY_CLOSEUP_RE = re.compile(r"指腹|指节|喉结|笔尖|压住|按住|扶住|托住|[停顿静]了一下|沉默了|愣住")
V_YIXIA_RE = re.compile(r"([一-鿿]{1,2})了一下(?=[。！])")


def _is_verb_before(clause: str) -> bool:
    import jieba.posseg as pseg  # 词性只在命中候选时才需要

    jieba_quiet()
    words = list(pseg.cut(clause))
    return bool(words) and words[-1].flag.startswith("v")


def jieba_quiet() -> None:
    import jieba

    jieba.setLogLevel(60)


def detect_body_closeup_filler(text: str) -> list[dict]:
    """身体特写与停顿套语：指腹、笔尖、压住/按住、停了一下、沉默了、愣住，以及句末的"V 了一下。"。"""
    hits = []
    occupied: list[tuple[int, int]] = []
    for m in BODY_CLOSEUP_RE.finditer(text):
        occupied.append((m.start(), m.end()))
        hits.append(_hit(text, "body_closeup_filler", m.group(), m.start(), m.end()))
    for m in V_YIXIA_RE.finditer(text):
        if any(m.start() < b and a < m.end() for a, b in occupied):
            continue
        head = text[max(0, m.start() - 6):m.end(1)]
        head = re.split(r"[，。！？；：、“”「」\s]", head)[-1]
        if head and _is_verb_before(head):
            start = m.end(1) - len(m.group(1))
            hits.append(_hit(text, "body_closeup_filler", "V了一下", start, m.end()))
    return sorted(hits, key=lambda h: h["start"])


STIFF_ADVERB_RE = re.compile(r"仍(?![然旧])")


def detect_stiff_adverb(text: str) -> list[dict]:
    """书面虚词"仍"（不含仍然、仍旧）。"""
    return [_hit(text, "stiff_adverb", "仍", m.start(), m.end()) for m in STIFF_ADVERB_RE.finditer(text)]


# ---------- 同声（英文） ----------

RATHER_STANCE_RE = re.compile(r"\b(?:I'd rather|I would rather|I'd sooner)\b|\brather [^.!?]{1,60} than\b", re.I)


def detect_rather_stance_en(text: str) -> list[dict]:
    """英文 rather 句式："I'd rather …""rather … than"。"""
    return [_hit(text, "rather_stance_en", "rather", m.start(), m.end()) for m in RATHER_STANCE_RE.finditer(text)]


DETECTORS_ZH = {
    "couplet_fragment": detect_couplet_fragment,
    "echo_negation": detect_echo_negation,
    "negation_list": detect_negation_list,
    "mirrored_pair": detect_mirrored_pair,
    "single_sentence_paragraph": detect_single_sentence_paragraph,
    "precise_number_repeat": detect_precise_number_repeat,
    "abstract_classifier": detect_abstract_classifier,
    "body_closeup_filler": detect_body_closeup_filler,
    "stiff_adverb": detect_stiff_adverb,
}
DETECTORS_EN = {
    "rather_stance_en": detect_rather_stance_en,
}
