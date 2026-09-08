#!/usr/bin/env python3
"""Machine contracts for protected literal and relation integrity.

The module owns one append-only scene artifact containing:

* immutable declaration snapshots, written before a directive can be pruned;
* token occurrence records, bound to the scene revision they verified;
* relation verification records, bound to the scene revision they reviewed.

Spans are zero-based, half-open character offsets into the current scene text.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


SCHEMA_VERSION = 1
TOKEN_SOURCES = frozenset({"scene_card", "reuse_manifest", "old_span"})
TOKEN_MATCH_MODES = frozenset({"exact", "normalized"})
TOKEN_SCOPES = frozenset({"patch_span", "scene"})
RELATION_TYPES = frozenset({
    "agency",
    "polarity",
    "modality",
    "causality",
    "temporal",
    "comparison",
})


class ProtectedIntegrityError(ValueError):
    """Fail-closed protected-integrity contract violation."""


def scene_sha256(scene_text: str) -> str:
    return hashlib.sha256(scene_text.encode("utf-8")).hexdigest()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_nonempty_string(value: object, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtectedIntegrityError(f"{context}:{field}_must_be_nonempty_string")
    return value


def _normalize_span(value: object, context: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ProtectedIntegrityError(f"{context}:current_span_invalid")
    start = value.get("start")
    end = value.get("end")
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
    ):
        raise ProtectedIntegrityError(f"{context}:current_span_invalid")
    return {"start": start, "end": end}


def _identity(item: Mapping, id_field: str, context: str) -> tuple[str, str]:
    patch_id = _require_nonempty_string(item.get("patch_id"), "patch_id", context)
    protected_id = _require_nonempty_string(item.get(id_field), id_field, context)
    return patch_id, protected_id


def _validate_token(token: object, index: int) -> dict:
    context = f"protected_tokens[{index}]"
    if not isinstance(token, Mapping):
        raise ProtectedIntegrityError(f"{context}:must_be_mapping")
    item = copy.deepcopy(dict(token))
    _identity(item, "token_id", context)
    source = item.get("source")
    if source not in TOKEN_SOURCES:
        raise ProtectedIntegrityError(
            f"{context}:source_invalid:{source!r}; allowed={sorted(TOKEN_SOURCES)}"
        )
    _require_nonempty_string(item.get("raw"), "raw", context)
    match_mode = item.get("match_mode")
    if match_mode not in TOKEN_MATCH_MODES:
        raise ProtectedIntegrityError(
            f"{context}:match_mode_invalid:{match_mode!r}; allowed={sorted(TOKEN_MATCH_MODES)}"
        )
    accepted_forms = item.get("accepted_forms", [])
    if not isinstance(accepted_forms, list) or any(
        not isinstance(form, str) or not form for form in accepted_forms
    ):
        raise ProtectedIntegrityError(f"{context}:accepted_forms_must_be_string_list")
    if len(set(accepted_forms)) != len(accepted_forms):
        raise ProtectedIntegrityError(f"{context}:accepted_forms_duplicate")
    if item["raw"] in accepted_forms:
        raise ProtectedIntegrityError(f"{context}:accepted_forms_repeats_raw")
    if match_mode == "exact" and accepted_forms:
        raise ProtectedIntegrityError(f"{context}:exact_disallows_accepted_forms")
    item["accepted_forms"] = accepted_forms
    scope = item.get("scope")
    if scope not in TOKEN_SCOPES:
        raise ProtectedIntegrityError(
            f"{context}:scope_invalid:{scope!r}; allowed={sorted(TOKEN_SCOPES)}"
        )
    return item


def _validate_relation(relation: object, index: int) -> dict:
    context = f"protected_relations[{index}]"
    if not isinstance(relation, Mapping):
        raise ProtectedIntegrityError(f"{context}:must_be_mapping")
    item = copy.deepcopy(dict(relation))
    _identity(item, "relation_id", context)
    relation_type = item.get("type")
    if relation_type not in RELATION_TYPES:
        raise ProtectedIntegrityError(
            f"{context}:type_invalid:{relation_type!r}; allowed={sorted(RELATION_TYPES)}"
        )
    _require_nonempty_string(item.get("expected"), "expected", context)
    _require_nonempty_string(item.get("before_quote"), "before_quote", context)
    return item


def validate_declarations(
    tokens: Sequence[object],
    relations: Sequence[object],
) -> tuple[list[dict], list[dict]]:
    """Validate declaration shape and protected-ID uniqueness.

    Protected IDs share one run-wide namespace. Compound identities remain the
    comparison key at verification time so a wrong patch binding cannot pass.
    """
    if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes)):
        raise ProtectedIntegrityError("protected_tokens_must_be_list")
    if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
        raise ProtectedIntegrityError("protected_relations_must_be_list")
    normalized_tokens = [_validate_token(item, index) for index, item in enumerate(tokens)]
    normalized_relations = [
        _validate_relation(item, index) for index, item in enumerate(relations)
    ]

    seen_ids: dict[str, tuple[str, str]] = {}
    seen_compound: set[tuple[str, str, str]] = set()
    for kind, id_field, items in (
        ("token", "token_id", normalized_tokens),
        ("relation", "relation_id", normalized_relations),
    ):
        for item in items:
            protected_id = item[id_field]
            identity = (item["patch_id"], protected_id)
            if protected_id in seen_ids:
                raise ProtectedIntegrityError(
                    "duplicate_protected_id:"
                    f"{protected_id!r}; first={seen_ids[protected_id]!r}; "
                    f"duplicate={(kind, item['patch_id'])!r}"
                )
            compound = (kind, *identity)
            if compound in seen_compound:
                raise ProtectedIntegrityError(f"duplicate_compound_identity:{compound!r}")
            seen_ids[protected_id] = (kind, item["patch_id"])
            seen_compound.add(compound)
    return normalized_tokens, normalized_relations


def _scene_path(work_dir: Path | str, scene_id: str) -> Path:
    _require_nonempty_string(scene_id, "scene_id", "scene")
    return Path(work_dir) / "pipeline" / f"scene_{scene_id}" / "protected_integrity.yaml"


def _empty_state(scene_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "scene_id": scene_id,
        "declaration_snapshots": [],
        "application_batches": [],
        "verified_batch_ids": [],
        "verification_runs": [],
        "token_verifications": [],
        "relation_verifications": [],
    }


def _snapshot_payload(snapshot: Mapping) -> dict:
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "tokens": snapshot.get("tokens"),
        "relations": snapshot.get("relations"),
    }


def _record_payload(record: Mapping) -> dict:
    return {key: copy.deepcopy(value) for key, value in record.items() if key != "record_sha"}


def _application_batch_payload(batch: Mapping) -> dict:
    return {
        key: copy.deepcopy(value)
        for key, value in batch.items()
        if key != "batch_sha"
    }


def _verification_run_payload(run: Mapping) -> dict:
    return {
        key: copy.deepcopy(value)
        for key, value in run.items()
        if key != "verification_sha"
    }


def _protected_key_ref(item: Mapping, id_field: str) -> dict[str, str]:
    return {"patch_id": str(item["patch_id"]), id_field: str(item[id_field])}


def _make_application_batch(
    *,
    batch_id: str,
    round_id: str,
    directive_sha: str,
    pre_scene_sha: str,
    patch_ids: Sequence[str],
    tokens: Sequence[Mapping],
    relation_scopes: Sequence[Mapping],
) -> dict:
    payload = {
        "batch_id": batch_id,
        "round_id": round_id,
        "directive_sha": directive_sha,
        "pre_scene_sha": pre_scene_sha,
        "patch_ids": list(dict.fromkeys(patch_ids)),
        "token_keys": [_protected_key_ref(item, "token_id") for item in tokens],
        "relation_scopes": [copy.deepcopy(dict(item)) for item in relation_scopes],
        "relation_review_required": bool(relation_scopes),
    }
    return {**payload, "batch_sha": _canonical_sha(payload)}


def _validate_token_record_shape(record: object, index: int) -> dict:
    context = f"token_verifications[{index}]"
    if not isinstance(record, Mapping):
        raise ProtectedIntegrityError(f"{context}:must_be_mapping")
    item = _record_payload(record)
    _identity(item, "token_id", context)
    _require_nonempty_string(item.get("matched_form"), "matched_form", context)
    item["current_span"] = _normalize_span(item.get("current_span"), context)
    scene_sha = item.get("scene_sha")
    if (
        not isinstance(scene_sha, str)
        or len(scene_sha) != 64
        or any(char not in "0123456789abcdef" for char in scene_sha)
    ):
        raise ProtectedIntegrityError(f"{context}:scene_sha_invalid")
    return item


def _load_state_path(path: Path, expected_scene_id: str | None = None) -> dict:
    if not path.exists():
        if expected_scene_id is None:
            raise ProtectedIntegrityError(f"protected_integrity_missing:{path}")
        return _empty_state(expected_scene_id)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ProtectedIntegrityError(f"protected_integrity_invalid:{path}:{exc}") from exc
    if not isinstance(raw, dict):
        raise ProtectedIntegrityError(f"protected_integrity_invalid:{path}:top_level_mapping_required")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ProtectedIntegrityError(
            f"protected_integrity_schema_version:{raw.get('schema_version')!r}"
        )
    scene_id = raw.get("scene_id")
    if not isinstance(scene_id, str) or not scene_id:
        raise ProtectedIntegrityError("protected_integrity_scene_id_invalid")
    if expected_scene_id is not None and scene_id != expected_scene_id:
        raise ProtectedIntegrityError(
            f"protected_integrity_scene_id_mismatch:{scene_id!r}!={expected_scene_id!r}"
        )
    snapshots = raw.get("declaration_snapshots")
    application_batches = raw.setdefault("application_batches", [])
    verified_batch_ids = raw.setdefault("verified_batch_ids", [])
    verification_runs = raw.setdefault("verification_runs", [])
    token_records = raw.setdefault("token_verifications", [])
    records = raw.get("relation_verifications")
    if (
        not isinstance(snapshots, list)
        or not isinstance(application_batches, list)
        or not isinstance(verified_batch_ids, list)
        or not isinstance(verification_runs, list)
        or not isinstance(token_records, list)
        or not isinstance(records, list)
    ):
        raise ProtectedIntegrityError("protected_integrity_append_only_lists_required")

    seen_snapshot_ids: set[str] = set()
    all_tokens: list[dict] = []
    all_relations: list[dict] = []
    for index, snapshot in enumerate(snapshots):
        context = f"declaration_snapshots[{index}]"
        if not isinstance(snapshot, dict):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        snapshot_id = _require_nonempty_string(snapshot.get("snapshot_id"), "snapshot_id", context)
        if snapshot_id in seen_snapshot_ids:
            raise ProtectedIntegrityError(f"duplicate_snapshot_id:{snapshot_id!r}")
        seen_snapshot_ids.add(snapshot_id)
        tokens, relations = validate_declarations(
            snapshot.get("tokens", []),
            snapshot.get("relations", []),
        )
        payload = {"snapshot_id": snapshot_id, "tokens": tokens, "relations": relations}
        if snapshot.get("declaration_sha") != _canonical_sha(payload):
            raise ProtectedIntegrityError(
                f"immutable_snapshot_tampered:{scene_id}:{snapshot_id}"
            )
        all_tokens.extend(tokens)
        all_relations.extend(relations)

    validate_declarations(all_tokens, all_relations)
    declared_token_keys = {
        (item["patch_id"], item["token_id"]) for item in all_tokens
    }
    declared_relation_keys = {
        (item["patch_id"], item["relation_id"]) for item in all_relations
    }

    seen_batch_ids: set[str] = set()
    for index, batch in enumerate(application_batches):
        context = f"application_batches[{index}]"
        if not isinstance(batch, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        payload = _application_batch_payload(batch)
        if batch.get("batch_sha") != _canonical_sha(payload):
            raise ProtectedIntegrityError(f"application_batch_tampered:{scene_id}:{index}")
        batch_id = _require_nonempty_string(batch.get("batch_id"), "batch_id", context)
        _require_nonempty_string(batch.get("round_id"), "round_id", context)
        directive_sha = batch.get("directive_sha")
        if (
            not isinstance(directive_sha, str)
            or len(directive_sha) != 64
            or any(char not in "0123456789abcdef" for char in directive_sha)
        ):
            raise ProtectedIntegrityError(f"{context}:directive_sha_invalid")
        pre_scene_sha = batch.get("pre_scene_sha")
        if (
            not isinstance(pre_scene_sha, str)
            or len(pre_scene_sha) != 64
            or any(char not in "0123456789abcdef" for char in pre_scene_sha)
        ):
            raise ProtectedIntegrityError(f"{context}:pre_scene_sha_invalid")
        if batch_id in seen_batch_ids:
            raise ProtectedIntegrityError(f"duplicate_application_batch:{batch_id!r}")
        seen_batch_ids.add(batch_id)
        patch_ids = batch.get("patch_ids")
        if (
            not isinstance(patch_ids, list)
            or any(not isinstance(value, str) or not value for value in patch_ids)
            or len(set(patch_ids)) != len(patch_ids)
        ):
            raise ProtectedIntegrityError(f"{context}:patch_ids_invalid")
        token_keys = batch.get("token_keys")
        relation_scopes = batch.get("relation_scopes")
        if not isinstance(token_keys, list) or not isinstance(relation_scopes, list):
            raise ProtectedIntegrityError(f"{context}:protected_keys_must_be_lists")
        seen_token_keys: set[tuple[str, str]] = set()
        for key_index, key_ref in enumerate(token_keys):
            key = _identity(key_ref, "token_id", f"{context}.token_keys[{key_index}]")
            if key in seen_token_keys or key not in declared_token_keys:
                raise ProtectedIntegrityError(f"{context}:token_key_invalid:{key!r}")
            seen_token_keys.add(key)
        seen_relation_keys: set[tuple[str, str]] = set()
        for scope_index, scope in enumerate(relation_scopes):
            scope_context = f"{context}.relation_scopes[{scope_index}]"
            key = _identity(scope, "relation_id", scope_context)
            triggers = scope.get("trigger_patch_ids") if isinstance(scope, Mapping) else None
            if (
                key in seen_relation_keys
                or key not in declared_relation_keys
                or not isinstance(triggers, list)
                or not triggers
                or any(not isinstance(value, str) or not value for value in triggers)
                or len(set(triggers)) != len(triggers)
                or not set(triggers).issubset(set(patch_ids))
            ):
                raise ProtectedIntegrityError(f"{context}:relation_scope_invalid:{key!r}")
            seen_relation_keys.add(key)
        if batch.get("relation_review_required") is not bool(relation_scopes):
            raise ProtectedIntegrityError(f"{context}:relation_review_required_mismatch")

    if (
        any(not isinstance(value, str) or not value for value in verified_batch_ids)
        or len(set(verified_batch_ids)) != len(verified_batch_ids)
        or not set(verified_batch_ids).issubset(seen_batch_ids)
    ):
        raise ProtectedIntegrityError("verified_batch_ids_invalid")

    for index, record in enumerate(token_records):
        if not isinstance(record, dict):
            raise ProtectedIntegrityError(f"token_verifications[{index}]:must_be_mapping")
        if record.get("record_sha") != _canonical_sha(_record_payload(record)):
            raise ProtectedIntegrityError(f"token_verification_tampered:{scene_id}:{index}")
        _validate_token_record_shape(record, index)

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ProtectedIntegrityError(f"relation_verifications[{index}]:must_be_mapping")
        if record.get("record_sha") != _canonical_sha(_record_payload(record)):
            raise ProtectedIntegrityError(f"relation_verification_tampered:{scene_id}:{index}")
        _validate_relation_record_shape(record, index)

    token_hashes = {record["record_sha"] for record in token_records}
    relation_hashes = {record["record_sha"] for record in records}
    run_batch_ids: list[str] = []
    seen_run_shas: set[str] = set()
    for index, run in enumerate(verification_runs):
        context = f"verification_runs[{index}]"
        if not isinstance(run, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        payload = _verification_run_payload(run)
        verification_sha = run.get("verification_sha")
        if verification_sha != _canonical_sha(payload) or verification_sha in seen_run_shas:
            raise ProtectedIntegrityError(f"verification_run_tampered:{scene_id}:{index}")
        seen_run_shas.add(verification_sha)
        batch_ids = run.get("batch_ids")
        if (
            not isinstance(batch_ids, list)
            or len(set(batch_ids)) != len(batch_ids)
            or not set(batch_ids).issubset(seen_batch_ids)
        ):
            raise ProtectedIntegrityError(f"{context}:batch_ids_invalid")
        run_batch_ids.extend(batch_ids)
        scene_hash = run.get("scene_sha")
        if (
            not isinstance(scene_hash, str)
            or len(scene_hash) != 64
            or any(char not in "0123456789abcdef" for char in scene_hash)
        ):
            raise ProtectedIntegrityError(f"{context}:scene_sha_invalid")
        _require_nonempty_string(run.get("review_path"), "review_path", context)
        for field, known_hashes in (
            ("token_record_shas", token_hashes),
            ("relation_record_shas", relation_hashes),
        ):
            hashes = run.get(field)
            if (
                not isinstance(hashes, list)
                or len(set(hashes)) != len(hashes)
                or any(value not in known_hashes for value in hashes)
            ):
                raise ProtectedIntegrityError(f"{context}:{field}_invalid")
    if run_batch_ids != verified_batch_ids or len(set(run_batch_ids)) != len(run_batch_ids):
        raise ProtectedIntegrityError("verified_batch_run_partition_invalid")
    return raw


def load_scene_integrity(work_dir: Path | str, scene_id: str) -> dict:
    """Load and integrity-check a scene artifact; absent artifacts are empty."""
    return _load_state_path(_scene_path(work_dir, scene_id), expected_scene_id=scene_id)


def _atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _all_run_declarations(work_dir: Path | str) -> tuple[list[dict], list[dict]]:
    tokens: list[dict] = []
    relations: list[dict] = []
    pipeline = Path(work_dir) / "pipeline"
    for path in sorted(pipeline.glob("scene_*/protected_integrity.yaml")):
        state = _load_state_path(path)
        for snapshot in state["declaration_snapshots"]:
            tokens.extend(copy.deepcopy(snapshot["tokens"]))
            relations.extend(copy.deepcopy(snapshot["relations"]))
    return tokens, relations


def validate_run_global_ids(work_dir: Path | str) -> None:
    """Fail if any protected ID is reused anywhere in one run."""
    tokens, relations = _all_run_declarations(work_dir)
    validate_declarations(tokens, relations)


def append_declaration_snapshot(
    work_dir: Path | str,
    scene_id: str,
    snapshot_id: str,
    *,
    tokens: Sequence[object],
    relations: Sequence[object],
    _register_application_batch: bool = True,
) -> Path:
    """Append one immutable scene declaration batch.

    Replaying the exact same snapshot is idempotent. Reusing its ID with other
    content or reusing any protected ID elsewhere in the run fails closed.
    """
    _require_nonempty_string(snapshot_id, "snapshot_id", "snapshot")
    normalized_tokens, normalized_relations = validate_declarations(tokens, relations)
    candidate_payload = {
        "snapshot_id": snapshot_id,
        "tokens": normalized_tokens,
        "relations": normalized_relations,
    }
    candidate_sha = _canonical_sha(candidate_payload)

    path = _scene_path(work_dir, scene_id)
    state = load_scene_integrity(work_dir, scene_id)
    for snapshot in state["declaration_snapshots"]:
        if snapshot["snapshot_id"] != snapshot_id:
            continue
        if snapshot["declaration_sha"] == candidate_sha:
            return path
        raise ProtectedIntegrityError(
            f"immutable_snapshot_conflict:{scene_id}:{snapshot_id}"
        )

    existing_tokens, existing_relations = _all_run_declarations(work_dir)
    validate_declarations(
        [*existing_tokens, *normalized_tokens],
        [*existing_relations, *normalized_relations],
    )
    state["declaration_snapshots"].append({
        **candidate_payload,
        "declaration_sha": candidate_sha,
    })
    scene_path = Path(work_dir) / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    if _register_application_batch and scene_path.exists():
        scene_text = scene_path.read_text(encoding="utf-8")
        patch_ids = [
            item["patch_id"] for item in [*normalized_tokens, *normalized_relations]
        ]
        relation_scopes = [
            {
                **_protected_key_ref(item, "relation_id"),
                "trigger_patch_ids": [item["patch_id"]],
            }
            for item in normalized_relations
        ]
        state["application_batches"].append(_make_application_batch(
            batch_id=f"declaration:{snapshot_id}",
            round_id=snapshot_id,
            directive_sha=candidate_sha,
            pre_scene_sha=scene_sha256(scene_text),
            patch_ids=patch_ids,
            tokens=normalized_tokens,
            relation_scopes=relation_scopes,
        ))
    _atomic_write_yaml(path, state)
    return path


def _append_application_batch(
    work_dir: Path | str,
    scene_id: str,
    batch: Mapping,
) -> Path:
    """Append one immutable application/review batch after declarations exist."""
    path = _scene_path(work_dir, scene_id)
    state = load_scene_integrity(work_dir, scene_id)
    candidate = copy.deepcopy(dict(batch))
    if candidate.get("batch_sha") != _canonical_sha(_application_batch_payload(candidate)):
        raise ProtectedIntegrityError("application_batch_candidate_invalid")
    for existing in state["application_batches"]:
        if existing["batch_id"] != candidate["batch_id"]:
            continue
        if existing["batch_sha"] == candidate["batch_sha"]:
            return path
        if existing["batch_id"] not in state["verified_batch_ids"]:
            raise ProtectedIntegrityError(
                f"pending_application_scene_changed:{candidate['batch_id']}"
            )
        raise ProtectedIntegrityError(
            f"immutable_application_batch_conflict:{candidate['batch_id']}"
        )
    state["application_batches"].append(candidate)
    _atomic_write_yaml(path, state)
    # Reloading applies the same declaration-reference and immutable-hash checks
    # used by every later consumer.
    load_scene_integrity(work_dir, scene_id)
    return path


def _protected_items_from_patch(patch: Mapping, field: str, context: str) -> list[object]:
    """Read the optional protected list from supported preserve surfaces."""
    locations: list[tuple[str, object]] = []
    if field in patch:
        locations.append((f"{context}.{field}", patch[field]))
    directive = patch.get("rewrite_directive")
    if isinstance(directive, Mapping):
        if field in directive:
            locations.append((f"{context}.rewrite_directive.{field}", directive[field]))
        preserve = directive.get("preserve")
        if isinstance(preserve, Mapping) and field in preserve:
            locations.append((f"{context}.rewrite_directive.preserve.{field}", preserve[field]))
    result: list[object] = []
    for location, value in locations:
        if not isinstance(value, list):
            raise ProtectedIntegrityError(f"{location}:must_be_list")
        result.extend(value)
    return result


def collect_patch_declarations(patch_document: Mapping) -> tuple[list[dict], list[dict]]:
    """Collect and validate protected declarations from a patch directive."""
    patches = patch_document.get("patches", [])
    if not isinstance(patches, list):
        raise ProtectedIntegrityError("patches_must_be_list")
    tokens: list[object] = []
    relations: list[object] = []
    seen_patch_ids: set[str] = set()
    for index, patch in enumerate(patches):
        context = f"patches[{index}]"
        if not isinstance(patch, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        declared_patch_id = patch.get("patch_id")
        if isinstance(declared_patch_id, str) and declared_patch_id:
            if declared_patch_id in seen_patch_ids:
                raise ProtectedIntegrityError(
                    f"duplicate_patch_id:{declared_patch_id!r}"
                )
            seen_patch_ids.add(declared_patch_id)
        patch_tokens = _protected_items_from_patch(patch, "protected_tokens", context)
        patch_relations = _protected_items_from_patch(patch, "protected_relations", context)
        if not patch_tokens and not patch_relations:
            continue
        patch_id = _require_nonempty_string(patch.get("patch_id"), "patch_id", context)
        for field, items, id_field in (
            ("protected_tokens", patch_tokens, "token_id"),
            ("protected_relations", patch_relations, "relation_id"),
        ):
            for item_index, item in enumerate(items):
                item_context = f"{context}.{field}[{item_index}]"
                if not isinstance(item, Mapping):
                    raise ProtectedIntegrityError(f"{item_context}:must_be_mapping")
                if item.get("patch_id") != patch_id:
                    raise ProtectedIntegrityError(
                        f"patch_binding_mismatch:{item_context}:"
                        f"{item.get(id_field)!r}:{item.get('patch_id')!r}!={patch_id!r}"
                    )
        tokens.extend(patch_tokens)
        relations.extend(patch_relations)
    return validate_declarations(tokens, relations)


def _declaration_index(work_dir: Path | str) -> dict[str, tuple[str, str, dict]]:
    result: dict[str, tuple[str, str, dict]] = {}
    pipeline = Path(work_dir) / "pipeline"
    for path in sorted(pipeline.glob("scene_*/protected_integrity.yaml")):
        state = _load_state_path(path)
        scene_id = state["scene_id"]
        for snapshot in state["declaration_snapshots"]:
            for kind, id_field, items in (
                ("token", "token_id", snapshot["tokens"]),
                ("relation", "relation_id", snapshot["relations"]),
            ):
                for item in items:
                    protected_id = item[id_field]
                    if protected_id in result:
                        raise ProtectedIntegrityError(
                            f"duplicate_protected_id:{protected_id!r}"
                        )
                    result[protected_id] = (kind, scene_id, copy.deepcopy(item))
    return result


def snapshot_patch_documents(
    work_dir: Path | str,
    scene_documents: Sequence[tuple[str, Mapping]],
) -> list[Path]:
    """Snapshot declarations and the distinct application/review batch.

    Declarations remain immutable and are stored once.  Every later application
    may reference those identities again; its batch records the current patch
    targets, pre-revision scene hash, and relation review scope.
    """
    existing = _declaration_index(work_dir)
    pending_ids: dict[str, tuple[str, str, dict]] = {}
    batches: list[tuple[str, str, list[dict], list[dict], dict, str]] = []
    for scene_id, patch_document in scene_documents:
        tokens, relations = collect_patch_declarations(patch_document)
        root = Path(work_dir)
        scene_path = root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
        try:
            scene_text = scene_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProtectedIntegrityError(
                f"declaration_scene_invalid:{scene_id}:{exc}"
            ) from exc
        state = load_scene_integrity(work_dir, scene_id)
        new_tokens: list[dict] = []
        new_relations: list[dict] = []
        for kind, id_field, items, target in (
            ("token", "token_id", tokens, new_tokens),
            ("relation", "relation_id", relations, new_relations),
        ):
            for item in items:
                protected_id = item[id_field]
                previous = existing.get(protected_id)
                if previous is not None:
                    previous_kind, previous_scene, previous_item = previous
                    if (
                        previous_kind == kind
                        and previous_scene == scene_id
                        and _canonical_sha(previous_item) == _canonical_sha(item)
                    ):
                        continue
                    raise ProtectedIntegrityError(
                        f"duplicate_protected_id:{protected_id!r};"
                        f"existing_scene={previous_scene!r};candidate_scene={scene_id!r}"
                    )
                duplicate = pending_ids.get(protected_id)
                if duplicate is not None:
                    raise ProtectedIntegrityError(
                        f"duplicate_protected_id:{protected_id!r};"
                        f"candidate_scenes={duplicate[1]!r},{scene_id!r}"
                    )
                pending_ids[protected_id] = (kind, scene_id, item)
                target.append(item)

        patches = patch_document.get("patches", [])
        assert isinstance(patches, list)  # established by collect_patch_declarations
        patch_ids: list[str] = []
        target_spans: dict[str, dict[str, int] | None] = {}
        for index, patch in enumerate(patches):
            if not isinstance(patch, Mapping):
                continue
            patch_id = patch.get("patch_id")
            if not isinstance(patch_id, str) or not patch_id:
                continue
            patch_ids.append(patch_id)
            quote = patch.get("old_span") or patch.get("anchor_quote")
            if not isinstance(quote, str) or not quote:
                target_spans[patch_id] = None
                continue
            occurrences = _find_occurrences(scene_text, quote)
            if len(occurrences) != 1:
                target_spans[patch_id] = None
                continue
            target_spans[patch_id] = {
                "start": occurrences[0],
                "end": occurrences[0] + len(quote),
            }

        scope_triggers: dict[tuple[str, str], set[str]] = {}
        for relation in relations:
            key = (relation["patch_id"], relation["relation_id"])
            scope_triggers.setdefault(key, set()).add(relation["patch_id"])

        _, historical_relations = _flatten_scene_declarations(state)
        if historical_relations and patch_ids:
            historical_anchors = derive_active_relation_anchors(
                historical_relations,
                state["relation_verifications"],
                scene_text,
            )
            for anchor in historical_anchors:
                key = (anchor["patch_id"], anchor["relation_id"])
                anchor_span = anchor["current_span"]
                for patch_id in patch_ids:
                    target = target_spans.get(patch_id)
                    if target is None or (
                        target["start"] < anchor_span["end"]
                        and anchor_span["start"] < target["end"]
                    ):
                        scope_triggers.setdefault(key, set()).add(patch_id)

        relation_scopes = [
            {
                "patch_id": key[0],
                "relation_id": key[1],
                "trigger_patch_ids": sorted(triggers),
            }
            for key, triggers in sorted(scope_triggers.items())
        ]
        if not patch_ids and not tokens and not relations and not relation_scopes:
            continue

        directive_fingerprint = _canonical_sha(dict(patch_document))
        application_id = (
            patch_document.get("application_id")
            or patch_document.get("review_round")
            or patch_document.get("round_id")
            or patch_document.get("protected_snapshot_id")
        )
        if not isinstance(application_id, str) or not application_id.strip():
            raise ProtectedIntegrityError(
                "application_id_required:(review_round accepted for legacy producers)"
            )
        round_label = application_id.strip()
        base_batch_id = f"{round_label}:{directive_fingerprint[:16]}"
        pre_scene_sha = scene_sha256(scene_text)
        candidate = _make_application_batch(
            batch_id=base_batch_id,
            round_id=round_label,
            directive_sha=directive_fingerprint,
            pre_scene_sha=pre_scene_sha,
            patch_ids=patch_ids,
            tokens=tokens,
            relation_scopes=relation_scopes,
        )

        same_round = [
            item for item in state["application_batches"]
            if item["round_id"] == round_label
        ]
        pending_same_round = [
            item for item in same_round
            if item["batch_id"] not in state["verified_batch_ids"]
        ]
        if pending_same_round:
            existing_batch = pending_same_round[-1]
            if existing_batch["batch_sha"] == candidate["batch_sha"]:
                continue
            candidate_token_keys = {
                (item["patch_id"], item["token_id"])
                for item in candidate["token_keys"]
            }
            existing_token_keys = {
                (item["patch_id"], item["token_id"])
                for item in existing_batch["token_keys"]
            }
            candidate_relation_keys = {
                (item["patch_id"], item["relation_id"])
                for item in candidate["relation_scopes"]
            }
            existing_relation_keys = {
                (item["patch_id"], item["relation_id"])
                for item in existing_batch["relation_scopes"]
            }
            if (
                candidate["directive_sha"] != existing_batch["directive_sha"]
                and candidate_token_keys.issubset(existing_token_keys)
                and candidate_relation_keys.issubset(existing_relation_keys)
                and set(candidate["patch_ids"]).issubset(existing_batch["patch_ids"])
            ):
                # The reviser pruned applied patches from this same round.
                continue
            if candidate["pre_scene_sha"] != existing_batch["pre_scene_sha"]:
                raise ProtectedIntegrityError(
                    f"pending_application_scene_changed:{existing_batch['batch_id']}"
                )
            raise ProtectedIntegrityError(
                f"application_batch_round_conflict:{round_label}"
            )

        if same_round:
            raise ProtectedIntegrityError(f"application_id_reused:{round_label}")

        snapshot_id = base_batch_id
        batches.append((
            scene_id,
            snapshot_id,
            new_tokens,
            new_relations,
            candidate,
            scene_text,
        ))

    # All candidate IDs are validated before the first artifact write.
    written: list[Path] = []
    for scene_id, snapshot_id, tokens, relations, application_batch, scene_text in batches:
        seed_records: list[dict] = []
        for relation in relations:
            quote = relation["before_quote"]
            occurrences = _find_occurrences(scene_text, quote)
            key = (relation["patch_id"], relation["relation_id"])
            if not occurrences:
                raise ProtectedIntegrityError(
                    f"declaration_before_quote_not_found:{key!r}"
                )
            if len(occurrences) != 1:
                raise ProtectedIntegrityError(
                    f"declaration_before_quote_ambiguous:{key!r}"
                )
            seed_records.append({
                "patch_id": key[0],
                "relation_id": key[1],
                "preserved": True,
                "after_quote": quote,
                "reason": "declaration_before_quote_seed",
                "current_span": {
                    "start": occurrences[0],
                    "end": occurrences[0] + len(quote),
                },
                "scene_sha": scene_sha256(scene_text),
            })
        existing_state = load_scene_integrity(work_dir, scene_id)
        _, existing_relations = _flatten_scene_declarations(existing_state)
        validate_verification_coverage(
            [],
            [*existing_relations, *relations],
            [],
            [*existing_state["relation_verifications"], *seed_records],
        )
        if tokens or relations:
            append_declaration_snapshot(
                work_dir,
                scene_id,
                snapshot_id,
                tokens=tokens,
                relations=relations,
                _register_application_batch=False,
            )
        if seed_records:
            append_relation_verifications(
                work_dir,
                scene_id,
                scene_text,
                seed_records,
            )
        written.append(_append_application_batch(work_dir, scene_id, application_batch))
    return written


def snapshot_patch_declarations(
    work_dir: Path | str,
    scene_id: str,
    patch_document: Mapping,
) -> Path | None:
    """Single-scene convenience wrapper for snapshot_patch_documents."""
    written = snapshot_patch_documents(work_dir, [(scene_id, patch_document)])
    return written[0] if written else None


def _normalize_patch_span(
    patch_spans: Mapping[str, object] | None,
    patch_id: str,
    scene_length: int,
) -> dict[str, int]:
    if patch_spans is None or patch_id not in patch_spans:
        raise ProtectedIntegrityError(f"patch_span_missing:{patch_id}")
    span = _normalize_span(patch_spans[patch_id], f"patch_span:{patch_id}")
    if span["end"] > scene_length:
        raise ProtectedIntegrityError(f"patch_span_out_of_bounds:{patch_id}")
    return span


def verify_literal_tokens(
    scene_text: str,
    tokens: Sequence[object],
    *,
    patch_spans: Mapping[str, object] | None = None,
) -> list[dict]:
    """Deterministically verify raw or explicitly enumerated literal forms."""
    normalized_tokens, _ = validate_declarations(tokens, [])
    results: list[dict] = []
    for token in normalized_tokens:
        if token["scope"] == "scene":
            span = {"start": 0, "end": len(scene_text)}
        else:
            span = _normalize_patch_span(patch_spans, token["patch_id"], len(scene_text))
        region_text = scene_text[span["start"]:span["end"]]
        forms = [token["raw"]]
        if token["match_mode"] == "normalized":
            forms.extend(token["accepted_forms"])
        matched_form = next((form for form in forms if form in region_text), None)
        results.append({
            "patch_id": token["patch_id"],
            "token_id": token["token_id"],
            "found": matched_form is not None,
            "matched_form": matched_form,
            "region": {"scope": token["scope"], **span},
        })
    return results


def verify_scene_literal_integrity(
    work_dir: Path | str,
    scene_id: str,
    scene_text: str,
    *,
    patch_spans: Mapping[str, object] | None = None,
) -> list[dict]:
    """Verify every literal in the immutable scene snapshot and hard-gate loss."""
    state = load_scene_integrity(work_dir, scene_id)
    tokens, _ = _flatten_scene_declarations(state)
    results = verify_literal_tokens(scene_text, tokens, patch_spans=patch_spans)
    validate_verification_coverage(tokens, [], results, [])
    return results


def _verification_keys(
    items: Iterable[object],
    id_field: str,
    kind: str,
    *,
    allow_duplicates: bool,
) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        context = f"{kind}_verifications[{index}]"
        if not isinstance(item, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        key = _identity(item, id_field, context)
        if key in keys and not allow_duplicates:
            raise ProtectedIntegrityError(f"duplicate_verification:{kind}:{key!r}")
        keys.add(key)
    return keys


def validate_verification_coverage(
    tokens: Sequence[object],
    relations: Sequence[object],
    token_results: Sequence[object],
    relation_records: Sequence[object],
) -> None:
    """Require declared and verified compound-identity sets to be equal."""
    normalized_tokens, normalized_relations = validate_declarations(tokens, relations)
    declared_tokens = {(item["patch_id"], item["token_id"]) for item in normalized_tokens}
    declared_relations = {
        (item["patch_id"], item["relation_id"]) for item in normalized_relations
    }
    verified_tokens = _verification_keys(
        token_results,
        "token_id",
        "token",
        allow_duplicates=False,
    )
    # Relation history intentionally contains repeated compound identities.
    verified_relations = _verification_keys(
        relation_records,
        "relation_id",
        "relation",
        allow_duplicates=True,
    )
    if declared_tokens != verified_tokens or declared_relations != verified_relations:
        raise ProtectedIntegrityError(
            "verification_set_mismatch:"
            f"tokens_missing={sorted(declared_tokens - verified_tokens)!r};"
            f"tokens_extra={sorted(verified_tokens - declared_tokens)!r};"
            f"relations_missing={sorted(declared_relations - verified_relations)!r};"
            f"relations_extra={sorted(verified_relations - declared_relations)!r}"
        )

    token_by_key = {
        (item["patch_id"], item["token_id"]): item for item in normalized_tokens
    }
    for index, result in enumerate(token_results):
        context = f"token_verifications[{index}]"
        assert isinstance(result, Mapping)  # established by _verification_keys
        key = (result["patch_id"], result["token_id"])
        found = result.get("found")
        if not isinstance(found, bool):
            raise ProtectedIntegrityError(f"{context}:found_must_be_bool")
        matched_form = result.get("matched_form")
        if not found:
            if matched_form is not None:
                raise ProtectedIntegrityError(f"{context}:missing_literal_has_matched_form")
            raise ProtectedIntegrityError(f"literal_not_found:{key!r}")
        if not isinstance(matched_form, str) or not matched_form:
            raise ProtectedIntegrityError(f"{context}:matched_form_required")
        declaration = token_by_key[key]
        allowed_forms = [declaration["raw"]]
        if declaration["match_mode"] == "normalized":
            allowed_forms.extend(declaration["accepted_forms"])
        if matched_form not in allowed_forms:
            raise ProtectedIntegrityError(
                f"{context}:matched_form_not_declared:{matched_form!r}"
            )
        region = result.get("region")
        span = _normalize_span(region, context)
        if not isinstance(region, Mapping) or region.get("scope") != declaration["scope"]:
            raise ProtectedIntegrityError(f"{context}:region_scope_mismatch")
        if span["end"] <= span["start"]:
            raise ProtectedIntegrityError(f"{context}:region_invalid")

    for index, record in enumerate(relation_records):
        _validate_relation_record_shape(record, index)


def _find_occurrences(text: str, quote: str) -> list[int]:
    result: list[int] = []
    offset = 0
    while True:
        found = text.find(quote, offset)
        if found < 0:
            return result
        result.append(found)
        offset = found + 1


def _validate_relation_record_shape(record: object, index: int) -> dict:
    context = f"relation_verifications[{index}]"
    if not isinstance(record, Mapping):
        raise ProtectedIntegrityError(f"{context}:must_be_mapping")
    item = _record_payload(record)
    _identity(item, "relation_id", context)
    if not isinstance(item.get("preserved"), bool):
        raise ProtectedIntegrityError(f"{context}:preserved_must_be_bool")
    _require_nonempty_string(item.get("after_quote"), "after_quote", context)
    _require_nonempty_string(item.get("reason"), "reason", context)
    item["current_span"] = _normalize_span(item.get("current_span"), context)
    scene_sha = item.get("scene_sha")
    if (
        not isinstance(scene_sha, str)
        or len(scene_sha) != 64
        or any(char not in "0123456789abcdef" for char in scene_sha)
    ):
        raise ProtectedIntegrityError(f"{context}:scene_sha_invalid")
    return item


def _validate_relation_record_against_scene(record: object, index: int, scene_text: str) -> dict:
    item = _validate_relation_record_shape(record, index)
    if item["scene_sha"] != scene_sha256(scene_text):
        raise ProtectedIntegrityError(
            f"relation_verifications[{index}]:scene_sha_mismatch"
        )
    occurrences = _find_occurrences(scene_text, item["after_quote"])
    if not occurrences:
        raise ProtectedIntegrityError(
            f"relation_verifications[{index}]:after_quote_not_found"
        )
    if len(occurrences) != 1:
        raise ProtectedIntegrityError(
            f"relation_verifications[{index}]:after_quote_ambiguous"
        )
    expected_span = {
        "start": occurrences[0],
        "end": occurrences[0] + len(item["after_quote"]),
    }
    if item["current_span"] != expected_span:
        raise ProtectedIntegrityError(
            f"relation_verifications[{index}]:current_span_mismatch"
        )
    return item


def _flatten_scene_declarations(state: Mapping) -> tuple[list[dict], list[dict]]:
    tokens: list[dict] = []
    relations: list[dict] = []
    for snapshot in state.get("declaration_snapshots", []):
        tokens.extend(copy.deepcopy(snapshot["tokens"]))
        relations.extend(copy.deepcopy(snapshot["relations"]))
    validate_declarations(tokens, relations)
    return tokens, relations


def scene_declarations(
    work_dir: Path | str,
    scene_id: str,
) -> tuple[list[dict], list[dict]]:
    """Return validated declarations from every immutable scene snapshot."""
    return _flatten_scene_declarations(load_scene_integrity(work_dir, scene_id))


def _batch_declarations(
    state: Mapping,
    batch_ids: Sequence[str],
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    tokens, relations = _flatten_scene_declarations(state)
    token_by_key = {(item["patch_id"], item["token_id"]): item for item in tokens}
    relation_by_key = {
        (item["patch_id"], item["relation_id"]): item for item in relations
    }
    selected = [
        batch for batch in state.get("application_batches", [])
        if batch["batch_id"] in set(batch_ids)
    ]
    if {item["batch_id"] for item in selected} != set(batch_ids):
        raise ProtectedIntegrityError("application_batch_unknown")
    token_keys: list[tuple[str, str]] = []
    relation_triggers: dict[tuple[str, str], set[str]] = {}
    patch_ids: list[str] = []
    for batch in selected:
        patch_ids.extend(batch["patch_ids"])
        for ref in batch["token_keys"]:
            key = (ref["patch_id"], ref["token_id"])
            if key not in token_keys:
                token_keys.append(key)
        for scope in batch["relation_scopes"]:
            key = (scope["patch_id"], scope["relation_id"])
            relation_triggers.setdefault(key, set()).update(scope["trigger_patch_ids"])
    current_tokens = [copy.deepcopy(token_by_key[key]) for key in token_keys]
    current_relations = [
        copy.deepcopy(relation_by_key[key]) for key in relation_triggers
    ]
    scopes = [
        {
            "patch_id": key[0],
            "relation_id": key[1],
            "trigger_patch_ids": sorted(triggers),
        }
        for key, triggers in relation_triggers.items()
    ]
    return current_tokens, current_relations, scopes, list(dict.fromkeys(patch_ids))


def _pending_application_declarations(
    state: Mapping,
) -> tuple[list[str], list[dict], list[dict], list[dict], list[str]]:
    verified = set(state.get("verified_batch_ids", []))
    batch_ids = [
        batch["batch_id"] for batch in state.get("application_batches", [])
        if batch["batch_id"] not in verified
    ]
    tokens, relations, scopes, patch_ids = _batch_declarations(state, batch_ids)
    return batch_ids, tokens, relations, scopes, patch_ids


def _scene_rewrite_mode(work_dir: Path, scene_id: str) -> str | None:
    path = work_dir / "pipeline" / "review" / f"scene_{scene_id}.yaml"
    try:
        review = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    verdict = str(review.get("verdict") or "").upper() if isinstance(review, Mapping) else ""
    return verdict if verdict in {"ROLLBACK", "REWRITE"} else None


def _rewrite_requires_relation_review(
    work_dir: Path,
    scene_id: str,
    state: Mapping,
) -> bool:
    if _scene_rewrite_mode(work_dir, scene_id) is None:
        return False
    _, relations = _flatten_scene_declarations(state)
    if not relations:
        return False
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    try:
        current_sha = scene_sha256(scene_path.read_text(encoding="utf-8"))
    except OSError:
        return True
    runs = state.get("verification_runs", [])
    return not runs or runs[-1].get("scene_sha") != current_sha


def _ensure_post_rewrite_batch(
    work_dir: Path,
    scene_id: str,
    scene_text: str,
) -> None:
    state = load_scene_integrity(work_dir, scene_id)
    if not _rewrite_requires_relation_review(work_dir, scene_id, state):
        return
    tokens, relations = _flatten_scene_declarations(state)
    mode = _scene_rewrite_mode(work_dir, scene_id)
    assert mode is not None
    current_sha = scene_sha256(scene_text)
    previous_sha = (
        state["verification_runs"][-1]["scene_sha"]
        if state["verification_runs"]
        else current_sha
    )
    directive_sha = _canonical_sha({
        "mode": mode,
        "pre_scene_sha": previous_sha,
        "post_scene_sha": current_sha,
    })
    synthetic_patch = f"__{mode.lower()}__"
    relation_scopes = [
        {
            **_protected_key_ref(item, "relation_id"),
            "trigger_patch_ids": [synthetic_patch],
        }
        for item in relations
    ]
    batch = _make_application_batch(
        batch_id=f"post_rewrite:{mode.lower()}:{current_sha[:16]}",
        round_id=f"post_rewrite:{mode.lower()}",
        directive_sha=directive_sha,
        pre_scene_sha=previous_sha,
        patch_ids=[synthetic_patch],
        tokens=tokens,
        relation_scopes=relation_scopes,
    )
    _append_application_batch(work_dir, scene_id, batch)


def prepare_post_rewrite_application(
    work_dir: Path | str,
    scene_id: str,
) -> bool:
    """Materialize the synthetic relation-review batch before reviewer dispatch.

    ROLLBACK rewrites do not have a patch directive from which the normal
    pre-revision validator can build an application batch.  Preparing it here
    exposes the exact current relation scopes to the reviewer while keeping the
    later verifier's idempotent fallback.
    """
    root = Path(work_dir)
    state_before = load_scene_integrity(root, scene_id)
    pending_before, _, _, _, _ = _pending_application_declarations(state_before)
    scene_path = root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    scene_text = scene_path.read_text(encoding="utf-8")
    _ensure_post_rewrite_batch(root, scene_id, scene_text)
    state_after = load_scene_integrity(root, scene_id)
    pending_after, _, _, _, _ = _pending_application_declarations(state_after)
    return pending_after != pending_before


def has_pending_relation_declarations(work_dir: Path | str, scene_id: str) -> bool:
    """Return whether this application round requires semantic review."""
    root = Path(work_dir)
    state = load_scene_integrity(root, scene_id)
    _, _, _, scopes, _ = _pending_application_declarations(state)
    return bool(scopes) or _rewrite_requires_relation_review(root, scene_id, state)


def _record_verification_run(
    work_dir: Path | str,
    scene_id: str,
    *,
    batch_ids: Sequence[str],
    scene_sha: str,
    review_path: str,
    token_records: Sequence[Mapping],
    relation_records: Sequence[Mapping],
) -> None:
    path = _scene_path(work_dir, scene_id)
    state = load_scene_integrity(work_dir, scene_id)
    pending_ids, _, _, _, _ = _pending_application_declarations(state)
    if list(batch_ids) != pending_ids:
        raise ProtectedIntegrityError(
            f"verification_batch_partition_changed:{pending_ids!r}!={list(batch_ids)!r}"
        )
    token_hashes = [_canonical_sha(_record_payload(item)) for item in token_records]
    relation_hashes = [_canonical_sha(_record_payload(item)) for item in relation_records]
    known_token_hashes = {item["record_sha"] for item in state["token_verifications"]}
    known_relation_hashes = {item["record_sha"] for item in state["relation_verifications"]}
    if not set(token_hashes).issubset(known_token_hashes):
        raise ProtectedIntegrityError("verification_run_token_records_missing")
    if not set(relation_hashes).issubset(known_relation_hashes):
        raise ProtectedIntegrityError("verification_run_relation_records_missing")
    payload = {
        "batch_ids": list(batch_ids),
        "scene_sha": scene_sha,
        "review_path": review_path,
        "token_record_shas": token_hashes,
        "relation_record_shas": relation_hashes,
    }
    verification_sha = _canonical_sha(payload)
    if state["verification_runs"] and (
        state["verification_runs"][-1]["verification_sha"] == verification_sha
    ):
        return
    state["verification_runs"].append({
        **payload,
        "verification_sha": verification_sha,
    })
    state["verified_batch_ids"].extend(batch_ids)
    _atomic_write_yaml(path, state)
    load_scene_integrity(work_dir, scene_id)


def _token_forms(token: Mapping) -> list[str]:
    forms = [str(token["raw"])]
    if token.get("match_mode") == "normalized":
        forms.extend(str(form) for form in token.get("accepted_forms", []))
    return forms


def append_token_verifications(
    work_dir: Path | str,
    scene_id: str,
    scene_text: str,
    records: Sequence[object],
) -> Path:
    """Append one exact current-occurrence record for every declared token."""
    path = _scene_path(work_dir, scene_id)
    state = load_scene_integrity(work_dir, scene_id)
    tokens, _ = _flatten_scene_declarations(state)
    declared = {(item["patch_id"], item["token_id"]): item for item in tokens}
    normalized: list[dict] = []
    keys: set[tuple[str, str]] = set()
    current_sha = scene_sha256(scene_text)
    for index, record in enumerate(records):
        item = _validate_token_record_shape(record, index)
        key = (item["patch_id"], item["token_id"])
        if key in keys:
            raise ProtectedIntegrityError(f"duplicate_verification:token:{key!r}")
        keys.add(key)
        token = declared.get(key)
        if token is None:
            raise ProtectedIntegrityError(f"undeclared_token_verification:{key!r}")
        if item["matched_form"] not in _token_forms(token):
            raise ProtectedIntegrityError(
                f"token_verifications[{index}]:matched_form_not_declared"
            )
        if item["scene_sha"] != current_sha:
            raise ProtectedIntegrityError(f"token_verifications[{index}]:scene_sha_mismatch")
        span = item["current_span"]
        if span["end"] > len(scene_text) or scene_text[span["start"]:span["end"]] != item["matched_form"]:
            raise ProtectedIntegrityError(f"token_verifications[{index}]:current_span_mismatch")
        normalized.append(item)
    if set(declared) != keys:
        raise ProtectedIntegrityError(
            "token_verification_set_mismatch:"
            f"missing={sorted(set(declared) - keys)!r};"
            f"extra={sorted(keys - set(declared))!r}"
        )

    existing_hashes = {item["record_sha"] for item in state["token_verifications"]}
    additions: list[dict] = []
    for item in normalized:
        record_sha = _canonical_sha(item)
        if record_sha not in existing_hashes:
            additions.append({**item, "record_sha": record_sha})
            existing_hashes.add(record_sha)
    if additions:
        state["token_verifications"].extend(additions)
        _atomic_write_yaml(path, state)
    return path


def derive_active_token_anchors(
    tokens: Sequence[object],
    token_records: Sequence[object],
    scene_text: str,
) -> list[dict]:
    """Project the latest exact token occurrence onto the supplied scene."""
    normalized_tokens, _ = validate_declarations(tokens, [])
    declared = {
        (item["patch_id"], item["token_id"]): item for item in normalized_tokens
    }
    latest: dict[tuple[str, str], dict] = {}
    for index, record in enumerate(token_records):
        item = _validate_token_record_shape(record, index)
        key = (item["patch_id"], item["token_id"])
        if key not in declared:
            raise ProtectedIntegrityError(f"undeclared_token_verification:{key!r}")
        latest[key] = item

    current_sha = scene_sha256(scene_text)
    anchors: list[dict] = []
    for key, token in declared.items():
        record = latest.get(key)
        if record is None:
            raise ProtectedIntegrityError(f"active_token_verification_missing:{key!r}")
        elif record["scene_sha"] == current_sha:
            position = record["current_span"]["start"]
            matched_form = record["matched_form"]
            if scene_text[position:record["current_span"]["end"]] != matched_form:
                raise ProtectedIntegrityError(f"active_token_span_mismatch:{key!r}")
        else:
            matches = [
                (position, form)
                for form in _token_forms(token)
                for position in _find_occurrences(scene_text, form)
            ]
            if not matches:
                raise ProtectedIntegrityError(f"active_token_not_found:{key!r}")
            if len(matches) != 1:
                raise ProtectedIntegrityError(f"active_token_ambiguous:{key!r}")
            position, matched_form = matches[0]
        anchors.append({
            "patch_id": key[0],
            "token_id": key[1],
            "matched_form": matched_form,
            "current_span": {"start": position, "end": position + len(matched_form)},
            "scene_sha": current_sha,
        })
    return anchors


def append_relation_verifications(
    work_dir: Path | str,
    scene_id: str,
    scene_text: str,
    records: Sequence[object],
) -> Path:
    """Append reviewer verification records without replacing prior rounds."""
    path = _scene_path(work_dir, scene_id)
    state = load_scene_integrity(work_dir, scene_id)
    _, relations = _flatten_scene_declarations(state)
    declared = {(item["patch_id"], item["relation_id"]) for item in relations}
    existing_hashes = {item["record_sha"] for item in state["relation_verifications"]}
    additions: list[dict] = []
    batch_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        normalized = _validate_relation_record_against_scene(record, index, scene_text)
        key = (normalized["patch_id"], normalized["relation_id"])
        if key not in declared:
            raise ProtectedIntegrityError(f"undeclared_relation_verification:{key!r}")
        if key in batch_keys:
            raise ProtectedIntegrityError(f"duplicate_verification:relation:{key!r}")
        batch_keys.add(key)
        record_sha = _canonical_sha(normalized)
        if record_sha in existing_hashes:
            continue
        additions.append({**normalized, "record_sha": record_sha})
        existing_hashes.add(record_sha)
    prospective_records = [*state["relation_verifications"], *additions]
    validate_verification_coverage([], relations, [], prospective_records)
    if additions:
        state["relation_verifications"].extend(additions)
        _atomic_write_yaml(path, state)
    return path


def derive_active_relation_anchors(
    relations: Sequence[object],
    relation_records: Sequence[object],
    scene_text: str,
) -> list[dict]:
    """Project each relation's latest PASS record onto the current scene.

    Stale numeric offsets are relocated by the exact quote. A missing or
    non-unique quote is a hard failure.
    """
    _, normalized_relations = validate_declarations([], relations)
    declared = {
        (item["patch_id"], item["relation_id"]): item
        for item in normalized_relations
    }
    normalized_records = [
        _validate_relation_record_shape(record, index)
        for index, record in enumerate(relation_records)
    ]
    validate_verification_coverage([], normalized_relations, [], normalized_records)
    latest_pass: dict[tuple[str, str], dict] = {}
    for record in normalized_records:
        key = (record["patch_id"], record["relation_id"])
        if key not in declared:
            raise ProtectedIntegrityError(f"undeclared_relation_verification:{key!r}")
        if record["preserved"]:
            latest_pass[key] = record

    current_sha = scene_sha256(scene_text)
    anchors: list[dict] = []
    for relation in normalized_relations:
        key = (relation["patch_id"], relation["relation_id"])
        record = latest_pass.get(key)
        if record is None:
            raise ProtectedIntegrityError(f"active_anchor_missing:{key!r}")
        occurrences = _find_occurrences(scene_text, record["after_quote"])
        if not occurrences:
            raise ProtectedIntegrityError(f"active_anchor_not_found:{key!r}")
        if len(occurrences) != 1:
            raise ProtectedIntegrityError(f"active_anchor_ambiguous:{key!r}")
        relocated = {
            "start": occurrences[0],
            "end": occurrences[0] + len(record["after_quote"]),
        }
        if record["scene_sha"] == current_sha and record["current_span"] != relocated:
            raise ProtectedIntegrityError(f"active_anchor_span_mismatch:{key!r}")
        anchors.append({
            "patch_id": key[0],
            "relation_id": key[1],
            "after_quote": record["after_quote"],
            "current_span": relocated,
            "scene_sha": current_sha,
        })
    return anchors


def derive_scene_active_relation_anchors(
    work_dir: Path | str,
    scene_id: str,
    scene_text: str,
) -> list[dict]:
    """Load a scene's append-only history and derive its active projection."""
    state = load_scene_integrity(work_dir, scene_id)
    _, relations = _flatten_scene_declarations(state)
    return derive_active_relation_anchors(
        relations,
        state["relation_verifications"],
        scene_text,
    )


