"""
大纲侧 inspiration card 查询：按 Phase 与 signals 字段匹配，把候选卡物化到本次 pipeline。

匹配契约（signals 容错）：接收任意 JSON 键值——已知键族（题材 genre / 冲突 conflict）加权，
未知键按自由文本权重 1.0 参与；中文按字符二元组覆盖率软匹配（同 kb_query 语态重排方案，
零额外 API），英文按词级匹配。不维护 per-phase 键表。

失败语义镜像 kb_query：卡库缺失或无匹配均 exit 2，调用方 graceful skip。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

try:
    from . import kb_index
    from . import runtime_assistance
    from .reference_scope import _reference_scope, bind_reference_profile
except ImportError:
    import kb_index
    import runtime_assistance
    from reference_scope import _reference_scope, bind_reference_profile

KB_ROOT = Path(__file__).resolve().parent.parent
ASCII_RE = re.compile(r"[a-z0-9_\-]+")
CJK_RE = re.compile(r"[一-鿿]+")

# phase 命中基线分；signals 覆盖率经 SIGNAL_SCALE × 键权重放大后叠加——
# 同 phase 池内由 signals 分层，跨 phase 仅多键强匹配可逆转
PHASE_BONUS = 5.0
SIGNAL_SCALE = 3.0
PREFERRED_WORK_BONUS = 8.0


def signal_weight(key: str) -> float:
    """已知键族加权：题材与冲突是卡库差异化检索的主轴，其余键自由文本同权。"""
    k = key.lower()
    if "genre" in k or "题材" in k:
        return 2.0
    if any(t in k for t in ("conflict", "crisis", "冲突", "困境")):
        return 1.8
    return 1.0


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def text_tokens(text: str) -> set[str]:
    """匹配 token 面 = 英文词 + 中文字符二元组（单字 run 保留原字）。"""
    lowered = text.lower()
    tokens: set[str] = set(ASCII_RE.findall(lowered))
    for run in CJK_RE.findall(lowered):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(a + b for a, b in zip(run, run[1:]))
    return tokens


def signals_tokens(value: Any) -> set[str]:
    return text_tokens(_flatten_text(value))


def card_tokens(card: dict) -> set[str]:
    fields = [
        card.get("pattern_name"),
        card.get("dramatic_function"),
        card.get("applicability"),
        card.get("tags"),
        card.get("reuse_candidates"),
        card.get("mechanism"),
        [{key: analysis.get(key) for key in
          ("creative_move", "narrative_reason", "transfer_conditions")}
         for analysis in card.get("source_analyses", []) if isinstance(analysis, dict)],
        [scene.get("note") for scene in (card.get("source_scenes") or []) if isinstance(scene, dict)],
    ]
    return signals_tokens(fields)


def load_cards(kb_root: Path = KB_ROOT) -> list[dict]:
    insp_dir = kb_root / "inspiration"
    if not insp_dir.exists():
        return []
    cards = []
    for path in sorted(insp_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            card = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(card, dict):
            card["_source_path"] = str(path)
            cards.append(card)
    return cards


def signal_items(signal_obj: dict) -> list[tuple[str, set[str], float]]:
    """signals JSON → (键, token 集, 权重) 列表；空值键剔除。"""
    items = []
    if not isinstance(signal_obj, dict):
        return items
    for key, value in signal_obj.items():
        tokens = signals_tokens(value)
        if tokens:
            items.append((str(key), tokens, signal_weight(str(key))))
    return items


def _source_works(card: dict) -> set[str]:
    return {
        str(scene.get("novel"))
        for scene in (card.get("source_scenes") or [])
        if isinstance(scene, dict) and scene.get("novel")
    }


def score_card(
    card: dict,
    phase: int,
    items: list[tuple[str, set[str], float]],
    preferred_works: set[str] | None = None,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    phases = card.get("phase_affinity") or []
    ctokens = card_tokens(card)
    semantic_score = 0.0
    for key, tokens, weight in items:
        coverage = len(tokens & ctokens) / len(tokens)
        if coverage > 0:
            increment = SIGNAL_SCALE * weight * coverage
            semantic_score += increment
            reasons.append(f"{key}:{coverage:.2f}(w{weight})")
    if items and semantic_score == 0:
        return 0.0, []
    score += semantic_score
    if phase in phases:
        score += PHASE_BONUS
        reasons.append(f"phase={phase}")
    elif not items:
        return 0.0, []
    matched_preferred = (preferred_works or set()) & _source_works(card)
    if matched_preferred:
        score += PREFERRED_WORK_BONUS
        reasons.append("preferred=" + ",".join(sorted(matched_preferred)))
    return round(score, 3), reasons


def rank_cards(
    cards: list[dict],
    phase: int,
    signal_obj: dict,
    limit: int = 5,
    preferred_works: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    items = signal_items(signal_obj)
    preferred = {item for item in (preferred_works or []) if item}
    ranked = []
    for card in cards:
        score, reasons = score_card(card, phase, items, preferred)
        ranked.append({**card, "_score": score, "_reasons": reasons})
    ranked.sort(key=lambda c: (-c["_score"], c.get("card_id", "")))
    selected = [c for c in ranked if c["_score"] > 0][:limit]
    rejected = [c for c in ranked if c not in selected]
    return selected, rejected


def scoped_cards(cards: list[dict], profile_path: str | None) -> list[dict]:
    """A cross-source card is usable only within all its sources' shared scope."""
    if not profile_path:
        return cards
    def declared_sources(card):
        return _source_works(card) | {
            str(analysis["novel"]) for analysis in (card.get("source_analyses") or [])
            if isinstance(analysis, dict) and analysis.get("novel")
        }

    works = sorted({work for card in cards for work in declared_sources(card)})
    allowed = {row["novel"]: row for row in
               bind_reference_profile([{"novel": work} for work in works], profile_path)}
    scoped = []
    for card in cards:
        sources = declared_sources(card)
        if sources - allowed.keys():
            continue
        scope = {}
        for work in sorted(sources):
            source = allowed[work]
            mode, domains = _reference_scope(scope, source.get("reuse_mode"), source.get("intended_domains"))
            if domains == []:
                break
            scope = {"reuse_mode": mode, "intended_domains": domains}
        else:
            scoped.append({**card, "_reuse_mode": scope.get("reuse_mode"),
                           "_intended_domains": scope.get("intended_domains"),
                           "_style_only": scope.get("reuse_mode") == "style_only" or
                           scope.get("intended_domains") == ["prose_style_imitation"]})
    return scoped


