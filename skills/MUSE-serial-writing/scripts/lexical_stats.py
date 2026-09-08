#!/usr/bin/env python3
"""S2 — 副词密度 / TTR / 高频词 / 感官平衡 lint（统计型脚本）。

覆盖 55+1 条清单第 5/11/13/30 条。统计型脚本 hits[] 保持空，场景级信号由
density.sensory_balance.imbalanced / density.adverb.overuse / density.ttr.too_low
布尔字段承载——下游 scene-reviewer 自行判断是否升级为场景级 issue。

jieba 硬依赖；缺失 fail-fast。阈值从 CLI 注入；生效阈值回写 meta.thresholds。
"""
from __future__ import annotations
import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

try:
    import jieba
    jieba.setLogLevel(60)
except ImportError:
    jieba = None  # main() 启动时 fail-fast


ADVERBS = [
    "非常", "极其", "格外", "稍稍", "默默",
    "缓缓", "静静", "深深", "轻轻", "微微",
]

SENSORY_LEXICON = {
    "visual": ["看", "望", "见", "瞥", "凝视", "注视", "目光", "眼", "光", "影"],
    "auditory": ["听", "闻", "声", "响", "喊", "叫", "低语", "呢喃"],
    "tactile": ["触", "摸", "冰凉", "温热", "疼", "颤抖", "冷", "烫"],
    "olfactory": ["味", "腥", "香", "臭", "气息"],
    "gustatory": ["尝", "咸", "甜", "苦", "涩"],
}

DEFAULT_VISUAL_RATIO_THRESHOLD = 0.70
DEFAULT_ADVERB_PER_1K_THRESHOLD = 20.0
DEFAULT_TTR_MIN_THRESHOLD = 0.40


def adverb_density(text: str) -> dict:
    total = len(text)
    counts: Counter[str] = Counter()
    for adv in ADVERBS:
        counts[adv] += text.count(adv)
    total_hits = sum(counts.values())
    return {
        "count": total_hits,
        "per_1k": round(total_hits / max(total, 1) * 1000, 2),
        "by_pattern": {k: v for k, v in counts.items() if v > 0},
    }


def sensory_balance(text: str) -> dict:
    counts = {cat: 0 for cat in SENSORY_LEXICON}
    for cat, words in SENSORY_LEXICON.items():
        for w in words:
            counts[cat] += text.count(w)
    total = sum(counts.values())
    if total == 0:
        return {"counts": counts, "visual_ratio": 0.0}
    visual_ratio = counts["visual"] / total
    return {
        "counts": counts,
        "visual_ratio": round(visual_ratio, 3),
    }


def type_token_ratio(text: str) -> dict:
    tokens = [t for t in jieba.lcut(text) if t.strip() and len(t) > 1]
    if not tokens:
        return {"ttr": 0.0, "token_count": 0}
    return {
        "ttr": round(len(set(tokens)) / len(tokens), 3),
        "token_count": len(tokens),
    }


def top_k_nouns(text: str, k: int = 20) -> list[dict]:
    tokens = [t for t in jieba.lcut(text) if len(t) > 1 and t.strip()]
    counter = Counter(tokens)
    return [{"token": t, "count": c} for t, c in counter.most_common(k)]


def analyze(
    text: str,
    visual_ratio_threshold: float = DEFAULT_VISUAL_RATIO_THRESHOLD,
    adverb_per_1k_threshold: float = DEFAULT_ADVERB_PER_1K_THRESHOLD,
    ttr_min_threshold: float = DEFAULT_TTR_MIN_THRESHOLD,
) -> dict:
    adv = adverb_density(text)
    balance = sensory_balance(text)
    ttr = type_token_ratio(text)
    top = top_k_nouns(text, 20)

    balance["imbalanced"] = balance["visual_ratio"] > visual_ratio_threshold
    adv["overuse"] = adv["per_1k"] > adverb_per_1k_threshold
    ttr["too_low"] = ttr["ttr"] < ttr_min_threshold

    return {
        "hits": [],
        "density": {
            "total_chars": len(text),
            "adverb": adv,
            "sensory_balance": balance,
            "ttr": ttr,
            "top_20_tokens": top,
        },
        "meta": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="S2 lexical stats lint")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--visual-ratio-threshold", type=float, default=None)
    parser.add_argument("--adverb-per-1k-threshold", type=float, default=None)
    parser.add_argument("--ttr-min-threshold", type=float, default=None)
    parser.add_argument("--genre", default=None)
    args = parser.parse_args()

    if jieba is None:
        print("[lexical_stats] ERROR: jieba 未安装。硬依赖，请 pip install jieba", file=sys.stderr)
        return 1

    work_dir: Path = args.work_dir.resolve()
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{args.scene_id}.md"
    if not scene_path.exists():
        print(f"[lexical_stats] ERROR: {scene_path} not found", file=sys.stderr)
        return 1

    cli_overrides = {
        "visual_ratio": args.visual_ratio_threshold,
        "adverb_per_1k": args.adverb_per_1k_threshold,
        "ttr_min": args.ttr_min_threshold,
    }
    defaults = {
        "visual_ratio": DEFAULT_VISUAL_RATIO_THRESHOLD,
        "adverb_per_1k": DEFAULT_ADVERB_PER_1K_THRESHOLD,
        "ttr_min": DEFAULT_TTR_MIN_THRESHOLD,
    }
    thresholds = {k: (v if v is not None else defaults[k]) for k, v in cli_overrides.items()}
    threshold_source = "cli" if any(v is not None for v in cli_overrides.values()) else "default"

    text = scene_path.read_text(encoding="utf-8")
    result = analyze(
        text,
        visual_ratio_threshold=thresholds["visual_ratio"],
        adverb_per_1k_threshold=thresholds["adverb_per_1k"],
        ttr_min_threshold=thresholds["ttr_min"],
    )
    result["meta"] = {
        "thresholds": thresholds,
        "threshold_source": threshold_source,
        "genre": args.genre,
    }
    output = {
        "scene_id": args.scene_id,
        "script": "lexical_stats",
        "version": "r2",
        **result,
    }

    out_path = work_dir / "pipeline" / "review" / "lint" / f"{args.scene_id}.lexical_stats.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(output, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    balance = result["density"]["sensory_balance"]
    print(
        f"✅ {out_path} · adverb={result['density']['adverb']['per_1k']}/1k · "
        f"visual_ratio={balance['visual_ratio']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