def validate_partial_relation_update(
    relations: Sequence[object],
    prior_records: Sequence[object],
    new_records: Sequence[object],
    *,
    applied_patch_ids: set[str],
    not_applied_patch_ids: set[str],
) -> list[dict]:
    """Validate the partial fork and return append-order record history."""
    _, normalized_relations = validate_declarations([], relations)
    applied = set(applied_patch_ids)
    not_applied = set(not_applied_patch_ids)
    if applied & not_applied:
        raise ProtectedIntegrityError(
            f"partial_patch_partition_overlap:{sorted(applied & not_applied)!r}"
        )
    relation_patch_ids = {item["patch_id"] for item in normalized_relations}
    if applied | not_applied != relation_patch_ids:
        raise ProtectedIntegrityError(
            "partial_patch_partition_mismatch:"
            f"missing={sorted(relation_patch_ids - (applied | not_applied))!r};"
            f"extra={sorted((applied | not_applied) - relation_patch_ids)!r}"
        )

    normalized_prior = [
        _validate_relation_record_shape(record, index)
        for index, record in enumerate(prior_records)
    ]
    normalized_new = [
        _validate_relation_record_shape(record, index)
        for index, record in enumerate(new_records)
    ]
    new_keys: set[tuple[str, str]] = set()
    for record in normalized_new:
        key = (record["patch_id"], record["relation_id"])
        if key in new_keys:
            raise ProtectedIntegrityError(f"duplicate_verification:relation:{key!r}")
        new_keys.add(key)
    expected_applied = {
        (item["patch_id"], item["relation_id"])
        for item in normalized_relations
        if item["patch_id"] in applied
    }
    expected_not_applied = {
        (item["patch_id"], item["relation_id"])
        for item in normalized_relations
        if item["patch_id"] in not_applied
    }
    missing_applied = expected_applied - new_keys
    if missing_applied:
        raise ProtectedIntegrityError(
            f"applied_relation_missing_verification:{sorted(missing_applied)!r}"
        )
    unexpected_applied = new_keys - expected_applied
    if unexpected_applied & expected_not_applied:
        raise ProtectedIntegrityError(
            "not_applied_relation_has_verification:"
            f"{sorted(unexpected_applied & expected_not_applied)!r}"
        )
    if unexpected_applied - expected_not_applied:
        raise ProtectedIntegrityError(
            f"undeclared_relation_verification:{sorted(unexpected_applied - expected_not_applied)!r}"
        )

    prior_pass = {
        (record["patch_id"], record["relation_id"])
        for record in normalized_prior
        if record["preserved"]
    }
    missing_old_anchor = expected_not_applied - prior_pass
    if missing_old_anchor:
        raise ProtectedIntegrityError(
            f"not_applied_relation_missing_active_anchor:{sorted(missing_old_anchor)!r}"
        )
    return [*normalized_prior, *normalized_new]