def render_cards(phase: int, selected: list[dict], rejected: list[dict]) -> str:
    lines = [f"# Inspiration Cards — Phase {phase}", ""]
    lines.extend(["排序表示检索相关性。采用机制时结合本作条件判断；卡面不足以解释时回读原文。", ""])
    lines.append("## Selected")
    lines.append("")
    for card in selected:
        lines.append(f"### {card.get('card_id')} — {card.get('pattern_name')}")
        lines.append(f"- score: {card.get('_score')}")
        lines.append(f"- reasons: {', '.join(card.get('_reasons', []))}")
        if card.get("_reuse_mode"):
            lines.append(f"- reuse_mode: {card['_reuse_mode']}")
        if card.get("_intended_domains"):
            lines.append(f"- intended_domains: {', '.join(card['_intended_domains'])}")
        tags = card.get("tags") or []
        if tags:
            lines.append(f"- tags: {'；'.join(map(str, tags))}")
        lines.append(f"- dramatic_function: {card.get('dramatic_function', '')}")
        lines.append(f"- applicability: {card.get('applicability', '')}")
        if card.get("mechanism"):
            lines.append(f"- mechanism: {card['mechanism']}")
        if card.get("_source_path"):
            lines.append(f"- card_source: {card['_source_path']}")
        for analysis in card.get("source_analyses") or []:
            lines.extend([
                f"\n#### 原作分析：{analysis.get('novel', '')}",
                f"- creative_move: {analysis.get('creative_move', '')}",
                f"- narrative_reason（文本分析）: {analysis.get('narrative_reason', '')}",
                f"- transfer_conditions: {analysis.get('transfer_conditions', '')}",
                f"- source_scene_ids: {', '.join(analysis.get('source_scene_ids') or [])}",
            ])
            if analysis.get("author_motivation"):
                author = analysis["author_motivation"]
                lines.append(f"- author_motivation: {author['claim']}（来源：{author['source']}）")
        analyzed = {a.get("novel") for a in card.get("source_analyses") or []}
        summary_only = _source_works(card) - analyzed
        if summary_only:
            lines.append("- 仅有检索摘要，采用前按需补读：" + "、".join(sorted(summary_only)))
        reuse = card.get("reuse_candidates") or []
        if reuse:
            lines.append(f"- reuse_candidates: {'；'.join(map(str, reuse))}")
        phases = card.get("phase_affinity") or []
        if phases:
            lines.append(f"- design_scale: phase {'/'.join(map(str, phases))}")
        for scene in card.get("source_scenes") or []:
            window = (f" L{scene['line_start']}-L{scene['line_end']}"
                      if "line_start" in scene and "line_end" in scene else "（完整场景）")
            lines.append(
                f"- source: {scene.get('novel', '')} · {scene.get('scene_id', '')} — "
                f"{scene.get('note', '')}{window}"
            )
        lines.append("")
    lines.append("## 落选")
    lines.append("")
    for card in rejected:
        lines.append(f"- {card.get('card_id')} — {card.get('pattern_name')} (score={card.get('_score')})")
    return "\n".join(lines) + "\n"


