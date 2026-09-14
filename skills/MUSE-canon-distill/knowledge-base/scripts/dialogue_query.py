#!/usr/bin/env python3
"""Retrieve role-scoped multi-turn dialogue exemplars without an API call."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_KB_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MATCH_FIELDS = ("relationship", "pressure", "speech_action")
CONTEXT_FIELDS = {"relationship", "power", "pressure"}
TURN_FIELDS = {"speech_action", "cooperation", "capacity"}


def terms(value: str) -> set[str]:
    value = value.lower().strip()
    words = set(re.findall(r"[a-z0-9_-]+", value))
    compact = re.sub(r"\s+", "", value)
    words.update(compact[i : i + 2] for i in range(max(0, len(compact) - 1)))
    return {item for item in words if item}


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return "" if value is None else str(value)


def choices(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def event_field_values(event: dict[str, Any], field: str) -> set[str]:
    if field == "medium":
        value = event.get("medium")
        return {str(value).lower()} if value else set()
    if field in CONTEXT_FIELDS:
        context = event.get("context", {})
        value = context.get(field) if isinstance(context, dict) else None
        if isinstance(value, list):
            return {str(item).lower() for item in value if item is not None}
        return {str(value).lower()} if value else set()
    if field in TURN_FIELDS:
        values = set()
        for turn in event.get("turns", []):
            if not isinstance(turn, dict):
                continue
            value = turn.get(field)
            if isinstance(value, list):
                values.update(str(item).lower() for item in value if item is not None)
            elif value:
                values.add(str(value).lower())
        return values
    return set()


def missing_required_fields(args: argparse.Namespace) -> list[str]:
    return [field for field in REQUIRED_MATCH_FIELDS if not getattr(args, field, "")]


def score_event(event: dict[str, Any], args: argparse.Namespace) -> tuple[float, list[str]]:
    if event.get("event_type") not in {"interaction", "group_exchange"} and not args.include_monologue:
        return -1.0, []
    annotation = event.get("annotation", {})
    if not isinstance(annotation, dict) or annotation.get("review_status") not in {
        "source_checked",
        "reviewed",
    }:
        return -1.0, []
    score = 0.0
    reasons: list[str] = []
    structured = {
        "medium": args.medium,
        "relationship": args.relationship,
        "power": args.power,
        "pressure": args.pressure,
        "speech_action": args.speech_action,
        "cooperation": args.cooperation,
        "capacity": args.capacity,
    }
    turn_filters = {name: value for name, value in structured.items() if name in TURN_FIELDS and value}
    compatible_turns = [
        turn for turn in event.get("turns", []) if isinstance(turn, dict)
        and all(choices(expected) & event_field_values({"turns": [turn]}, name)
                for name, expected in turn_filters.items())
    ]
    if turn_filters and not compatible_turns:
        return -1.0, []
    haystack = flatten(event).lower()
    for label, expected in structured.items():
        if not expected:
            continue
        if label in TURN_FIELDS:
            score += 3.0
            reasons.append(label)
            continue
        if choices(expected) & event_field_values(event, label):
            score += 3.0
            reasons.append(label)
        else:
            return -1.0, []
    query_terms = terms(args.query or "")
    if query_terms:
        overlap = query_terms & terms(haystack)
        if overlap:
            score += min(4.0, len(overlap) * 0.5)
            reasons.append("context")
    if turn_filters:
        reasons.extend("target_turn:" + str(turn.get("turn_id") or turn.get("speaker_label") or turn.get("speaker_id") or "unlabeled") for turn in compatible_turns)
    return score, reasons


def decide_matches(
    events: list[dict[str, Any]], args: argparse.Namespace, *, top_k: int
) -> tuple[list[tuple[dict[str, Any], list[str]]], str, int, int]:
    missing = missing_required_fields(args)
    if missing:
        return [], "missing_required_fields:" + ",".join(missing), 0, 0

    ranked = []
    for event in events:
        if not isinstance(event, dict):
            continue
        score, reasons = score_event(event, args)
        if score >= 0:
            ranked.append((score, str(event.get("event_id", "")), event, reasons))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    distinct_works = {
        str(event.get("work_id")) for _, _, event, _ in ranked if event.get("work_id")
    }
    if not ranked:
        return [], "no_compatible_event", 0, 0

    selected = []
    selected_works: set[str] = set()
    for _, _, event, reasons in ranked:
        work = str(event.get("work_id", ""))
        if not work or work in selected_works:
            continue
        selected.append((event, reasons))
        selected_works.add(work)
        if len(selected) >= top_k:
            break
    return selected, "compatible_event", len(ranked), len(distinct_works)


def render_source_exchange(event: dict[str, Any]) -> list[str]:
    """Keep source conditions that a plain speaker/text transcript would hide."""
    turns = event.get("turns", [])
    participants = event.get("participants", [])
    labels = {
        p["character_id"]: p.get("display_name") or p["character_id"].rsplit(":", 1)[-1]
        for p in participants if p.get("character_id")
    }
    for turn in turns:
        if turn.get("speaker_id") and turn.get("speaker_label"):
            labels[turn["speaker_id"]] = turn["speaker_label"]
    participant_ids = set(labels)
    for turn in turns:
        if turn.get("speaker_id"):
            participant_ids.add(turn["speaker_id"])
        participant_ids.update(turn.get("addressee_ids") or [])
    by_id = {turn["turn_id"]: turn for turn in turns if turn.get("turn_id")}
    annotations = []
    needs_turn_ids = False
    for index, turn in enumerate(turns):
        notes = []
        recipients = turn.get("addressee_ids") or []
        # Two-person adjacent exchanges already make the ordinary receiver clear.
        if recipients and (
            len(participant_ids) > 2 or len(recipients) > 1
            or turn.get("speaker_id") in recipients
        ):
            notes.append("接收：" + "、".join(labels.get(r, r.rsplit(":", 1)[-1]) for r in recipients))
        elif "addressee_ids" in turn and not recipients:
            notes.append("接收未明")
        response_id = turn.get("response_to")
        prior = turns[index - 1] if index else {}
        response = by_id.get(response_id, {})
        if response_id and (
            response_id != prior.get("turn_id")
            or (turn.get("speaker_id") and turn.get("speaker_id") == response.get("speaker_id"))
        ):
            notes.append(f"回应：{response_id}")
            needs_turn_ids = True
        annotations.append(notes)

    lines = []
    for participant in participants:
        boundary = participant.get("knowledge_boundary")
        if boundary:
            name = labels.get(participant.get("character_id"), participant.get("display_name", "来源人物"))
            lines.append(f"来源知情条件（{name}）：{boundary}")
    if lines:
        lines.append("")
    lines.append("<dialogue_exemplar>")
    for turn, notes in zip(turns, annotations):
        speaker = turn.get("speaker_label") or labels.get(turn.get("speaker_id")) or str(turn.get("speaker_id", "speaker")).rsplit(":", 1)[-1]
        locator = f"[{turn['turn_id']}] " if needs_turn_ids and turn.get("turn_id") else ""
        receiving = f"（{'；'.join(notes)}）" if notes else ""
        lines.append(f"{locator}{speaker}{receiving}：{turn.get('text', '')}")
    lines.append("</dialogue_exemplar>")
    return lines


def render_reference(
    *,
    scene_id: str,
    role_slug: str,
    matches: list[tuple[dict[str, Any], list[str]]],
    match_reason: str = "no_compatible_event",
    eligible_event_count: int = 0,
    independent_source_count: int = 0,
) -> str:
    matched_works = {
        str(event.get("work_id")) for event, _ in matches if event.get("work_id")
    }
    if matches:
        eligible_event_count = max(eligible_event_count, len(matches))
        independent_source_count = max(independent_source_count, len(matched_works))
    lines = [
        "dialogue_reference: true",
        f"scene_id: {scene_id}",
        f"role_slug: {role_slug}",
        "reuse_policy: behavior_exemplar",
    ]
    if not matches:
        lines.extend(
            [
                "status: NO_MATCH",
                f"match_reason: {match_reason}",
                f"eligible_event_count: {eligible_event_count}",
                f"independent_source_count: {independent_source_count}",
                "",
                "本次没有取得相容对白事件。按当前角色依据与对白理论继续，不加载同名旧示例。",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "status: MATCH",
            f"match_reason: {match_reason}",
            f"eligible_event_count: {eligible_event_count}",
            f"independent_source_count: {independent_source_count}",
        ]
    )
    for index, (event, reasons) in enumerate(matches, start=1):
        lines.extend(
            [
                "",
                f"## 示例 {index}",
                f"- event_id: {event.get('event_id')}",
                f"- source: {event.get('work_id')} / {event.get('scene_id')}",
                f"- source_file: {event.get('event_file')}",
                "- source_locators: "
                + ", ".join(
                    dict.fromkeys(
                        str(turn.get("source_locator"))
                        for turn in event.get("turns", [])
                        if turn.get("source_locator")
                    )
                ),
                f"- match: {', '.join(reasons) if reasons else 'general_interaction'}",
                f"- context: {flatten(event.get('context', {}))}",
                "",
            ]
        )
        lines.extend(render_source_exchange(event))
        lines.append("")
        mechanism = event.get("transferable_mechanism") or event.get("outcome", {}).get("visible_result")
        visible_result = event.get("outcome", {}).get("visible_result")
        if visible_result and visible_result != mechanism:
            lines.append(f"来源结果：{visible_result}")
        lines.append(f"迁移机制：{mechanism or '观察上一轮如何改变下一轮。'}")
    lines.extend(
        [
            "",
            "<usage_protocol>",
            "按当前人物条件判断每个来源事件的互动机制；单例可以提供候选，多例可比较差异，来源数量不证明通法。以本人 role_view.character_basis 及调用方显式给出的合时补充为人物依据；不迁移示例人物的姓名、经历、专有称谓、标志性原句或固定口癖。",
            "来源的接收关系、知情条件和结果用于解释例子；当前人物能听见、知道和做到什么，仍由本场事实决定。",
            "</usage_protocol>",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", type=Path, default=DEFAULT_KB_ROOT)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--role-slug", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--medium", default="")
    parser.add_argument("--relationship", default="")
    parser.add_argument("--power", default="")
    parser.add_argument("--pressure", default="")
    parser.add_argument("--speech-action", default="")
    parser.add_argument("--cooperation", default="")
    parser.add_argument("--capacity", default="")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--include-monologue", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")

    index_path = args.kb_root.resolve() / "dialogue" / "event_index.json"
    events = []
    if index_path.exists():
        value = json.loads(index_path.read_text(encoding="utf-8"))
        events = value.get("events", []) if isinstance(value, dict) else []
    matches, match_reason, eligible_count, source_count = decide_matches(
        events, args, top_k=args.top_k
    )
    output = args.output_dir / f"{args.scene_id}_{args.role_slug}_dialogue_ref.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_reference(
            scene_id=args.scene_id,
            role_slug=args.role_slug,
            matches=matches,
            match_reason=match_reason,
            eligible_event_count=eligible_count,
            independent_source_count=source_count,
        ),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