def detect_relation_overlaps(
    changes: Sequence[object],
    active_anchors: Sequence[object],
) -> list[dict]:
    """Return edits intersecting an anchor; a start-boundary insertion can modify it."""
    normalized_anchors: list[tuple[tuple[str, str], dict[str, int]]] = []
    seen: set[tuple[str, str]] = set()
    for index, anchor in enumerate(active_anchors):
        context = f"active_anchors[{index}]"
        if not isinstance(anchor, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        key = _identity(anchor, "relation_id", context)
        if key in seen:
            raise ProtectedIntegrityError(f"duplicate_active_anchor:{key!r}")
        seen.add(key)
        normalized_anchors.append((key, _normalize_span(anchor.get("current_span"), context)))

    overlaps: list[dict] = []
    for index, change in enumerate(changes):
        context = f"changes[{index}]"
        if not isinstance(change, Mapping):
            raise ProtectedIntegrityError(f"{context}:must_be_mapping")
        raw_span = change.get("current_span")
        if not isinstance(raw_span, Mapping):
            raise ProtectedIntegrityError(f"{context}:current_span_invalid")
        start = raw_span.get("start")
        end = raw_span.get("end")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end < start
        ):
            raise ProtectedIntegrityError(f"{context}:current_span_invalid")
        span = {"start": start, "end": end}
        change_id = change.get("change_id", f"change_{index}")
        for key, anchor_span in normalized_anchors:
            if span["start"] == span["end"]:
                intersects = anchor_span["start"] <= span["start"] < anchor_span["end"]
            else:
                intersects = max(span["start"], anchor_span["start"]) < min(
                    span["end"], anchor_span["end"]
                )
            if intersects:
                overlaps.append({
                    "change_id": change_id,
                    "change_span": span,
                    "patch_id": key[0],
                    "relation_id": key[1],
                    "relation_span": anchor_span,
                })
    return overlaps


