"""Read character identity and persona scope without rewriting character ledgers."""
from __future__ import annotations

import re
from pathlib import Path

import yaml


class CharacterContextError(ValueError):
    pass


def read_persona(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        if text.startswith("---\n") or text.startswith("---\r\n"):
            raise CharacterContextError(f"{path}: persona frontmatter 未闭合")
        return {}, text.strip()
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise CharacterContextError(f"{path}: persona frontmatter 无法解析: {exc}") from exc
    if not isinstance(meta, dict):
        raise CharacterContextError(f"{path}: persona frontmatter 必须为映射")
    if "name" in meta and (not isinstance(meta["name"], str) or not meta["name"].strip()):
        raise CharacterContextError(f"{path}: name 必须为非空显示名")
    return meta, text[match.end():].strip()


def scoped_persona(
    path: Path, published_seq: dict[str, int], cutoff: int, *, initial_design: bool = False,
) -> tuple[str | None, str | None]:
    """Return eligible prose and an omission reason; old prose is latest-only."""
    meta, body = read_persona(path)
    if "through_chapter" not in meta:
        if cutoff < max(published_seq.values(), default=0):
            return None, "旧 persona 未标覆盖章，历史时点只使用当时可见快照与来源"
        return body, None
    through = meta["through_chapter"]
    if through is None:
        if initial_design:
            return body, None
        raise CharacterContextError(f"{path}: through_chapter 为 null 仅适用于有 V00 快照的开工设计")
    if not isinstance(through, str) or through not in published_seq:
        raise CharacterContextError(f"{path}: through_chapter {through!r} 未在发布册登记")
    if published_seq[through] > cutoff:
        return None, f"persona 覆盖至 {through}，晚于当前可见时点"
    return body, None


def character_names(work_dir: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Explicit names, or an exact legacy H1, may resolve a unique character ID.

    No tokenization, transliteration, subtitle stripping or fuzzy matching is used.
    A display name shared by characters remains ambiguous.
    """
    root = work_dir / "series" / "ledgers" / "characters"
    ids: set[str] = set()
    names: dict[str, set[str]] = {}
    if not root.is_dir():
        return ids, names
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        ids.add(directory.name)
        persona = directory / "persona.md"
        if not persona.is_file():
            continue
        meta, body = read_persona(persona)
        name = meta.get("name")
        if not name:
            heading = re.search(r"^#\s+(.+?)\s*$", body, re.M)
            name = heading.group(1) if heading else None
        if name:
            names.setdefault(name.strip(), set()).add(directory.name)
    return ids, names


def resolve_character(value: str, ids: set[str], names: dict[str, set[str]]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        raise CharacterContextError("人物标识必须为非空文本")
    if value in ids:
        return value
    matches = names.get(value, set())
    if len(matches) > 1:
        raise CharacterContextError(f"人物名 {value!r} 对应多个 char_id，请使用角色目录 ID")
    return next(iter(matches)) if matches else None


def normalize_character_facts(
    facts: list[dict], ids: set[str], names: dict[str, set[str]],
    noncharacter_entities: set[str] | None = None,
    selected_characters: set[str] | None = None,
) -> list[dict]:
    """Resolve names only in fields whose contract identifies a person.

    Generic entity names do not establish whether the entity is a person. Those
    rows require char_id at production; a same-named item stays an item. Only
    selected rows are interpreted, leaving unrelated legacy ambiguities alone.
    """
    normalized = []
    noncharacter_entities = noncharacter_entities or set()
    selected_characters = ids if selected_characters is None else selected_characters
    for fact in facts:
        if not isinstance(fact, dict):
            raise CharacterContextError("事实条目必须为映射")
        row = dict(fact)
        entity = row.get("entity")
        if not isinstance(entity, str) or not entity.strip():
            raise CharacterContextError("事实 entity 必须为非空实体标识")
        relation = row.get("kind") == "relation"
        selected = entity in selected_characters or entity in noncharacter_entities
        if relation and names.get(entity, set()) & selected_characters:
            selected = True
        if not selected:
            normalized.append(row)
            continue
        if entity in selected_characters and entity in noncharacter_entities:
            raise CharacterContextError(f"实体 {entity!r} 同时被点名为人物与非人物，请消除标识歧义")
        if row.get("kind") == "relation":
            resolved = resolve_character(entity, ids, names)
            if resolved:
                if entity in noncharacter_entities:
                    raise CharacterContextError(f"关系主体 {entity!r} 被点名为非人物，请明确实体标识")
                row["entity"] = resolved
            attr = row.get("attribute")
            target = attr[len("relation:"):] if isinstance(attr, str) and attr.startswith("relation:") else ""
            recipient = resolve_character(target, ids, names)
            if not target:
                raise CharacterContextError(f"关系事实 {row.get('fact_id', '')}: attribute 必须为 relation:<对方 char_id>")
            # Fast takeovers may only distill the active characters. Unregistered
            # counterpart IDs remain valid; names are resolved only with evidence.
            row["attribute"] = f"relation:{recipient or target}"
        if row.get("kind") == "secret":
            known = []
            for entry in row.get("known_by") or []:
                if not isinstance(entry, dict):
                    raise CharacterContextError("known_by 条目必须为映射")
                item = dict(entry)
                char_id = item.get("char_id")
                if isinstance(char_id, str):
                    item["char_id"] = resolve_character(char_id, ids, names) or char_id
                known.append(item)
            row["known_by"] = known
        normalized.append(row)
    return normalized
