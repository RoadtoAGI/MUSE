"""Zero-API retrieval and rendering for source-verified rhetoric cards."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


INDEX_SCHEMA = "rhetoric-occurrence-index/v1"
ELIGIBLE_QUALITIES = {"exemplary", "effective"}
QUALITY_RANK = {"exemplary": 0, "effective": 1}
_PUNCTUATION = "，。、；：/（）「」『』！？·,.;:()<>\"'-—…"
_LOCATOR_RE = re.compile(r"^(?P<path>.+):L(?P<start>\d+)(?:-L?(?P<end>\d+))?$")


def _tokens(text: str) -> list[str]:
    """Tokenize Chinese as character bigrams and retain ASCII words."""

    ascii_words = re.findall(r"[A-Za-z0-9_]+", text.lower())
    chars = [char for char in text if not char.isspace() and char not in _PUNCTUATION]
    return ascii_words + [left + right for left, right in zip(chars, chars[1:])]


def load_occurrences(kb_root: Path) -> list[dict[str, Any]]:
    """Load the derived rhetoric index; missing or malformed data degrades to []."""

    path = Path(kb_root) / "rhetoric" / "occurrence_index.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != INDEX_SCHEMA
        or payload.get("scope_status") != "complete"
    ):
        return []
    occurrences = payload.get("occurrences")
    if not isinstance(occurrences, list):
        return []
    return [item for item in occurrences if isinstance(item, dict)]


def _classic_source_path(kb_root: Path, enrollment: Mapping[str, Any]) -> Path | None:
    """Resolve and checksum one frozen classic source enrollment."""

    required = ("container", "work", "source_file", "source_sha256", "start_line", "end_line")
    if any(field not in enrollment for field in required):
        return None
    container = str(enrollment["container"])
    work = str(enrollment["work"])
    source_file = str(enrollment["source_file"])
    if container not in {"novels", "dramas"}:
        return None
    container_dir = (kb_root / container).resolve()
    work_dir = (container_dir / work).resolve()
    if work_dir.parent != container_dir:
        return None
    source_path = (work_dir / source_file).resolve()
    try:
        source_path.relative_to(work_dir)
    except ValueError:
        return None
    if not source_path.is_file():
        return None
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return source_path if digest == enrollment["source_sha256"] else None


def _classic_quote_is_backed(
    source_path: Path,
    enrollment: Mapping[str, Any],
    locator: Any,
    quote: Any,
) -> bool:
    """Check that a representative card still points to its frozen source text."""

    if not isinstance(locator, str) or not isinstance(quote, str):
        return False
    match = _LOCATOR_RE.fullmatch(locator)
    if match is None or Path(match.group("path")).as_posix() != str(enrollment["source_file"]):
        return False
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if start < int(enrollment["start_line"]) or end > int(enrollment["end_line"]) or end < start:
        return False
    lines = source_path.read_text(encoding="utf-8").splitlines()
    if end > len(lines):
        return False
    window = re.sub(r"\s+", "", "\n".join(lines[start - 1 : end]))
    return bool(quote.strip()) and re.sub(r"\s+", "", quote) in window


def load_classic_exemplars(kb_root: Path) -> list[dict[str, Any]]:
    """Load source-checked representative cards and flatten their learning fields."""

    kb_root = Path(kb_root)
    cards_path = kb_root / "rhetoric" / "classics_rhetoric_exemplars.yaml"
    scope_path = kb_root / "rhetoric" / "corpus_scope.yaml"
    try:
        payload = yaml.safe_load(cards_path.read_text(encoding="utf-8")) or {}
        scope = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}
    except (OSError, TypeError, yaml.YAMLError):
        return []
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "rhetoric-learning-exemplars/v1"
        or payload.get("status") != "source_checked"
        or payload.get("scope_manifest") != "corpus_scope.yaml"
        or payload.get("scope_manifest_sha256")
        != hashlib.sha256(scope_path.read_bytes()).hexdigest()
        or not isinstance(payload.get("cards"), list)
        or not isinstance(scope, dict)
        or not isinstance(scope.get("corpus"), list)
    ):
        return []
    scope_by_title = {
        str(entry.get("title")): entry
        for entry in scope["corpus"]
        if isinstance(entry, dict) and entry.get("title")
    }
    card_titles = {
        str(card.get("work"))
        for card in payload["cards"]
        if isinstance(card, dict) and card.get("work")
    }
    source_by_title = {
        title: _classic_source_path(kb_root, enrollment)
        for title, enrollment in scope_by_title.items()
        if title in card_titles
    }
    normalized: list[dict[str, Any]] = []
    for raw in payload["cards"]:
        if not isinstance(raw, dict):
            continue
        enrollment = scope_by_title.get(str(raw.get("work", "")))
        source_path = source_by_title.get(str(raw.get("work", "")))
        vividness = raw.get("vividness")
        aptness = raw.get("aptness")
        mappings = aptness.get("mappings") if isinstance(aptness, dict) else None
        if (
            not isinstance(enrollment, dict)
            or not isinstance(source_path, Path)
            or not isinstance(vividness, dict)
            or not isinstance(aptness, dict)
            or not isinstance(mappings, list)
            or not _classic_quote_is_backed(
                source_path,
                enrollment,
                raw.get("source_locator"),
                raw.get("quote"),
            )
        ):
            continue
        required = (
            "card_id",
            "source_locator",
            "figure_type",
            "quote",
            "narrative_function",
            "transfer_rule",
            "quality_assessment",
        )
        if any(not isinstance(raw.get(field), str) or not raw[field].strip() for field in required):
            continue
        normalized.append(
            {
                **raw,
                "occurrence_id": raw["card_id"],
                "work_id": f"{enrollment.get('container')}:{enrollment.get('work')}",
                "source_container": enrollment.get("container"),
                "image_mechanism": str(vividness.get("mechanism", "")),
                "sensory_mapping": "、".join(
                    map(str, vividness.get("sensory_channels") or [])
                ),
                "property_alignment": "；".join(map(str, mappings)),
                "context_alignment": str(aptness.get("context_fit", "")),
                "failure_boundary": str(aptness.get("failure_boundary", "")),
            }
        )
    return normalized


def load_learning_cards(kb_root: Path) -> list[dict[str, Any]]:
    """Combine exhaustive occurrences and representative cards without duplicates."""

    cards = load_occurrences(kb_root) + load_classic_exemplars(kb_root)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for card in cards:
        key = (
            str(card.get("work_id", "")),
            str(card.get("source_locator", "")),
            str(card.get("figure_type", "")),
            str(card.get("quote", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(card)
    return unique


def _text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _text_values(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _text_values(nested)


def _query_surface(query_text: str, scene_results: Iterable[Mapping[str, Any]]) -> str:
    parts = [query_text]
    fields = (
        "novel",
        "description",
        "tags",
        "conflict_type",
        "conflict_axis",
        "pov",
        "style_profile",
    )
    for result in scene_results:
        for field in fields:
            parts.extend(_text_values(result.get(field)))
    return " ".join(part for part in parts if part)


def _card_surface(card: Mapping[str, Any]) -> str:
    fields = (
        "figure_type",
        "quote",
        "tenor",
        "vehicle",
        "ground",
        "sensory_mapping",
        "context_fact",
        "image_mechanism",
        "property_alignment",
        "context_alignment",
        "narrative_function",
        "transfer_rule",
        "device_elements",
    )
    parts: list[str] = []
    for field in fields:
        parts.extend(_text_values(card.get(field)))
    return " ".join(parts)


def _medium_group_from_card(card: Mapping[str, Any]) -> str | None:
    container = str(card.get("source_container", ""))
    if container == "novels":
        return "prose"
    if container == "dramas":
        return "dramatic"
    path = str(card.get("occurrence_file", ""))
    if path.startswith("novels/"):
        return "prose"
    if path.startswith("dramas/"):
        return "dramatic"
    return None


def _medium_group_from_result(result: Mapping[str, Any]) -> str | None:
    medium = str(result.get("source_medium", "")).strip()
    if medium:
        return "prose" if medium == "novel" else "dramatic"
    file_path = str(result.get("file", ""))
    if file_path.startswith("novels/"):
        return "prose"
    if file_path.startswith("dramas/"):
        return "dramatic"
    return None


def _allowed_medium_groups(scene_results: list[Mapping[str, Any]]) -> set[str]:
    groups = {
        group
        for result in scene_results
        if (group := _medium_group_from_result(result)) is not None
    }
    return groups or {"prose"}


def _relevance_scores(query_text: str, cards: list[dict[str, Any]]) -> list[float]:
    query_terms = _tokens(query_text)
    if not query_terms or not cards:
        return [0.0] * len(cards)
    documents = [_tokens(_card_surface(card)) for card in cards]
    document_frequency = Counter(
        token for document in documents for token in set(document)
    )
    scores: list[float] = []
    total_documents = len(documents)
    for document in documents:
        term_frequency = Counter(document)
        score = 0.0
        for token in query_terms:
            frequency = term_frequency.get(token, 0)
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (total_documents + 0.5) / (document_frequency[token] + 0.5)
            )
            score += inverse_frequency * (1 + math.log(frequency))
        scores.append(score)
    return scores


def select_rhetoric_cards(
    kb_root: Path,
    query_text: str,
    scene_results: Iterable[Mapping[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` relevant, high-quality cards without API calls."""

    if limit <= 0:
        return []
    result_list = list(scene_results)
    allowed_groups = _allowed_medium_groups(result_list)
    cards = [
        card
        for card in load_learning_cards(Path(kb_root))
        if card.get("quality_assessment") in ELIGIBLE_QUALITIES
        and _medium_group_from_card(card) in allowed_groups
    ]
    surface = _query_surface(query_text, result_list)
    scores = _relevance_scores(surface, cards)
    ranked = [(score, card) for score, card in zip(scores, cards) if score > 0]
    ranked.sort(
        key=lambda item: (
            -item[0],
            QUALITY_RANK[str(item[1]["quality_assessment"])],
            str(item[1].get("occurrence_id", "")),
        )
    )
    return [dict(card) for _, card in ranked[:limit]]