def assert_no_relation_overlap(
    changes: Sequence[object],
    active_anchors: Sequence[object],
) -> None:
    overlaps = detect_relation_overlaps(changes, active_anchors)
    if overlaps:
        raise ProtectedIntegrityError(f"relation_span_overlap:{overlaps!r}")


def diff_change_spans(before_text: str, after_text: str) -> list[dict]:
    """Project deterministic text changes onto half-open coordinates in before_text.

    Insertions use a zero-width span.  Overlap detection treats an insertion
    strictly inside an active relation as a protected modification while
    preserving the usual half-open boundary behavior.
    """
    matcher = difflib.SequenceMatcher(None, before_text, after_text, autojunk=False)
    changes: list[dict] = []
    for index, (tag, before_start, before_end, after_start, after_end) in enumerate(
        matcher.get_opcodes()
    ):
        if tag == "equal":
            continue
        changes.append({
            "change_id": f"diff_{index}",
            "kind": tag,
            "current_span": {"start": before_start, "end": before_end},
            "after_span": {"start": after_start, "end": after_end},
        })
    return changes


def _project_token_anchors_after_revision(
    tokens: Sequence[dict],
    active_before: Sequence[dict],
    before_text: str,
    after_text: str,
) -> list[dict]:
    token_by_key = {(item["patch_id"], item["token_id"]): item for item in tokens}
    current_sha = scene_sha256(after_text)
    projected: list[dict] = []
    for anchor in active_before:
        key = (anchor["patch_id"], anchor["token_id"])
        token = token_by_key[key]
        allowed = _token_forms(token)
        mapped = _map_unchanged_span(before_text, after_text, anchor["current_span"])
        position: int | None = None
        matched_form: str | None = None
        if mapped is not None:
            candidate = after_text[mapped["start"]:mapped["end"]]
            if candidate in allowed:
                position = mapped["start"]
                matched_form = candidate
        if matched_form is None:
            matches = [
                (found, form)
                for form in allowed
                for found in _find_occurrences(after_text, form)
            ]
            if not matches:
                raise ProtectedIntegrityError(f"active_token_not_found:{key!r}")
            if len(matches) != 1:
                raise ProtectedIntegrityError(f"active_token_ambiguous:{key!r}")
            position, matched_form = matches[0]
        assert position is not None and matched_form is not None
        projected.append({
            "patch_id": key[0],
            "token_id": key[1],
            "matched_form": matched_form,
            "current_span": {
                "start": position,
                "end": position + len(matched_form),
            },
            "scene_sha": current_sha,
        })
    return projected


