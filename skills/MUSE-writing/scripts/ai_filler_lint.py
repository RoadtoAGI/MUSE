#!/usr/bin/env python3
"""S1 — AI 口癖 / 禁用 Markdown / 排比模板 / 关联词 lint。

覆盖 55+1 条清单第 3/7/46/47/49 条。脚本不调 LLM，纯正则/词表。
"""
from __future__ import annotations
import argparse
import hashlib
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

import yaml

from ai_policy import (
    AGGREGATION_ONLY_RULES,
    FAMILY_CLUSTERS,
    FAMILY_GROUPS,
    FAMILY_REGISTRY,
    RULE_TO_FAMILY,
    calibration_value,
    effective_policy,
)


@dataclass(frozen=True)
class Thresholds:
    # short_paragraph_run
    short_paragraph_max_chars: int = 12
    short_paragraph_max_sentences: int = 2
    short_paragraph_run_severe: int = 2
    # clause_fragment_density
    clause_fragment_min_paragraph_chars: int = 60
    clause_fragment_min_clauses: int = 6
    clause_fragment_avg_chars_lte: int = 8
    clause_fragment_short_chars_lte: int = 8
    clause_fragment_short_ratio_gte: float = 0.70
    # dash_density
    dash_density_min_paragraph_chars: int = 40
    dash_density_medium_gte: int = 3
    dash_density_high_gte: int = 4
    # repeated_clause_head
    repeated_head_verb_advisory_gte: int = 2
    repeated_head_verb_standalone_gte: int = 3
    repeated_head_noun_advisory_gte: int = 2
    repeated_head_noun_standalone_gte: int = 3
    repeated_head_pronoun_run_gte: int = 3
    repeated_head_prep_run_gte: int = 3
    # micro_action_density
    micro_action_min_paragraph_chars: int = 80
    micro_action_count_gte: int = 5
    micro_action_unique_gte: int = 3
    # English profile
    en_em_dash_paragraph_min_words: int = 30
    en_em_dash_medium_gte: int = 2
    en_em_dash_high_gte: int = 3
    en_em_dash_per_1k_words_gte: float = 4.0
    en_staccato_sentence_max_words: int = 4
    en_staccato_run_gte: int = 3
    en_simile_per_1k_words_gte: float = 5.0


_THRESHOLD_PROFILES = {
    "conservative": Thresholds(),
    "strict": Thresholds(
        clause_fragment_min_paragraph_chars=45,
        clause_fragment_min_clauses=5,
        clause_fragment_avg_chars_lte=9,
        clause_fragment_short_ratio_gte=0.60,
        dash_density_min_paragraph_chars=30,
        dash_density_medium_gte=2,
        dash_density_high_gte=3,
        repeated_head_verb_advisory_gte=2,
        repeated_head_verb_standalone_gte=2,
        repeated_head_pronoun_run_gte=3,
        micro_action_min_paragraph_chars=60,
        micro_action_count_gte=4,
    ),
}

UNIFORM_RHYTHM_CV_FLOOR: dict[str, float] = {
    "zh": 0.4951,
    "en": 0.0,
}

KEYWORD_CLICHE_PATTERNS = [
    "只见", "就在这时", "片刻后", "随即", "于是", "因此",
    "不由得", "不禁", "似乎", "仿佛", "好像",
    "极", "格外", "稍稍",
]

# meta_language_leak seed lexicons: design §2.2, sourced from the low-score audit
# sample and filtered aigc-detector template/hedging lists.
META_LANGUAGE_ZH = (
    "综上所述",
    "值得注意的是",
    "需要指出的是",
    "不难发现",
    "由此可见",
    "总的来说",
    "换言之",
    "综合来看",
)

META_LANGUAGE_EN = (
    "it is worth noting",
    "it should be noted",
    "it is important to note",
    "in conclusion",
    "as previously mentioned",
    "firstly, ... secondly",
    "to summarize",
)

# 命中位置周围 2 字内若构成词内成分则跳过——这些词不属于副词口癖的检测对象。
KEYWORD_CLICHE_OUT_OF_SCOPE_CONTEXTS = {
    "极": [
        "北极", "南极", "太极", "积极", "消极", "两极", "终极", "至极",
        "极地", "极光", "极圈", "极昼", "极夜", "极乐", "极端", "极简",
        "极限", "极致", "极点",
    ],
}

CONJUNCTION_PATTERNS = [
    (r"虽然[^。]{1,40}但是", "虽然…但是"),
    (r"尽管[^。]{1,40}却", "尽管…却"),
    (r"并不[^，。]{1,20}却", "并不…却"),
    (r"(?:^|。)\s*然后", "段首然后"),
]

PARALLEL_NEGATION_PATTERNS = [
    (r"没有[^，。]{1,15}，没有[^，。]{1,15}(?!，只有)", "没有A没有B"),
    (r"没有[^，。]{1,15}，没有[^，。]{1,15}，只有[^，。]{1,15}", "没有A没有B只有C"),
    (r"没有[^，。]{1,15}，甚至没有[^，。]{1,15}", "没有A甚至没有B"),
    (r"不是[^，。]{1,15}，而是[^，。]{1,15}", "不是A而是B"),
    (r"不是[^，。]{1,15}，不是[^，。]{1,15}", "不是A不是B"),
    (r"不是[^，。]{1,15}，(?!而是|不是|只是)是[^，。]{1,15}", "不是A是B"),
    (r"不是[^，。—]{1,15}——是[^，。]{1,15}", "不是A——是B"),
    (r"不是[^，。]{1,15}，只是[^，。]{1,15}", "不是A只是B"),
    (r"是[^，。]{1,15}的，不是[^，。]{1,15}", "是A的不是B"),
    (r"没有[^，。]{1,15}，(?!没有|甚至|只有)是[^，。]{1,15}", "没有A是B"),
    (r"没有[^，。]{1,15}，只是[^，。]{1,15}", "没有A只是B"),
    (r"并非[^，。]{1,15}，(?:而是|是)[^，。]{1,15}", "并非A是B"),
    (r"并不[^，。]{1,15}，却[^，。]{1,15}", "并不A却B"),
]
PARALLEL_NEGATION_SOFT_PATTERNS = {
    "没有A是B", "没有A只是B", "并非A是B",
}

CONTRASTIVE_NEGATION_PATTERNS = [
    (r"不是因为[^，。]{1,15}，而是因为[^，。]{1,15}", "不是因为X而是因为Y"),
    (r"不是因为[^，。]{1,15}，是因为[^，。]{1,15}", "不是因为X是因为Y"),
    (r"真正的不是[^，。]{1,15}，是[^，。]{1,15}", "真正的不是A是B"),
    (r"不是(?!因为)[^，。]{1,15}，而是[^，。]{1,15}", "不是A而是B"),
    (r"不是(?!因为)[^，。]{1,15}，是[^，。]{1,15}", "不是A是B"),
    (r"并非[^，。]{1,15}，是[^，。]{1,15}", "并非A是B"),
    (r"没有[^，。]{1,15}，(是|只是)[^，。]{1,15}", "没有A是B"),
    (r"表面[^，。]{1,15}，实际[^，。]{1,15}", "表面A实际B"),
    # 光杆否定 + 限缩转折（"不掰开，只是裹住" / "没说话，只是看着"）——
    # 不是/没有 系由上方 pattern 承接，这里只接光杆 不/没 起手
    (r"不(?!是)[一-鿿]{1,5}[，,]\s*只(?:是|有)?[一-鿿]{1,15}", "不X只Y"),
    (r"没(?!有)[一-鿿]{1,5}[，,]\s*只(?:是|有)?[一-鿿]{1,15}", "没X只Y"),
]

COUNTED_SPEECH_PATTERN = re.compile(
    r"(只说了|说了|吐出|报了)(一|二|两|三|四|五|六|七|八|九|十|\d+)(个)?字"
)

ORDINAL_GRAVITY_PATTERN = re.compile(
    r"(第一次|最后一次|这一刻|这一日|这一击|这一息|这一次|今天第一次)"
)

STATE_PERSISTENCE_PATTERN = re.compile(
    r"(?P<anchor>[一-龥A-Za-z0-9_]{1,8}?)(?P<state>还在那里|还在|仍然在|仍在|一直在|没有变|空着|到位|守住)"
)

CHANGE_DELTA_VERBS = ("变", "歪", "倒", "断", "落", "塌", "散", "起", "开", "合", "动")

# 动词起手词表（2-3 字组合，高 AI 信号）
REPEATED_HEAD_VERB_HEADS = (
    "想到", "想起", "记起", "看见", "看到", "听见", "听到", "闻到",
    "走到", "走过", "回到", "回来", "来到", "经过",
    "发现", "意识到", "感到", "感觉到", "觉得",
    "抬头", "低头", "转身", "回头", "伸手", "抬手", "收回",
)
REPEATED_HEAD_PRONOUNS = ("他们", "她们", "我们", "你们", "他", "她", "我", "你", "它")
REPEATED_HEAD_PREPS = ("在", "从", "向", "把", "对", "往", "朝", "由", "被")

# 微动作链密度：词表克制版（高信号动作）
MICRO_ACTION_TOKENS = (
    "走到", "转身", "回头", "低头", "抬头",
    "推开", "拉开", "拿起", "放下",
    "看了看", "听了听", "停下",
    "放进", "塞进", "摸出", "翻开", "翻找",
    "关上", "合上",
)
# 危险词：动作戏 / 逃亡 / 战斗合法高动作密度，命中则降 severity
MICRO_ACTION_DANGER_TOKENS = (
    "刀", "枪", "血",
    "撞上", "撞开", "撞倒",
    "爆炸", "爆开", "爆响",
    "咬", "砍", "踢",
    "追上", "追来", "追过去", "被追",
    "闪过", "闪开", "躲开", "躲过", "躲到",
    "出拳",
)

MARKDOWN_PATTERNS = [
    (r"^#{1,6}\s", "标题"),
    (r"^\d+[\.、]\s", "有序列表"),
    (r"^[-*]\s", "无序列表"),
    (r"\*\*[^*]+\*\*", "加粗"),
    (r"^【[^】]+】", "段首方括号"),
]


def _locate(text: str, pos: int) -> str:
    return f"L{text.count(chr(10), 0, pos) + 1}"


def detect_lang(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return "zh"
    cjk = len(re.findall(r"[\u4e00-\u9fff]", compact))
    return "zh" if cjk / len(compact) > 0.3 else "en"


def _normalize_lang(text: str, lang: str) -> str:
    if lang == "auto":
        return detect_lang(text)
    if lang not in {"zh", "en"}:
        raise ValueError(f"Unsupported lang: {lang}")
    return lang


def _resolve_device_budget(
    devices: Iterable[str],
    lang: str,
) -> tuple[dict[str, float], list[str]]:
    multipliers: dict[str, float] = {}
    valid_devices: list[str] = []
    for raw_device in devices:
        device = str(raw_device).strip()
        if not device:
            continue
        budget = {
            family: float(policy["device_budget"][device])
            for family in FAMILY_REGISTRY
            if (
                (policy := effective_policy(family, lang)).get("lifecycle") == "enforced"
                and device in policy.get("device_budget", {})
            )
        }
        if not budget:
            print(f"[ai_filler_lint] WARN: unknown literary_device ignored: {device}", file=sys.stderr)
            continue
        valid_devices.append(device)
        for family, multiplier in budget.items():
            multipliers[family] = max(multipliers.get(family, 1.0), multiplier)
    return multipliers, valid_devices


def _mask_chars(chars: list[str], start: int, end: int) -> None:
    for idx in range(start, end):
        if chars[idx] != "\n":
            chars[idx] = " "


def _mask_quoted_spans(text: str) -> str:
    chars = list(text)
    spans: list[tuple[int, int]] = []
    for open_quote, close_quote in (("「", "」"), ("『", "』"), ("“", "”")):
        pos = 0
        while True:
            start = text.find(open_quote, pos)
            if start < 0:
                break
            end = text.find(close_quote, start + len(open_quote))
            if end < 0:
                pos = start + len(open_quote)
                continue
            spans.append((start, end + len(close_quote)))
            pos = end + len(close_quote)

    pos = 0
    while True:
        start = text.find('"', pos)
        if start < 0:
            break
        end = text.find('"', start + 1)
        if end < 0:
            break
        spans.append((start, end + 1))
        pos = end + 1

    for start, end in spans:
        _mask_chars(chars, start, end)
    return "".join(chars)


def _meta_language_patterns(lang: str) -> list[tuple[str, re.Pattern[str]]]:
    if lang == "en":
        patterns = []
        for phrase in META_LANGUAGE_EN:
            if phrase == "firstly, ... secondly":
                pattern = r"\bfirstly\s*,[\s\S]{0,200}?\bsecondly\b"
            else:
                pattern = r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b"
            patterns.append((phrase, re.compile(pattern, flags=re.IGNORECASE)))
        return patterns
    return [(phrase, re.compile(re.escape(phrase))) for phrase in META_LANGUAGE_ZH]


# 叙述层碎片结算短句：叙述者用超短句替读者做情绪结算（名著 703 场景四形态 P90=0，
# 95% 场景零命中——单发即显著异常）。对白内不检测（引号 mask）；句号限定
# （叹号是对白/爆发腔的合法形态）。
FRAGMENT_SETTLEMENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("negation_dangling", re.compile(r"(?:^|[。！？\n])\s*(不是[一-鿿]{1,6})。")),
    ("binary_evaluative_pair", re.compile(r"(很[一-鿿]{1,3}[，,]很[一-鿿]{1,3})。")),
    ("self_assurance", re.compile(r"(?:^|[。！？\n])\s*(可以的|还来得及|来得及|够了|就这样|挺好)。")),
    ("commentary_settlement", re.compile(r"[，,]((?:倒|总归|也算)(?!了|下|出|在|进|退|水|茶|酒|地)[一-鿿]{1,4})。")),
]


