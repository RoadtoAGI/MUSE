#!/usr/bin/env python3
"""打印语料覆盖矩阵（设计 §5.2）与各作品的语域三项分布，每批入库后跑一次。

矩阵只数写作范文默认能召回的场景：聚合索引 embeddings/scene_index.json 中原作语言等于 --lang、
媒介在 --source-medium 内、不是 exemplar_pool: on_request 的行（on_request 的作品另列，
--novel 点名才用），按 narrative_person × register 分格，列出场景数、正文字数、
作者数和主要来源。§5.1 要求每格至少两位作者、合计 20 万字以上，矩阵末列标出是否达到。
三项分布（口语标记、对白占比、平均句长）按作品从场景文件现算，供作者核对
annotate_register.py 的阈值。

用法::

    python3 kb_coverage.py
    python3 kb_coverage.py --lang en
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from . import annotate_register as ar
    from . import kb_index
except ImportError:
    import annotate_register as ar
    import kb_index

KB_ROOT = Path(__file__).resolve().parent.parent

# 设计 §5.2 的目标（中文原作）；None 表示该格不补。
ZH_TARGETS = {
    ("first", "colloquial"): 60,
    ("first", "literary"): 40,
    ("third", "colloquial"): 80,
    ("third", "literary"): None,
}
CELL_MIN_AUTHORS = 2
CELL_MIN_CHARS = 200_000
CELL_ORDER = [(p, r) for p in ("first", "third", "mixed") for r in ("colloquial", "literary", "mixed", None)]


def _allowed_media(source_medium: str) -> set[str] | None:
    if not source_medium or source_medium == "all":
        return None
    return {m.strip() for m in source_medium.split(",") if m.strip()}


def recallable_rows(index: list[dict], lang: str, source_medium: str,
                    on_request: list[dict] | None = None) -> tuple[list[dict], list[dict], int]:
    """返回 (默认池原作行, 同语言译本行, 缺标注字段的行数)；on_request 的原作行放进传入的列表。"""
    media = _allowed_media(source_medium)
    originals: list[dict] = []
    translations: list[dict] = []
    unannotated = 0
    for row in index:
        if media and row.get("source_medium", "novel") not in media:
            continue
        if row.get("lang") != lang:
            continue
        if "narrative_person" not in row or "original_lang" not in row:
            unannotated += 1
            continue
        if row.get("original_lang") != lang:
            translations.append(row)
        elif row.get("exemplar_pool") == "on_request":
            if on_request is not None:
                on_request.append(row)
        else:
            originals.append(row)
    return originals, translations, unannotated


def _row_chars(row: dict) -> int:
    count = row.get("word_count")
    return count if isinstance(count, int) else 0


def matrix_lines(rows: list[dict], lang: str) -> list[str]:
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        cells[(row.get("narrative_person"), row.get("register"))].append(row)
    targets = ZH_TARGETS if lang == "zh" else {}
    lines = ["人称 × 语域\t场景\t字数\t作者\t主要来源\t目标\t两位作者且 20 万字"]
    keys = [k for k in CELL_ORDER if k in cells or k in targets] + sorted(
        (k for k in cells if k not in CELL_ORDER), key=str)
    for key in keys:
        members = cells.get(key, [])
        works = Counter(r.get("novel") for r in members)
        authors = {r.get("author") or r.get("novel") for r in members}
        chars = sum(_row_chars(r) for r in members)
        top = "、".join(f"{w} {n}" for w, n in works.most_common(3)) or "—"
        if key not in targets:
            target_text = "—"
        elif targets[key] is None:
            target_text = "不补"
        else:
            target_text = f"≥ {targets[key]}"
        enough = "是" if len(authors) >= CELL_MIN_AUTHORS and chars >= CELL_MIN_CHARS else "否"
        label = f"{key[0] or '—'} × {key[1] or '—'}"
        lines.append(f"{label}\t{len(members)}\t{chars:,}\t{len(authors)}\t{top}\t{target_text}\t{enough}")
    return lines


def _span(values: list[float]) -> str:
    if not values:
        return "—"
    return f"{min(values):.1f} / {statistics.median(values):.1f} / {max(values):.1f}"


def feature_lines(kb_root: Path, lang: str) -> list[str]:
    lines = ["三项各列最小 / 中位 / 最大；戏剧不判 register",
             "作品\t场景\t口语标记/千字\t对白占比\t平均句长\tregister 计数"]
    for index_path in kb_index.iter_work_indexes(kb_root):
        work_dir = index_path.parent
        drama = kb_index.medium_of(index_path) == "drama"
        profile = ar.work_profile(work_dir)
        if (profile["text_lang"] or "zh") != lang:
            continue
        feats = []
        registers: Counter = Counter()
        for entry in kb_index.load_index(index_path):
            scene = work_dir / entry.get("file", "")
            if not scene.is_file():
                continue
            feat = ar.features(scene.read_text(encoding="utf-8"), lang, drama=drama)
            feats.append(feat)
            registers[None if drama else ar.classify_register(feat)] += 1
        if not feats:
            continue
        reg = "、".join(f"{k or '—'} {v}" for k, v in sorted(registers.items(), key=str))
        tag = f"{work_dir.name}（{profile['original_lang'] or '?'}）"
        lines.append(
            f"{tag}\t{len(feats)}\t{_span([f.markers_per_1k for f in feats])}\t"
            f"{_span([f.dialogue_ratio for f in feats])}\t{_span([f.mean_sentence_len for f in feats])}\t{reg}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="语料覆盖矩阵与语域三项分布")
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--source-medium", default="novel",
                        help="与 kb_query 同义；默认 novel，'all' 不过滤")
    parser.add_argument("--no-features", action="store_true", help="只打印矩阵")
    parser.add_argument("--kb", default=str(KB_ROOT))
    args = parser.parse_args(argv)

    kb_root = Path(args.kb)
    index_path = kb_root / "embeddings" / "scene_index.json"
    if not index_path.exists():
        print(f"[coverage] 聚合索引不存在: {index_path}", file=sys.stderr)
        return 2
    index = json.loads(index_path.read_text(encoding="utf-8"))
    on_request: list[dict] = []
    originals, translations, unannotated = recallable_rows(index, args.lang, args.source_medium, on_request)

    print(f"## 覆盖矩阵：{args.lang} 原作，source_medium={args.source_medium}")
    print(f"默认可召回 {len(originals)} 场（{len({r.get('novel') for r in originals})} 部）；"
          f"同语言译本另有 {len(translations)} 场，--original-only 下不召回")
    if on_request:
        works = Counter(r.get("novel") for r in on_request)
        print("exemplar_pool: on_request（--novel 点名才用）："
              + "、".join(f"{name} {n} 场" for name, n in works.most_common()))
    if args.lang not in ar.REGISTER_LANGS:
        print(f"{args.lang} 的 register 阈值尚未标定，本列为空，检索时 --register 对其不过滤")
    if unannotated:
        print(f"⚠️ {unannotated} 行缺 narrative_person / original_lang：先跑 annotate_register.py，"
              "再跑 merge_scene_index.py", file=sys.stderr)
    print("\n".join(matrix_lines(originals, args.lang)))

    if not args.no_features:
        print(f"\n## 语域三项分布：文本语言 {args.lang}（作品名后括号为原作语言）")
        print("\n".join(feature_lines(kb_root, args.lang)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