def audit_scene_revision_integrity(
    work_dir: Path | str,
    scene_id: str,
    before_text: str,
    after_text: str,
) -> dict:
    """Run the deterministic protected checks for a distribution-style edit."""
    report = {
        "verdict": "PASS",
        "literal_results": [],
        "active_tokens_before": [],
        "active_tokens_after": [],
        "active_relations_before": [],
        "active_relations_after": [],
        "relation_overlaps": [],
    }
    errors: list[str] = []
    try:
        state = load_scene_integrity(work_dir, scene_id)
        tokens, relations = _flatten_scene_declarations(state)
    except ProtectedIntegrityError as exc:
        report.update({"verdict": "FAIL", "reason": str(exc)})
        return report

    try:
        before_tokens = derive_active_token_anchors(
            tokens,
            state["token_verifications"],
            before_text,
        )
        after_tokens = _project_token_anchors_after_revision(
            tokens,
            before_tokens,
            before_text,
            after_text,
        )
        token_by_key = {
            (token["patch_id"], token["token_id"]): token for token in tokens
        }
        literal_results = [{
            "patch_id": anchor["patch_id"],
            "token_id": anchor["token_id"],
            "found": True,
            "matched_form": anchor["matched_form"],
            "region": {
                "scope": token_by_key[(anchor["patch_id"], anchor["token_id"])]["scope"],
                **anchor["current_span"],
            },
        } for anchor in after_tokens]
        report["literal_results"] = literal_results
        report["active_tokens_before"] = before_tokens
        report["active_tokens_after"] = after_tokens
        validate_verification_coverage(tokens, [], literal_results, [])
    except ProtectedIntegrityError as exc:
        errors.append(str(exc))

    changes = diff_change_spans(before_text, after_text)
    try:
        before_anchors = derive_active_relation_anchors(
            relations,
            state["relation_verifications"],
            before_text,
        )
        report["active_relations_before"] = before_anchors
        overlaps = detect_relation_overlaps(changes, before_anchors)
        report["relation_overlaps"] = overlaps
        if overlaps:
            errors.append(f"relation_span_overlap:{overlaps!r}")
        after_anchors = derive_active_relation_anchors(
            relations,
            state["relation_verifications"],
            after_text,
        )
        report["active_relations_after"] = after_anchors
    except ProtectedIntegrityError as exc:
        errors.append(str(exc))

    if errors:
        report["verdict"] = "FAIL"
        report["reason"] = ";".join(errors)
    return report