def detect_fragment_settlement(text: str) -> list[dict]:
    family = RULE_TO_FAMILY["fragment_settlement"]
    masked = _mask_quoted_spans(text)
    hits = []
    for subform, pattern in FRAGMENT_SETTLEMENT_PATTERNS:
        for m in pattern.finditer(masked):
            start = m.start(1)
            hits.append({
                "rule": "fragment_settlement",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": subform,
                "location": _locate(text, start),
                "snippet": text[start:m.end(1)][:100],
                "span": text[start:m.end(1)],
                "start": start,
                "end": m.end(1),
                "confidence": "high",
                "severity": "medium",
            })
    return hits


# 碎切短分句链：叙述层同一句内连续 ≥2 个 ≤6 字逗号分句（"碰到空的，收回来，"）。
# 超短分句节拍连排检测器：保留 span 供语义复核，不直接立案。
# 对白不属于检测对象；顿号列举不切分；含冒号 / 破折号 / 省略号 / mask 残留的分句作链断点。
MICRO_CLAUSE_CHAIN_MIN_RUN = 2
MICRO_CLAUSE_CHAIN_MAX_CHARS = 6
_MICRO_CLAUSE_QUALIFY_RE = re.compile(r"[一-鿿0-9]{1,%d}" % MICRO_CLAUSE_CHAIN_MAX_CHARS)


def detect_micro_clause_chain(text: str) -> list[dict]:
    family = RULE_TO_FAMILY["micro_clause_chain"]
    masked = _mask_quoted_spans(text)
    hits = []

    def emit(run: list[tuple[int, int]]):
        if len(run) < MICRO_CLAUSE_CHAIN_MIN_RUN:
            return
        start, end = run[0][0], run[-1][1]
        hits.append({
            "rule": "micro_clause_chain",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": "consecutive_short_clause_run",
            "run_length": len(run),
            "location": _locate(text, start),
            "snippet": text[start:end][:100],
            "span": text[start:end],
            "start": start,
            "end": end,
            "confidence": "high",
            "severity": "medium",
        })

    for sent_m in re.finditer(r"[^。！？；!?\n]+", masked):
        sent_start = sent_m.start()
        run: list[tuple[int, int]] = []
        pos = 0
        parts = re.split(r"[，,]", sent_m.group(0))
        for part in parts:
            stripped = part.strip()
            lead = len(part) - len(part.lstrip())
            clause_start = sent_start + pos + lead
            clause_end = clause_start + len(stripped)
            pos += len(part) + 1
            if _MICRO_CLAUSE_QUALIFY_RE.fullmatch(stripped):
                run.append((clause_start, clause_end))
            else:
                emit(run)
                run = []
        emit(run)
    return hits


# 指代含混两 family（阈值制，观测消费）：泛指性代词/限定词挤占实词位——
# 病理 = 叙述者用"它/这东西/这道口子"代替可命名的实体（解释代替经历的词尺度形态）。
# 阈值制立案（名著场景 P90 基线，非单发）；alert 走观测通道，由 scene-reviewer
# 按指代 licensing 逐处裁决（紧邻实词指涉 / 故意不命名是场景功能 → 合法不修）。
# 对白 mask 豁免（人物口语"这玩意"合法）。
DUMMY_PRONOUN_LEXICON = re.compile(r"(?:这|那)(?:东西|玩意儿?|套东西|种东西|句话|话)")
DUMMY_PRONOUN_IT_SUBJECT = re.compile(
    r"(?:^|[，。；！？\n：“”「」『』])\s*(它们?)(?=[一-鿿])", re.MULTILINE
)
DUMMY_PRONOUN_IT_OBJECT = re.compile(
    r"(?:把|被|对|朝|向|冲|拿|嫌|盯着|看着|望着|摸着|碰|抱着|举着)(它们?)"
)

# 这/那+量词：时间词（天年月日夜晚宿）不入表；刻/日/击/息/次归 ordinal_gravity 不重复计
DEMONSTRATIVE_CLASSIFIERS = (
    "个只把条道声张片块场副幅样种阵股层根截段口回套件支枚颗粒团抹缕丝滴摊排串捧撮"
    "盏盆扇页封具尊柄杆枝轮汪泓带招式记步眼脚拳"
)
DEMONSTRATIVE_CLASSIFIER_RE = re.compile(
    r"[这那][一两]?[" + DEMONSTRATIVE_CLASSIFIERS + r"](?=[一-鿿])"
)


def _referential_hits(text: str, rule: str, patterns: list[tuple[str, re.Pattern[str], int]]) -> list[dict]:
    family = RULE_TO_FAMILY[rule]
    masked = _mask_quoted_spans(text)
    hits = []
    for subform, pattern, group_idx in patterns:
        for m in pattern.finditer(masked):
            start, end = m.start(group_idx), m.end(group_idx)
            hits.append({
                "rule": rule,
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": subform,
                "location": _locate(text, start),
                "snippet": text[max(0, start - 6):min(len(text), end + 10)].replace("\n", " "),
                "span": text[start:end],
                "start": start,
                "end": end,
                "confidence": "medium",
                "severity": "medium",
            })
    return hits


def detect_dummy_pronoun(text: str) -> list[dict]:
    return _referential_hits(text, "dummy_pronoun", [
        ("formal_lexicon", DUMMY_PRONOUN_LEXICON, 0),
        ("it_subject", DUMMY_PRONOUN_IT_SUBJECT, 1),
        ("it_object", DUMMY_PRONOUN_IT_OBJECT, 1),
    ])


def detect_demonstrative_classifier(text: str) -> list[dict]:
    return _referential_hits(text, "demonstrative_classifier", [
        ("demonstrative_classifier", DEMONSTRATIVE_CLASSIFIER_RE, 0),
    ])


def detect_meta_language(text: str, lang: str = "zh") -> list[dict]:
    selected_lang = _normalize_lang(text, lang)
    masked = _mask_quoted_spans(text)
    rule = f"meta_language_leak_{selected_lang}"
    family = RULE_TO_FAMILY[rule]
    hits = []
    for phrase, pattern in _meta_language_patterns(selected_lang):
        for m in pattern.finditer(masked):
            hits.append({
                "rule": rule,
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": phrase,
                "location": _locate(text, m.start()),
                "snippet": text[m.start():m.end()].replace("\n", " ")[:100],
                "span": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "confidence": "high",
                "severity": "medium",
            })
    return hits


def detect_keyword_cliche(text: str) -> list[dict]:
    hits = []
    for pat in KEYWORD_CLICHE_PATTERNS:
        out_of_scope = KEYWORD_CLICHE_OUT_OF_SCOPE_CONTEXTS.get(pat, ())
        for m in re.finditer(pat, text):
            if out_of_scope:
                ctx_start = max(0, m.start() - 2)
                ctx_end = min(len(text), m.end() + 2)
                ctx = text[ctx_start:ctx_end]
                if any(token in ctx for token in out_of_scope):
                    continue
            snip_start = max(0, m.start() - 3)
            snip_end = min(len(text), m.end() + 8)
            hits.append({
                "rule": "keyword_ai_cliche",
                "pattern": pat,
                "location": _locate(text, m.start()),
                "snippet": text[snip_start:snip_end].replace("\n", " "),
                "confidence": "high",
            })
    return hits


def detect_conjunction_overuse(text: str) -> list[dict]:
    hits = []
    for pattern, label in CONJUNCTION_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.MULTILINE):
            hits.append({
                "rule": "conjunction_overuse",
                "pattern": label,
                "location": _locate(text, m.start()),
                "snippet": m.group(0)[:40],
                "confidence": "high",
            })
    return hits


def detect_parallel_negation(text: str) -> list[dict]:
    hits = []
    for pattern, label in PARALLEL_NEGATION_PATTERNS:
        for m in re.finditer(pattern, text):
            hit = {
                "rule": "parallel_negation",
                "pattern": label,
                "location": _locate(text, m.start()),
                "snippet": m.group(0),
                "confidence": "high",
            }
            if label in PARALLEL_NEGATION_SOFT_PATTERNS:
                hit["severity"] = "low"
                hit["group"] = "heuristic"
            hits.append(hit)
    return hits


def _span_overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in occupied)


def detect_contrastive_negation_assertion(text: str) -> list[dict]:
    hits = []
    occupied: list[tuple[int, int]] = []
    family = RULE_TO_FAMILY["contrastive_negation_assertion"]
    # 对白不属于本检测对象；mask 后只检叙述层（offset 等长映射回原文）。
    masked = _mask_quoted_spans(text)
    for pattern, variant in CONTRASTIVE_NEGATION_PATTERNS:
        for m in re.finditer(pattern, masked):
            span = (m.start(), m.end())
            if _span_overlaps(span, occupied):
                continue
            occupied.append(span)
            hits.append({
                "rule": "contrastive_negation_assertion",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "variant": variant,
                "pattern": variant,
                "location": _locate(text, m.start()),
                "snippet": text[m.start():m.end()],
                "span": text[m.start():m.end()],
                "start": m.start(),
                "end": m.end(),
                "confidence": "high",
                "severity": "medium",
            })
    return hits


def _strip_dialogue_spans(text: str) -> str:
    return re.sub(r'["“][^"”]*["”]', "", text)


def detect_narrative_micro_label(text: str) -> list[dict]:
    """非对白叙述 <=6 字独立短句，段内 >=4 + 段长 >=80 字 + 占比 >=0.25 触发。"""
    hits = []
    family = RULE_TO_FAMILY["narrative_micro_label"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = _strip_dialogue_spans(m.group())
        para_net = _PUNCT_STRIP_RE.sub("", para)
        if len(para_net) < 80:
            continue
        units = [u.strip() for u in re.split(r'[。！？]', para) if u.strip()]
        micro_units = [u for u in units if len(_PUNCT_STRIP_RE.sub("", u)) <= 6]
        if len(micro_units) < 4 or len(micro_units) / max(len(units), 1) < 0.25:
            continue
        search_pos = m.start()
        for unit in micro_units:
            start = text.find(unit, search_pos)
            if start < 0:
                start = m.start()
            search_pos = start + len(unit)
            hits.append({
                "rule": "narrative_micro_label",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "narrative_micro_label",
                "location": _locate(text, start),
                "snippet": unit,
                "span": unit,
                "start": start,
                "end": start + len(unit),
                "confidence": "medium",
                "severity": "medium",
            })
    return hits


def detect_counted_speech_weight(text: str) -> list[dict]:
    hits = []
    family = RULE_TO_FAMILY["counted_speech_weight"]
    for m in COUNTED_SPEECH_PATTERN.finditer(text):
        hits.append({
            "rule": "counted_speech_weight",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": "counted_speech_weight",
            "location": _locate(text, m.start()),
            "snippet": m.group(0),
            "span": m.group(0),
            "start": m.start(),
            "end": m.end(),
            "confidence": "medium",
            "severity": "low",
        })
    return hits


def detect_ordinal_gravity_marker(text: str) -> list[dict]:
    hits = []
    family = RULE_TO_FAMILY["ordinal_gravity_marker"]
    for m in ORDINAL_GRAVITY_PATTERN.finditer(text):
        hits.append({
            "rule": "ordinal_gravity_marker",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": "ordinal_gravity_marker",
            "location": _locate(text, m.start()),
            "snippet": m.group(0),
            "span": m.group(0),
            "start": m.start(),
            "end": m.end(),
            "confidence": "medium",
            "severity": "low",
        })
    return hits


def _containing_sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(p, 0, start) for p in "\n。！？")
    right_candidates = [text.find(p, end) for p in "\n。！？" if text.find(p, end) != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1:right]


def detect_state_persistence_tag(text: str) -> list[dict]:
    hits = []
    family = RULE_TO_FAMILY["state_persistence_tag"]
    matches = list(STATE_PERSISTENCE_PATTERN.finditer(text))
    by_anchor: dict[str, list[re.Match[str]]] = {}
    for m in matches:
        anchor = m.group("anchor")
        by_anchor.setdefault(anchor, []).append(m)

    for anchor, anchor_matches in by_anchor.items():
        if len(anchor_matches) < 2:
            continue
        anchor_has_delta = False
        for m in anchor_matches:
            sentence = _containing_sentence(text, m.start(), m.end())
            state_phrase = m.group("state")
            without_state = sentence.replace(anchor, "", 1).replace(state_phrase, "", 1)
            if any(v in without_state for v in CHANGE_DELTA_VERBS):
                anchor_has_delta = True
                break
        if anchor_has_delta:
            continue
        for m in anchor_matches:
            hits.append({
                "rule": "state_persistence_tag",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "state_persistence_tag",
                "location": _locate(text, m.start()),
                "snippet": m.group(0),
                "span": m.group(0),
                "anchor_phrase": anchor,
                "repeated_anchor_count": len(anchor_matches),
                "change_delta_present": False,
                "start": m.start(),
                "end": m.end(),
                "confidence": "medium",
                "severity": "medium",
            })
    return hits




