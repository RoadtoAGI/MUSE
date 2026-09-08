#!/usr/bin/env python3
"""Evaluate kb_query retrieval configurations on a graded query set."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb_query  # noqa: E402

KB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_SET = KB_ROOT / "eval" / "retrieval-queries.yaml"


CONFIGS = [
    {"name": "baseline", "hybrid": False, "style_mode": "bigram", "mmr_lambda": 0.0},
    {"name": "+hybrid", "hybrid": True, "style_mode": "bigram", "mmr_lambda": 0.0},
    {"name": "+stylevec", "hybrid": False, "style_mode": "vector", "mmr_lambda": 0.0},
    {"name": "+mmr", "hybrid": False, "style_mode": "bigram", "mmr_lambda": 0.7},
    {"name": "full", "hybrid": True, "style_mode": "vector", "mmr_lambda": 0.7},
    # fit 进 rank 的 gate 对照（design §7）——use_function_hint 只控制是否传 function_hint；
    # 混合权重（FIT_RANK_WEIGHT）是 kb_query.py 内部默认逻辑，本文件不重复实现。
    {"name": "+function", "hybrid": True, "style_mode": "vector", "mmr_lambda": 0.7, "use_function_hint": True},
]


def _key(item: dict) -> tuple[str, str]:
    return (item.get("novel", ""), item.get("scene_id", ""))


def recall_at_k(results: list[dict], relevant: dict[tuple[str, str], int], k: int = 5) -> float:
    if not relevant:
        return 0.0
    hits = {_key(item) for item in results[:k]} & set(relevant)
    return len(hits) / len(relevant)


def mrr(results: list[dict], relevant: dict[tuple[str, str], int]) -> float:
    for rank, item in enumerate(results, start=1):
        if _key(item) in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(grades: list[int], *, ideal: list[int] | None = None, k: int = 2) -> float:
    def dcg(vals: list[int]) -> float:
        return sum((2 ** grade - 1) / math.log2(i + 2) for i, grade in enumerate(vals[:k]))

    ideal_vals = ideal if ideal is not None else sorted(grades, reverse=True)
    denom = dcg(ideal_vals)
    if denom == 0:
        return 0.0
    return dcg(grades) / denom


def _query_relevant(query: dict) -> dict[tuple[str, str], int]:
    return {(item["novel"], item["scene_id"]): int(item.get("grade", 1)) for item in query.get("relevant", [])}


def _default_retriever(query: dict, config: dict) -> list[dict]:
    return kb_query.query(
        query_text=query["query"],
        genre=query.get("genre"),
        source_medium=query.get("source_medium", "novel"),
        top_k=5,
        threshold=0.0,
        style_hint=query.get("style_hint"),
        style_mode=config["style_mode"],
        function_hint=query.get("function_hint") if config.get("use_function_hint") else None,
        hybrid=config["hybrid"],
        mmr_lambda=config["mmr_lambda"],
    )


def _score_query(results: list[dict], relevant: dict[tuple[str, str], int]) -> dict:
    grades = [relevant.get(_key(item), 0) for item in results]
    ideal = sorted(relevant.values(), reverse=True)
    style_vals = [float(item.get("style_match", 0) or 0) for item in results[:5]]
    return {
        "recall@5": recall_at_k(results, relevant, 5),
        "mrr": mrr(results, relevant),
        "ndcg@2": ndcg_at_k(grades, ideal=ideal, k=2),
        "style_match@5": sum(style_vals) / len(style_vals) if style_vals else 0.0,
    }


def run_eval(eval_set: str | Path = DEFAULT_EVAL_SET, *, out_path: str | Path | None = None,
             retriever=None) -> dict:
    eval_set = Path(eval_set)
    if not eval_set.exists():
        raise SystemExit(2)
    queries = yaml.safe_load(eval_set.read_text(encoding="utf-8")) or []
    retriever = retriever or _default_retriever
    metrics = {
        "query_count": len(queries),
        "eval_set": str(eval_set),
        "configs": {},
    }
    for config in CONFIGS:
        rows = []
        for query in queries:
            print(f"[eval] {config['name']} {query.get('query_id', '?')}", file=sys.stderr)
            results = retriever(query, config)
            rows.append(_score_query(results, _query_relevant(query)))
        denom = max(len(rows), 1)
        metrics["configs"][config["name"]] = {
            key: sum(row[key] for row in rows) / denom
            for key in ("recall@5", "mrr", "ndcg@2", "style_match@5")
        }
    if out_path:
        Path(out_path).write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def _print_table(metrics: dict) -> None:
    print("config\trecall@5\tmrr\tndcg@2\tstyle_match@5")
    for name, vals in metrics["configs"].items():
        print(
            f"{name}\t{vals['recall@5']:.4f}\t{vals['mrr']:.4f}\t"
            f"{vals['ndcg@2']:.4f}\t{vals['style_match@5']:.4f}"
        )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Evaluate KB retrieval matrix")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--out")
    parser.add_argument("--all", action="store_true", help="Run the full standard matrix")
    args = parser.parse_args(argv)

    metrics = run_eval(args.eval_set, out_path=args.out)
    _print_table(metrics)
    return metrics


if __name__ == "__main__":
    main()