def _assembled_story_source(work_dir: Path | str) -> tuple[str, dict[str, dict[str, int]]]:
    """Reproduce assemble_story.py output and return scene spans."""
    root = Path(work_dir).resolve()
    index_path = root / "pipeline" / "phase6_development.yaml"
    if not index_path.exists():
        raise ProtectedIntegrityError(f"phase6_development_missing:{index_path}")
    index_text = index_path.read_text(encoding="utf-8")
    file_paths: list[str] = []
    try:
        parsed = yaml.safe_load(index_text) or {}
    except yaml.YAMLError:
        parsed = {}
    if isinstance(parsed, Mapping) and isinstance(parsed.get("scenes"), list):
        file_paths = [
            str(item["file_path"])
            for item in parsed["scenes"]
            if isinstance(item, Mapping)
            and isinstance(item.get("file_path"), str)
            and item["file_path"]
        ]
    if not file_paths:
        file_paths = [
            value.strip().strip('"').strip("'")
            for value in re.findall(r"^\s+file_path:\s+(.+)$", index_text, re.MULTILINE)
        ]
    if not file_paths:
        raise ProtectedIntegrityError("phase6_scene_paths_missing")

    parts: list[str] = []
    spans: dict[str, dict[str, int]] = {}
    cursor = 0
    for rel_path in file_paths:
        scene_path = (root / rel_path).resolve()
        try:
            scene_path.relative_to(root)
        except ValueError as exc:
            raise ProtectedIntegrityError(f"scene_path_outside_work_dir:{rel_path}") from exc
        if not scene_path.exists():
            raise ProtectedIntegrityError(f"scene_path_missing:{rel_path}")
        match = re.fullmatch(r"scene_(.+)\.md", scene_path.name)
        if match is None:
            raise ProtectedIntegrityError(f"scene_path_name_invalid:{rel_path}")
        scene_id = match.group(1)
        if scene_id in spans:
            raise ProtectedIntegrityError(f"duplicate_scene_id:{scene_id}")
        part = scene_path.read_text(encoding="utf-8").rstrip("\n")
        if parts:
            cursor += 2
        start = cursor
        cursor += len(part)
        spans[scene_id] = {"start": start, "end": cursor}
        parts.append(part)
    return "\n\n".join(parts) + "\n", spans


def _map_unchanged_span(
    before_text: str,
    after_text: str,
    span: Mapping[str, int],
) -> dict[str, int] | None:
    matcher = difflib.SequenceMatcher(None, before_text, after_text, autojunk=False)
    for tag, before_start, before_end, after_start, _ in matcher.get_opcodes():
        if (
            tag == "equal"
            and before_start <= span["start"]
            and span["end"] <= before_end
        ):
            mapped_start = after_start + span["start"] - before_start
            return {
                "start": mapped_start,
                "end": mapped_start + span["end"] - span["start"],
            }
    return None


def audit_terminal_integrity(work_dir: Path | str, story_text: str) -> dict:
    """Check current scene declarations and manuscript edits before release."""
    root = Path(work_dir)
    artifact_paths = sorted((root / "pipeline").glob("scene_*/protected_integrity.yaml"))
    empty = {
        "verdict": "PASS",
        "scene_results": [],
        "literal_results": [],
        "active_tokens_before": [],
        "active_tokens_after": [],
        "active_relations_before": [],
        "active_relations_after": [],
        "relation_overlaps": [],
    }
    if not artifact_paths:
        return empty

    report = copy.deepcopy(empty)
    errors: list[str] = []
    try:
        validate_run_global_ids(root)
        assembled, scene_spans = _assembled_story_source(root)
    except (OSError, ProtectedIntegrityError) as exc:
        report.update({"verdict": "FAIL", "reason": str(exc)})
        return report

    manuscript_tokens: list[dict] = []
    manuscript_anchors: list[dict] = []
    for artifact_path in artifact_paths:
        scene_id = artifact_path.parent.name.removeprefix("scene_")
        try:
            scene_state = load_scene_integrity(root, scene_id)
            pending_batch_ids, _, _, _, _ = _pending_application_declarations(
                scene_state
            )
        except ProtectedIntegrityError as exc:
            errors.append(f"scene_{scene_id}:{exc}")
            continue
        if pending_batch_ids:
            errors.append(
                f"scene_{scene_id}:pending_application_batches:{pending_batch_ids!r}"
            )
            continue
        scene_path = root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
        if not scene_path.exists() or scene_id not in scene_spans:
            errors.append(f"protected_scene_missing_from_phase6:{scene_id}")
            continue
        scene_text = scene_path.read_text(encoding="utf-8")
        scene_result = audit_scene_revision_integrity(
            root,
            scene_id,
            scene_text,
            scene_text,
        )
        report["scene_results"].append({"scene_id": scene_id, **scene_result})
        if scene_result["verdict"] != "PASS":
            errors.append(f"scene_{scene_id}:{scene_result.get('reason', 'protected_failed')}")
        try:
            tokens, _ = scene_declarations(root, scene_id)
            token_by_key = {
                (item["patch_id"], item["token_id"]): item for item in tokens
            }
            base_start = scene_spans[scene_id]["start"]
            for anchor in scene_result.get("active_tokens_after", []):
                span = anchor["current_span"]
                declaration = token_by_key[(anchor["patch_id"], anchor["token_id"])]
                manuscript_tokens.append({
                    **anchor,
                    "scene_id": scene_id,
                    "allowed_forms": _token_forms(declaration),
                    "current_span": {
                        "start": base_start + span["start"],
                        "end": base_start + span["end"],
                    },
                })
            for anchor in scene_result.get("active_relations_before", []):
                span = anchor["current_span"]
                manuscript_anchors.append({
                    **anchor,
                    "scene_id": scene_id,
                    "current_span": {
                        "start": base_start + span["start"],
                        "end": base_start + span["end"],
                    },
                })
        except ProtectedIntegrityError as exc:
            errors.append(f"scene_{scene_id}:{exc}")

    report["active_tokens_before"] = manuscript_tokens
    final_tokens: list[dict] = []
    literal_results: list[dict] = []
    for anchor in manuscript_tokens:
        key = (anchor["patch_id"], anchor["token_id"])
        mapped = _map_unchanged_span(assembled, story_text, anchor["current_span"])
        matched_form: str | None = None
        position: int | None = None
        if mapped is not None:
            candidate = story_text[mapped["start"]:mapped["end"]]
            if candidate in anchor["allowed_forms"]:
                matched_form = candidate
                position = mapped["start"]
        if matched_form is None:
            matches = [
                (found, form)
                for form in anchor["allowed_forms"]
                for found in _find_occurrences(story_text, form)
            ]
            if not matches:
                errors.append(f"manuscript_literal_not_found:{key!r}")
            elif len(matches) != 1:
                errors.append(f"manuscript_literal_ambiguous:{key!r}")
            else:
                position, matched_form = matches[0]
        found = matched_form is not None and position is not None
        literal_results.append({
            "patch_id": key[0],
            "token_id": key[1],
            "found": found,
            "matched_form": matched_form,
        })
        if found:
            assert matched_form is not None and position is not None
            final_tokens.append({
                **anchor,
                "matched_form": matched_form,
                "current_span": {
                    "start": position,
                    "end": position + len(matched_form),
                },
                "scene_sha": scene_sha256(story_text),
            })
    report["literal_results"] = literal_results
    report["active_tokens_after"] = final_tokens

    report["active_relations_before"] = manuscript_anchors
    changes = diff_change_spans(assembled, story_text)
    try:
        overlaps = detect_relation_overlaps(changes, manuscript_anchors)
        report["relation_overlaps"] = overlaps
        if overlaps:
            errors.append(f"manuscript_relation_span_overlap:{overlaps!r}")
    except ProtectedIntegrityError as exc:
        errors.append(str(exc))

    final_anchors: list[dict] = []
    for anchor in manuscript_anchors:
        quote = anchor["after_quote"]
        occurrences = _find_occurrences(story_text, quote)
        key = (anchor["patch_id"], anchor["relation_id"])
        if not occurrences:
            errors.append(f"manuscript_active_anchor_not_found:{key!r}")
            continue
        if len(occurrences) != 1:
            errors.append(f"manuscript_active_anchor_ambiguous:{key!r}")
            continue
        final_anchors.append({
            **anchor,
            "current_span": {
                "start": occurrences[0],
                "end": occurrences[0] + len(quote),
            },
            "scene_sha": scene_sha256(story_text),
        })
    report["active_relations_after"] = final_anchors

    if errors:
        report["verdict"] = "FAIL"
        report["reason"] = ";".join(errors)
    return report