def read_card(card_id: str, output_dir: str, sources: list[str] | None = None) -> int:
    """Export selected original passages through exact per-work indexes; no model call."""
    card = next((c for c in load_cards(KB_ROOT) if c.get("card_id") == card_id), None)
    if card is None:
        print(f"[inspiration_query NO_CARD] {card_id}", file=sys.stderr)
        return 2
    # Use the known card filename, not arbitrary CLI text, for the output name.
    out_path = Path(output_dir) / "inspiration" / f"{Path(card['_source_path']).stem}_reading.md"
    requested = set(sources or [])
    scenes = card.get("source_scenes") or []
    available = {f"{s.get('novel')}:{s.get('scene_id')}" for s in scenes}
    if requested - available:
        out_path.unlink(missing_ok=True)
        print(f"[inspiration_query SOURCE_MISSING] 卡内无来源 {sorted(requested - available)}", file=sys.stderr)
        return 2
    passages = []
    try:
        for scene in scenes:
            key = f"{scene['novel']}:{scene['scene_id']}"
            if requested and key not in requested:
                continue
            index_path = kb_index.find_index_path(KB_ROOT, scene["novel"])
            if index_path is None:
                raise ValueError(f"{key} 无作品索引")
            entry = next((e for e in kb_index.load_index(index_path)
                          if e.get("scene_id") == scene["scene_id"]), None)
            if entry is None or not entry.get("file"):
                raise ValueError(f"{key} 无原文 file")
            path = index_path.parent / entry["file"]
            lines = path.read_text(encoding="utf-8").splitlines()
            start, end = scene.get("line_start", 1), scene.get("line_end", len(lines))
            if (type(start) is not int or type(end) is not int
                    or start < 1 or end < start or end > len(lines)):
                raise ValueError(f"{key} 原文行范围无效")
            passages.append(
                f"## {key} · L{start}-L{end}\n\n"
                f"来源：{path.resolve()}\n\n用途：{scene.get('note', '')}\n\n"
                + "\n".join(f"{n}: {line}" for n, line in enumerate(lines[start-1:end], start))
            )
        if not passages:
            raise ValueError("卡片没有可读来源")
    except (OSError, ValueError, KeyError) as exc:
        out_path.unlink(missing_ok=True)
        print(f"[inspiration_query SOURCE_MISSING] {exc}", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"# 原文回读：{card_id}\n\n" + "\n\n".join(passages) + "\n", encoding="utf-8")
    print(f"写入: {out_path}")
    return 0


