"""量化文风靶：指代策略 + 标点经济密度指标

为 kb_query.py 的段落密度区块提供即时计算的第二组数字靶（design §5）——
口径与治理线统一：per-1k-chars（不筛汉字，含标点，同 wholetext_gate.py `_dash_per_1k`
先例）；"——"按一个破折号单元计 1，不拆成两个"—"。

纯正则 + 计数，零第三方依赖，可被 calibrate_baselines.py 按纯函数签名导入。

用法（作为模块）::

    from stylometry import analyze_file
    stats = analyze_file("story.md")
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_COLON_RE = re.compile(r"[:：]")
_SEMICOLON_RE = re.compile(r"[;；]")

_DEM_CLASSIFIERS = (
    "个 些 种 只 条 张 把 块 次 回 阵 片 丝 缕 道 扇 朵 颗 粒 枚 件 "
    "双 群 队 批 伙 帮 拨 堆 摊 串 艘 辆 架 台 栋 间 幢 座 层"
).split()
_DEM_CLASSIFIER_RE = re.compile(
    r"[这那][一二三四五六七八九十百千两几]?(?:" + "|".join(_DEM_CLASSIFIERS) + ")"
)

# 启发式：句首命中常见动作动词首字 → 判定承前省略主语。不做词性分析，
# 无法覆盖全部无主语句式（如省略主语的判断句），仅供密度趋势参考。
_PRO_DROP_VERB_HEADS = set(
    "走看说想听笑哭转抬低站坐躺闭睁抓推拉伸缩点摇皱咬舔嗅闻叹喊叫骂哼愣僵绕"
    "靠贴挪跨跳蹲跪扑挥甩砸摔撞碰摸握捏掐拧扭搭披裹盖掀掰撕揉搓擦抹涂铺摆放收拿取递接扔丢踢踩踏蹬"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
_LEADING_QUOTE_RE = re.compile(r'^[「『""\'\s]+')

_PUNCT_FOR_BIGRAM = set("，。、；：/（）「」『』！？·,.;:()<>\"'-—\n\t ")


@dataclass
class StylometryStats:
    """量化文风靶统计结果（per-1k-chars，pro_drop_ratio 除外为占比 0-1）"""
    dash_per_1k: float
    colon_per_1k: float
    semicolon_per_1k: float
    ta_per_1k: float                 # "它"
    dem_classifier_per_1k: float     # 这/那+量词 限定式
    pro_drop_ratio: float            # 句首无主语句占比（启发式）
    top_noun_repetition_per_1k: float


def _split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _is_pro_drop(sentence: str) -> bool:
    s = _LEADING_QUOTE_RE.sub("", sentence).strip()
    if not s:
        return False
    return s[0] in _PRO_DROP_VERB_HEADS


def _top_repetition_per_1k(text: str) -> float:
    """启发式：以高频 CJK 字符二元组代理"高频实词复现"（零依赖，无 POS 标注）。"""
    chars = [c for c in text if c not in _PUNCT_FOR_BIGRAM]
    grams = [a + b for a, b in zip(chars, chars[1:])]
    if not grams:
        return 0.0
    top_count = Counter(grams).most_common(1)[0][1]
    return round(top_count / max(len(text), 1) * 1000, 2)


def signature_per_1k(text: str, lexicon: list[str]) -> float:
    if not text or not lexicon:
        return 0.0
    hits = sum(text.count(w) for w in lexicon if w)
    return hits / len(text) * 1000


def signature_distribution(segments: list[tuple[str, str]], lexicon: list[str]) -> dict[str, float]:
    stats: dict[str, list[int]] = {}
    for gear, seg_text in segments:
        hits = sum(seg_text.count(w) for w in lexicon if w) if (seg_text and lexicon) else 0
        cur = stats.setdefault(gear, [0, 0])
        cur[0] += hits
        cur[1] += len(seg_text)
    return {gear: (h / n * 1000 if n else 0.0) for gear, (h, n) in stats.items()}


def analyze_text(text: str) -> StylometryStats:
    """分析一段文本，返回量化文风靶统计（空文本零除保护，全部指标为 0）"""
    denom = max(len(text), 1)

    dash_per_1k = round(text.count("——") / denom * 1000, 2)
    colon_per_1k = round(len(_COLON_RE.findall(text)) / denom * 1000, 2)
    semicolon_per_1k = round(len(_SEMICOLON_RE.findall(text)) / denom * 1000, 2)
    ta_per_1k = round(text.count("它") / denom * 1000, 2)
    dem_classifier_per_1k = round(len(_DEM_CLASSIFIER_RE.findall(text)) / denom * 1000, 2)

    sentences = _split_sentences(text)
    pro_drop_ratio = (
        round(sum(1 for s in sentences if _is_pro_drop(s)) / len(sentences), 3)
        if sentences else 0.0
    )

    top_noun_repetition_per_1k = _top_repetition_per_1k(text)

    return StylometryStats(
        dash_per_1k=dash_per_1k,
        colon_per_1k=colon_per_1k,
        semicolon_per_1k=semicolon_per_1k,
        ta_per_1k=ta_per_1k,
        dem_classifier_per_1k=dem_classifier_per_1k,
        pro_drop_ratio=pro_drop_ratio,
        top_noun_repetition_per_1k=top_noun_repetition_per_1k,
    )


def analyze_file(path: str | Path) -> StylometryStats | None:
    """分析一个文件，返回量化文风靶统计；读取失败返回 None"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"❌ 读取文件失败: {path}: {e}", file=sys.stderr)
        return None
    return analyze_text(text)