def _revision_summary_patch_details(
    summary_text: str,
    scene_text: str,
) -> tuple[dict[str, dict[str, int]], set[str], set[str]]:
    """Extract patch partition and applied new_span rows from one summary."""
    regions: dict[str, dict[str, int]] = {}
    applied_patch_ids: set[str] = set()
    not_applied_patch_ids: set[str] = set()
    current_patch: str | None = None
    current_applied = False
    header_re = re.compile(r"^\s*\d+\.\s+\*\*\[([^\]]+)\]\*\*")
    new_span_re = re.compile(r"^\s*-\s*new_span\s*[：:]\s*(.+?)\s*$")
    for line in summary_text.splitlines():
        header = header_re.match(line)
        if header:
            parts = [part.strip() for part in header.group(1).split("·")]
            current_patch = parts[0] if parts else None
            current_applied = "applied" in parts
            if current_patch and current_applied:
                applied_patch_ids.add(current_patch)
            elif current_patch and "not_applied" in parts:
                not_applied_patch_ids.add(current_patch)
            continue
        match = new_span_re.match(line)
        if not match or not current_patch or not current_applied:
            continue
        value = match.group(1)
        occurrences = _find_occurrences(scene_text, value)
        if not occurrences:
            raise ProtectedIntegrityError(
                f"applied_new_span_not_found:{current_patch}"
            )
        if len(occurrences) != 1:
            raise ProtectedIntegrityError(
                f"applied_new_span_ambiguous:{current_patch}"
            )
        if current_patch in regions:
            raise ProtectedIntegrityError(
                f"applied_new_span_duplicate:{current_patch}"
            )
        regions[current_patch] = {
            "start": occurrences[0],
            "end": occurrences[0] + len(value),
        }
    overlap = applied_patch_ids & not_applied_patch_ids
    if overlap:
        raise ProtectedIntegrityError(
            f"revision_summary_patch_partition_overlap:{sorted(overlap)!r}"
        )
    return regions, applied_patch_ids, not_applied_patch_ids


def _applied_new_span_regions(
    summary_text: str,
    scene_text: str,
) -> dict[str, dict[str, int]]:
    """Compatibility view of applied patch regions."""
    regions, _, _ = _revision_summary_patch_details(summary_text, scene_text)
    return regions


def _pending_patch_regions(
    work_dir: Path,
    scene_id: str,
    scene_text: str,
) -> dict[str, dict[str, int]]:
    path = work_dir / "pipeline" / f"scene_{scene_id}" / "patch_directive.yaml"
    if not path.exists():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ProtectedIntegrityError(f"pending_patch_directive_invalid:{exc}") from exc
    patches = document.get("patches") if isinstance(document, Mapping) else None
    if not isinstance(patches, list):
        raise ProtectedIntegrityError("pending_patch_directive_patches_invalid")
    regions: dict[str, dict[str, int]] = {}
    for patch in patches:
        if not isinstance(patch, Mapping) or not isinstance(patch.get("patch_id"), str):
            continue
        patch_id = patch["patch_id"]
        quote = patch.get("old_span") or patch.get("anchor_quote")
        if not isinstance(quote, str) or not quote:
            continue
        occurrences = _find_occurrences(scene_text, quote)
        if not occurrences:
            raise ProtectedIntegrityError(f"pending_patch_span_not_found:{patch_id}")
        if len(occurrences) != 1:
            raise ProtectedIntegrityError(f"pending_patch_span_ambiguous:{patch_id}")
        regions[patch_id] = {
            "start": occurrences[0],
            "end": occurrences[0] + len(quote),
        }
    return regions


def _token_records_from_results(
    scene_text: str,
    tokens: Sequence[dict],
    results: Sequence[dict],
) -> list[dict]:
    token_by_key = {(item["patch_id"], item["token_id"]): item for item in tokens}
    current_sha = scene_sha256(scene_text)
    records: list[dict] = []
    for result in results:
        key = (result["patch_id"], result["token_id"])
        token = token_by_key[key]
        region = result["region"]
        matched_form = result["matched_form"]
        region_text = scene_text[region["start"]:region["end"]]
        occurrences = _find_occurrences(region_text, matched_form)
        if not occurrences:
            raise ProtectedIntegrityError(f"token_occurrence_not_found:{key!r}")
        if len(occurrences) != 1:
            raise ProtectedIntegrityError(f"token_occurrence_ambiguous:{key!r}")
        start = region["start"] + occurrences[0]
        if matched_form not in _token_forms(token):
            raise ProtectedIntegrityError(f"token_matched_form_not_declared:{key!r}")
        records.append({
            "patch_id": key[0],
            "token_id": key[1],
            "matched_form": matched_form,
            "current_span": {"start": start, "end": start + len(matched_form)},
            "scene_sha": current_sha,
        })
    return records


def _expected_post_revision_review_path(work_dir: Path, scene_id: str) -> Path:
    return (
        work_dir / "pipeline" / "review" / f"scene_{scene_id}.post_revision.yaml"
    ).resolve()