def _work_name(card: Mapping[str, Any]) -> str:
    if card.get("work"):
        return str(card["work"])
    path = str(card.get("occurrence_file", ""))
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] in {"novels", "dramas"}:
        return parts[1]
    work_id = str(card.get("work_id", ""))
    return work_id.split(":", 1)[-1] if work_id else "?"


def render_rhetoric_cards(cards: Iterable[Mapping[str, Any]]) -> list[str]:
    """Render cards as an execution-facing reference block."""

    card_list = list(cards)
    if not card_list:
        return []
    lines = [
        '<rhetoric_cards note="迁移感知机制与对应关系；喻体服从本场视角和物理条件">',
        "",
    ]
    for rank, card in enumerate(card_list, start=1):
        lines.append(
            f"### 修辞卡 {rank}：{_work_name(card)} · "
            f"{card.get('figure_type', '?')}"
        )
        lines.append(
            f"- 证据：{card.get('source_locator', '?')}；「{card.get('quote', '')}」"
        )
        lines.append(f"- 形象机制：{card.get('image_mechanism', '')}")
        lines.append(f"- 属性对应：{card.get('property_alignment', '')}")
        lines.append(f"- 语境贴合：{card.get('context_alignment', '')}")
        lines.append(f"- 叙事功能：{card.get('narrative_function', '')}")
        lines.append(f"- 迁移规则：{card.get('transfer_rule', '')}")
        lines.append(f"- 失效边界：{card.get('failure_boundary', '')}")
        lines.append("")
    lines.append("</rhetoric_cards>")
    return lines
