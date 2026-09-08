#!/usr/bin/env python3
"""Build and verify the source-backed dialogue knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    from . import kb_index
except ImportError:
    import kb_index


DEFAULT_KB_ROOT = Path(__file__).resolve().parents[1]
LOCATOR_RE = re.compile(r"^(?P<path>.+):L(?P<start>\d+)(?:-L?(?P<end>\d+))?$")
EVIDENCE_RE = re.compile(r"[\w\-/.]+\.md:L\d+(?:-L?\d+)?")


def read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def iter_works(kb_root: Path, work_dir: Path | None = None) -> Iterable[tuple[str, Path]]:
    if work_dir is not None:
        selected = work_dir.resolve()
        relative = selected.relative_to(kb_root.resolve())
        if len(relative.parts) != 2 or relative.parts[0] not in {"novels", "dramas"} or not selected.is_dir():
            raise ValueError("work-dir must be an existing work directly under novels/ or dramas/")
        yield ("novel" if relative.parts[0] == "novels" else "drama"), selected
        return
    for container, medium in (("novels", "novel"), ("dramas", "drama")):
        root = kb_root / container
        if not root.is_dir():
            continue
        for work_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
            yield medium, work_dir


def work_id(medium: str, work_dir: Path) -> str:
    return f"{medium}:{work_dir.name}"


def load_scene_index(work_dir: Path) -> list[dict[str, Any]]:
    index_path = kb_index.index_path_of(work_dir)
    if index_path is None:
        return []
    value = kb_index.load_index(index_path)
    if isinstance(value, dict):
        value = value.get("scenes", value.get("entries", []))
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def scene_records(work_dir: Path) -> list[dict[str, Any]]:
    indexed = load_scene_index(work_dir)
    by_file: dict[str, dict[str, Any]] = {}
    for item in indexed:
        file_value = item.get("file") or item.get("scene_file")
        if file_value:
            by_file[str(file_value)] = item
    records: list[dict[str, Any]] = []
    scenes_dir = work_dir / "scenes"
    if scenes_dir.is_dir():
        for path in sorted(scenes_dir.glob("*.md"), key=lambda p: p.name):
            rel = path.relative_to(work_dir).as_posix()
            item = by_file.get(rel, {})
            sid = item.get("scene_id") or re.sub(r"^scene_", "", path.stem)
            records.append({"scene_id": str(sid), "file": rel, "indexed": rel in by_file})
    indexed_files = {record["file"] for record in records}
    for rel, item in by_file.items():
        if rel not in indexed_files:
            records.append(
                {"scene_id": str(item.get("scene_id", Path(rel).stem)), "file": rel, "indexed": True}
            )
    return records


def event_documents(work_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    result: list[tuple[Path, dict[str, Any]]] = []
    events_dir = work_dir / "dialogue" / "events"
    if not events_dir.is_dir():
        return result
    for path in sorted(events_dir.glob("*.yaml"), key=lambda p: p.name):
        value = read_yaml(path) or {}
        if isinstance(value, dict):
            result.append((path, value))
    return result


def events_for_work(work_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for _, document in event_documents(work_dir):
        events = document.get("events", [])
        if isinstance(events, list):
            result.extend(item for item in events if isinstance(item, dict))
    return result


def load_backbone(kb_root: Path) -> dict[str, Any]:
    path = kb_root / "dialogue" / "canon_backbone_v1.yaml"
    if not path.exists():
        return {"catalog_id": "canon_backbone_v1", "categories": []}
    value = read_yaml(path) or {}
    return value if isinstance(value, dict) else {"catalog_id": "canon_backbone_v1", "categories": []}


def backbone_titles(backbone: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for category in backbone.get("categories", []):
        if isinstance(category, dict):
            result.update(str(title) for title in category.get("works", []))
    return result


def first_metadata(work_dir: Path) -> dict[str, Any]:
    meta_path = work_dir / "work-meta.yaml"
    metadata = read_yaml(meta_path) if meta_path.exists() else {}
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    index = load_scene_index(work_dir)
    if index:
        source_medium = metadata.get("source_medium")
        metadata.update({key: value for key, value in index[0].items() if value not in (None, "")})
        if source_medium:
            metadata["source_medium"] = source_medium
    return metadata


def character_profile_paths(work_dir: Path) -> list[Path]:
    characters = work_dir / "characters"
    return sorted(characters.rglob("dialogue-profile.yaml")) if characters.is_dir() else []


def build_coverage(medium: str, work_dir: Path) -> dict[str, Any]:
    records = scene_records(work_dir)
    event_docs = event_documents(work_dir)
    scene_event_counts: dict[str, int] = {}
    for _, document in event_docs:
        sid = str(document.get("scene_id", ""))
        count = len(document.get("events", [])) if isinstance(document.get("events"), list) else 0
        if sid:
            scene_event_counts[sid] = scene_event_counts.get(sid, 0) + count

    existing_path = work_dir / "dialogue" / "coverage.yaml"
    existing = read_yaml(existing_path) if existing_path.exists() else {}
    existing_status = {}
    if isinstance(existing, dict):
        for item in existing.get("scenes", []):
            if isinstance(item, dict) and item.get("scene_id"):
                existing_status[str(item["scene_id"])] = item.get("status")

    scenes = []
    counts = {"annotated": 0, "no_dialogue": 0, "excluded": 0, "unresolved": 0}
    for record in records:
        sid = record["scene_id"]
        if scene_event_counts.get(sid, 0):
            status = "annotated"
        elif existing_status.get(sid) in {"no_dialogue", "excluded"}:
            status = existing_status[sid]
        else:
            status = "unresolved"
        counts[status] += 1
        scenes.append(
            {
                "scene_id": sid,
                "file": record["file"],
                "indexed": bool(record["indexed"]),
                "status": status,
                "event_count": scene_event_counts.get(sid, 0),
            }
        )

    profile_paths = character_profile_paths(work_dir)
    event_count = sum(scene_event_counts.values())
    if records and counts["unresolved"] == 0 and all(item["indexed"] for item in scenes):
        status = "complete"
    elif event_count or profile_paths:
        status = "partial"
    else:
        status = "unresolved"
    return {
        "schema_version": "dialogue-coverage/v1",
        "work_id": work_id(medium, work_dir),
        "status": status,
        "counts": {
            "scene_files": len(records),
            "indexed_scenes": sum(1 for item in scenes if item["indexed"]),
            "dialogue_events": event_count,
            "dialogue_profiles": len(profile_paths),
            **counts,
        },
        "scenes": scenes,
    }


def build_catalog(kb_root: Path, *, write: bool, work_dir: Path | None = None) -> dict[str, Any]:
    backbone = load_backbone(kb_root)
    canon_titles = backbone_titles(backbone)
    registry_path = kb_root / "dialogue" / "corpus_registry.yaml"
    existing = read_yaml(registry_path) if registry_path.exists() else {}
    existing = existing if isinstance(existing, dict) else {}
    prior = {entry["work_id"]: entry for entry in existing.get("works", [])
             if isinstance(entry, dict) and entry.get("work_id")}
    works = dict(prior) if work_dir is not None else {}
    for medium, current in iter_works(kb_root, work_dir):
        coverage = build_coverage(medium, current)
        metadata = first_metadata(current)
        wid = work_id(medium, current)
        entry = dict(prior.get(wid, {}))
        entry.update({
            "work_id": wid,
            "title": current.name,
            "directory": current.relative_to(kb_root).as_posix(),
            "medium": metadata.get("source_medium") or metadata.get("medium") or medium,
            "canon_class": "canonical" if current.name in canon_titles else "registered",
            "source_status": "available" if (current / "full_text.md").exists() or coverage["counts"]["scene_files"] else "missing",
            "processing_status": coverage["status"],
            "counts": coverage["counts"],
        })
        entry.setdefault("author", metadata.get("author") or "unknown")
        entry.setdefault("aliases", [])
        entry.setdefault("editions", [{
            "edition_id": "current", "language": metadata.get("lang") or metadata.get("language") or "unknown",
            "translator": metadata.get("translator") or "unknown", "rights": "unreviewed",
        }])
        works[wid] = entry
        if write:
            write_yaml(current / "dialogue" / "coverage.yaml", coverage)
    catalog = {
        **existing,
        "schema_version": "dialogue-corpus/v1",
        "catalogs": existing.get("catalogs") or [
            {
                "catalog_id": backbone.get("catalog_id", "canon_backbone_v1"),
                "file": "canon_backbone_v1.yaml",
                "status": "planned_or_available",
            }
        ],
        "works": sorted(works.values(), key=lambda entry: entry["work_id"]),
    }
    if write:
        write_yaml(kb_root / "dialogue" / "corpus_registry.yaml", catalog)
    return catalog


def extract_section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    end_match = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + end_match.start() if end_match else len(text)
    return text[start:end].strip()


def bootstrap_profiles(kb_root: Path, *, write: bool, force: bool = False) -> int:
    created = 0
    for medium, work_dir in iter_works(kb_root):
        characters_dir = work_dir / "characters"
        if not characters_dir.is_dir():
            continue
        for skill_path in sorted(characters_dir.rglob("SKILL.md"), key=lambda p: p.as_posix()):
            role_dir = skill_path.parent
            output = role_dir / "dialogue-profile.yaml"
            if output.exists() and not force:
                continue
            text = skill_path.read_text(encoding="utf-8")
            voice = extract_section(text, "声音框架")
            if not voice:
                continue
            locators = list(dict.fromkeys(EVIDENCE_RE.findall(voice)))
            display_match = re.search(r"^#\s+(.+?)(?:（|\s*$)", text, re.MULTILINE)
            relative_role = role_dir.relative_to(characters_dir)
            role_key = "--".join(relative_role.parts)
            profile = {
                "schema_version": "dialogue-character/v1",
                "character_id": f"{work_id(medium, work_dir)}:{role_key}",
                "work_id": work_id(medium, work_dir),
                "display_name": display_match.group(1).strip() if display_match else role_dir.name,
                "profile_tier": "compact",
                "character_skill": "SKILL.md",
                "baseline_voice": {
                    "observed_summary": voice,
                    "evidence_locators": locators,
                },
                "relationship_registers": [],
                "pressure_transformations": [],
                "interaction_patterns": {},
                "negative_space": {},
                "prototype_axes": {},
                "prototype_eligible": False,
                "review_status": "derived_from_character_skill",
            }
            if write:
                write_yaml(output, profile)
            created += 1
    return created


def build_indexes(kb_root: Path, *, write: bool, work_dir: Path | None = None) -> dict[str, Any]:
    selected = list(iter_works(kb_root, work_dir))
    selected_ids = {work_id(medium, current) for medium, current in selected}
    dialogue_root = kb_root / "dialogue"

    def retained(filename: str, field: str) -> list[dict]:
        path = dialogue_root / filename
        if work_dir is None or not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else read_yaml(path)
        if not isinstance(data, dict):
            raise ValueError(f"invalid shared index: {path}")
        return [entry for entry in data.get(field, [])
                if isinstance(entry, dict) and entry.get("work_id") not in selected_ids]

    event_entries = retained("event_index.json", "events")
    prototype_entries = retained("prototype_index.json", "characters")
    coverage_works = retained("coverage_report.yaml", "works")
    for medium, current in selected:
        wid = work_id(medium, current)
        metadata = first_metadata(current)
        source_medium = metadata.get("source_medium") or metadata.get("medium") or medium
        # Keep the work namespace stable while retaining the actual source medium.
        work_path = current
        for path, document in event_documents(work_path):
            for event in document.get("events", []):
                if not isinstance(event, dict):
                    continue
                entry = dict(event)
                entry["work_id"] = wid
                entry["medium"] = source_medium
                entry["scene_id"] = document.get("scene_id")
                entry["scene_file"] = document.get("scene_file")
                entry["event_file"] = path.relative_to(kb_root).as_posix()
                event_entries.append(entry)
        for path in character_profile_paths(work_path):
            profile = read_yaml(path)
            if not isinstance(profile, dict):
                continue
            prototype_entries.append(
                {
                    "character_id": profile.get("character_id"),
                    "work_id": wid,
                    "display_name": profile.get("display_name"),
                    "profile_tier": profile.get("profile_tier"),
                    "prototype_eligible": bool(profile.get("prototype_eligible")),
                    "baseline_voice": profile.get("baseline_voice", {}),
                    "prototype_axes": profile.get("prototype_axes", {}),
                    "profile_file": path.relative_to(kb_root).as_posix(),
                }
            )
        coverage = build_coverage(medium, work_path)
        coverage_works.append(
            {"work_id": wid, "status": coverage["status"], "counts": coverage["counts"]}
        )
        if write:
            write_yaml(work_path / "dialogue" / "coverage.yaml", coverage)
    event_index = {"schema_version": "dialogue-event-index/v1", "events": event_entries}
    prototype_index = {
        "schema_version": "dialogue-prototype-index/v1",
        "characters": prototype_entries,
    }
    report = {
        "schema_version": "dialogue-coverage-report/v1",
        "summary": {
            "works": len(coverage_works),
            "complete_works": sum(1 for item in coverage_works if item["status"] == "complete"),
            "dialogue_events": len(event_entries),
            "dialogue_profiles": len(prototype_entries),
        },
        "works": coverage_works,
    }
    if write:
        dialogue_root = kb_root / "dialogue"
        write_json(dialogue_root / "event_index.json", event_index)
        write_json(dialogue_root / "prototype_index.json", prototype_index)
        write_yaml(dialogue_root / "coverage_report.yaml", report)
    return report


def locator_window(work_dir: Path, locator: str) -> tuple[Path, str] | None:
    match = LOCATOR_RE.match(locator)
    if not match:
        return None
    path = (work_dir / match.group("path")).resolve()
    if not path.is_relative_to(work_dir.resolve()) or not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if start < 1 or end < start or end > len(lines):
        return None
    return path, "\n".join(lines[start - 1 : end])


def verify(kb_root: Path, *, strict_complete: bool = False, work_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    event_ids: set[str] = set()
    for medium, work_dir in iter_works(kb_root, work_dir):
        wid = work_id(medium, work_dir)
        known_scenes = {item["scene_id"] for item in scene_records(work_dir)}
        for path, document in event_documents(work_dir):
            if document.get("schema_version") != "dialogue-scene-events/v1":
                errors.append(f"{path}: invalid schema_version")
            if document.get("work_id") != wid:
                errors.append(f"{path}: work_id mismatch")
            sid = str(document.get("scene_id", ""))
            if sid not in known_scenes:
                errors.append(f"{path}: unknown scene_id {sid}")
            for event in document.get("events", []):
                if not isinstance(event, dict):
                    errors.append(f"{path}: event must be a mapping")
                    continue
                eid = str(event.get("event_id", ""))
                if not eid or eid in event_ids:
                    errors.append(f"{path}: missing or duplicate event_id {eid}")
                event_ids.add(eid)
                participants = {
                    str(item.get("character_id"))
                    for item in event.get("participants", [])
                    if isinstance(item, dict)
                }
                turns = event.get("turns")
                if not isinstance(turns, list) or not turns:
                    errors.append(f"{path}: turns must be a nonempty list")
                    continue
                seen_turns: set[str] = set()
                for turn in turns:
                    if not isinstance(turn, dict):
                        errors.append(f"{path}: turn must be a mapping")
                        continue
                    tid = str(turn.get("turn_id", ""))
                    speaker = str(turn.get("speaker_id", ""))
                    if not tid or tid in seen_turns:
                        errors.append(f"{path}: duplicate or missing turn_id {tid}")
                    if speaker not in participants:
                        errors.append(f"{path}: speaker {speaker} not in participants")
                    addressees = turn.get("addressee_ids", [])
                    if not isinstance(addressees, list) or any(not isinstance(item, str) or item not in participants for item in addressees):
                        errors.append(f"{path}: addressee_ids must reference participants")
                    text = turn.get("text")
                    if not isinstance(text, str) or not text.strip():
                        errors.append(f"{path}: turn text must be nonempty original text")
                    response_to = turn.get("response_to")
                    if response_to is not None and response_to not in seen_turns:
                        errors.append(f"{path}: response_to {response_to} is not an earlier turn")
                    locator = str(turn.get("source_locator", ""))
                    located = locator_window(work_dir, locator)
                    if located is None:
                        errors.append(f"{path}: invalid locator {locator}")
                    elif turn.get("text") and normalize_text(str(turn["text"])) not in normalize_text(located[1]):
                        errors.append(f"{path}: turn text not found at {locator}")
                    seen_turns.add(tid)
                source_file = event.get("annotation", {}).get("source_file") if isinstance(event.get("annotation"), dict) else None
                expected_hash = event.get("annotation", {}).get("source_sha256") if isinstance(event.get("annotation"), dict) else None
                if source_file and expected_hash:
                    source_path = work_dir / str(source_file)
                    if not source_path.is_file() or sha256(source_path) != expected_hash:
                        errors.append(f"{path}: source checksum mismatch")
        coverage = build_coverage(medium, work_dir)
        if strict_complete and coverage["status"] != "complete":
            errors.append(f"{work_dir}: dialogue coverage is {coverage['status']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", type=Path, default=DEFAULT_KB_ROOT)
    parser.add_argument("--work-dir", type=Path, help="Scope dialogue refresh/build/verify to one work")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("catalog", "bootstrap-profiles", "build", "refresh"):
        command = sub.add_parser(name)
        command.add_argument("--write", action="store_true")
        if name == "bootstrap-profiles":
            command.add_argument("--force", action="store_true")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--strict-complete", action="store_true")
    args = parser.parse_args()
    kb_root = args.kb_root.resolve()
    try:
        list(iter_works(kb_root, args.work_dir))
    except ValueError as exc:
        parser.error(str(exc))
    if args.work_dir and args.command == "bootstrap-profiles":
        parser.error("bootstrap-profiles is a separate corpus operation; do not combine with work-dir")

    if args.command == "catalog":
        result = build_catalog(kb_root, write=args.write, work_dir=args.work_dir)
        print(json.dumps({"works": len(result["works"])}, ensure_ascii=False))
    elif args.command == "bootstrap-profiles":
        count = bootstrap_profiles(kb_root, write=args.write, force=args.force)
        print(json.dumps({"profiles_created": count}, ensure_ascii=False))
    elif args.command == "build":
        result = build_indexes(kb_root, write=args.write, work_dir=args.work_dir)
        print(json.dumps(result["summary"], ensure_ascii=False))
    elif args.command == "refresh":
        errors = verify(kb_root, work_dir=args.work_dir)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        build_catalog(kb_root, write=args.write, work_dir=args.work_dir)
        result = build_indexes(kb_root, write=args.write, work_dir=args.work_dir)
        print(json.dumps({**result["summary"], "errors": 0}, ensure_ascii=False))
    else:
        errors = verify(kb_root, strict_complete=args.strict_complete, work_dir=args.work_dir)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("dialogue KB verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