def _required_relation_record_keys(
    relation_scopes: Sequence[Mapping],
    batch_patch_ids: Sequence[str],
    applied_patch_ids: set[str],
    not_applied_patch_ids: set[str],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    current_patches = set(batch_patch_ids)
    touched = current_patches & (applied_patch_ids | not_applied_patch_ids)
    all_keys = {
        (scope["patch_id"], scope["relation_id"]) for scope in relation_scopes
    }
    if not touched:
        return all_keys, set()
    classified = current_patches & (applied_patch_ids | not_applied_patch_ids)
    if classified != current_patches:
        raise ProtectedIntegrityError(
            "revision_summary_batch_partition_incomplete:"
            f"missing={sorted(current_patches - classified)!r}"
        )
    applied = current_patches & applied_patch_ids
    required = {
        (scope["patch_id"], scope["relation_id"])
        for scope in relation_scopes
        if set(scope["trigger_patch_ids"]) & applied
    }
    return required, all_keys - required


def validate_post_revision_proof(
    work_dir: Path | str,
    scene_id: str,
    proof: Mapping | None = None,
) -> dict:
    """Purely validate the generated proof against its sidecar verification run.

    The proof file carries no authority by itself.  Its current-scene hash,
    canonical reviewer path, exact record hashes, and application batch IDs must
    equal the latest append-only sidecar run.
    """
    root = Path(work_dir)
    state = load_scene_integrity(root, scene_id)
    if proof is None:
        proof_path = (
            root
            / "pipeline"
            / "review"
            / f"{scene_id}.protected_integrity.post_revision.yaml"
        )
        try:
            loaded = yaml.safe_load(proof_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ProtectedIntegrityError(f"proof_missing_or_invalid:{exc}") from exc
        proof = loaded
    if not isinstance(proof, Mapping):
        raise ProtectedIntegrityError("proof_must_be_mapping")
    if proof.get("scene_id") != scene_id:
        raise ProtectedIntegrityError("proof_scene_id_mismatch")
    if str(proof.get("verdict") or "").upper() != "PASS":
        raise ProtectedIntegrityError("proof_not_pass")
    if not state["verification_runs"]:
        raise ProtectedIntegrityError("proof_batch_not_verified")
    pending_batch_ids, _, _, _, _ = _pending_application_declarations(state)
    if pending_batch_ids:
        raise ProtectedIntegrityError(
            f"proof_pending_application_batches:{pending_batch_ids!r}"
        )
    latest_run = state["verification_runs"][-1]
    proof_batch_ids = proof.get("verified_batch_ids")
    if (
        not isinstance(proof_batch_ids, list)
        or proof_batch_ids != latest_run["batch_ids"]
    ):
        raise ProtectedIntegrityError("proof_batch_not_verified")

    applied_path = (
        root / "pipeline" / f"scene_{scene_id}" / "patch_directive.applied.yaml"
    )
    if applied_path.exists():
        try:
            applied_document = yaml.safe_load(
                applied_path.read_text(encoding="utf-8")
            ) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ProtectedIntegrityError(
                f"proof_applied_directive_invalid:{exc}"
            ) from exc
        if not isinstance(applied_document, Mapping):
            raise ProtectedIntegrityError("proof_applied_directive_invalid")
        application_id = (
            applied_document.get("application_id")
            or applied_document.get("review_round")
        )
        if not isinstance(application_id, str) or not application_id.strip():
            raise ProtectedIntegrityError("proof_applied_directive_application_id_missing")
        directive_sha = _canonical_sha(dict(applied_document))
        matching_batches = [
            batch
            for batch in state["application_batches"]
            if batch["round_id"] == application_id.strip()
            and batch["directive_sha"] == directive_sha
        ]
        # A later distribution-only verification may legitimately be the
        # latest proof run while the applied patch belongs to an earlier,
        # already verified application batch.  Keep the directive identity
        # check exact and require that batch to exist in the append-only
        # verified history; it need not be re-applied in the latest run.
        if (
            len(matching_batches) != 1
            or matching_batches[0]["batch_id"] not in state["verified_batch_ids"]
        ):
            raise ProtectedIntegrityError("proof_applied_directive_batch_mismatch")

    scene_path = root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    try:
        scene_text = scene_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProtectedIntegrityError(f"proof_scene_invalid:{exc}") from exc
    current_sha = scene_sha256(scene_text)
    if proof.get("scene_sha") != current_sha or latest_run["scene_sha"] != current_sha:
        raise ProtectedIntegrityError("proof_scene_sha_mismatch")
    expected_review = _expected_post_revision_review_path(root, scene_id)
    raw_review_path = proof.get("review_path")
    if not isinstance(raw_review_path, str) or not raw_review_path:
        raise ProtectedIntegrityError("proof_review_path_invalid")
    candidate_review = Path(raw_review_path)
    if not candidate_review.is_absolute():
        candidate_review = root / candidate_review
    if candidate_review.resolve() != expected_review:
        raise ProtectedIntegrityError("proof_review_path_unexpected")
    if Path(latest_run["review_path"]).resolve() != expected_review:
        raise ProtectedIntegrityError("proof_sidecar_review_path_unexpected")

    raw_token_records = proof.get("token_verifications")
    raw_relation_records = proof.get("relation_verifications")
    if not isinstance(raw_token_records, list) or not isinstance(raw_relation_records, list):
        raise ProtectedIntegrityError("proof_records_must_be_lists")
    token_records = [
        _validate_token_record_shape(record, index)
        for index, record in enumerate(raw_token_records)
    ]
    relation_records = [
        _validate_relation_record_against_scene(record, index, scene_text)
        for index, record in enumerate(raw_relation_records)
    ]
    token_hashes = [_canonical_sha(item) for item in token_records]
    relation_hashes = [_canonical_sha(item) for item in relation_records]
    if token_hashes != latest_run["token_record_shas"]:
        raise ProtectedIntegrityError("proof_token_records_sidecar_mismatch")
    if relation_hashes != latest_run["relation_record_shas"]:
        raise ProtectedIntegrityError("proof_relation_records_sidecar_mismatch")
    sidecar_token_hashes = {item["record_sha"] for item in state["token_verifications"]}
    sidecar_relation_hashes = {
        item["record_sha"] for item in state["relation_verifications"]
    }
    if not set(token_hashes).issubset(sidecar_token_hashes):
        raise ProtectedIntegrityError("proof_token_records_missing_from_sidecar")
    if not set(relation_hashes).issubset(sidecar_relation_hashes):
        raise ProtectedIntegrityError("proof_relation_records_missing_from_sidecar")

    tokens, relations = _flatten_scene_declarations(state)
    token_keys = _verification_keys(
        token_records, "token_id", "token", allow_duplicates=False
    )
    declared_token_keys = {(item["patch_id"], item["token_id"]) for item in tokens}
    if token_keys != declared_token_keys:
        raise ProtectedIntegrityError("proof_token_record_set_mismatch")
    for index, record in enumerate(token_records):
        span = record["current_span"]
        if (
            record["scene_sha"] != current_sha
            or scene_text[span["start"]:span["end"]] != record["matched_form"]
        ):
            raise ProtectedIntegrityError(
                f"proof_token_verifications[{index}]:current_scene_mismatch"
            )

    _, _, relation_scopes, batch_patch_ids = _batch_declarations(
        state, proof_batch_ids
    )
    summary_path = root / "pipeline" / f"scene_{scene_id}" / "revision_summary.md"
    applied_patch_ids: set[str] = set()
    not_applied_patch_ids: set[str] = set()
    if summary_path.exists():
        try:
            summary_text = summary_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProtectedIntegrityError(f"proof_revision_summary_invalid:{exc}") from exc
        _, applied_patch_ids, not_applied_patch_ids = _revision_summary_patch_details(
            summary_text, scene_text
        )
    required_relation_keys, not_applied_relation_keys = _required_relation_record_keys(
        relation_scopes,
        batch_patch_ids,
        applied_patch_ids,
        not_applied_patch_ids,
    )
    proof_relation_keys = _verification_keys(
        relation_records, "relation_id", "relation", allow_duplicates=False
    )
    if proof_relation_keys != required_relation_keys:
        if required_relation_keys - proof_relation_keys:
            raise ProtectedIntegrityError(
                "applied_relation_missing_verification:"
                f"{sorted(required_relation_keys - proof_relation_keys)!r}"
            )
        if proof_relation_keys & not_applied_relation_keys:
            raise ProtectedIntegrityError(
                "not_applied_relation_has_verification:"
                f"{sorted(proof_relation_keys & not_applied_relation_keys)!r}"
            )
        raise ProtectedIntegrityError("proof_relation_record_set_mismatch")
    if any(item["reason"] == "declaration_before_quote_seed" for item in relation_records):
        raise ProtectedIntegrityError("applied_relation_uses_declaration_seed")
    if any(item["preserved"] is not True for item in relation_records):
        raise ProtectedIntegrityError("relation_verification_not_preserved")

    live = audit_scene_revision_integrity(root, scene_id, scene_text, scene_text)
    if live.get("verdict") != "PASS":
        raise ProtectedIntegrityError(
            f"proof_live_integrity_failed:{live.get('reason', 'unknown')}"
        )
    return copy.deepcopy(dict(proof))


def verify_post_revision_review(
    work_dir: Path | str,
    scene_id: str,
    *,
    review_path: Path | str | None = None,
) -> tuple[int, dict]:
    """Consume a post-revision review, verify literals, and advance anchors."""
    root = Path(work_dir)
    output_path = (
        root
        / "pipeline"
        / "review"
        / f"{scene_id}.protected_integrity.post_revision.yaml"
    )
    report: dict = {
        "scene_id": scene_id,
        "verdict": "FAIL",
        "literal_results": [],
        "relation_verifications": [],
        "active_relations": [],
    }
    try:
        initial_state = load_scene_integrity(root, scene_id)
        tokens, relations = scene_declarations(root, scene_id)
        if not tokens and not relations and not initial_state["application_batches"]:
            report.update({"verdict": "PASS", "compatibility": "no_declarations"})
            _atomic_write_yaml(output_path, report)
            return 0, report

        selected_review = (
            Path(review_path)
            if review_path is not None
            else root / "pipeline" / "review" / f"scene_{scene_id}.post_revision.yaml"
        )
        if not selected_review.is_absolute():
            selected_review = root / selected_review
        selected_review = selected_review.resolve()
        if selected_review != _expected_post_revision_review_path(root, scene_id):
            raise ProtectedIntegrityError("post_revision_review_path_unexpected")
        try:
            review = yaml.safe_load(selected_review.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ProtectedIntegrityError(f"post_revision_review_invalid:{exc}") from exc
        if not isinstance(review, Mapping):
            raise ProtectedIntegrityError("post_revision_review_must_be_mapping")
        if str(review.get("verdict") or "").upper() != "PASS":
            raise ProtectedIntegrityError("post_revision_review_not_pass")

        scene_path = root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
        try:
            scene_text = scene_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProtectedIntegrityError(f"scene_text_invalid:{exc}") from exc
        _ensure_post_rewrite_batch(root, scene_id, scene_text)
        state_before = load_scene_integrity(root, scene_id)
        (
            pending_batch_ids,
            current_batch_tokens,
            current_batch_relations,
            current_relation_scopes,
            current_batch_patch_ids,
        ) = _pending_application_declarations(state_before)

        raw_gate = review.get("protected_integrity_gate")
        if current_relation_scopes:
            if not isinstance(raw_gate, Mapping) or raw_gate.get("evaluated") is not True:
                raise ProtectedIntegrityError("protected_integrity_gate_not_evaluated")
            if raw_gate.get("gate_pass") is not True:
                raise ProtectedIntegrityError("protected_integrity_gate_failed")
            if str(raw_gate.get("literal_gate") or "").lower() != "pass":
                raise ProtectedIntegrityError("protected_literal_gate_not_pass")
            if raw_gate.get("relation_review_required") is not True:
                raise ProtectedIntegrityError("relation_review_required_mismatch")
            gate: Mapping = raw_gate
        else:
            # Literal-only declarations preserve the existing script fastpath.
            # The script is the authority for token verification and therefore
            # does not require reviewer-authored protected gate fields.
            if raw_gate is None:
                gate = {}
            elif not isinstance(raw_gate, Mapping):
                raise ProtectedIntegrityError("protected_integrity_gate_must_be_mapping")
            else:
                gate = raw_gate
                if "gate_pass" in gate and gate.get("gate_pass") is not True:
                    raise ProtectedIntegrityError("protected_integrity_gate_failed")
                if "literal_gate" in gate and str(gate.get("literal_gate")).lower() != "pass":
                    raise ProtectedIntegrityError("protected_literal_gate_not_pass")
                if gate.get("relation_review_required") not in {None, False}:
                    raise ProtectedIntegrityError("relation_review_required_mismatch")
        summary_path = root / "pipeline" / f"scene_{scene_id}" / "revision_summary.md"
        summary_text: str | None = None
        if summary_path.exists():
            try:
                summary_text = summary_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ProtectedIntegrityError(f"revision_summary_invalid:{exc}") from exc
        patch_spans: dict[str, dict[str, int]] = {}
        applied_patch_ids: set[str] = set()
        not_applied_patch_ids: set[str] = set()
        if summary_text is not None:
            (
                patch_spans,
                applied_patch_ids,
                not_applied_patch_ids,
            ) = _revision_summary_patch_details(summary_text, scene_text)

        current_token_keys = {
            (token["patch_id"], token["token_id"])
            for token in current_batch_tokens
        }
        existing_token_keys = {
            (record.get("patch_id"), record.get("token_id"))
            for record in state_before["token_verifications"]
            if isinstance(record, Mapping)
        }
        pending_spans: dict[str, dict[str, int]] | None = None
        direct_tokens: list[dict] = []
        reuse_tokens: list[dict] = []
        direct_patch_spans = dict(patch_spans)
        for token in tokens:
            key = (token["patch_id"], token["token_id"])
            if key in current_token_keys and token["patch_id"] in applied_patch_ids:
                if token["scope"] == "patch_span" and token["patch_id"] not in patch_spans:
                    raise ProtectedIntegrityError(
                        f"applied_new_span_missing:{token['patch_id']}"
                    )
                direct_tokens.append(token)
                continue
            if key in existing_token_keys:
                reuse_tokens.append(token)
                continue
            if token["scope"] == "scene":
                direct_tokens.append(token)
                continue
            if token["patch_id"] in not_applied_patch_ids:
                if pending_spans is None:
                    pending_spans = _pending_patch_regions(root, scene_id, scene_text)
                span = pending_spans.get(token["patch_id"])
                if span is not None:
                    direct_patch_spans[token["patch_id"]] = span
                    direct_tokens.append(token)
                    continue
            raise ProtectedIntegrityError(
                f"applied_new_span_missing:{token['patch_id']};"
                f"active_token_verification_missing:{key!r}"
            )

        direct_results = verify_literal_tokens(
            scene_text,
            direct_tokens,
            patch_spans=direct_patch_spans,
        )
        reuse_keys = {(item["patch_id"], item["token_id"]) for item in reuse_tokens}
        reuse_records = [
            record
            for record in state_before["token_verifications"]
            if (record.get("patch_id"), record.get("token_id")) in reuse_keys
        ]
        reuse_anchors = derive_active_token_anchors(
            reuse_tokens,
            reuse_records,
            scene_text,
        )
        reuse_by_key = {
            (anchor["patch_id"], anchor["token_id"]): anchor
            for anchor in reuse_anchors
        }
        direct_by_key = {
            (result["patch_id"], result["token_id"]): result
            for result in direct_results
        }
        token_by_key = {
            (token["patch_id"], token["token_id"]): token for token in tokens
        }
        literal_results: list[dict] = []
        for key in token_by_key:
            if key in direct_by_key:
                literal_results.append(direct_by_key[key])
                continue
            anchor = reuse_by_key[key]
            literal_results.append({
                "patch_id": key[0],
                "token_id": key[1],
                "found": True,
                "matched_form": anchor["matched_form"],
                "region": {
                    "scope": token_by_key[key]["scope"],
                    **anchor["current_span"],
                },
            })
        validate_verification_coverage(tokens, [], literal_results, [])
        report["literal_results"] = literal_results
        token_records = _token_records_from_results(scene_text, tokens, literal_results)

        records = gate.get("relation_verifications", [])
        if not isinstance(records, list):
            raise ProtectedIntegrityError("relation_verifications_must_be_list")
        required_relation_keys, not_applied_relation_keys = _required_relation_record_keys(
            current_relation_scopes,
            current_batch_patch_ids,
            applied_patch_ids,
            not_applied_patch_ids,
        )
        record_keys = _verification_keys(
            records,
            "relation_id",
            "relation",
            allow_duplicates=False,
        )
        if record_keys != required_relation_keys:
            missing = required_relation_keys - record_keys
            if missing:
                raise ProtectedIntegrityError(
                    f"applied_relation_missing_verification:{sorted(missing)!r}"
                )
            not_applied_records = record_keys & not_applied_relation_keys
            if not_applied_records:
                raise ProtectedIntegrityError(
                    "not_applied_relation_has_verification:"
                    f"{sorted(not_applied_records)!r}"
                )
            raise ProtectedIntegrityError(
                f"undeclared_current_relation_verification:{sorted(record_keys)!r}"
            )
        if any(record.get("preserved") is not True for record in records):
            raise ProtectedIntegrityError("relation_verification_not_preserved")
        if any(
            record.get("reason") == "declaration_before_quote_seed"
            for record in records
        ):
            raise ProtectedIntegrityError("applied_relation_uses_declaration_seed")
        for index, record in enumerate(records):
            _validate_relation_record_against_scene(record, index, scene_text)

        # Validate token record shape and occurrence before any append-only
        # artifact is advanced.
        current_sha = scene_sha256(scene_text)
        for index, record in enumerate(token_records):
            normalized = _validate_token_record_shape(record, index)
            span = normalized["current_span"]
            if normalized["scene_sha"] != current_sha or scene_text[
                span["start"]:span["end"]
            ] != normalized["matched_form"]:
                raise ProtectedIntegrityError(
                    f"token_verifications[{index}]:current_scene_mismatch"
                )

        # append_relation_verifications rechecks scene hash, quote uniqueness,
        # exact current span, declaration identity, and append-only integrity.
        if tokens:
            append_token_verifications(root, scene_id, scene_text, token_records)
        if records:
            append_relation_verifications(root, scene_id, scene_text, records)
        state = load_scene_integrity(root, scene_id)
        active = derive_active_relation_anchors(
            relations,
            state["relation_verifications"],
            scene_text,
        )
        report.update({
            "verdict": "PASS",
            "token_verifications": token_records,
            "relation_verifications": copy.deepcopy(records),
            "active_relations": active,
            "scene_sha": scene_sha256(scene_text),
            "review_path": str(selected_review),
            "verified_batch_ids": list(pending_batch_ids),
        })
        # A PASS file without the matching sidecar run remains inadmissible.  The
        # ordering also leaves a retryable pending batch if the sidecar write is
        # interrupted.
        _atomic_write_yaml(output_path, report)
        _record_verification_run(
            root,
            scene_id,
            batch_ids=pending_batch_ids,
            scene_sha=report["scene_sha"],
            review_path=report["review_path"],
            token_records=token_records,
            relation_records=records,
        )
        validate_post_revision_proof(root, scene_id, report)
        return 0, report
    except (OSError, ProtectedIntegrityError) as exc:
        report["reason"] = str(exc)
        _atomic_write_yaml(output_path, report)
        return 2, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    post_parser = subparsers.add_parser("verify-post-revision")
    post_parser.add_argument("--work-dir", type=Path, required=True)
    post_parser.add_argument("--scene-id", required=True)
    post_parser.add_argument("--review", type=Path)
    requires_parser = subparsers.add_parser("requires-review")
    requires_parser.add_argument("--work-dir", type=Path, required=True)
    requires_parser.add_argument("--scene-id", required=True)
    prepare_parser = subparsers.add_parser("prepare-post-rewrite")
    prepare_parser.add_argument("--work-dir", type=Path, required=True)
    prepare_parser.add_argument("--scene-id", required=True)
    args = parser.parse_args(argv)

    if args.command == "verify-post-revision":
        rc, report = verify_post_revision_review(
            args.work_dir.resolve(),
            args.scene_id,
            review_path=args.review,
        )
        print(
            f"{report['verdict']} protected_integrity "
            f"scene={args.scene_id} stage=post_revision"
        )
        if report.get("reason"):
            print(report["reason"], file=sys.stderr)
        return rc
    if args.command == "requires-review":
        try:
            required = has_pending_relation_declarations(
                args.work_dir.resolve(), args.scene_id
            )
        except (OSError, ProtectedIntegrityError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("true" if required else "false")
        return 0 if required else 1
    if args.command == "prepare-post-rewrite":
        try:
            prepared = prepare_post_rewrite_application(
                args.work_dir.resolve(), args.scene_id
            )
        except (OSError, ProtectedIntegrityError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("prepared" if prepared else "not_required")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