_DIALOGUE_QUOTES = ('"', '“', '”', "'", '‘', '’', '「', '」')
_PUNCT_STRIP_RE = re.compile(r'[\s。，、！？；：（）()【】「」“”‘’"\'.,;:!?\-—─]+')


def _is_short_paragraph(p: str, thresholds: Thresholds | None = None) -> bool:
    """短段判定：净字 ≤ 12 且 句数 ≤ 2 且 非对话段。"""
    t = thresholds or Thresholds()
    if not p.strip():
        return False
    # 对话段排除：含引号、段首破折号
    if any(q in p for q in _DIALOGUE_QUOTES):
        return False
    stripped = p.lstrip()
    if stripped.startswith(('—', '──', '--')):
        return False
    # Markdown 标题段排除（由 banned_markdown 单独抓）
    if stripped.startswith('#'):
        return False
    net = _PUNCT_STRIP_RE.sub('', p)
    sents = [s for s in re.split(r'[。！？]', p) if s.strip()]
    return (
        len(net) <= t.short_paragraph_max_chars
        and 1 <= len(sents) <= t.short_paragraph_max_sentences
    )


def detect_short_paragraph_run(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """段落极端化（流水账）：短段连发 ≥ 2 报高严重度，孤立短段报低严重度。"""
    t = thresholds or Thresholds()
    # 按空行切段，保留原始位置
    paras: list[tuple[int, str]] = []  # (start_pos, content)
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        paras.append((m.start(), m.group()))
    if not paras:
        return []
    flags = [_is_short_paragraph(p, t) for _, p in paras]

    hits = []
    i, n = 0, len(paras)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j < n and flags[j]:
            j += 1
        run_len = j - i
        run_start_pos = paras[i][0]
        snippet = " | ".join(p[:30] for _, p in paras[i:j])[:80]
        if run_len >= t.short_paragraph_run_severe:
            hits.append({
                "rule": "short_paragraph_run",
                "pattern": f"短段连发×{run_len}",
                "location": _locate(text, run_start_pos),
                "snippet": snippet,
                "confidence": "high",
                "severity": "high",
            })
        else:
            hits.append({
                "rule": "short_paragraph_run",
                "pattern": "短段单发",
                "location": _locate(text, run_start_pos),
                "snippet": paras[i][1][:60],
                "confidence": "high",
                "severity": "low",
            })
        i = j
    return hits


def detect_clause_fragment_density(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """启发式：段内分句过碎（流水账段内版）。

    同时满足全部条件 → 命中：
    - 段落净字 ≥ 60（避免短段误报）
    - 分句数 ≥ 6（避免几个短分句误报）
    - 平均分句净字 ≤ 8
    - 短分句（净字 ≤ 8）占比 ≥ 70%
    severity：clause_count ≥ 8 且 avg ≤ 7 → high；否则 medium。
    """
    t = thresholds or Thresholds()
    hits = []
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if any(q in para for q in _DIALOGUE_QUOTES):
            continue
        stripped = para.lstrip()
        if stripped.startswith(('—', '──', '--', '#')):
            continue

        para_net = _PUNCT_STRIP_RE.sub('', para)
        if len(para_net) < t.clause_fragment_min_paragraph_chars:
            continue

        clauses = re.split(r'[，；]', para)
        clause_lens = [
            len(_PUNCT_STRIP_RE.sub('', c)) for c in clauses if c.strip()
        ]
        clause_lens = [n for n in clause_lens if n >= 2]  # 丢空碎片

        if len(clause_lens) < t.clause_fragment_min_clauses:
            continue

        avg = sum(clause_lens) / len(clause_lens)
        if avg > t.clause_fragment_avg_chars_lte:
            continue

        short_count = sum(1 for n in clause_lens if n <= t.clause_fragment_short_chars_lte)
        short_ratio = short_count / len(clause_lens)
        if short_ratio < t.clause_fragment_short_ratio_gte:
            continue

        severity = "high" if (len(clause_lens) >= 8 and avg <= 7) else "medium"

        hits.append({
            "rule": "clause_fragment_density",
            "pattern": f"段内分句过碎×{len(clause_lens)}",
            "location": _locate(text, m.start()),
            "snippet": para[:80].replace("\n", " "),
            "confidence": "high",
            "severity": severity,
            "group": "heuristic",
            "details": {
                "clause_count": len(clause_lens),
                "avg_clause_chars": round(avg, 2),
                "short_clause_ratio": round(short_ratio, 2),
            },
        })
    return hits


COMMA_INTERVAL_MIN_UNITS = 4
COMMA_INTERVAL_AVG_CHARS_LTE = 9
COMMA_INTERVAL_SHORT_CHARS_LTE = 8
COMMA_INTERVAL_SHORT_RATIO_GTE = 0.60
COMMA_INTERVAL_PARA_MIN_CHARS = 35


def detect_comma_short_interval(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: rhythm_fragmentation; group: syntax_heuristic; severity: low."""
    hits = []
    family = RULE_TO_FAMILY["comma_short_interval"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        para_net = _PUNCT_STRIP_RE.sub('', para)
        if len(para_net) < COMMA_INTERVAL_PARA_MIN_CHARS:
            continue
        units = [u.strip() for u in re.split(r'[，；]', para) if u.strip()]
        if len(units) < COMMA_INTERVAL_MIN_UNITS:
            continue
        unit_lens = [len(_PUNCT_STRIP_RE.sub('', u)) for u in units]
        avg = sum(unit_lens) / len(unit_lens)
        if avg > COMMA_INTERVAL_AVG_CHARS_LTE:
            continue
        short_count = sum(1 for n in unit_lens if n <= COMMA_INTERVAL_SHORT_CHARS_LTE)
        short_ratio = short_count / len(unit_lens)
        if short_ratio < COMMA_INTERVAL_SHORT_RATIO_GTE:
            continue
        hits.append({
            "rule": "comma_short_interval",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": "逗号过密",
            "location": _locate(text, m.start()),
            "snippet": para[:80],
            "confidence": "medium",
            "severity": "low",
            "unit_count": len(units),
            "avg_unit_chars": round(avg, 1),
            "short_unit_ratio": round(short_ratio, 2),
            "sample_units": units[:4],
            "details": {
                "unit_count": len(units),
                "avg_unit_chars": round(avg, 1),
                "short_unit_ratio": round(short_ratio, 2),
                "sample_units": units[:4],
            },
        })
    return hits


def detect_dash_density(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """启发式：破折号密度（"——" 单段过多）。

    判据：
    - 段落净字 ≥ 40
    - 排除引号内 "——"（对白打断 / 人物结巴等合法用法）
    - 段外 "——" 计数 ≥ 3 → medium；≥ 4 → high
    - 整段以引号占主导（≥ 50% 字符在引号内）→ 跳过
    """
    t = thresholds or Thresholds()
    hits = []
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        stripped = para.lstrip()
        if stripped.startswith('#'):
            continue

        para_net = _PUNCT_STRIP_RE.sub('', para)
        if len(para_net) < t.dash_density_min_paragraph_chars:
            continue

        # 剔除引号内文本（中英文引号成对匹配）
        para_outside = re.sub(r'[“”"][^“”"]*[“”"]|[‘’\'][^‘’\']*[‘’\']', '', para)
        # 引号占主导（剔除后剩余 < 50%）→ 视为对话段
        if len(para_outside) < len(para) * 0.5:
            continue

        dash_count = len(re.findall(r'——', para_outside))
        if dash_count < t.dash_density_medium_gte:
            continue

        severity = "high" if dash_count >= t.dash_density_high_gte else "medium"
        hits.append({
            "rule": "dash_density",
            "pattern": f"破折号密度×{dash_count}",
            "location": _locate(text, m.start()),
            "snippet": para[:80].replace("\n", " "),
            "confidence": "high",
            "severity": severity,
            "group": "heuristic",
            "details": {"dash_count": dash_count},
        })
    return hits


def _classify_clause_head(clause: str) -> tuple[str, str] | None:
    """识别分句起手 → (subtype, head_token)；不命中返回 None。"""
    c = clause.strip().strip('"“”\'‘’').lstrip()
    if not c:
        return None
    # 动词起手优先（更具体）
    for v in REPEATED_HEAD_VERB_HEADS:
        if c.startswith(v):
            return ("verb_head_run", v)
    # 名词模板"X的Y"：head 取 "的Y"，让"穿黑衣的人 / 穿白衣的人"归同一 run
    nm = re.match(r'^[^\s，。；！？—]{1,3}的([^\s，。；！？]{1,8})$', c)
    if nm:
        return ("noun_pattern_run", f"的{nm.group(1)}")
    # 代词起手
    for p in REPEATED_HEAD_PRONOUNS:
        if c.startswith(p):
            return ("pronoun_head_run", p)
    # 介词起手
    for p in REPEATED_HEAD_PREPS:
        if c.startswith(p):
            return ("prep_head_run", p)
    return None


def _para_has_short_signal(para: str) -> bool:
    """段内是否含短分句密度信号（轻量联动判据）。"""
    if any(q in para for q in _DIALOGUE_QUOTES):
        return False
    para_net = _PUNCT_STRIP_RE.sub('', para)
    if len(para_net) < 40:
        return False
    clauses = re.split(r'[，；]', para)
    clause_lens = [
        len(_PUNCT_STRIP_RE.sub('', c)) for c in clauses if c.strip()
    ]
    clause_lens = [n for n in clause_lens if n >= 2]
    if len(clause_lens) < 4:
        return False
    avg = sum(clause_lens) / len(clause_lens)
    return avg <= 8


def detect_repeated_clause_head(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """启发式：同字/同词开头连发（排比）。"""
    t = thresholds or Thresholds()
    hits = []
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        clauses = [c for c in re.split(r'[，；]', para) if c.strip()]
        if len(clauses) < 2:
            continue
        has_short = _para_has_short_signal(para)

        current_subtype = None
        current_head = None
        run_clauses: list[str] = []
        run_first_clause_text: str | None = None

        def flush() -> None:
            nonlocal current_subtype, current_head, run_clauses, run_first_clause_text
            if current_subtype is None or not run_clauses:
                current_subtype = None
                current_head = None
                run_clauses = []
                run_first_clause_text = None
                return

            run_len = len(run_clauses)
            if current_subtype == "verb_head_run":
                advisory = t.repeated_head_verb_advisory_gte
                standalone = t.repeated_head_verb_standalone_gte
            elif current_subtype == "noun_pattern_run":
                advisory = t.repeated_head_noun_advisory_gte
                standalone = t.repeated_head_noun_standalone_gte
            elif current_subtype == "pronoun_head_run":
                advisory = t.repeated_head_pronoun_run_gte
                standalone = t.repeated_head_pronoun_run_gte
            else:
                advisory = t.repeated_head_prep_run_gte
                standalone = t.repeated_head_prep_run_gte

            if run_len >= standalone:
                severity = "medium"
                report = True
            elif run_len >= advisory and has_short:
                severity = "medium"
                report = True
            elif run_len >= advisory:
                severity = "low"
                report = current_subtype in ("verb_head_run", "noun_pattern_run")
            else:
                report = False

            if report:
                first_pos = text.find(run_first_clause_text, m.start()) if run_first_clause_text else m.start()
                if first_pos < 0:
                    first_pos = m.start()
                hits.append({
                    "rule": "repeated_clause_head",
                    "pattern": f"{current_subtype}×{run_len}",
                    "subtype": current_subtype,
                    "location": _locate(text, first_pos),
                    "snippet": " | ".join(c.strip()[:20] for c in run_clauses)[:80],
                    "confidence": "medium",
                    "severity": severity,
                    "group": "heuristic",
                    "details": {
                        "head": current_head,
                        "run_length": run_len,
                        "escalated_by_short_clauses": (
                            run_len < standalone
                            and has_short
                            and current_subtype in ("verb_head_run", "noun_pattern_run")
                        ),
                    },
                })
            current_subtype = None
            current_head = None
            run_clauses = []
            run_first_clause_text = None

        for c in clauses:
            classified = _classify_clause_head(c)
            if classified is None:
                flush()
                continue
            sub, head = classified
            if current_subtype == sub and current_head == head:
                run_clauses.append(c)
            else:
                flush()
                current_subtype = sub
                current_head = head
                run_clauses = [c]
                run_first_clause_text = c
        flush()
    return hits


def detect_micro_action_density(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """启发式：微动作链密度（流水账信号）。

    判据：
    - 段落净字 ≥ 80
    - 微动作 token 命中 ≥ 5 次
    - 不同 token ≥ 3 种（避免单一动词重复触发——那是 repeated_clause_head 的事）
    - 含危险词（刀/枪/血/追 等）→ severity 降一级（合法动作戏）
    severity：默认 medium；同段同时命中 clause_fragment_density 时不在此判断（由消费端聚合）。
    """
    t = thresholds or Thresholds()
    hits = []
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if any(q in para for q in _DIALOGUE_QUOTES):
            continue
        if para.lstrip().startswith('#'):
            continue
        para_net = _PUNCT_STRIP_RE.sub('', para)
        if len(para_net) < t.micro_action_min_paragraph_chars:
            continue

        action_counts: dict[str, int] = {}
        for tok in MICRO_ACTION_TOKENS:
            cnt = para.count(tok)
            if cnt > 0:
                action_counts[tok] = cnt

        total_actions = sum(action_counts.values())
        unique_actions = len(action_counts)
        if total_actions < t.micro_action_count_gte or unique_actions < t.micro_action_unique_gte:
            continue

        has_danger = any(d in para for d in MICRO_ACTION_DANGER_TOKENS)
        severity = "low" if has_danger else "medium"

        hits.append({
            "rule": "micro_action_density",
            "pattern": f"微动作链×{total_actions}",
            "location": _locate(text, m.start()),
            "snippet": para[:80].replace("\n", " "),
            "confidence": "high",
            "severity": severity,
            "group": "heuristic",
            "start": m.start(),
            "end": m.end(),
            "span": text[m.start():m.end()],
            "details": {
                "action_count": total_actions,
                "unique_actions": unique_actions,
                "danger_context": has_danger,
                "tokens": dict(sorted(action_counts.items(), key=lambda x: -x[1])),
            },
        })
    return hits


STRONG_ACTION_VERBS = {
    "转身", "回头", "低头", "抬头", "点头", "摇头",
    "推开", "拉开", "拿起", "放下", "关上", "打开",
}

WEAK_ACTION_REGEXES = [
    re.compile(r'^看(向|了|见|一眼|过去|过来)'),
    re.compile(r'^走(向|到|过去|进|出|开)'),
    re.compile(r'^去[^，。；！？]{1,8}(了|去|看|倒|换|接|找)'),
    re.compile(r'^接(过|起|电话)'),
    re.compile(r'^跟[^，。；！？]{1,8}(说话|走|下楼)'),
    re.compile(r'^停(下|了|住)'),
    re.compile(r'^望(着|去|向)'),
]

GO_VERB_REGEX = re.compile(r'去[^，。；！？]{1,8}了')
LOOK_LOOK_REGEX = re.compile(r'看(向|了)[^，。；！？]{1,12}[，。]?[^，。；！？]{0,5}看(了一眼|了|过去)')
SOCIAL_CHOREOGRAPHY_HINT_REGEX = re.compile(r'(接电话去了|说话去了|应酬去了|说了什么)')


def _classify_action_head(clause: str) -> tuple[str, str] | None:
    """返回 (subtype, head) 或 None；社交调度语义问题交给独立 rule。"""
    c = clause.strip().lstrip('他她我你它').lstrip('了')
    if SOCIAL_CHOREOGRAPHY_HINT_REGEX.search(c):
        return None
    for v in STRONG_ACTION_VERBS:
        if c.startswith(v):
            return ("action_run", v)
    for regex in WEAK_ACTION_REGEXES:
        m = regex.match(c)
        if m:
            return ("action_run", m.group())
    return None


def _emit_action_phrase_hit(text: str, m: re.Match[str], run_clauses: list[str], *, subtype: str) -> dict:
    family = RULE_TO_FAMILY["consecutive_action_phrase"]
    paragraph = m.group()
    relative_start = paragraph.find(run_clauses[0])
    relative_end_start = paragraph.find(run_clauses[-1], max(relative_start, 0))
    if relative_start < 0 or relative_end_start < 0:
        start, end = m.start(), m.end()
    else:
        start = m.start() + relative_start
        end = m.start() + relative_end_start + len(run_clauses[-1])
    return {
        "rule": "consecutive_action_phrase",
        "family": family,
        "group": FAMILY_GROUPS[family],
        "cluster": FAMILY_CLUSTERS[family],
        "pattern": f"action_run×{len(run_clauses)}",
        "subtype": subtype,
        "location": _locate(text, m.start()),
        "snippet": " | ".join(c[:20] for c in run_clauses)[:80],
        "confidence": "medium",
        "severity": "medium" if len(run_clauses) >= 3 else "low",
        "run_length": len(run_clauses),
        "start": start,
        "end": end,
        "span": text[start:end],
        "details": {"sample_units": run_clauses[:4]},
    }


def _emit_template_action_hit(
    text: str,
    m: re.Match[str],
    samples: list[str],
    *,
    subtype: str,
) -> dict:
    family = RULE_TO_FAMILY["consecutive_action_phrase"]
    paragraph = m.group()
    relative_start = paragraph.find(samples[0])
    relative_end_start = paragraph.find(samples[-1], max(relative_start, 0))
    if relative_start < 0 or relative_end_start < 0:
        start, end = m.start(), m.end()
    else:
        start = m.start() + relative_start
        end = m.start() + relative_end_start + len(samples[-1])
    return {
        "rule": "consecutive_action_phrase",
        "family": family,
        "group": FAMILY_GROUPS[family],
        "cluster": FAMILY_CLUSTERS[family],
        "pattern": subtype,
        "subtype": subtype,
        "location": _locate(text, m.start()),
        "snippet": " | ".join(samples)[:80],
        "confidence": "medium",
        "severity": "low",
        "run_length": len(samples),
        "start": start,
        "end": end,
        "span": text[start:end],
        "details": {"matched": samples},
    }


def detect_consecutive_action_phrase(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: action_log; group: syntax_heuristic; excludes social_choreography_log."""
    hits: list[dict] = []
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue

        clauses = [c.strip() for c in re.split(r'[，；。！？]', para) if c.strip()]
        current_run: list[str] = []
        for clause in clauses:
            if _classify_action_head(clause) is not None:
                current_run.append(clause)
                continue
            if len(current_run) >= 3:
                hits.append(_emit_action_phrase_hit(text, m, current_run, subtype="action_run"))
            current_run = []
        if len(current_run) >= 3:
            hits.append(_emit_action_phrase_hit(text, m, current_run, subtype="action_run"))

        go_matches = list(GO_VERB_REGEX.finditer(para))
        if len(go_matches) >= 2:
            samples = [g.group() for g in go_matches[:3]]
            hits.append(_emit_template_action_hit(text, m, samples, subtype="go_verb_run"))

        ll_match = LOOK_LOOK_REGEX.search(para)
        if ll_match:
            hits.append(_emit_template_action_hit(
                text,
                m,
                [ll_match.group()],
                subtype="look_look_redundancy",
            ))
    return hits


SOCIAL_CHOREOGRAPHY_PHRASES = [
    "接电话去了", "说话去了", "应酬去了", "走开了",
    "去看别的画了", "去倒了杯酒", "去倒杯酒", "说了什么",
]


def detect_social_choreography_log(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: social_choreography; group: semantic_heuristic."""
    hits = []
    family = RULE_TO_FAMILY["social_choreography_log"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        para_hits: list[tuple[str, int]] = []
        for phrase in SOCIAL_CHOREOGRAPHY_PHRASES:
            for pm in re.finditer(re.escape(phrase), para):
                para_hits.append((phrase, pm.start()))
        if not para_hits:
            continue
        para_hits.sort(key=lambda item: item[1])
        severity = "medium" if len(para_hits) >= 2 else "low"
        for phrase, pos in para_hits:
            hits.append({
                "rule": "social_choreography_log",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "社交调度流水",
                "location": _locate(text, m.start() + pos),
                "snippet": phrase,
                "confidence": "medium",
                "severity": severity,
                "matched_phrase": phrase,
                "matched_phrases": [p for p, _ in para_hits],
            })
    return hits


SIMILE_DEBT_ABSTRACT_NOUNS = {
    "重量", "空气", "沉默", "空白", "距离", "裂缝", "阴影", "灰",
    "光", "声音", "余温", "旧事", "空洞", "重力", "间隔",
}

_ABSTRACT_NOUN_ALT = "|".join(sorted(map(re.escape, SIMILE_DEBT_ABSTRACT_NOUNS), key=len, reverse=True))
SIMILE_TEMPLATES = [
    ("like_abstract_noun", re.compile(rf'像某种(?P<noun>{_ABSTRACT_NOUN_ALT})')),
    ("like_abstract_noun", re.compile(rf'像一种(?P<noun>{_ABSTRACT_NOUN_ALT})')),
    ("like_missing_quality", re.compile(rf'像一个没有(?P<missing>[一-龥]{{1,3}})的(?P<noun>{_ABSTRACT_NOUN_ALT})')),
    ("like_missing_quality", re.compile(rf'像一种没有(?P<missing>[一-龥]{{1,3}})的(?P<noun>{_ABSTRACT_NOUN_ALT})')),
    ("like_missing_quality", re.compile(rf'像没有(?P<missing>[一-龥]{{1,3}})的(?P<noun>{_ABSTRACT_NOUN_ALT})')),
    ("vague_object_simile", re.compile(r'像什么东西[一-龥]{1,3}了')),
    ("weight_silence_air_template", re.compile(rf'(仿佛|好像|如同)(?P<noun>{_ABSTRACT_NOUN_ALT})')),
]


def detect_short_simile_debt(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: figurative_debt; group: semantic_heuristic."""
    hits = []
    family = RULE_TO_FAMILY["short_simile_debt"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        para_hits = []
        for subtype, pattern in SIMILE_TEMPLATES:
            for pm in pattern.finditer(para):
                noun = pm.groupdict().get("noun")
                para_hits.append({
                    "subtype": subtype,
                    "matched_template": pm.group(),
                    "abstract_noun": noun,
                    "pos": pm.start(),
                })
        if not para_hits:
            continue
        severity = "medium" if len(para_hits) >= 2 else "low"
        for hit in para_hits:
            hits.append({
                "rule": "short_simile_debt",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "short_simile",
                "subtype": hit["subtype"],
                "location": _locate(text, m.start() + hit["pos"]),
                "snippet": hit["matched_template"][:80],
                "confidence": "medium",
                "severity": severity,
                "matched_template": hit["matched_template"],
                "abstract_noun": hit["abstract_noun"],
            })
    return hits


ABSTRACT_PHRASE_PATTERNS = [
    re.compile(rf'某种(?P<noun>{_ABSTRACT_NOUN_ALT})'),
    re.compile(rf'一种(?P<noun>{_ABSTRACT_NOUN_ALT})'),
    re.compile(rf'一层(?P<noun>{_ABSTRACT_NOUN_ALT})'),
    re.compile(rf'一点(?P<noun>{_ABSTRACT_NOUN_ALT})'),
    re.compile(r'没有(?P<missing>[一-龥]{1,3})的(东西|地方)'),
    re.compile(r'不属于这里的(?P<noun>[一-龥]{1,3})'),
    re.compile(r'空气短了一下'),
    re.compile(r'时间停了一秒'),
]


def detect_abstract_phrase_debt(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: abstract_phrase_debt; group: semantic_heuristic; severity is always low."""
    hits = []
    family = RULE_TO_FAMILY["abstract_phrase_debt"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        for pattern in ABSTRACT_PHRASE_PATTERNS:
            for pm in pattern.finditer(para):
                noun = pm.groupdict().get("noun")
                if noun and noun not in SIMILE_DEBT_ABSTRACT_NOUNS:
                    continue
                hits.append({
                    "rule": "abstract_phrase_debt",
                    "family": family,
                    "group": FAMILY_GROUPS[family],
                    "cluster": FAMILY_CLUSTERS[family],
                    "pattern": "abstract_phrase",
                    "location": _locate(text, m.start() + pm.start()),
                    "snippet": pm.group()[:80],
                    "confidence": "medium",
                    "severity": "low",
                    "matched_phrase": pm.group(),
                })
    return hits


SILENCE_PAUSE_PHRASES = [
    "没说话", "没有再说什么", "停了一秒", "停了一下",
    "看了一眼", "只看了一眼",
    "嘴角动了动", "幅度很小", "语调是平的",
    "空气静了", "沉默了一会儿", "似乎在等", "没回应",
]


def detect_stock_silence_pause_phrase(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    """family: silence_pause_cliche; group: semantic_heuristic."""
    hits = []
    family = RULE_TO_FAMILY["stock_silence_pause_phrase"]
    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        if para.lstrip().startswith('#'):
            continue
        para_phrases: list[tuple[str, int]] = []
        for phrase in SILENCE_PAUSE_PHRASES:
            for pm in re.finditer(re.escape(phrase), para):
                para_phrases.append((phrase, pm.start()))
        if not para_phrases:
            continue
        para_phrases.sort(key=lambda item: item[1])
        severity = "medium" if len(para_phrases) >= 2 else "low"
        for phrase, pos in para_phrases:
            start = m.start() + pos
            end = start + len(phrase)
            hits.append({
                "rule": "stock_silence_pause_phrase",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "silence_pause",
                "location": _locate(text, start),
                "snippet": phrase,
                "confidence": "medium",
                "severity": severity,
                "matched_phrase": phrase,
                "start": start,
                "end": end,
                "span": text[start:end],
            })
    return hits


def detect_banned_markdown(text: str) -> list[dict]:
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, label in MARKDOWN_PATTERNS:
            if re.search(pattern, line):
                hits.append({
                    "rule": "banned_markdown",
                    "pattern": label,
                    "location": f"L{line_no}",
                    "snippet": line[:60],
                    "confidence": "high",
                })
                break
    return hits


EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _en_words(text: str) -> list[str]:
    return EN_WORD_RE.findall(text)


def detect_em_dash_density_en(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    t = thresholds or Thresholds()
    hits = []
    family = RULE_TO_FAMILY["em_dash_density"]
    total_words = max(len(_en_words(text)), 1)
    total_dashes = text.count("—")
    per_1k = total_dashes / total_words * 1000

    for m in re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text):
        para = m.group()
        word_count = len(_en_words(para))
        dash_count = para.count("—")
        if word_count < t.en_em_dash_paragraph_min_words or dash_count < t.en_em_dash_medium_gte:
            continue
        severity = "high" if dash_count >= t.en_em_dash_high_gte else "medium"
        hits.append({
            "rule": "em_dash_density",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": f"em_dash_density×{dash_count}",
            "location": _locate(text, m.start()),
            "snippet": para[:100].replace("\n", " "),
            "confidence": "high",
            "severity": severity,
            "details": {"dash_count": dash_count, "word_count": word_count},
        })

    if per_1k > t.en_em_dash_per_1k_words_gte and total_dashes:
        hits.append({
            "rule": "em_dash_density",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": "em_dash_per_1k_words",
            "location": "L1",
            "snippet": text[:100].replace("\n", " "),
            "confidence": "high",
            "severity": "high",
            "details": {"dash_count": total_dashes, "em_dash_per_1k_words": round(per_1k, 2)},
        })
    return hits


# en 高特异 slop 短语词表（来源 sam-paech/antislop-sampler, Apache-2.0；
# 取 LLM 过表征频次 >=1000 的短语层条目）。相对过表征条目（人类亦用，如
# 'took a deep breath'）混在其中——en 处于观测模式，hit 仅记录不立案；
# 恢复立案前须按金标做条目级误杀清洗。
SLOP_PHRASES_EN = [
    'took a deep breath', 'voice barely above a whisper', "couldn't help but feel", 'help but feel a sense',
    'voice barely audible', 'casting long shadows', 'voice barely a whisper', "couldn't shake the feeling",
    "couldn't help but wonder", 'long shadows across', 'heart pounding in my chest', 'sun dipped below the horizon',
    'felt a chill run', 'air was thick with the scent', 'felt like an eternity', 'heart pounding in her chest',
    'voice steady despite', 'felt a shiver run', 'said, his voice low', 'room fell silent', 'ready to face whatever',
    'trying to make sense', 'said, his voice barely', 'dipped below the horizon, casting', 'said, her voice barely',
    'asked, my voice barely', 'deep breath, trying', 'felt a strange sense', 'something else entirely',
    'could feel the weight', 'words hung in the air', 'heart pounding in his chest', 'brow furrowed in concentration',
    'sun began to set', 'smile playing on his lips', 'voice trembling slightly', 'asked, her voice barely',
    'door creaked open', 'eyes never leaving', 'days turned into weeks', 'voice a low rumble', 'growing sense of unease',
    'took a step back', 'heart skipped a beat', 'air hung thick', 'said, her voice steady', 'rain continued to fall',
    'sun hung low', 'shiver run down my spine', 'took a step forward', 'said, my voice barely', 'casting a warm glow',
    'renewed sense of purpose', 'spreading across his face', 'Taking a deep breath', 'horizon, casting long',
    'hung low in the sky', 'whispered, her voice barely', 'smile spreading across', 'leaned back in his chair',
    'low in the sky, casting', 'hung heavy in the air', 'eyes wide with fear', 'took a step closer',
    'shake the feeling that something', 'something else, something', 'face whatever challenges',
    'one last time', 'spread like wildfire', 'asked, his voice barely', 'road ahead would', 'Days turned into weeks',
    'felt a sense of peace', 'newfound sense of purpose', 'door swung open', 'grin spreading across',
    'eyes filled with a mixture', 'said, his voice a low', 'flicker of something akin', 'eyes locked onto',
    'dimly lit room', 'tried to make sense', 'challenges lay ahead', 'hung in the air, heavy', 'chill run down my spine',
    'small, intricately carved', 'said, his voice filled', 'eyes darting around', 'said, his voice steady',
    "couldn't help but notice", 'deep breath, steeling', 'brow furrowed in confusion', 'sent a shiver down my spine',
    'chill run down her spine', 'would find a way', 'young woman named', 'breath caught in her throat',
    'fingers flying across', 'eyes wide with wonder', 'Dust motes danced', 'mind raced, trying',
    'figure emerged from the shadows', 'heart hammered against my ribs', 'turned and walked away',
    'piercing blue eyes', 'felt a strange sensation', 'small smile playing', 'trying to keep my voice',
    'felt a cold dread', 'hung thick with the scent', 'air was thick with tension', 'sky, casting long',
    'would never forget', 'whatever challenges lay', 'mind racing with questions', 'said, trying to sound',
    'said, her voice trembling', 'gaze sweeping across', 'spent countless hours', 'said, his voice dripping',
    'resonated deep within', 'first time in a long', 'blood ran cold', 'deep breath, feeling', 'mind racing with the implications',
    'mind racing with possibilities', 'eyes widened in surprise', 'said, her voice filled', 'eyes wide with a mixture',
    'smile playing on her lips', 'taking a deep breath', 'could find a way', 'never seen anything',
    'knew one thing', 'said, my voice steady', 'air thick with the scent', 'eyes scanning the room',
    'felt a growing sense', 'seen anything like', 'asked, her voice trembling', 'help but feel a twinge',
    'smile spread across', 'breath caught in my throat', 'heart pounded in my chest', 'feel a sense of unease',
    'scent of damp earth', 'growing sense of dread', 'looked around the room', 'intricately carved wooden',
    'raised a hand, silencing', 'began to set, casting', 'sighed, running a hand', 'hand instinctively reaching',
    'sense of peace wash', 'heart heavy with the weight', 'knew that the road ahead', 'said, her voice soft',
    'smile tugging at the corners', 'leaned forward, his eyes', 'keep my voice steady', 'knuckles turning white',
    'said, her voice firm', 'felt a glimmer of hope', 'heart pounded in her chest', 'cast long shadows',
    'eyes widened in shock', 'first time since', 'air grew thick', 'feel a sense of pride', 'horizon, painting the sky',
    'whispered, his voice barely', 'faint, almost imperceptible', 'said, his voice firm', 'continued to fall, washing',
    'casting an eerie glow', 'ahead would be long', 'knew, with a chilling certainty', 'eyes locking onto',
    'voice thick with emotion', 'mind already racing', 'air was thick with anticipation', 'said, trying to keep',
    'find a way to break', 'long, dancing shadows', 'uuwu, uuwu, uuwu', 'casting a golden glow',
    'chill run down his spine', 'whispered, her voice trembling', 'needed to find a way', 'change the course of history',
    "couldn't quite place", 'eyes wide with terror', 'pushed open the door', 'time would tell', 'would change the course',
    'need to find a way', 'sent shivers down my spine', 'asked, my voice trembling', 'find a way to make',
    'painting the sky in hues', 'eyes wide with disbelief', 'air grew colder', 'said, her voice low',
    'time in a long time', 'began to take shape', 'life would never', 'said, his voice laced', 'small, almost imperceptible',
    'eyes filled with tears', 'one thing was certain', 'challenges that lay ahead', 'cool night air',
    'whatever lay ahead', 'could feel the power', 'first time in years', 'legs over the side of the bed',
    'one step ahead', 'eyes fluttered open', 'shiver ran down my spine', 'like a physical blow',
    'chill ran down my spine', "couldn't help but smile", 'nodded, a small smile', 'set, casting long',
    'horizon, casting a warm', 'given a second chance', 'voice tinged with a hint', 'shiver run down her spine',
    'took another step', 'like a second skin', 'make things right', 'shook my head, trying', 'asked, trying to keep',
    'eyes darted around', 'could almost hear', 'tasting like ash', 'darting around the room', 'exchanged uneasy glances',
    'screen flickered to life', 'whatever came next', 'mix of excitement and trepidation', 'fingers dancing across',
    'heart pounding with a mixture', 'felt like hours', 'felt a flicker of hope', 'felt a surge of energy',
    'blinding flash of light', 'heart pounded in his chest', 'wave of nausea washed', 'senses on high alert',
    'deep breath and stepped', 'blood run cold', 'brow furrowed with concern', 'warm, golden glow',
    'heart skip a beat', 'air hung heavy', 'seemed to hold its breath', 'air crackled with energy',
    'mind racing with a thousand', 'Lumina, Lumina, Lumina', 'locked onto mine', 'felt a surge of anger',
    'voice devoid of emotion', 'first light of dawn', 'breath, trying to steady',
]


def detect_negation_pivot_en(text: str) -> list[dict]:
    family = RULE_TO_FAMILY["negation_pivot_en"]
    hits = []
    # 只打显式对照结构（"Not X, but Y" negative parallelism）；
    # 普通叙事否定（"did not move. She..."）不属于本 family，不命中。
    patterns = [
        # not X, but (also) Y —— not 与 but 之间须有分隔标点
        re.compile(r"\bnot\s+[^.!?;]{2,60}?[,;—]\s*but\b", re.IGNORECASE),
        re.compile(r"\bnot because\b.{3,40},\s*but because\b", re.IGNORECASE),
        # Not X. Instead / Rather, Y —— 句界对照（句首大写限定）
        re.compile(r"\bnot\s+[^.!?]{2,60}\.\s+(?:Instead|Rather)\b"),
    ]
    for pattern in patterns:
        for m in pattern.finditer(text):
            hits.append({
                "rule": "negation_pivot_en",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "not_x_pivot",
                "location": _locate(text, m.start()),
                "snippet": m.group(0)[:100].replace("\n", " "),
                "confidence": "medium",
                "severity": "medium",
                "start": m.start(),
                "end": m.end(),
            })
    return hits


def detect_slop_phrase_en(text: str) -> list[dict]:
    family = RULE_TO_FAMILY["slop_phrase_en"]
    lowered = text.lower()
    hits = []
    for phrase in SLOP_PHRASES_EN:
        start = 0
        while True:
            idx = lowered.find(phrase, start)
            if idx < 0:
                break
            hits.append({
                "rule": "slop_phrase_en",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": "antislop_lexicon",
                "location": _locate(text, idx),
                "snippet": text[idx:idx + len(phrase)],
                "confidence": "high",
                "severity": "low",
                "start": idx,
                "end": idx + len(phrase),
            })
            start = idx + len(phrase)
    return hits


def detect_staccato_run_en(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    t = thresholds or Thresholds()
    family = RULE_TO_FAMILY["staccato_run"]
    hits = []
    sentence_matches = list(re.finditer(r"[^.!?\n]+[.!?]", text))
    run: list[re.Match[str]] = []
    for match in sentence_matches:
        word_count = len(_en_words(match.group()))
        if 0 < word_count <= t.en_staccato_sentence_max_words:
            run.append(match)
            continue
        if len(run) >= t.en_staccato_run_gte:
            first = run[0]
            snippet = " ".join(m.group().strip() for m in run)
            hits.append({
                "rule": "staccato_run",
                "family": family,
                "group": FAMILY_GROUPS[family],
                "cluster": FAMILY_CLUSTERS[family],
                "pattern": f"short_sentence_run×{len(run)}",
                "location": _locate(text, first.start()),
                "snippet": snippet[:100],
                "confidence": "medium",
                "severity": "medium",
                "start": first.start(),
                "end": run[-1].end(),
            })
        run = []
    if len(run) >= t.en_staccato_run_gte:
        first = run[0]
        snippet = " ".join(m.group().strip() for m in run)
        hits.append({
            "rule": "staccato_run",
            "family": family,
            "group": FAMILY_GROUPS[family],
            "cluster": FAMILY_CLUSTERS[family],
            "pattern": f"short_sentence_run×{len(run)}",
            "location": _locate(text, first.start()),
            "snippet": snippet[:100],
            "confidence": "medium",
            "severity": "medium",
            "start": first.start(),
            "end": run[-1].end(),
        })
    return hits


def detect_simile_density_en(text: str, thresholds: Thresholds | None = None) -> list[dict]:
    t = thresholds or Thresholds()
    family = RULE_TO_FAMILY["simile_density_en"]
    matches = list(re.finditer(r"\b(like|as if|as though)\b", text, flags=re.IGNORECASE))
    word_count = max(len(_en_words(text)), 1)
    per_1k = len(matches) / word_count * 1000
    if per_1k <= t.en_simile_per_1k_words_gte:
        return []
    return [{
        "rule": "simile_density_en",
        "family": family,
        "group": FAMILY_GROUPS[family],
        "cluster": FAMILY_CLUSTERS[family],
        "pattern": "simile_per_1k_words",
        "location": _locate(text, matches[0].start()) if matches else "L1",
        "snippet": text[:100].replace("\n", " "),
        "confidence": "medium",
        "severity": "medium",
        "details": {"simile_count": len(matches), "simile_per_1k_words": round(per_1k, 2)},
    }]


def _sentence_lengths(text: str, lang: str) -> list[int]:
    selected_lang = _normalize_lang(text, lang)
    if selected_lang == "en":
        lengths = []
        for m in re.finditer(r"[^.!?\n]+[.!?]", text):
            word_count = len(_en_words(m.group()))
            if word_count:
                lengths.append(word_count)
        return lengths

    lengths = []
    for m in re.finditer(r"[^。！？…]+[。！？…]+[」』”\"]?", text):
        sentence = m.group()
        net_len = len(_PUNCT_STRIP_RE.sub("", sentence))
        if net_len:
            lengths.append(net_len)
    return lengths


def _coefficient_of_variation(values: list[int]) -> float:
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / mean


def check_uniform_rhythm(text: str, lang: str) -> dict | None:
    selected_lang = _normalize_lang(text, lang)
    lengths = _sentence_lengths(text, selected_lang)
    if len(lengths) < 12:
        return None

    floor = UNIFORM_RHYTHM_CV_FLOOR.get(selected_lang, 0.0)
    cv = _coefficient_of_variation(lengths)
    if cv >= floor:
        return None

    return {
        "issue_type": "uniform_rhythm",
        "severity": "minor",
        "trigger": {
            "sentence_count": len(lengths),
            "sentence_cv": round(cv, 4),
            "cv_floor": floor,
            "language": selected_lang,
        },
        "distribution": {
            "mode": "scene_level",
            "min_sentence_length": min(lengths),
            "max_sentence_length": max(lengths),
            "avg_sentence_length": round(sum(lengths) / len(lengths), 2),
        },
    }


SEMANTIC_CLUSTERS = {
    "figurative_debt",
    "abstract_explanation",
    "silence_pause_cliche",
    "social_choreography",
    "explanatory_detour",
}
SYNTAX_CLUSTERS = {"rhythm_fragmentation", "action_log"}
FAMILY_GROUP_ORDER = {"hard": 1, "syntax_heuristic": 2, "semantic_heuristic": 3}


def _para_line_range(text: str, m: re.Match[str]) -> list[int]:
    start_line = text[:m.start()].count('\n') + 1
    end_line = text[:m.end()].count('\n') + 1
    return [start_line, end_line]


def _hit_line(hit: dict) -> int:
    loc = str(hit.get("location", "L1"))
    if not loc.startswith("L"):
        return 1
    line_text = loc[1:].split("-")[0].split(":")[0]
    try:
        return int(line_text)
    except ValueError:
        return 1


def _span_relevant_hits(hits: list[dict]) -> list[dict]:
    """Drop isolated low advisory hits that would drown the actual semantic family."""
    if len(hits) <= 1:
        return hits
    filtered = [
        h for h in hits
        if not (
            h.get("rule") == "short_paragraph_run"
            and h.get("severity") == "low"
            and h.get("pattern") == "短段单发"
        )
    ]
    return filtered or hits


def build_span_aggregation(hits: list[dict], text: str) -> list[dict]:
    """Aggregate lint hits by paragraph/span for gate consumption."""
    paragraphs = list(re.finditer(r'[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*', text))
    if not paragraphs:
        return []

    ranges = [_para_line_range(text, m) for m in paragraphs]

    def hit_para_idx(hit: dict) -> int:
        line = _hit_line(hit)
        for idx, (start_line, end_line) in enumerate(ranges):
            if start_line <= line <= end_line:
                return idx
        return max(0, len(paragraphs) - 1)

    para_to_hits: dict[int, list[dict]] = {}
    for hit in hits:
        para_to_hits.setdefault(hit_para_idx(hit), []).append(hit)

    spans = []
    for para_idx, raw_hits in sorted(para_to_hits.items()):
        para_hits = _span_relevant_hits(raw_hits)
        if not para_hits:
            continue

        rule_counts: dict[str, int] = {}
        family_counts: dict[str, int] = {}
        family_group_breakdown = {"hard": 0, "syntax_heuristic": 0, "semantic_heuristic": 0}
        contains_medium = False
        for hit in para_hits:
            rid = hit.get("rule")
            fid = hit.get("family") or RULE_TO_FAMILY.get(rid)
            group = FAMILY_GROUPS.get(fid)
            if rid:
                rule_counts[rid] = rule_counts.get(rid, 0) + 1
            if fid:
                family_counts[fid] = family_counts.get(fid, 0) + 1
            if group in family_group_breakdown:
                family_group_breakdown[group] += 1
            if hit.get("severity") == "medium":
                contains_medium = True

        cluster_counts: dict[str, int] = {}
        cluster_best_group: dict[str, str] = {}
        for fid, count in family_counts.items():
            cluster = FAMILY_CLUSTERS.get(fid, "lexical_cliche")
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + count
            group = FAMILY_GROUPS.get(fid, "hard")
            current = cluster_best_group.get(cluster)
            if current is None or FAMILY_GROUP_ORDER[group] > FAMILY_GROUP_ORDER[current]:
                cluster_best_group[cluster] = group

        def cluster_priority(cluster: str) -> int:
            group = cluster_best_group.get(cluster, "hard")
            return FAMILY_GROUP_ORDER.get(group, 1)

        dominant_cluster = (
            max(cluster_counts, key=lambda c: (cluster_counts[c], cluster_priority(c)))
            if cluster_counts else "lexical_cliche"
        )

        severity_basis = []
        total_hits = sum(rule_counts.values())
        n_families = len(family_counts)
        has_semantic = family_group_breakdown["semantic_heuristic"] > 0
        has_syntax = family_group_breakdown["syntax_heuristic"] > 0
        has_hard = family_group_breakdown["hard"] > 0

        if has_semantic and has_syntax:
            if total_hits >= 3 or contains_medium:
                severity = "high"
                severity_basis.append(f"semantic+syntax co-occurred, total_hits={total_hits}")
                if contains_medium:
                    severity_basis.append("semantic+syntax co-occurred, contains_medium_hit=true")
            else:
                severity = "medium"
                severity_basis.append(f"semantic+syntax co-occurred, total_hits={total_hits}")
        elif n_families >= 2 and contains_medium:
            severity = "medium"
            severity_basis.append(f"{n_families} families with at least one medium hit")
        elif has_hard and (has_syntax or has_semantic):
            severity = "medium"
            severity_basis.append("hard + heuristic co-occurred")
        elif dominant_cluster in SEMANTIC_CLUSTERS and n_families >= 2:
            severity = "high"
            severity_basis.append("dominant semantic cluster with >=2 semantic families")
        elif contains_medium:
            severity = "medium"
            severity_basis.append("single family contains medium hit")
        elif n_families >= 2:
            severity = "low"
            severity_basis.append(f"{n_families} families all low")
        else:
            severity = "low"
            severity_basis.append("single family single hit")

        hint = "rewrite_span" if severity == "high" else "rewrite_sentence" if severity == "medium" else None
        spans.append({
            "span_id": f"span_{para_idx + 1:03d}",
            "line_range": ranges[para_idx],
            "rule_counts": rule_counts,
            "family_counts": family_counts,
            "family_group_breakdown": family_group_breakdown,
            "dominant_cluster": dominant_cluster,
            "severity_aggregate": severity,
            "severity_basis": severity_basis,
            "rewrite_recommendation_hint": hint,
        })
    return spans


# Rn+2 O4: canonical_family 条件性归并（同 span 才合并）+ aggregation_only 无条件标记。
# 决策依据：GPT P1-1（parallel_negation/contrastive_negation_assertion 同 span 重复加权）
# + GPT P1-3（narrative_micro_label 段级信号不该计单 hit）。
CANONICAL_FAMILY_MAP = {
    "parallel_negation": {
        "canonical_rule": "contrastive_negation_assertion",
        "scope": "same_span",
    },
}

# rules whose hits are advisory aggregation signals, never counted toward cluster total.
RULE_REGISTRY_AGGREGATION_ONLY = AGGREGATION_ONLY_RULES


def apply_canonical_dedup(hits: list[dict]) -> list[dict]:
    """同 span 上若 canonical rule 与 supporting rule 共存，supporting hit 标 dedup_supporting=True。

    in-place 修改 hits 列表；返回原列表以便链式调用。supporting hit 仍保留在列表中，
    后续 aggregate_cluster_alerts 只在计 family_counts/total_count 时跳过。
    """
    def span_key(hit: dict) -> tuple[int, int] | None:
        if isinstance(hit.get("start"), int) and isinstance(hit.get("end"), int):
            return (hit["start"], hit["end"])
        return None

    def text_key(hit: dict) -> str | None:
        text = hit.get("text") or hit.get("snippet") or hit.get("match")
        if not isinstance(text, str) or not text.strip():
            return None
        return re.sub(r"\s+", "", text)

    by_rule_span: dict[tuple[str, str, tuple[int, int]], dict] = {}
    by_rule_text: dict[tuple[str, str, str], dict] = {}
    for h in hits:
        rule = h.get("rule")
        if not rule:
            continue
        lane = str(h.get("policy_lifecycle") or "enforced")
        sk = span_key(h)
        if sk is not None:
            by_rule_span[(rule, lane, sk)] = h
        tk = text_key(h)
        if tk:
            by_rule_text[(rule, lane, tk)] = h
    for h in hits:
        mapping = CANONICAL_FAMILY_MAP.get(h.get("rule"))
        if not mapping or mapping["scope"] != "same_span":
            continue
        lane = str(h.get("policy_lifecycle") or "enforced")
        canonical = None
        sk = span_key(h)
        if sk is not None:
            canonical = by_rule_span.get((mapping["canonical_rule"], lane, sk))
        else:
            # Rn+2 T8 regression: legacy parallel_negation hits only carry snippet/location.
            # Treat exact snippet/text equality as same-span fallback when offsets are absent.
            tk = text_key(h)
            if tk:
                canonical = by_rule_text.get((mapping["canonical_rule"], lane, tk))
        if canonical:
            h["dedup_supporting"] = True
            h["merged_into"] = canonical["lint_id"]
    return hits


STRICT_PROFILE = {
    "same_rule_scene_count_gte": 2,
    "same_family_scene_count_gte": 3,
    "same_family_per_1k_gte": 2.0,
    "same_paragraph_count_gte": 2,
}

# alert 升 high（= wholetext 阻断档）的命中数门槛。enforced 与 observed 两处聚合
# 共用此常量，并随 alert 的 escalation_threshold 透传给 reviser——它据此知道
# "收到几处才解除阻断"，不必清零或盲改。
SEVERITY_HIGH_COUNT_GTE = 4

def _paragraph_boundaries(text: str) -> list[tuple[int, int]]:
    boundaries = []
    pos = 0
    for para in text.split("\n"):
        boundaries.append((pos, pos + len(para)))
        pos += len(para) + 1
    return boundaries


def _hit_start_for_distribution(hit: dict, text: str) -> int:
    if isinstance(hit.get("start"), int) and hit["start"] >= 0:
        return hit["start"]
    line = _hit_line(hit)
    if line <= 1:
        return 0
    current_line = 1
    for idx, ch in enumerate(text):
        if ch == "\n":
            current_line += 1
            if current_line == line:
                return idx + 1
    return 0


def _hit_paragraph_index(hit: dict, boundaries: list[tuple[int, int]], text: str) -> int:
    start = _hit_start_for_distribution(hit, text)
    for idx, (para_start, para_end) in enumerate(boundaries):
        if para_start <= start <= para_end:
            return idx
    return max(0, len(boundaries) - 1)


def compute_distribution_mode(hits: list[dict], scene_text: str) -> dict:
    """判定 cluster hit 分布：single_span / single_sentence / distributed / catastrophic / paragraph_pattern."""
    if not hits:
        return {"mode": "single_span", "paragraph_count": 0, "contiguous": True}

    boundaries = _paragraph_boundaries(scene_text)
    hit_paras = {_hit_paragraph_index(hit, boundaries, scene_text) for hit in hits}
    paragraph_count = len(hit_paras)
    contiguous = (max(hit_paras) - min(hit_paras) + 1) == paragraph_count if hit_paras else True

    if len(hits) >= 5 and any("micro_punchline" in hit.get("family", "") for hit in hits):
        return {"mode": "catastrophic", "paragraph_count": paragraph_count, "contiguous": contiguous}

    if paragraph_count >= 3:
        return {"mode": "distributed", "paragraph_count": paragraph_count, "contiguous": contiguous}

    if paragraph_count == 1:
        para_idx = next(iter(hit_paras))
        para_start, para_end = boundaries[para_idx]
        para_text = scene_text[para_start:para_end]
        sentence_boundaries = [
            (para_start + m.start(), para_start + m.end())
            for m in re.finditer(r'[^。！？\n]*[。！？]', para_text)
        ]
        hit_sentences = set()
        for hit in hits:
            start = _hit_start_for_distribution(hit, scene_text)
            for idx, (sent_start, sent_end) in enumerate(sentence_boundaries):
                if sent_start <= start < sent_end:
                    hit_sentences.add(idx)
                    break
        if len(hit_sentences) == 1 and len(hits) >= 2:
            return {"mode": "single_sentence", "paragraph_count": 1, "contiguous": True}
        return {"mode": "paragraph_pattern", "paragraph_count": 1, "contiguous": True}

    return {"mode": "single_span", "paragraph_count": paragraph_count, "contiguous": contiguous}


def _paragraph_hit_counts(hits: list[dict], scene_text: str) -> Counter:
    boundaries = _paragraph_boundaries(scene_text)
    return Counter(_hit_paragraph_index(hit, boundaries, scene_text) for hit in hits)


def _evidence_quote_for_span(text: str, start: int, end: int) -> str:
    """Return a deterministic >=10-char quote that contains the exact hit span.

    The quote is deliberately derived from the current scene rather than used as
    a cross-round fingerprint.  If surrounding prose changes, objection refresh
    must revalidate the author-supplied quote and may withdraw the exemption.
    """
    left = max(0, start)
    right = min(len(text), end)
    while right - left < 10 and (left > 0 or right < len(text)):
        if left > 0:
            left -= 1
        if right < len(text) and right - left < 10:
            right += 1
    while text.count(text[left:right]) > 1 and right - left < 80 and (left > 0 or right < len(text)):
        if left > 0:
            left -= 1
        if right < len(text) and right - left < 80:
            right += 1
    return text[left:right]


def _candidate_hit_texts(hit: dict) -> list[str]:
    candidates = []
    for key in ("span", "matched_phrase", "snippet"):
        value = hit.get(key)
        if isinstance(value, str) and value and " | " not in value:
            candidates.append(value)
    details = hit.get("details")
    if isinstance(details, dict):
        for key in ("sample_units", "matched"):
            values = details.get(key)
            if isinstance(values, list):
                candidates.extend(str(value) for value in values if value)
    return candidates


def _attach_hit_locator(hit: dict, text: str) -> None:
    start = hit.get("start")
    end = hit.get("end")
    if not (
        isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < end <= len(text)
    ):
        start = end = None
        line_start = 0
        line_end = len(text)
        location = hit.get("location")
        if isinstance(location, str) and re.fullmatch(r"L\d+", location):
            line_no = int(location[1:])
            lines = text.splitlines(keepends=True)
            if 1 <= line_no <= len(lines):
                line_start = sum(len(line) for line in lines[:line_no - 1])
                line_end = line_start + len(lines[line_no - 1])
        for candidate in _candidate_hit_texts(hit):
            pos = text.find(candidate, line_start, line_end)
            if pos < 0:
                pos = text.find(candidate)
            if pos >= 0:
                start, end = pos, pos + len(candidate)
                break
    if start is None or end is None:
        return
    span = text[start:end]
    hit["start"] = start
    hit["end"] = end
    hit["span"] = span
    hit["locator"] = {"start": start, "end": end, "span": span}
    hit["evidence_quote"] = _evidence_quote_for_span(text, start, end)


def _ensure_lint_ids(hits: list[dict], scene_id: str, scene_text: str) -> list[dict]:
    for idx, hit in enumerate(hits, start=1):
        _attach_hit_locator(hit, scene_text)
        hit.setdefault("lint_id", f"{scene_id}-{hit.get('rule', 'unknown')}-{idx:03d}")
    return hits


def _prepare_policy_lanes(hits: list[dict], lang: str) -> None:
    """Annotate lifecycle before dedup so observe/enforced lanes never merge."""
    for hit in hits:
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if not family:
            hit["policy_lifecycle"] = "not_registered"
            continue
        hit["family"] = family
        policy = effective_policy(family, lang, hit.get("rule"))
        hit["policy_lifecycle"] = policy["lifecycle"]
    apply_canonical_dedup(hits)


def aggregate_cluster_alerts(
    hits: list[dict],
    scene_id: str,
    scene_text: str,
    budget_multipliers: dict[str, float] | None = None,
    *,
    lang: str = "zh",
) -> list[dict]:
    budget_multipliers = budget_multipliers or {}

    # Policy is resolved before canonical dedup. A supporting enforced hit may
    # not be swallowed by a same-span canonical rule that is still observe.
    _prepare_policy_lanes(hits, lang)

    by_family: dict[str, list[dict]] = {}
    for hit in hits:
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if not family:
            continue
        hit["family"] = family
        if hit.get("policy_lifecycle") != "enforced":
            continue
        # Rn+2 O4: dedup_supporting 和 aggregation_only 不计入 family_counts/total_count，
        # 但仍保留在 supporting_hit_ids（作 evidence）。
        if hit.get("dedup_supporting") or hit.get("rule") in RULE_REGISTRY_AGGREGATION_ONLY:
            continue
        by_family.setdefault(family, []).append(hit)

    alerts = []
    char_k = max(len(scene_text) / 1000, 0.001)
    for family, family_hits in by_family.items():
        policy = effective_policy(family, lang)
        thresholds = {**STRICT_PROFILE, **policy.get("aggregation", {})}
        multiplier = budget_multipliers.get(family, 1.0)
        if multiplier > 1.0:
            thresholds = {
                key: value * multiplier
                if isinstance(value, (int, float)) and key.endswith(("_gte", "_count_gte"))
                else value
                for key, value in thresholds.items()
            }
        rule_counts = Counter(hit.get("rule", "unknown") for hit in family_hits)
        total_count = len(family_hits)
        density = total_count / char_k
        max_para_count = max(_paragraph_hit_counts(family_hits, scene_text).values(), default=0)
        max_anchor_count = max(
            (hit.get("repeated_anchor_count", 0) for hit in family_hits),
            default=0,
        )
        # Rn+2 P0-1: density 必须 with count gate，禁止短文本 + 1 hit 触发。
        # per-family override 只能加路径不能降门槛（不允许定义 density_only_gte）。
        triggered = (
            any(count >= thresholds["same_rule_scene_count_gte"] for count in rule_counts.values())
            or total_count >= thresholds["same_family_scene_count_gte"]
            or max_para_count >= thresholds["same_paragraph_count_gte"]
            or (total_count >= 2 and density >= thresholds["same_family_per_1k_gte"])
            or (
                "same_anchor_repeated_count_gte" in thresholds
                and max_anchor_count >= thresholds["same_anchor_repeated_count_gte"]
            )
        )
        if not triggered:
            continue
        # 名著基线 AND gate：count 证据成立后，密度还须超过 KB 校准基线（P90 × 装置乘数）
        # 才升级为 cluster alert——保护高风格化合法形态（说书腔 / 动作短切 / 克制裸句）。
        # hits 本身不受影响，仍全量落盘可观测。
        baseline = calibration_value(policy) * multiplier
        if baseline and density < baseline:
            continue
        registry = FAMILY_REGISTRY.get(family, {})
        distribution = compute_distribution_mode(family_hits, scene_text)
        severity = "high" if total_count >= SEVERITY_HIGH_COUNT_GTE else "medium"
        # Rn+2 R1 F6: canonical family 的 hit_ids
        canonical_hit_ids = [
            h["lint_id"] for h in hits
            if (h.get("family") == family or RULE_TO_FAMILY.get(h.get("rule")) == family)
            and h.get("policy_lifecycle") == "enforced"
            and not h.get("dedup_supporting")
            and h.get("rule") not in RULE_REGISTRY_AGGREGATION_ONLY
        ]
        # F6: supporting hit 单独承载（不混入 hit_ids）
        canonical_hit_set = set(canonical_hit_ids)
        supporting_hit_ids = [
            h["lint_id"] for h in hits
            if h.get("policy_lifecycle") == "enforced"
            and ((h.get("dedup_supporting") and h.get("merged_into") in canonical_hit_set)
            or (h.get("rule") in RULE_REGISTRY_AGGREGATION_ONLY
                and (h.get("family") == family or RULE_TO_FAMILY.get(h.get("rule")) == family)))
        ]
        # 逐 hit 定位：reviser 被要求按 repair_strategy 逐处改写而非凭语感删改，
        # 只给 alert_id 它无从下手（observed 组给了定位、blocking 组反而没有 = 信息与
        # 优先级倒挂）。构造同 observed 侧，canonical hit 才进（supporting 不重复列）。
        canonical_hits = [h for h in family_hits if h["lint_id"] in canonical_hit_set]
        hit_records = [
            {
                "lint_id": hit["lint_id"],
                "family": family,
                "rule": hit.get("rule"),
                "locator": hit.get("locator"),
                "evidence_quote": hit.get("evidence_quote"),
            }
            for hit in canonical_hits
        ]
        alerts.append({
            "alert_id": f"{scene_id}-{family}-{len(alerts) + 1}",
            "scope": "scene",
            "family": family,
            "cluster": registry.get("cluster", ""),
            "group": registry.get("group", "semantic_heuristic"),
            "rule_counts": dict(rule_counts),
            "total_count": total_count,
            "density_per_1k": round(density, 2),
            "hit_ids": canonical_hit_ids,
            "hit_records": hit_records,
            "supporting_hit_ids": supporting_hit_ids,
            "distribution": distribution,
            "severity": severity,
            # 降级目标：severity 降到 medium 即解除 wholetext 阻断。不给这个数，
            # reviser 只能清零（把文风均质化）或盲改（改完仍 FAIL）。
            "escalation_threshold": {
                "high_gte": SEVERITY_HIGH_COUNT_GTE,
                "current_count": total_count,
                "non_blocking_at_or_below": SEVERITY_HIGH_COUNT_GTE - 1,
            },
            "budget_multiplier": multiplier,
            "governance": {
                "individual_exemption_allowed": False,
                "required_triage": "cluster_finding",
                "required_patch_mode": "rewrite_patch_set",
                "required_patch_kind_options": ["rewrite_sentence", "rewrite_span"],
                "forbidden_patch_kind": ["delete_token", "replace_phrase"],
            },
        })
    return alerts


def aggregate_observed_alerts(
    hits: list[dict],
    scene_id: str,
    scene_text: str,
    budget_multipliers: dict[str, float] | None = None,
    *,
    lang: str = "zh",
) -> list[dict]:
    """Build locatable, non-blocking alert groups for calibrated observe policies."""
    budget_multipliers = budget_multipliers or {}
    _prepare_policy_lanes(hits, lang)

    by_family: dict[str, list[dict]] = {}
    for hit in hits:
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if not family or hit.get("policy_lifecycle") != "observe":
            continue
        if hit.get("dedup_supporting") or hit.get("rule") in RULE_REGISTRY_AGGREGATION_ONLY:
            continue
        by_family.setdefault(family, []).append(hit)

    alerts = []
    char_k = max(len(scene_text) / 1000, 0.001)
    for family, family_hits in by_family.items():
        policy = effective_policy(family, lang)
        if policy.get("lifecycle") != "observe":
            continue
        baseline_value = calibration_value(policy)
        if baseline_value <= 0:
            continue
        thresholds = {**STRICT_PROFILE, **policy.get("aggregation", {})}
        multiplier = budget_multipliers.get(family, 1.0)
        if multiplier > 1.0:
            thresholds = {
                key: value * multiplier
                if isinstance(value, (int, float)) and key.endswith(("_gte", "_count_gte"))
                else value
                for key, value in thresholds.items()
            }
        rule_counts = Counter(hit.get("rule", "unknown") for hit in family_hits)
        total_count = len(family_hits)
        density = total_count / char_k
        max_para_count = max(_paragraph_hit_counts(family_hits, scene_text).values(), default=0)
        max_anchor_count = max(
            (hit.get("repeated_anchor_count", 0) for hit in family_hits),
            default=0,
        )
        triggered = (
            any(count >= thresholds["same_rule_scene_count_gte"] for count in rule_counts.values())
            or total_count >= thresholds["same_family_scene_count_gte"]
            or max_para_count >= thresholds["same_paragraph_count_gte"]
            or (total_count >= 2 and density >= thresholds["same_family_per_1k_gte"])
            or (
                "same_anchor_repeated_count_gte" in thresholds
                and max_anchor_count >= thresholds["same_anchor_repeated_count_gte"]
            )
        )
        baseline = baseline_value * multiplier
        if not triggered or density < baseline:
            continue

        registry = FAMILY_REGISTRY.get(family, {})
        hit_ids = [hit["lint_id"] for hit in family_hits]
        hit_records = [
            {
                "lint_id": hit["lint_id"],
                "family": family,
                "rule": hit.get("rule"),
                "locator": hit.get("locator"),
                "evidence_quote": hit.get("evidence_quote"),
            }
            for hit in family_hits
        ]
        alerts.append({
            "alert_id": f"{scene_id}-{family}-observed-{len(alerts) + 1}",
            "scope": "scene",
            "family": family,
            "cluster": registry.get("cluster", ""),
            "group": registry.get("group", "semantic_heuristic"),
            "rule_counts": dict(rule_counts),
            "total_count": total_count,
            "density_per_1k": round(density, 2),
            "baseline_per_1k": round(baseline, 2),
            "hit_ids": hit_ids,
            "hit_records": hit_records,
            "distribution": compute_distribution_mode(family_hits, scene_text),
            "severity": "high" if total_count >= SEVERITY_HIGH_COUNT_GTE else "medium",
            "escalation_threshold": {
                "high_gte": SEVERITY_HIGH_COUNT_GTE,
                "current_count": total_count,
                "non_blocking_at_or_below": SEVERITY_HIGH_COUNT_GTE - 1,
            },
            "budget_multiplier": multiplier,
            "lifecycle": "observe",
            "blocking": False,
        })
    return alerts




RULE_EXECUTORS = {
    "zh": {
        "meta_language_leak_zh": lambda text, thresholds: detect_meta_language(text, "zh"),
        "fragment_settlement": lambda text, thresholds: detect_fragment_settlement(text),
        "micro_clause_chain": lambda text, thresholds: detect_micro_clause_chain(text),
        "dummy_pronoun": lambda text, thresholds: detect_dummy_pronoun(text),
        "demonstrative_classifier": lambda text, thresholds: detect_demonstrative_classifier(text),
        "keyword_ai_cliche": lambda text, thresholds: detect_keyword_cliche(text),
        "conjunction_overuse": lambda text, thresholds: detect_conjunction_overuse(text),
        "parallel_negation": lambda text, thresholds: detect_parallel_negation(text),
        "contrastive_negation_assertion": lambda text, thresholds: detect_contrastive_negation_assertion(text),
        "narrative_micro_label": lambda text, thresholds: detect_narrative_micro_label(text),
        "counted_speech_weight": lambda text, thresholds: detect_counted_speech_weight(text),
        "ordinal_gravity_marker": lambda text, thresholds: detect_ordinal_gravity_marker(text),
        "state_persistence_tag": lambda text, thresholds: detect_state_persistence_tag(text),
        "short_paragraph_run": lambda text, thresholds: detect_short_paragraph_run(text, thresholds),
        "clause_fragment_density": lambda text, thresholds: detect_clause_fragment_density(text, thresholds),
        "comma_short_interval": lambda text, thresholds: detect_comma_short_interval(text, thresholds),
        "dash_density": lambda text, thresholds: detect_dash_density(text, thresholds),
        "repeated_clause_head": lambda text, thresholds: detect_repeated_clause_head(text, thresholds),
        "micro_action_density": lambda text, thresholds: detect_micro_action_density(text, thresholds),
        "consecutive_action_phrase": lambda text, thresholds: detect_consecutive_action_phrase(text, thresholds),
        "social_choreography_log": lambda text, thresholds: detect_social_choreography_log(text, thresholds),
        "short_simile_debt": lambda text, thresholds: detect_short_simile_debt(text, thresholds),
        "abstract_phrase_debt": lambda text, thresholds: detect_abstract_phrase_debt(text, thresholds),
        "stock_silence_pause_phrase": lambda text, thresholds: detect_stock_silence_pause_phrase(text, thresholds),
        "banned_markdown": lambda text, thresholds: detect_banned_markdown(text),
    },
    "en": {
        "meta_language_leak_en": lambda text, thresholds: detect_meta_language(text, "en"),
        "em_dash_density": lambda text, thresholds: detect_em_dash_density_en(text, thresholds),
        "negation_pivot_en": lambda text, thresholds: detect_negation_pivot_en(text),
        "slop_phrase_en": lambda text, thresholds: detect_slop_phrase_en(text),
        "staccato_run": lambda text, thresholds: detect_staccato_run_en(text, thresholds),
        "simile_density_en": lambda text, thresholds: detect_simile_density_en(text, thresholds),
        "banned_markdown": lambda text, thresholds: detect_banned_markdown(text),
    },
}
RULES_ZH = tuple(RULE_EXECUTORS["zh"].values())
RULES_EN = tuple(RULE_EXECUTORS["en"].values())


def collect_lint_hits(
    text: str,
    thresholds: Thresholds | None = None,
    *,
    lang: str = "zh",
) -> list[dict]:
    t = thresholds or Thresholds()
    selected_lang = _normalize_lang(text, lang)
    hits: list[dict] = []
    for rule_id, executor in RULE_EXECUTORS[selected_lang].items():
        family = RULE_TO_FAMILY[rule_id]
        if effective_policy(family, selected_lang, rule_id)["registered"]:
            hits.extend(executor(text, t))
    return hits


def run_ai_filler_lint(
    scene_text: str,
    scene_id: str = "S01",
    thresholds: Thresholds | None = None,
    *,
    lang: str = "zh",
    devices: Iterable[str] = (),
) -> dict:
    selected_lang = _normalize_lang(scene_text, lang)
    budget_multipliers, valid_devices = _resolve_device_budget(devices, selected_lang)
    lint_hits = _ensure_lint_ids(
        collect_lint_hits(scene_text, thresholds, lang=selected_lang),
        scene_id,
        scene_text,
    )
    cluster_alerts = aggregate_cluster_alerts(
        lint_hits, scene_id, scene_text, budget_multipliers, lang=selected_lang
    )
    observed_alerts = aggregate_observed_alerts(
        lint_hits, scene_id, scene_text, budget_multipliers, lang=selected_lang
    )
    uniform_rhythm = check_uniform_rhythm(scene_text, selected_lang)
    scene_level_issues = [
        issue for issue in (uniform_rhythm,)
        if issue is not None
    ]
    return {
        "input_text_sha256": hashlib.sha256(scene_text.encode("utf-8")).hexdigest(),
        "lint_hits": lint_hits,
        "cluster_alerts": cluster_alerts,
        "observed_alerts": observed_alerts,
        "scene_level_issues": scene_level_issues,
        "language": selected_lang,
        "device_budget_applied": bool(valid_devices),
        "budget_class": valid_devices,
        "budget_source": "declared" if valid_devices else "default",
    }


def analyze(
    text: str,
    thresholds: Thresholds | None = None,
    *,
    scene_id: str = "S01",
    lang: str = "zh",
    devices: Iterable[str] = (),
) -> dict:
    selected_lang = _normalize_lang(text, lang)
    budget_multipliers, valid_devices = _resolve_device_budget(devices, selected_lang)
    all_hits = _ensure_lint_ids(
        collect_lint_hits(text, thresholds, lang=selected_lang),
        scene_id,
        text,
    )
    cluster_alerts = aggregate_cluster_alerts(
        all_hits, scene_id, text, budget_multipliers, lang=selected_lang
    )
    observed_alerts = aggregate_observed_alerts(
        all_hits, scene_id, text, budget_multipliers, lang=selected_lang
    )
    uniform_rhythm = check_uniform_rhythm(text, selected_lang)
    scene_level_issues = [
        issue for issue in (uniform_rhythm,)
        if issue is not None
    ]
    pattern_counter = Counter(h["pattern"] for h in all_hits)
    total_chars = len(text)
    return {
        "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "language": selected_lang,
        "device_budget_applied": bool(valid_devices),
        "budget_class": valid_devices,
        "budget_source": "declared" if valid_devices else "default",
        "hits": all_hits,
        "cluster_alerts": cluster_alerts,
        "observed_alerts": observed_alerts,
        "scene_level_issues": scene_level_issues,
        "density": {
            "total_chars": total_chars,
            "hits_per_1k": round(len(all_hits) / max(total_chars, 1) * 1000, 2),
            "top_patterns": [
                {"pattern": p, "count": c}
                for p, c in pattern_counter.most_common(5)
            ],
        },
        "span_aggregation": build_span_aggregation(all_hits, text),
        "meta": {},
    }


def _phase0_language(work_dir: Path) -> str | None:
    path = work_dir / "pipeline" / "phase0_conception.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    candidates = [data.get("language")]
    phase0 = data.get("phase0")
    if isinstance(phase0, dict):
        candidates.append(phase0.get("language"))
    for value in candidates:
        if value in {"zh", "en"}:
            return value
    return None


def _resolve_lang(text: str, cli_lang: str, work_dir: Path | None = None) -> tuple[str, str]:
    if work_dir is not None:
        field_lang = _phase0_language(work_dir)
        if field_lang:
            if cli_lang != "auto" and cli_lang != field_lang:
                print(
                    f"[ai_filler_lint] WARN: --lang {cli_lang} conflicts with phase0.language {field_lang}; using field",
                    file=sys.stderr,
                )
            return field_lang, "field"
    if cli_lang != "auto":
        return cli_lang, "cli"
    return detect_lang(text), "auto"


def _coerce_devices(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _devices_for_scene(work_dir: Path, scene_id: str) -> list[str]:
    path = work_dir / "pipeline" / "phase5_scenes.yaml"
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []

    candidates = []
    if isinstance(data, dict):
        for key in ("scenes", "scene_cards", "phase5_scenes"):
            value = data.get(key)
            if isinstance(value, (dict, list)):
                candidates.append(value)
        for seq in data.get("sequence_expansions") or []:
            if isinstance(seq, dict) and isinstance(seq.get("scenes"), list):
                candidates.append(seq["scenes"])
        candidates.append(data)
    elif isinstance(data, list):
        candidates.append(data)

    for candidate in candidates:
        if isinstance(candidate, dict):
            scene = candidate.get(scene_id) or candidate.get(f"scene_{scene_id}")
            if isinstance(scene, dict):
                return _coerce_devices(scene.get("literary_device"))
        if isinstance(candidate, list):
            for scene in candidate:
                if not isinstance(scene, dict):
                    continue
                sid = scene.get("scene_id") or scene.get("id") or scene.get("scene")
                if sid in {scene_id, f"scene_{scene_id}"}:
                    return _coerce_devices(scene.get("literary_device"))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="S1 AI filler lint")
    parser.add_argument("scene_file", nargs="?", type=Path, help="可选：直接 lint 单个 scene markdown 文件")
    parser.add_argument("--scene-path", default=None, type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--scene-id", default=None)
    parser.add_argument("--story", default=None, type=Path,
                        help="全文模式：直接 lint 整篇正文（如 story.md），输出 whole.ai_filler.yaml（scene_id=WHOLE，work-dir YAML 形态）")
    parser.add_argument("--work-dir", default=None, type=Path)
    parser.add_argument("--lang", default="auto", choices=["auto", "zh", "en"])
    parser.add_argument("--genre", default=None)
    parser.add_argument(
        "--threshold-profile",
        default="conservative",
        choices=list(_THRESHOLD_PROFILES.keys()),
        help="阈值 profile：conservative（默认）/ strict",
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help='JSON 字典覆盖阈值，如 \'{"clause_fragment_avg_chars_lte": 7}\'',
    )
    parser.add_argument(
        "--output-suffix",
        default="",
        help="输出文件名后缀，如 v2 -> {scene_id}.ai_filler.v2.yaml",
    )
    args = parser.parse_args()
    if args.scene_path is not None:
        if args.scene_file is not None:
            parser.error("Use either positional scene_file or --scene-path, not both")
        args.scene_file = args.scene_path

    base = _THRESHOLD_PROFILES[args.threshold_profile]
    if args.thresholds:
        import json

        overrides = json.loads(args.thresholds)
        base = replace(base, **overrides)

    if args.scene_file:
        import json

        scene_path = args.scene_file.resolve()
        if not scene_path.exists():
            print(f"[ai_filler_lint] ERROR: {scene_path} not found", file=sys.stderr)
            return 1
        scene_id = args.scene_id or scene_path.stem.removeprefix("scene_")
        text = scene_path.read_text(encoding="utf-8")
        lang, lang_source = _resolve_lang(text, args.lang)
        result = run_ai_filler_lint(
            text,
            scene_id=scene_id,
            thresholds=base,
            lang=lang,
        )
        result["density"] = {
            "total_chars": len(text),
            "hits_per_1k": round(len(result["lint_hits"]) / max(len(text), 1) * 1000, 2),
        }
        result["meta"] = {"lang_source": lang_source}
        suffix = args.output_suffix or "ai_filler"
        out_path = scene_path.with_name(f"{scene_path.stem}_{suffix}.json")
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ {out_path} · {len(result['lint_hits'])} hits · {len(result['cluster_alerts'])} cluster_alerts")
        return 0

    if not args.work_dir or not (args.scene_id or args.story):
        parser.error("--scene-id (or --story) and --work-dir are required unless scene_file is provided")
    if args.scene_id and args.story:
        parser.error("--scene-id 与 --story 二选一")

    work_dir: Path = args.work_dir.resolve()
    if args.story:
        scene_id = "WHOLE"
        scene_path = args.story.resolve()
    else:
        scene_id = args.scene_id
        scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    if not scene_path.exists():
        print(f"[ai_filler_lint] ERROR: {scene_path} not found", file=sys.stderr)
        return 1

    text = scene_path.read_text(encoding="utf-8")
    lang, lang_source = _resolve_lang(text, args.lang, work_dir)
    devices = [] if args.story else _devices_for_scene(work_dir, scene_id)
    result = analyze(text, base, scene_id=scene_id, lang=lang, devices=devices)
    result["meta"].update({
        "thresholds": asdict(base),
        "threshold_source": args.threshold_profile + ("+overrides" if args.thresholds else ""),
        "genre": args.genre,
        "lang_source": lang_source,
    })

    output = {
        "scene_id": scene_id,
        "script": "ai_filler_lint",
        "version": "r3",
        **result,
    }

    suffix = f".{args.output_suffix}" if args.output_suffix else ""
    out_name = f"whole.ai_filler{suffix}.yaml" if args.story else f"{scene_id}.ai_filler{suffix}.yaml"
    out_path = work_dir / "pipeline" / "review" / "lint" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(output, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"✅ {out_path} · {len(result['hits'])} hits · {result['density']['hits_per_1k']}/1k")
    return 0


if __name__ == "__main__":
    sys.exit(main())