def run(
    phase: int,
    signals: str,
    output_dir: str,
    top_k: int = 5,
    preferred_works: list[str] | None = None,
    work_dir: str | None = None,
    must: list[str] | None = None,
    canon_reference_profile: str | None = None,
) -> int:
    out_path = Path(output_dir) / "inspiration" / f"phase{phase}_cards.md"
    cards = load_cards(KB_ROOT)
    if not cards:
        out_path.unlink(missing_ok=True)
        print("[inspiration_query KB_MISSING] inspiration 卡库为空或不存在", file=sys.stderr)
        return 2

    try:
        signal_obj = json.loads(signals) if signals else {}
    except ValueError as e:
        out_path.unlink(missing_ok=True)
        print(f"[inspiration_query SIGNALS_WARN] signals JSON 解析失败: {e}", file=sys.stderr)
        return 2
    try:
        must = runtime_assistance.checked_must(must)
        assistance = runtime_assistance.settings_for(work_dir, output_dir)
        cards = scoped_cards(cards, canon_reference_profile)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        out_path.unlink(missing_ok=True)
        print(f"[inspiration_query CONFIG_ERROR] {exc}", file=sys.stderr)
        return 2
    selected, rejected = rank_cards(cards, phase, signal_obj, top_k, preferred_works)
    metadata = {"request_id": uuid4().hex, "mode": assistance.mode if assistance else "standard",
                "phase": phase, "strategy": "baseline"}
    if assistance is not None and assistance.enabled and selected and signal_items(signal_obj):
        pool, _ = rank_cards(cards, phase, signal_obj, max(top_k * 3, 9), preferred_works)
        views = [{"id": c["card_id"], "intended_domains": c.get("_intended_domains"),
                  "style_only": c.get("_style_only", False),
                  "material": {k: v for k, v in c.items() if not k.startswith("_")}}
                 for c in pool]
        try:
            assessed = runtime_assistance.rank(
                assistance, "inspiration_retrieval",
                {"phase": phase, "signals": signal_obj,
                 "design_scale": "premise" if phase == 0 else "plot_plan" if phase == 3 else "chapter_outline" if phase == 5 else "design"},
                views, must=must, request_id=metadata["request_id"])
        except ValueError as exc:
            out_path.unlink(missing_ok=True)
            print(f"[inspiration_query CONFIG_ERROR] {exc}", file=sys.stderr)
            return 2
        metadata["strategy"] = "fallback" if assessed is None else "score"
        if assessed is not None and preferred_works:
            # Keep the existing soft preference contract until its fusion is validated.
            metadata["strategy"] = "evaluation_only_preferred"
        elif assessed is not None:
            by_id = {c["card_id"]: c for c in pool}
            ranked = [by_id[a["id"]] for a in assessed]
            selected = ranked[:top_k]
            selected_ids = {c["card_id"] for c in selected}
            # Preserve the existing unselected-card list and its baseline metadata.
            all_ranked, all_rejected = rank_cards(cards, phase, signal_obj, len(cards), preferred_works)
            rejected = [c for c in all_ranked + all_rejected if c["card_id"] not in selected_ids]
    if not selected:
        out_path.unlink(missing_ok=True)
        print("[inspiration_query NO_MATCH] 无匹配 inspiration cards", file=sys.stderr)
        return 2

    out_dir = Path(output_dir) / "inspiration"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_cards(phase, selected, rejected), encoding="utf-8")
    metadata["selected_ids"] = [card["card_id"] for card in selected]
    runtime_assistance.record(assistance, "inspiration_retrieval", "delivered",
                              **metadata, output_path=str(out_path))
    print(f"写入: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="按大纲 signals 查询 inspiration cards")
    parser.add_argument("--phase", type=int, choices=range(6), help="0=构想，1-5=设计阶段")
    parser.add_argument("--read-card", help="按 card_id 物化原文，替代本次检索")
    parser.add_argument("--source", action="append", default=[], help="回读时限定 作品:scene_id；可重复")
    parser.add_argument("--signals", default="{}")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--work-dir", help="作品工作区；默认沿 output-dir 的 pipeline 归属")
    parser.add_argument("--must", action="append", default=[], help="当前用途的必要条件；可重复，一次一个条件")
    parser.add_argument("--canon-reference-profile", help="当前 Phase 0 YAML；按所有卡内来源取用途交集")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--preferred-work",
        action="append",
        default=[],
        help="用户手选作品；可重复传入，命中来源时优先排序",
    )
    args = parser.parse_args()
    if args.read_card:
        return read_card(args.read_card, args.output_dir, args.source)
    if args.phase is None or args.source:
        parser.error("检索需 --phase；--source 仅用于 --read-card")
    return run(args.phase, args.signals, args.output_dir, args.top_k, args.preferred_work,
               args.work_dir, args.must, args.canon_reference_profile)


if __name__ == "__main__":
    sys.exit(main())
