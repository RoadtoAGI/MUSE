#!/usr/bin/env python3
"""Prepare, ingest, verify, and index source-backed rhetoric occurrences.

The script deliberately makes no LLM calls. The prepare command freezes one
source edition and emits two review lanes:

* explicit cue tasks for high-recall comparison markers;
* non-overlapping semantic chunks covering every selected body line.

Slice turns the frozen parent package into bounded annotation views while
preserving its task IDs and digest. An agent reviews those views outside this
script. Ingest validates the returned dispositions and evidence before writing
a transactional per-work YAML snapshot. Verify rechecks the frozen source and
manifest enrollment. Index rebuilds the derived global consumer index from
verified work cards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_KB_ROOT = Path(__file__).resolve().parents[1]
CONTAINERS = {"novels": "novel", "dramas": "drama"}
COMPARISON_FIGURES = frozenset({"simile", "metaphor", "analogy"})
NONCOMPARISON_FIGURES = frozenset(
    {
        "personification",
        "synesthesia",
        "hyperbole",
        "parallelism",
        "repetition",
        "contrast",
        "irony",
        "pun",
        "symbol",
        "metonymy",
        "rhetorical_question",
        "apostrophe",
        "allusion",
        "euphemism",
        "paradox",
        "oxymoron",
        "gradation",
        "synecdoche",
    }
)
FIGURE_TYPES = (
    "simile",
    "metaphor",
    "analogy",
    "personification",
    "synesthesia",
    "hyperbole",
    "parallelism",
    "repetition",
    "contrast",
    "irony",
    "pun",
    "symbol",
    "metonymy",
    "rhetorical_question",
    "apostrophe",
    "allusion",
    "euphemism",
    "paradox",
    "oxymoron",
    "gradation",
    "synecdoche",
)
QUALITY_ASSESSMENTS = frozenset(
    {"exemplary", "effective", "functional", "conventional", "strained"}
)
UNRESOLVED_STATUSES = frozenset(
    {"", "unresolved", "pending", "needs_review", "unknown", "todo"}
)
OCCURRENCE_SCHEMA = "rhetoric-occurrence/v1"
COVERAGE_SCHEMA = "rhetoric-coverage/v1"
TASK_SCHEMA = "rhetoric-task-package/v1"
TASK_SHARD_SCHEMA = "rhetoric-task-shard/v1"
SHARD_MANIFEST_SCHEMA = "rhetoric-task-shard-manifest/v1"
OUTPUT_SCHEMA = "rhetoric-agent-output/v1"
MAX_QUOTE_CHARS = 120
DEFAULT_CHUNK_CHARS = 8000
DEFAULT_SHARD_CHARS = 40000
DEFAULT_SHARD_TASKS = 40

LOCATOR_RE = re.compile(r"^(?P<path>.+):L(?P<start>\d+)(?:-L?(?P<end>\d+))?$")
CHINESE_HEADING_RE = re.compile(
    r"^(?:第[〇零一二三四五六七八九十百千万两0-9]+[部章节卷篇回])(?:\s.*)?$"
)

# Long/specific forms precede their substrings. False positives are expected:
# every hit still requires an explicit include/exclude disposition.
CUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("仿佛", re.compile(r"仿佛")),
    ("如同", re.compile(r"如同")),
    ("犹如", re.compile(r"犹如")),
    ("宛如", re.compile(r"宛如")),
    ("好似", re.compile(r"好似")),
    ("好像", re.compile(r"好像")),
    ("宛若", re.compile(r"宛若")),
    ("仿若", re.compile(r"仿若")),
    ("恰似", re.compile(r"恰似")),
    ("有如", re.compile(r"有如")),
    ("譬如", re.compile(r"譬如")),
    ("似…般", re.compile(r"似[^，。！？；\n]*般")),
    ("似的", re.compile(r"似的")),
    ("一般", re.compile(r"一般")),
    ("一样", re.compile(r"一样")),
    ("像", re.compile(r"像")),
    (
        "如",
        re.compile(
            r"(?<!譬)如(?!果|今|何|是|此|实|常|期|意|愿|下|上|同|犹|约|数|来|前|后|初|若)"
        ),
    ),
)

COMMON_ANALYSIS_FIELDS = (
    "sensory_mapping",
    "context_fact",
    "image_mechanism",
    "property_alignment",
    "context_alignment",
    "narrative_function",
    "transfer_rule",
    "failure_boundary",
)
COMMON_CANDIDATE_FIELDS = (
    "source_locator",
    "chapter",
    "figure_type",
    "quote",
    *COMMON_ANALYSIS_FIELDS,
    "quality_assessment",
    "confidence",
    "review_status",
)
GENERATED_FIELDS = (
    "schema_version",
    "occurrence_id",
    "work_id",
    "edition_id",
    "source_file",
    "source_sha256",
)


class RhetoricError(ValueError):
    """Raised when a task package or evidence payload violates the contract."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RhetoricError(f"{path}: JSON root must be an object")
    return value


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RhetoricError(f"{path}: YAML root must be a mapping")
    return value


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    )


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        yaml.safe_dump(dict(value), allow_unicode=True, sort_keys=False, width=120),
    )


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(*parts: object, length: int = 20) -> str:
    serialized = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:length]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(
            isinstance(key, str) and bool(key.strip()) and _contains_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_content(item) for item in value)
    return value is not None


def _work_dir(kb_root: Path, container: str, work: str) -> Path:
    if container not in CONTAINERS:
        raise RhetoricError(f"invalid container: {container}")
    root = kb_root.resolve()
    container_dir = (root / container).resolve()
    candidate = (container_dir / work).resolve()
    if candidate.parent != container_dir:
        raise RhetoricError("work must name one direct child of its container")
    if not candidate.is_dir():
        raise RhetoricError(f"work directory not found: {candidate}")
    return candidate


def _source_path(work_dir: Path, source: str | Path) -> tuple[Path, str]:
    raw = Path(source)
    candidate = raw.resolve() if raw.is_absolute() else (work_dir / raw).resolve()
    try:
        relative = candidate.relative_to(work_dir.resolve())
    except ValueError as exc:
        raise RhetoricError("source must stay inside the selected work directory") from exc
    if not candidate.is_file():
        raise RhetoricError(f"source file not found: {candidate}")
    return candidate, relative.as_posix()


def _work_id(container: str, work: str) -> str:
    return f"{CONTAINERS[container]}:{work}"


def expand_figure_scope(values: Iterable[str]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(part.strip() for part in str(value).split(",") if part.strip())
    if not tokens:
        raise RhetoricError("figure_scope must not be empty")
    expanded: set[str] = set()
    for token in tokens:
        if token == "all":
            expanded.update(FIGURE_TYPES)
        elif token == "comparison":
            expanded.update(COMPARISON_FIGURES)
        elif token in FIGURE_TYPES:
            expanded.add(token)
        else:
            raise RhetoricError(f"invalid figure scope: {token}")
    return [figure for figure in FIGURE_TYPES if figure in expanded]


def _resolve_scope_locator(kb_root: Path, raw_scope_file: str | Path) -> tuple[Path, str]:
    root = Path(kb_root).resolve()
    raw = Path(raw_scope_file)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        if ".." in raw.parts:
            raise RhetoricError("scope manifest locator must not escape kb_root")
        path = (root / raw).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RhetoricError("scope manifest locator must stay inside kb_root") from exc
    if not path.is_file():
        raise RhetoricError(f"scope manifest not found: {path}")
    try:
        locator = path.relative_to(root).as_posix()
    except ValueError:
        locator = str(path)
    return path, locator


def _read_scope_manifest(
    kb_root: Path,
    scope_file: str | Path,
) -> tuple[Path, str, str, dict[str, Any]]:
    path, locator = _resolve_scope_locator(kb_root, scope_file)
    manifest = _read_yaml(path)
    if manifest.get("status") != "frozen" or not isinstance(manifest.get("corpus"), list):
        raise RhetoricError("scope manifest must be frozen and contain a corpus list")
    return path, locator, _sha256_path(path), manifest


def _load_scope_enrollment(
    kb_root: Path,
    scope_file: str | Path,
) -> tuple[str, str, list[dict[str, Any]]]:
    _path, locator, digest, manifest = _read_scope_manifest(kb_root, scope_file)
    corpus = manifest["corpus"]
    if not corpus:
        raise RhetoricError("rhetoric corpus enrollment is empty")
    seen: set[tuple[str, str]] = set()
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(corpus):
        if not isinstance(raw_entry, dict):
            raise RhetoricError(f"scope manifest corpus[{index}] must be a mapping")
        container = raw_entry.get("container")
        work = raw_entry.get("work")
        source_file = raw_entry.get("source_file")
        source_sha256 = raw_entry.get("source_sha256")
        start_line = raw_entry.get("start_line")
        end_line = raw_entry.get("end_line")
        if container not in CONTAINERS:
            raise RhetoricError(f"scope manifest corpus[{index}] has invalid container")
        if not _nonempty_string(work) or not _nonempty_string(source_file):
            raise RhetoricError(f"scope manifest corpus[{index}] missing work/source_file")
        if not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
            raise RhetoricError(f"scope manifest corpus[{index}] has invalid source_sha256")
        if (
            not isinstance(start_line, int)
            or isinstance(start_line, bool)
            or not isinstance(end_line, int)
            or isinstance(end_line, bool)
            or start_line < 1
            or end_line < start_line
        ):
            raise RhetoricError(f"scope manifest corpus[{index}] has invalid body range")
        key = (str(container), str(work))
        if key in seen:
            raise RhetoricError(
                f"scope manifest contains duplicate enrollment: {container}/{work}"
            )
        seen.add(key)
        entries.append(dict(raw_entry))
    return locator, digest, entries


def _load_scope_binding(
    kb_root: Path,
    scope_file: str | Path,
    *,
    container: str,
    work: str,
    source_path: Path,
    source_file: str,
    source_sha256: str,
    body_start: int,
    body_end: int,
) -> dict[str, Any]:
    locator, digest, entries = _load_scope_enrollment(kb_root, scope_file)
    matches = [
        item
        for item in entries
        if isinstance(item, dict)
        and item.get("container") == container
        and item.get("work") == work
    ]
    if len(matches) != 1:
        raise RhetoricError(
            f"scope manifest must contain exactly one entry for {container}/{work}"
        )
    entry = matches[0]
    entry_source = entry.get("source_file")
    if not _nonempty_string(entry_source):
        raise RhetoricError("scope manifest entry missing source_file")
    normalized_entry = str(entry_source).replace("\\", "/").removeprefix("./")
    kb_relative = f"{container}/{work}/{source_file}"
    accepted_relative = {
        source_file,
        kb_relative,
        f"knowledge-base/{kb_relative}",
        f"MUSE-canon-distill/knowledge-base/{kb_relative}",
        f"skills/MUSE-canon-distill/knowledge-base/{kb_relative}",
    }
    absolute_match = False
    if Path(str(entry_source)).is_absolute():
        absolute_match = Path(str(entry_source)).resolve() == source_path.resolve()
    if normalized_entry not in accepted_relative and not absolute_match:
        raise RhetoricError("scope manifest source_file mismatch")
    if entry.get("source_sha256") != source_sha256:
        raise RhetoricError("scope manifest source checksum mismatch")
    if entry.get("start_line") != body_start or entry.get("end_line") != body_end:
        raise RhetoricError(
            "scope manifest body boundary mismatch: "
            f"expected L{entry.get('start_line')}-L{entry.get('end_line')}, "
            f"got L{body_start}-L{body_end}"
        )
    return {
        "scope_file": locator,
        "scope_file_sha256": digest,
        "scope_entry": dict(entry),
    }


def _heading_title(line: str) -> str | None:
    stripped = line.strip()
    markdown = re.match(r"^#{1,6}\s+(.+?)\s*$", stripped)
    if markdown:
        return markdown.group(1).strip()
    if CHINESE_HEADING_RE.fullmatch(stripped):
        return stripped
    if len(stripped) >= 3 and stripped.startswith("【") and stripped.endswith("】"):
        return stripped
    bold = re.fullmatch(r"\*\*(.+?)\*\*", stripped)
    if bold:
        return bold.group(1).strip()
    return None


def _chapter_labels(lines: list[str]) -> list[str]:
    labels: list[str] = []
    current = "正文"
    for line in lines:
        title = _heading_title(line)
        if title:
            current = title
        labels.append(current)
    return labels


def _cue_terms(line: str) -> list[str]:
    return [label for label, pattern in CUE_PATTERNS if pattern.search(line)]


def _locator(source_file: str, start: int, end: int) -> str:
    return f"{source_file}:L{start}" if start == end else f"{source_file}:L{start}-L{end}"


def _task_id(
    kind: str,
    *,
    work_id: str,
    edition_id: str,
    source_sha256: str,
    source_locator: str,
    figure_scope: list[str],
    cue_line: int | None = None,
) -> str:
    prefix = "rt-exp" if kind == "explicit_cue" else "rt-sem"
    digest = _stable_hash(
        kind,
        work_id,
        edition_id,
        source_sha256,
        source_locator,
        figure_scope,
        cue_line,
    )
    return f"{prefix}-{digest}"


def prepare_package(
    kb_root: Path,
    *,
    container: str,
    work: str,
    source: str | Path,
    body_start: int,
    body_end: int,
    figure_scope: Iterable[str],
    chunk_lines: int = 120,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    edition_id: str = "current",
    scope_file: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic, source-frozen two-lane review task package."""

    work_dir = _work_dir(kb_root, container, work)
    source_path, source_file = _source_path(work_dir, source)
    lines = source_path.read_text(encoding="utf-8").splitlines()
    if not _nonempty_string(edition_id):
        raise RhetoricError("edition_id must be a non-empty string")
    if not isinstance(chunk_lines, int) or isinstance(chunk_lines, bool) or chunk_lines < 1:
        raise RhetoricError("chunk_lines must be a positive integer")
    if not isinstance(chunk_chars, int) or isinstance(chunk_chars, bool) or chunk_chars < 1:
        raise RhetoricError("chunk_chars must be a positive integer")
    if body_start < 1 or body_end < body_start or body_end > len(lines):
        raise RhetoricError(
            f"invalid body range L{body_start}-L{body_end}; source has {len(lines)} lines"
        )

    scope = expand_figure_scope(figure_scope)
    source_digest = _sha256_path(source_path)
    scope_binding = (
        _load_scope_binding(
            kb_root,
            scope_file,
            container=container,
            work=work,
            source_path=source_path,
            source_file=source_file,
            source_sha256=source_digest,
            body_start=body_start,
            body_end=body_end,
        )
        if scope_file is not None
        else {
            "scope_file": None,
            "scope_file_sha256": None,
            "scope_entry": None,
        }
    )
    wid = _work_id(container, work)
    chapters = _chapter_labels(lines)

    semantic_tasks: list[dict[str, Any]] = []
    cursor = body_start
    while cursor <= body_end:
        chapter = chapters[cursor - 1]
        chapter_end = cursor
        while chapter_end < body_end and chapters[chapter_end] == chapter:
            chapter_end += 1
        chunk_start = cursor
        while chunk_start <= chapter_end:
            chunk_end = chunk_start - 1
            chunk_text_chars = 0
            while chunk_end < chapter_end and chunk_end - chunk_start + 1 < chunk_lines:
                next_line = lines[chunk_end]
                added_chars = len(next_line) + (1 if chunk_end >= chunk_start else 0)
                if chunk_end >= chunk_start and chunk_text_chars + added_chars > chunk_chars:
                    break
                chunk_end += 1
                chunk_text_chars += added_chars
            locator = _locator(source_file, chunk_start, chunk_end)
            semantic_tasks.append(
                {
                    "task_id": _task_id(
                        "semantic_chunk",
                        work_id=wid,
                        edition_id=edition_id,
                        source_sha256=source_digest,
                        source_locator=locator,
                        figure_scope=scope,
                    ),
                    "task_type": "semantic_chunk",
                    "source_file": source_file,
                    "source_sha256": source_digest,
                    "source_locator": locator,
                    "start_line": chunk_start,
                    "end_line": chunk_end,
                    "chapter": chapter,
                    "text": "\n".join(lines[chunk_start - 1 : chunk_end]),
                }
            )
            chunk_start = chunk_end + 1
        cursor = chapter_end + 1

    explicit_tasks: list[dict[str, Any]] = []
    if COMPARISON_FIGURES.intersection(scope):
        for line_number in range(body_start, body_end + 1):
            terms = _cue_terms(lines[line_number - 1])
            if not terms:
                continue
            chapter = chapters[line_number - 1]
            context_start = line_number
            if line_number > body_start and chapters[line_number - 2] == chapter:
                context_start -= 1
            context_end = line_number
            if line_number < body_end and chapters[line_number] == chapter:
                context_end += 1
            locator = _locator(source_file, context_start, context_end)
            explicit_tasks.append(
                {
                    "task_id": _task_id(
                        "explicit_cue",
                        work_id=wid,
                        edition_id=edition_id,
                        source_sha256=source_digest,
                        source_locator=locator,
                        figure_scope=scope,
                        cue_line=line_number,
                    ),
                    "task_type": "explicit_cue",
                    "source_file": source_file,
                    "source_sha256": source_digest,
                    "source_locator": locator,
                    "start_line": context_start,
                    "end_line": context_end,
                    "cue_line": line_number,
                    "cue_terms": terms,
                    "chapter": chapter,
                    "text": lines[line_number - 1],
                }
            )

    return {
        "schema_version": TASK_SCHEMA,
        "work_id": wid,
        "container": container,
        "work": work,
        "edition_id": edition_id,
        "figure_scope": scope,
        "source": {
            "file": source_file,
            "sha256": source_digest,
            "line_count": len(lines),
            "body_start": body_start,
            "body_end": body_end,
        },
        "chunk_lines": chunk_lines,
        "chunk_chars": chunk_chars,
        "cue_lexicon_version": "zh-comparison-cues/v1",
        **scope_binding,
        "instructions": {
            "completeness": (
                "逐项处置 explicit_tasks，并逐块复核 semantic_tasks；收录常规、勉强和优秀实例，"
                "quality_assessment 负责分级，不得只挑好例子。"
            ),
            "explicit_lane": "每项 disposition 取 include/exclude；include 给 occurrences，exclude 可给 reason。",
            "semantic_lane": "每块 reviewed 必须为 true；discoveries 可为空，只填显式任务未收录的新发现。",
            "quote_policy": (
                f"locator 可覆盖完整修辞跨度；quote 只摘 locator 内的连续短证据，"
                f"去空白后不超过 {MAX_QUOTE_CHARS} 字且最多两行。"
            ),
            "conditional_schema": (
                "simile/metaphor/analogy 必填 tenor/vehicle/ground；其他 figure_type 必填非空 "
                "device_elements 对象，可省略三要素。"
            ),
        },
        "output_contract": {
            "schema_version": OUTPUT_SCHEMA,
            "task_package_sha256": "<本任务包文件的 sha256>",
            "partial_outputs": (
                "可把任务结果拆成多份同 schema/digest 的 JSON；每个 task_id 只能出现一次，"
                "ingest 时重复传 --output，联合后必须恰好覆盖全部任务。"
            ),
            "explicit_results": [
                {
                    "task_id": "<explicit task_id>",
                    "disposition": "include|exclude",
                    "reason": "<exclude 可填>",
                    "occurrences": ["<occurrence candidate>"],
                }
            ],
            "semantic_results": [
                {
                    "task_id": "<semantic task_id>",
                    "reviewed": True,
                    "discoveries": ["<occurrence candidate>"],
                }
            ],
            "occurrence_candidate_common_fields": [
                *COMMON_CANDIDATE_FIELDS,
                "quality_assessment: exemplary|effective|functional|conventional|strained",
            ],
            "comparison_fields": ["tenor", "vehicle", "ground"],
            "noncomparison_field": "device_elements",
        },
        "explicit_tasks": explicit_tasks,
        "semantic_tasks": semantic_tasks,
    }


def _parse_locator(locator: str) -> tuple[str, int, int] | None:
    match = LOCATOR_RE.fullmatch(locator)
    if not match:
        return None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if start < 1 or end < start:
        return None
    return match.group("path"), start, end


def _locator_window(work_dir: Path, locator: str) -> tuple[Path, int, int, str] | None:
    parsed = _parse_locator(locator)
    if parsed is None:
        return None
    relative, start, end = parsed
    candidate = (work_dir / relative).resolve()
    try:
        candidate.relative_to(work_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    lines = candidate.read_text(encoding="utf-8").splitlines()
    if end > len(lines):
        return None
    return candidate, start, end, "\n".join(lines[start - 1 : end])


def _validate_task_package(package: dict[str, Any], kb_root: Path) -> tuple[Path, Path, list[str]]:
    if package.get("schema_version") != TASK_SCHEMA:
        raise RhetoricError("invalid task package schema_version")
    container = package.get("container")
    work = package.get("work")
    if not _nonempty_string(container) or not _nonempty_string(work):
        raise RhetoricError("task package missing container/work")
    work_dir = _work_dir(kb_root, str(container), str(work))
    source = package.get("source")
    if not isinstance(source, dict) or not _nonempty_string(source.get("file")):
        raise RhetoricError("task package missing source metadata")
    source_path, source_file = _source_path(work_dir, str(source["file"]))
    if source_file != source["file"]:
        raise RhetoricError("task package source_file is not canonical")
    if _sha256_path(source_path) != source.get("sha256"):
        raise RhetoricError("source checksum mismatch")
    expected = prepare_package(
        kb_root,
        container=str(container),
        work=str(work),
        source=source_file,
        body_start=source.get("body_start"),
        body_end=source.get("body_end"),
        figure_scope=package.get("figure_scope") or [],
        chunk_lines=package.get("chunk_lines"),
        chunk_chars=package.get("chunk_chars", DEFAULT_CHUNK_CHARS),
        edition_id=package.get("edition_id"),
        scope_file=package.get("scope_file") or None,
    )
    for key in (
        "work_id",
        "container",
        "work",
        "edition_id",
        "figure_scope",
        "source",
        "chunk_lines",
        "chunk_chars",
        "cue_lexicon_version",
        "scope_file",
        "scope_file_sha256",
        "scope_entry",
        "instructions",
        "output_contract",
        "explicit_tasks",
        "semantic_tasks",
    ):
        if package.get(key) != expected.get(key):
            raise RhetoricError(f"task package {key} does not match frozen source")
    return work_dir, source_path, source_path.read_text(encoding="utf-8").splitlines()


def _serialized_chars(value: Mapping[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def slice_task_package(
    task_path: Path,
    out_dir: Path,
    *,
    kb_root: Path = DEFAULT_KB_ROOT,
    max_chars: int = DEFAULT_SHARD_CHARS,
    max_tasks: int = DEFAULT_SHARD_TASKS,
) -> dict[str, Any]:
    """Split a frozen parent task package into bounded, non-authoritative shards."""

    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise RhetoricError("max_chars must be a positive integer")
    if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or max_tasks < 1:
        raise RhetoricError("max_tasks must be a positive integer")
    task_path = Path(task_path)
    package = _read_json(task_path)
    _validate_task_package(package, Path(kb_root))
    parent_digest = _sha256_path(task_path)
    units: list[tuple[str, dict[str, Any], int]] = []
    for lane, key in (("explicit", "explicit_tasks"), ("semantic", "semantic_tasks")):
        for task in package[key]:
            size = _serialized_chars(task)
            if size > max_chars:
                raise RhetoricError(
                    f"task {task['task_id']} requires {size} chars, over max_chars={max_chars}; "
                    "raise the shard budget or prepare with a smaller --chunk-chars value"
                )
            units.append((lane, task, size))

    groups: list[list[tuple[str, dict[str, Any], int]]] = []
    current: list[tuple[str, dict[str, Any], int]] = []
    current_chars = 0
    for unit in units:
        size = unit[2]
        if current and (len(current) >= max_tasks or current_chars + size > max_chars):
            groups.append(current)
            current = []
            current_chars = 0
        current.append(unit)
        current_chars += size
    if current:
        groups.append(current)
    if not groups:
        raise RhetoricError("task package contains no review tasks")

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RhetoricError(f"shard output directory must be empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    shard_records: list[dict[str, Any]] = []
    shard_count = len(groups)
    for index, group in enumerate(groups, start=1):
        explicit = [task for lane, task, _size in group if lane == "explicit"]
        semantic = [task for lane, task, _size in group if lane == "semantic"]
        ordered_ids = [task["task_id"] for _lane, task, _size in group]
        payload_chars = sum(size for _lane, _task, size in group)
        shard_id = f"rt-shard-{_stable_hash(parent_digest, ordered_ids, length=24)}"
        file_name = f"shard-{index:04d}-of-{shard_count:04d}.json"
        output_contract = dict(package["output_contract"])
        output_contract["task_package_sha256"] = parent_digest
        shard = {
            "schema_version": TASK_SHARD_SCHEMA,
            "parent_task_package_sha256": parent_digest,
            "shard_id": shard_id,
            "shard_index": index,
            "shard_count": shard_count,
            "task_count": len(group),
            "task_payload_chars": payload_chars,
            "max_chars": max_chars,
            "max_tasks": max_tasks,
            "work_id": package["work_id"],
            "container": package["container"],
            "work": package["work"],
            "edition_id": package["edition_id"],
            "figure_scope": package["figure_scope"],
            "source": package["source"],
            "scope_file": package.get("scope_file"),
            "scope_file_sha256": package.get("scope_file_sha256"),
            "scope_entry": package.get("scope_entry"),
            "instructions": package["instructions"],
            "output_contract": output_contract,
            "explicit_tasks": explicit,
            "semantic_tasks": semantic,
        }
        _write_json(out_dir / file_name, shard)
        shard_records.append(
            {
                "file": file_name,
                "shard_id": shard_id,
                "task_count": len(group),
                "task_payload_chars": payload_chars,
                "task_ids": ordered_ids,
            }
        )
    manifest = {
        "schema_version": SHARD_MANIFEST_SCHEMA,
        "parent_task_package_sha256": parent_digest,
        "work_id": package["work_id"],
        "max_chars": max_chars,
        "max_tasks": max_tasks,
        "task_count": len(units),
        "shard_count": shard_count,
        "shards": shard_records,
    }
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


def _occurrence_id(document: Mapping[str, Any]) -> str:
    digest = _stable_hash(
        document.get("work_id"),
        document.get("edition_id"),
        document.get("source_file"),
        document.get("source_sha256"),
        document.get("source_locator"),
        document.get("figure_type"),
        _normalize_text(str(document.get("quote", ""))),
        length=24,
    )
    return f"rh-{digest}"


def _validate_candidate_strings(candidate: Mapping[str, Any]) -> None:
    missing = [
        field
        for field in ("source_locator", "chapter", "figure_type", "quote", *COMMON_ANALYSIS_FIELDS, "review_status")
        if not _nonempty_string(candidate.get(field))
    ]
    if missing:
        raise RhetoricError(f"occurrence missing required fields: {missing}")
    quote = str(candidate["quote"])
    if len(_normalize_text(quote)) > MAX_QUOTE_CHARS or len(quote.splitlines()) > 2:
        raise RhetoricError(f"quote exceeds short-evidence limit ({MAX_QUOTE_CHARS} chars, 2 lines)")
    quality = candidate.get("quality_assessment")
    if quality not in QUALITY_ASSESSMENTS:
        raise RhetoricError(f"invalid quality_assessment: {quality}")
    confidence = candidate.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise RhetoricError("confidence must be a number from 0 to 1")
    if str(candidate.get("review_status", "")).strip().lower() in UNRESOLVED_STATUSES:
        raise RhetoricError("review_status is unresolved")


def build_occurrence(
    candidate: Mapping[str, Any],
    *,
    package: Mapping[str, Any],
    task: Mapping[str, Any],
    work_dir: Path,
    source_lines: list[str],
) -> dict[str, Any]:
    """Validate one agent candidate and add deterministic source metadata."""

    if not isinstance(candidate, Mapping):
        raise RhetoricError("occurrence candidate must be an object")
    _validate_candidate_strings(candidate)
    figure = candidate.get("figure_type")
    if figure not in FIGURE_TYPES:
        raise RhetoricError(f"invalid figure_type: {figure}")
    if figure not in package.get("figure_scope", []):
        raise RhetoricError(f"figure_type {figure} is outside task figure_scope")
    if figure in COMPARISON_FIGURES:
        missing = [
            field for field in ("tenor", "vehicle", "ground") if not _nonempty_string(candidate.get(field))
        ]
        if missing:
            raise RhetoricError(f"comparison fields missing: {missing}")
    else:
        elements = candidate.get("device_elements")
        if not isinstance(elements, Mapping) or not _contains_content(elements):
            raise RhetoricError("non-comparison occurrence requires non-empty device_elements")

    locator = str(candidate["source_locator"])
    located = _locator_window(work_dir, locator)
    if located is None:
        raise RhetoricError(f"invalid locator: {locator}")
    located_path, start, end, window = located
    source_meta = package["source"]
    expected_source_path = (work_dir / source_meta["file"]).resolve()
    if located_path != expected_source_path:
        raise RhetoricError("occurrence locator points to a different source_file")
    task_start = int(task["start_line"])
    task_end = int(task["end_line"])
    body_start = int(source_meta.get("body_start", task_start))
    body_end = int(source_meta.get("body_end", task_end))
    if start < body_start or end > body_end:
        raise RhetoricError(f"occurrence locator {locator} falls outside declared body")
    task_type = task.get("task_type", "stored_occurrence")
    if task_type == "explicit_cue":
        cue_line = int(task["cue_line"])
        if not start <= cue_line <= end:
            raise RhetoricError(
                f"explicit occurrence locator {locator} does not contain cue_line L{cue_line}"
            )
    elif task_type == "semantic_chunk":
        if not task_start <= start <= task_end:
            raise RhetoricError(
                f"semantic occurrence start L{start} is not owned by task L{task_start}-L{task_end}"
            )
    elif task_type != "stored_occurrence":
        raise RhetoricError(f"invalid task_type for occurrence: {task_type}")
    if _normalize_text(str(candidate["quote"])) not in _normalize_text(window):
        raise RhetoricError(f"quote not found at locator: {locator}")
    chapters = _chapter_labels(source_lines)
    expected_chapter = chapters[start - 1]
    if candidate.get("chapter") != expected_chapter:
        raise RhetoricError(
            f"chapter mismatch at {locator}: expected {expected_chapter}, got {candidate.get('chapter')}"
        )

    document: dict[str, Any] = {
        "schema_version": OCCURRENCE_SCHEMA,
        "occurrence_id": "",
        "work_id": package["work_id"],
        "edition_id": package["edition_id"],
        "source_file": source_meta["file"],
        "source_sha256": source_meta["sha256"],
    }
    for field in COMMON_CANDIDATE_FIELDS:
        document[field] = candidate[field]
    if figure in COMPARISON_FIGURES:
        for field in ("tenor", "vehicle", "ground"):
            document[field] = candidate[field]
        if "device_elements" in candidate:
            document["device_elements"] = candidate["device_elements"]
    else:
        document["device_elements"] = dict(candidate["device_elements"])
        for field in ("tenor", "vehicle", "ground"):
            if field in candidate:
                document[field] = candidate[field]
    document["occurrence_id"] = _occurrence_id(document)

    for field in GENERATED_FIELDS:
        if field in candidate and candidate[field] != document[field]:
            if field == "source_sha256":
                raise RhetoricError("source checksum mismatch")
            if field == "occurrence_id":
                raise RhetoricError("occurrence_id hash mismatch")
            raise RhetoricError(f"candidate {field} does not match generated value")
    return document


def _keyed_results(
    value: Any,
    *,
    lane: str,
    expected_ids: set[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise RhetoricError(f"{lane} results must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict) or not _nonempty_string(item.get("task_id")):
            raise RhetoricError(f"{lane} result missing task_id")
        task_id = str(item["task_id"])
        if task_id in result:
            raise RhetoricError(f"duplicate {lane} task result: {task_id}")
        if task_id not in expected_ids:
            raise RhetoricError(f"unknown {lane} task result: {task_id}")
        result[task_id] = item
    missing = sorted(expected_ids - set(result))
    if missing:
        raise RhetoricError(f"unhandled {lane} tasks: {missing}")
    return result


def _load_occurrences(work_dir: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    occurrences_dir = work_dir / "rhetoric" / "occurrences"
    documents: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    if not occurrences_dir.is_dir():
        return documents, errors
    for path in sorted(occurrences_dir.glob("*.yaml"), key=lambda item: item.name):
        try:
            documents.append((path, _read_yaml(path)))
        except (OSError, yaml.YAMLError, RhetoricError) as exc:
            errors.append(f"{path}: {exc}")
    return documents, errors


def _quote_cell(value: Any, limit: int = MAX_QUOTE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip().replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _locator_sort_key(value: Any) -> tuple[str, int, int, str]:
    """Sort source locators by numeric line position, with stable fallback."""

    text = str(value)
    parsed = _parse_locator(text)
    if parsed is None:
        return text, sys.maxsize, sys.maxsize, text
    path, start, end = parsed
    return path, start, end, text


def _work_index_markdown(
    *,
    work_id: str,
    status: str,
    occurrences: Iterable[Mapping[str, Any]],
) -> str:
    items = sorted(
        occurrences,
        key=lambda item: (
            *_locator_sort_key(item.get("source_locator", "")),
            str(item.get("figure_type", "")),
            str(item.get("occurrence_id", "")),
        ),
    )
    lines = [
        f"# {work_id} 修辞证据索引",
        "",
        f"- coverage: {status}",
        f"- occurrences: {len(items)}",
        "",
        "| occurrence_id | locator | chapter | figure | quality | quote |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| {id} | {locator} | {chapter} | {figure} | {quality} | {quote} |".format(
                id=item.get("occurrence_id", ""),
                locator=_quote_cell(item.get("source_locator", ""), 48),
                chapter=_quote_cell(item.get("chapter", ""), 40),
                figure=item.get("figure_type", ""),
                quality=item.get("quality_assessment", ""),
                quote=_quote_cell(item.get("quote", "")),
            )
        )
    return "\n".join(lines) + "\n"


def _validate_staged_snapshot(
    stage_dir: Path,
    *,
    coverage: Mapping[str, Any],
    occurrences: Mapping[str, Mapping[str, Any]],
    index_text: str,
) -> None:
    expected_files = {"coverage.yaml", "index.md"}
    expected_files.update(f"occurrences/{occurrence_id}.yaml" for occurrence_id in occurrences)
    actual_files = {
        path.relative_to(stage_dir).as_posix()
        for path in stage_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise RhetoricError("staged rhetoric snapshot file set mismatch")
    if _read_yaml(stage_dir / "coverage.yaml") != dict(coverage):
        raise RhetoricError("staged rhetoric coverage round-trip mismatch")
    if (stage_dir / "index.md").read_text(encoding="utf-8") != index_text:
        raise RhetoricError("staged rhetoric index round-trip mismatch")
    declared_ids = coverage.get("occurrence_ids")
    if declared_ids != sorted(occurrences):
        raise RhetoricError("staged rhetoric occurrence_ids mismatch")
    range_errors = _coverage_range_errors(coverage)
    if range_errors:
        raise RhetoricError("invalid staged rhetoric coverage: " + "; ".join(range_errors))
    for occurrence_id, expected in occurrences.items():
        path = stage_dir / "occurrences" / f"{occurrence_id}.yaml"
        if _read_yaml(path) != dict(expected):
            raise RhetoricError(f"staged rhetoric occurrence round-trip mismatch: {occurrence_id}")


def _stage_rhetoric_snapshot(
    work_dir: Path,
    *,
    coverage: Mapping[str, Any],
    occurrences: Mapping[str, Mapping[str, Any]],
    index_text: str,
) -> Path:
    stage_dir = Path(tempfile.mkdtemp(prefix=".rhetoric-stage-", dir=work_dir))
    try:
        (stage_dir / "occurrences").mkdir()
        for occurrence_id, occurrence in occurrences.items():
            _write_yaml(stage_dir / "occurrences" / f"{occurrence_id}.yaml", occurrence)
        _write_yaml(stage_dir / "coverage.yaml", coverage)
        _atomic_write_text(stage_dir / "index.md", index_text)
        _validate_staged_snapshot(
            stage_dir,
            coverage=coverage,
            occurrences=occurrences,
            index_text=index_text,
        )
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    return stage_dir


def _promote_rhetoric_snapshot(work_dir: Path, stage_dir: Path) -> None:
    target = work_dir / "rhetoric"
    backup = work_dir / f".rhetoric-backup-{stage_dir.name.removeprefix('.rhetoric-stage-')}"
    if backup.exists():
        raise RhetoricError(f"transaction backup path already exists: {backup}")
    moved_old = False
    try:
        if target.exists():
            if not target.is_dir() or target.is_symlink():
                raise RhetoricError(f"rhetoric target is not a regular directory: {target}")
            target.rename(backup)
            moved_old = True
        try:
            stage_dir.rename(target)
        except Exception as promotion_error:
            if moved_old:
                try:
                    backup.rename(target)
                except Exception as rollback_error:
                    raise RhetoricError(
                        "rhetoric snapshot promotion and rollback both failed; "
                        f"recover backup at {backup}: {rollback_error}"
                    ) from promotion_error
            raise
        if moved_old:
            shutil.rmtree(backup)
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)


def _stored_occurrence_errors(
    document: dict[str, Any],
    *,
    path: Path,
    package_like: dict[str, Any],
    work_dir: Path,
    source_lines: list[str],
    body_start: int,
    body_end: int,
) -> list[str]:
    errors: list[str] = []
    fake_task = {
        "task_type": "stored_occurrence",
        "start_line": body_start,
        "end_line": body_end,
    }
    package_for_validation = dict(package_like)
    package_for_validation["figure_scope"] = list(FIGURE_TYPES)
    try:
        rebuilt = build_occurrence(
            document,
            package=package_for_validation,
            task=fake_task,
            work_dir=work_dir,
            source_lines=source_lines,
        )
    except (RhetoricError, KeyError, TypeError) as exc:
        errors.append(f"{path}: {exc}")
        return errors
    if document.get("schema_version") != OCCURRENCE_SCHEMA:
        errors.append(f"{path}: invalid schema_version")
    if document.get("occurrence_id") != rebuilt["occurrence_id"]:
        errors.append(f"{path}: occurrence_id hash mismatch")
    if path.stem != str(document.get("occurrence_id", "")):
        errors.append(f"{path}: filename does not match occurrence_id")
    return errors


def _merge_agent_outputs(
    output_paths: Path | str | Iterable[Path | str],
    *,
    task_digest: str,
) -> dict[str, Any]:
    if isinstance(output_paths, (str, Path)):
        paths = [Path(output_paths)]
    else:
        paths = [Path(path) for path in output_paths]
    if not paths:
        raise RhetoricError("at least one agent output file is required")
    merged: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA,
        "task_package_sha256": task_digest,
        "explicit_results": [],
        "semantic_results": [],
    }
    for path in paths:
        fragment = _read_json(path)
        if fragment.get("schema_version") != OUTPUT_SCHEMA:
            raise RhetoricError(f"{path}: invalid agent output schema_version")
        if fragment.get("task_package_sha256") != task_digest:
            raise RhetoricError(f"{path}: task package checksum mismatch")
        for key in ("explicit_results", "semantic_results"):
            items = fragment.get(key)
            if not isinstance(items, list):
                raise RhetoricError(f"{path}: {key} must be a list")
            merged[key].extend(items)
    return merged


def ingest_files(
    task_path: Path,
    output_paths: Path | str | Iterable[Path | str],
    *,
    kb_root: Path = DEFAULT_KB_ROOT,
    replace: bool = False,
) -> dict[str, Any]:
    """Validate one or more partial outputs and write one complete work snapshot."""

    task_path = Path(task_path)
    package = _read_json(task_path)
    actual_task_digest = _sha256_path(task_path)
    output = _merge_agent_outputs(output_paths, task_digest=actual_task_digest)
    work_dir, _source_path_value, source_lines = _validate_task_package(package, Path(kb_root))

    explicit_tasks = {
        str(item["task_id"]): item for item in package.get("explicit_tasks", [])
    }
    semantic_tasks = {
        str(item["task_id"]): item for item in package.get("semantic_tasks", [])
    }
    if len(explicit_tasks) != len(package.get("explicit_tasks", [])):
        raise RhetoricError("duplicate explicit task_id in package")
    if len(semantic_tasks) != len(package.get("semantic_tasks", [])):
        raise RhetoricError("duplicate semantic task_id in package")
    explicit_results = _keyed_results(
        output.get("explicit_results"),
        lane="explicit",
        expected_ids=set(explicit_tasks),
    )
    semantic_results = _keyed_results(
        output.get("semantic_results"),
        lane="semantic",
        expected_ids=set(semantic_tasks),
    )

    new_occurrences: dict[str, dict[str, Any]] = {}
    explicit_coverage: list[dict[str, Any]] = []
    semantic_coverage: list[dict[str, Any]] = []

    def accept_candidates(raw_items: Any, task: dict[str, Any]) -> list[str]:
        if not isinstance(raw_items, list):
            raise RhetoricError(f"{task['task_id']}: occurrences/discoveries must be a list")
        ids: list[str] = []
        for raw in raw_items:
            occurrence = build_occurrence(
                raw,
                package=package,
                task=task,
                work_dir=work_dir,
                source_lines=source_lines,
            )
            occurrence_id = occurrence["occurrence_id"]
            if occurrence_id in new_occurrences:
                raise RhetoricError(f"duplicate occurrence_id in agent output: {occurrence_id}")
            new_occurrences[occurrence_id] = occurrence
            ids.append(occurrence_id)
        return ids

    for task in package["explicit_tasks"]:
        result = explicit_results[task["task_id"]]
        disposition = result.get("disposition")
        if disposition not in {"include", "exclude"}:
            raise RhetoricError(f"{task['task_id']}: invalid explicit disposition")
        occurrence_ids = accept_candidates(result.get("occurrences", []), task)
        if disposition == "include" and not occurrence_ids:
            raise RhetoricError(f"{task['task_id']}: include requires at least one occurrence")
        if disposition == "exclude" and occurrence_ids:
            raise RhetoricError(f"{task['task_id']}: exclude cannot contain occurrences")
        explicit_coverage.append(
            {
                **{key: task[key] for key in (
                    "task_id",
                    "source_locator",
                    "start_line",
                    "end_line",
                    "cue_line",
                    "cue_terms",
                    "chapter",
                )},
                "disposition": disposition,
                "reason": result.get("reason", ""),
                "occurrence_ids": occurrence_ids,
            }
        )

    for task in package["semantic_tasks"]:
        result = semantic_results[task["task_id"]]
        if result.get("reviewed") is not True:
            raise RhetoricError(f"{task['task_id']}: semantic task not reviewed")
        occurrence_ids = accept_candidates(result.get("discoveries", []), task)
        semantic_coverage.append(
            {
                **{key: task[key] for key in (
                    "task_id",
                    "source_locator",
                    "start_line",
                    "end_line",
                    "chapter",
                )},
                "reviewed": True,
                "occurrence_ids": occurrence_ids,
            }
        )

    source = package["source"]
    package_like = {
        "work_id": package["work_id"],
        "edition_id": package["edition_id"],
        "source": source,
        "figure_scope": list(FIGURE_TYPES),
    }
    existing_documents, existing_errors = _load_occurrences(work_dir)
    existing: dict[str, dict[str, Any]] = {}
    for path, document in existing_documents:
        existing_errors.extend(
            _stored_occurrence_errors(
                document,
                path=path,
                package_like=package_like,
                work_dir=work_dir,
                source_lines=source_lines,
                body_start=source["body_start"],
                body_end=source["body_end"],
            )
        )
        occurrence_id = str(document.get("occurrence_id", ""))
        if occurrence_id in existing:
            existing_errors.append(f"{path}: duplicate occurrence_id {occurrence_id}")
        existing[occurrence_id] = document
    if existing_errors:
        raise RhetoricError("existing rhetoric cards are invalid:\n" + "\n".join(existing_errors))
    for occurrence_id, occurrence in new_occurrences.items():
        if occurrence_id in existing and existing[occurrence_id] != occurrence:
            if not replace:
                raise RhetoricError(
                    f"occurrence_id collision with different content: {occurrence_id}; use --replace"
                )

    stale_ids = sorted(set(existing) - set(new_occurrences))
    if stale_ids and not replace:
        raise RhetoricError(
            "stale occurrence cards are not present in this output: "
            + ", ".join(stale_ids)
            + "; use --replace after confirming the complete task snapshot"
        )

    all_occurrence_ids = sorted(new_occurrences)
    coverage = {
        "schema_version": COVERAGE_SCHEMA,
        "work_id": package["work_id"],
        "container": package["container"],
        "work": package["work"],
        "edition_id": package["edition_id"],
        "source_file": source["file"],
        "source_sha256": source["sha256"],
        "body_start": source["body_start"],
        "body_end": source["body_end"],
        "chunk_lines": package["chunk_lines"],
        "chunk_chars": package["chunk_chars"],
        "figure_scope": package["figure_scope"],
        "task_package_sha256": actual_task_digest,
        "scope_file": package.get("scope_file"),
        "scope_file_sha256": package.get("scope_file_sha256"),
        "scope_entry": package.get("scope_entry"),
        "status": "complete" if package.get("scope_file") else "range_complete",
        "counts": {
            "explicit_tasks": len(explicit_coverage),
            "included_explicit": sum(
                item["disposition"] == "include" for item in explicit_coverage
            ),
            "excluded_explicit": sum(
                item["disposition"] == "exclude" for item in explicit_coverage
            ),
            "semantic_chunks": len(semantic_coverage),
            "reviewed_semantic_chunks": len(semantic_coverage),
            "occurrences": len(new_occurrences),
        },
        "explicit_tasks": explicit_coverage,
        "semantic_chunks": semantic_coverage,
        "occurrence_ids": all_occurrence_ids,
        "unresolved": [],
    }

    index_text = _work_index_markdown(
        work_id=package["work_id"],
        status=coverage["status"],
        occurrences=new_occurrences.values(),
    )
    stage_dir = _stage_rhetoric_snapshot(
        work_dir,
        coverage=coverage,
        occurrences=new_occurrences,
        index_text=index_text,
    )
    _promote_rhetoric_snapshot(work_dir, stage_dir)
    return coverage


def _coverage_range_errors(coverage: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    body_start = coverage.get("body_start")
    body_end = coverage.get("body_end")
    chunks = coverage.get("semantic_chunks")
    if (
        not isinstance(body_start, int)
        or isinstance(body_start, bool)
        or not isinstance(body_end, int)
        or isinstance(body_end, bool)
        or body_start < 1
        or body_end < body_start
        or not isinstance(chunks, list)
    ):
        return ["semantic chunk gap or overlap: invalid body range/chunk list"]
    expected = body_start
    for chunk in chunks:
        if not isinstance(chunk, dict):
            errors.append("semantic chunk gap or overlap: chunk is not a mapping")
            continue
        start = chunk.get("start_line")
        end = chunk.get("end_line")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start != expected
            or end < start
            or end > body_end
        ):
            errors.append(
                f"semantic chunk gap or overlap: expected L{expected}, got L{start}-L{end}"
            )
            if isinstance(end, int) and not isinstance(end, bool):
                expected = end + 1
            continue
        expected = end + 1
    if expected != body_end + 1:
        errors.append(
            f"semantic chunk gap or overlap: coverage ends at L{expected - 1}, expected L{body_end}"
        )
    return errors


def verify_work(kb_root: Path, container: str, work: str) -> list[str]:
    """Return all completeness and evidence errors for one rhetoric work."""

    errors: list[str] = []
    try:
        work_dir = _work_dir(Path(kb_root), container, work)
    except RhetoricError as exc:
        return [str(exc)]
    coverage_path = work_dir / "rhetoric" / "coverage.yaml"
    if not coverage_path.is_file():
        return [f"{coverage_path}: missing coverage.yaml"]
    try:
        coverage = _read_yaml(coverage_path)
    except (OSError, yaml.YAMLError, RhetoricError) as exc:
        return [f"{coverage_path}: {exc}"]
    if coverage.get("schema_version") != COVERAGE_SCHEMA:
        errors.append(f"{coverage_path}: invalid schema_version")
    if coverage.get("work_id") != _work_id(container, work):
        errors.append(f"{coverage_path}: work_id mismatch")
    if coverage.get("unresolved") != []:
        errors.append(f"{coverage_path}: unresolved entries remain")

    source_file = coverage.get("source_file")
    source_path: Path | None = None
    source_lines: list[str] = []
    if not _nonempty_string(source_file):
        errors.append(f"{coverage_path}: missing source_file")
    else:
        try:
            source_path, canonical = _source_path(work_dir, str(source_file))
            if canonical != source_file:
                errors.append(f"{coverage_path}: source_file is not canonical")
            source_lines = source_path.read_text(encoding="utf-8").splitlines()
            if _sha256_path(source_path) != coverage.get("source_sha256"):
                errors.append(f"{coverage_path}: source checksum mismatch")
        except RhetoricError as exc:
            errors.append(f"{coverage_path}: {exc}")

    scope_file = coverage.get("scope_file")
    expected_status = "complete" if _nonempty_string(scope_file) else "range_complete"
    if coverage.get("status") != expected_status:
        errors.append(
            f"{coverage_path}: coverage status must be {expected_status} for its scope binding"
        )
    if _nonempty_string(scope_file) and source_path is not None:
        try:
            current_binding = _load_scope_binding(
                Path(kb_root),
                str(scope_file),
                container=container,
                work=work,
                source_path=source_path,
                source_file=str(source_file),
                source_sha256=str(coverage.get("source_sha256", "")),
                body_start=coverage.get("body_start"),
                body_end=coverage.get("body_end"),
            )
            if current_binding["scope_file_sha256"] != coverage.get("scope_file_sha256"):
                errors.append(f"{coverage_path}: scope manifest checksum mismatch")
            if current_binding["scope_entry"] != coverage.get("scope_entry"):
                errors.append(f"{coverage_path}: scope manifest entry snapshot mismatch")
        except (RhetoricError, TypeError) as exc:
            errors.append(f"{coverage_path}: {exc}")
    errors.extend(f"{coverage_path}: {item}" for item in _coverage_range_errors(coverage))

    explicit = coverage.get("explicit_tasks")
    semantic = coverage.get("semantic_chunks")
    if not isinstance(explicit, list):
        errors.append(f"{coverage_path}: explicit_tasks must be a list")
        explicit = []
    if not isinstance(semantic, list):
        errors.append(f"{coverage_path}: semantic_chunks must be a list")
        semantic = []
    task_ids: set[str] = set()
    referenced_ids: set[str] = set()
    for item in explicit:
        if not isinstance(item, dict):
            errors.append(f"{coverage_path}: explicit task must be a mapping")
            continue
        task_id = str(item.get("task_id", ""))
        if not task_id or task_id in task_ids:
            errors.append(f"{coverage_path}: duplicate or missing task_id {task_id}")
        task_ids.add(task_id)
        disposition = item.get("disposition")
        ids = item.get("occurrence_ids")
        if disposition not in {"include", "exclude"}:
            errors.append(f"{coverage_path}: unhandled explicit task {task_id}")
        if not isinstance(ids, list):
            errors.append(f"{coverage_path}: explicit task {task_id} occurrence_ids must be a list")
            ids = []
        if disposition == "include" and not ids:
            errors.append(f"{coverage_path}: included explicit task {task_id} has no occurrence")
        if disposition == "exclude" and ids:
            errors.append(f"{coverage_path}: excluded explicit task {task_id} has occurrences")
        referenced_ids.update(str(value) for value in ids)
    for item in semantic:
        if not isinstance(item, dict):
            errors.append(f"{coverage_path}: semantic task must be a mapping")
            continue
        task_id = str(item.get("task_id", ""))
        if not task_id or task_id in task_ids:
            errors.append(f"{coverage_path}: duplicate or missing task_id {task_id}")
        task_ids.add(task_id)
        if item.get("reviewed") is not True:
            errors.append(f"{coverage_path}: semantic task {task_id} not reviewed")
        ids = item.get("occurrence_ids")
        if not isinstance(ids, list):
            errors.append(f"{coverage_path}: semantic task {task_id} occurrence_ids must be a list")
            ids = []
        referenced_ids.update(str(value) for value in ids)

    if source_path is not None and source_lines:
        try:
            expected = prepare_package(
                Path(kb_root),
                container=container,
                work=work,
                source=str(source_file),
                body_start=coverage.get("body_start"),
                body_end=coverage.get("body_end"),
                figure_scope=coverage.get("figure_scope") or [],
                chunk_lines=coverage.get("chunk_lines"),
                chunk_chars=coverage.get("chunk_chars", DEFAULT_CHUNK_CHARS),
                edition_id=coverage.get("edition_id"),
                scope_file=str(scope_file) if _nonempty_string(scope_file) else None,
            )
            expected_cues = [item["cue_line"] for item in expected["explicit_tasks"]]
            actual_cues = [
                item.get("cue_line") for item in explicit if isinstance(item, dict)
            ]
            if actual_cues != expected_cues:
                errors.append(f"{coverage_path}: explicit cue coverage mismatch")
            expected_semantic = [
                (item["task_id"], item["start_line"], item["end_line"])
                for item in expected["semantic_tasks"]
            ]
            actual_semantic = [
                (item.get("task_id"), item.get("start_line"), item.get("end_line"))
                for item in semantic
                if isinstance(item, dict)
            ]
            if actual_semantic != expected_semantic:
                errors.append(f"{coverage_path}: semantic task structure mismatch")
        except (RhetoricError, TypeError) as exc:
            errors.append(f"{coverage_path}: cannot reproduce tasks: {exc}")

    documents, load_errors = _load_occurrences(work_dir)
    errors.extend(load_errors)
    seen_ids: set[str] = set()
    stored_ids: set[str] = set()
    if source_lines:
        package_like = {
            "work_id": _work_id(container, work),
            "edition_id": coverage.get("edition_id"),
            "source": {
                "file": source_file,
                "sha256": coverage.get("source_sha256"),
                "body_start": coverage.get("body_start"),
                "body_end": coverage.get("body_end"),
            },
            "figure_scope": list(FIGURE_TYPES),
        }
        for path, document in documents:
            occurrence_id = str(document.get("occurrence_id", ""))
            if not occurrence_id or occurrence_id in seen_ids:
                errors.append(f"{path}: duplicate occurrence_id {occurrence_id}")
            seen_ids.add(occurrence_id)
            stored_ids.add(occurrence_id)
            errors.extend(
                _stored_occurrence_errors(
                    document,
                    path=path,
                    package_like=package_like,
                    work_dir=work_dir,
                    source_lines=source_lines,
                    body_start=coverage.get("body_start", 0),
                    body_end=coverage.get("body_end", 0),
                )
            )
    declared_ids = coverage.get("occurrence_ids")
    if not isinstance(declared_ids, list):
        errors.append(f"{coverage_path}: occurrence_ids must be a list")
        declared_set: set[str] = set()
    else:
        declared_set = {str(value) for value in declared_ids}
        if len(declared_set) != len(declared_ids):
            errors.append(f"{coverage_path}: duplicate occurrence_id in coverage")
    if stored_ids != declared_set:
        errors.append(f"{coverage_path}: occurrence_ids do not match stored cards")
    if referenced_ids != stored_ids:
        errors.append(f"{coverage_path}: task occurrence references do not match stored cards")
    counts = coverage.get("counts")
    expected_counts = {
        "explicit_tasks": len(explicit),
        "included_explicit": sum(
            isinstance(item, dict) and item.get("disposition") == "include"
            for item in explicit
        ),
        "excluded_explicit": sum(
            isinstance(item, dict) and item.get("disposition") == "exclude"
            for item in explicit
        ),
        "semantic_chunks": len(semantic),
        "reviewed_semantic_chunks": sum(
            isinstance(item, dict) and item.get("reviewed") is True
            for item in semantic
        ),
        "occurrences": len(stored_ids),
    }
    if not isinstance(counts, dict) or any(
        counts.get(key) != value for key, value in expected_counts.items()
    ):
        errors.append(f"{coverage_path}: coverage counts mismatch")
    return errors


def _iter_rhetoric_works(kb_root: Path) -> Iterable[tuple[str, str]]:
    for container in CONTAINERS:
        root = Path(kb_root) / container
        if not root.is_dir():
            continue
        for work_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name):
            if (work_dir / "rhetoric" / "coverage.yaml").is_file():
                yield container, work_dir.name


def _scope_coverage_binding_errors(
    kb_root: Path,
    *,
    container: str,
    work: str,
    scope_locator: str,
    scope_digest: str,
    scope_entry: Mapping[str, Any],
) -> list[str]:
    coverage_path = Path(kb_root) / container / work / "rhetoric" / "coverage.yaml"
    if not coverage_path.is_file():
        return []
    try:
        coverage = _read_yaml(coverage_path)
    except (OSError, yaml.YAMLError, RhetoricError) as exc:
        return [f"{coverage_path}: {exc}"]
    errors: list[str] = []
    if coverage.get("status") != "complete":
        errors.append(f"{coverage_path}: scoped enrollment requires status complete")
    if coverage.get("scope_file") != scope_locator:
        errors.append(f"{coverage_path}: scope manifest locator mismatch")
    if coverage.get("scope_file_sha256") != scope_digest:
        errors.append(f"{coverage_path}: scope manifest checksum mismatch")
    if coverage.get("scope_entry") != dict(scope_entry):
        errors.append(f"{coverage_path}: scope manifest entry snapshot mismatch")
    return errors


def verify_all(
    kb_root: Path,
    *,
    scope_file: str | Path | None = None,
) -> list[str]:
    """Verify a manifest-enrolled corpus; discovery alone cannot certify completeness."""

    if scope_file is None:
        return ["global rhetoric verification requires --scope-file enrollment"]
    try:
        scope_locator, scope_digest, entries = _load_scope_enrollment(kb_root, scope_file)
    except (OSError, yaml.YAMLError, RhetoricError) as exc:
        return [str(exc)]
    errors: list[str] = []
    for entry in entries:
        container = str(entry["container"])
        work = str(entry["work"])
        errors.extend(verify_work(kb_root, container, work))
        errors.extend(
            _scope_coverage_binding_errors(
                kb_root,
                container=container,
                work=work,
                scope_locator=scope_locator,
                scope_digest=scope_digest,
                scope_entry=entry,
            )
        )
    return errors


def rebuild_global_index(
    kb_root: Path = DEFAULT_KB_ROOT,
    *,
    scope_file: str | Path | None = None,
) -> dict[str, Any]:
    """Rebuild the derived global index from complete, verified work cards."""

    kb_root = Path(kb_root)
    entries: list[dict[str, Any]] = []
    if scope_file is not None:
        scope_locator, scope_digest, scope_entries = _load_scope_enrollment(
            kb_root,
            scope_file,
        )
        errors = verify_all(kb_root, scope_file=scope_file)
        if errors:
            raise RhetoricError(
                "cannot index incomplete scoped rhetoric corpus:\n" + "\n".join(errors)
            )
        works = [(str(entry["container"]), str(entry["work"])) for entry in scope_entries]
        scope_status = "complete"
        enrolled_work_ids = [
            _work_id(str(entry["container"]), str(entry["work"]))
            for entry in scope_entries
        ]
    else:
        works = list(_iter_rhetoric_works(kb_root))
        if not works:
            raise RhetoricError("rhetoric corpus enrollment is empty")
        scope_locator = None
        scope_digest = None
        scope_status = "unscoped_derived"
        enrolled_work_ids = [_work_id(container, work) for container, work in works]
    for container, work in works:
        errors = verify_work(kb_root, container, work)
        if errors:
            raise RhetoricError(
                f"cannot index incomplete rhetoric work {container}/{work}:\n" + "\n".join(errors)
            )
        work_dir = _work_dir(kb_root, container, work)
        documents, load_errors = _load_occurrences(work_dir)
        if load_errors:
            raise RhetoricError("\n".join(load_errors))
        for path, document in documents:
            entries.append(
                {
                    **document,
                    "occurrence_file": path.relative_to(kb_root).as_posix(),
                }
            )
    entries.sort(
        key=lambda item: (
            str(item.get("work_id", "")),
            *_locator_sort_key(item.get("source_locator", "")),
            str(item.get("figure_type", "")),
            str(item.get("occurrence_id", "")),
        )
    )
    index = {
        "schema_version": "rhetoric-occurrence-index/v1",
        "source_of_truth": "novels|dramas/{work}/rhetoric/occurrences/*.yaml",
        "scope_status": scope_status,
        "scope_file": scope_locator,
        "scope_file_sha256": scope_digest,
        "enrolled_work_ids": enrolled_work_ids,
        "work_count": len(works),
        "count": len(entries),
        "occurrences": entries,
    }
    global_dir = kb_root / "rhetoric"
    _write_json(global_dir / "occurrence_index.json", index)
    lines = [
        "# 全局修辞证据索引",
        "",
        "> 只读派生视图；源数据位于各作品 rhetoric/occurrences/*.yaml。",
        "",
        f"- occurrences: {len(entries)}",
        "",
        "| work | figure | quality | locator | quote |",
        "|---|---|---|---|---|",
    ]
    for item in entries:
        lines.append(
            "| {work} | {figure} | {quality} | {locator} | {quote} |".format(
                work=_quote_cell(item.get("work_id", ""), 48),
                figure=item.get("figure_type", ""),
                quality=item.get("quality_assessment", ""),
                locator=_quote_cell(item.get("source_locator", ""), 64),
                quote=_quote_cell(item.get("quote", "")),
            )
        )
    _atomic_write_text(global_dir / "index.md", "\n".join(lines) + "\n")
    return index


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-root", type=Path, default=DEFAULT_KB_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="freeze source and emit review tasks")
    prepare_parser.add_argument("--container", choices=tuple(CONTAINERS), required=True)
    prepare_parser.add_argument("--work", required=True)
    prepare_parser.add_argument("--source", required=True)
    prepare_parser.add_argument("--body-start", type=int, required=True)
    prepare_parser.add_argument("--body-end", type=int, required=True)
    prepare_parser.add_argument(
        "--figure-scope",
        action="append",
        required=True,
        help=(
            "comparison, all supported figures, a concrete supported figure, "
            "or comma-separated figures; repeatable"
        ),
    )
    prepare_parser.add_argument("--chunk-lines", type=int, default=120)
    prepare_parser.add_argument(
        "--chunk-chars",
        type=int,
        default=DEFAULT_CHUNK_CHARS,
        help="maximum text characters per semantic task when line boundaries permit",
    )
    prepare_parser.add_argument("--edition-id", default="current")
    prepare_parser.add_argument(
        "--scope-file",
        type=Path,
        help="frozen YAML corpus manifest; required for work-level complete status",
    )
    prepare_parser.add_argument("--out", type=Path, required=True)

    slice_parser = subparsers.add_parser(
        "slice",
        help="split a frozen parent task package into bounded annotator shards",
    )
    slice_parser.add_argument("--tasks", type=Path, required=True)
    slice_parser.add_argument("--out-dir", type=Path, required=True)
    slice_parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_SHARD_CHARS,
        help="maximum serialized task-payload characters per shard; envelope excluded",
    )
    slice_parser.add_argument("--max-tasks", type=int, default=DEFAULT_SHARD_TASKS)

    ingest_parser = subparsers.add_parser("ingest", help="validate agent output and write work cards")
    ingest_parser.add_argument("--tasks", type=Path, required=True)
    ingest_parser.add_argument(
        "--output",
        type=Path,
        action="append",
        required=True,
        help="agent output fragment; repeat for partial outputs",
    )
    ingest_parser.add_argument(
        "--replace",
        action="store_true",
        help="after full validation, remove stored cards absent from this task snapshot",
    )

    verify_parser = subparsers.add_parser("verify", help="verify evidence and complete coverage")
    verify_parser.add_argument("--container", choices=tuple(CONTAINERS))
    verify_parser.add_argument("--work")
    verify_parser.add_argument(
        "--scope-file",
        type=Path,
        help="frozen enrollment manifest required for corpus-level certification",
    )

    index_parser = subparsers.add_parser(
        "index",
        help="rebuild the global derived occurrence index",
    )
    index_parser.add_argument(
        "--scope-file",
        type=Path,
        help="frozen enrollment manifest for a scope-complete index",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    kb_root = args.kb_root.resolve()
    try:
        if args.command == "prepare":
            package = prepare_package(
                kb_root,
                container=args.container,
                work=args.work,
                source=args.source,
                body_start=args.body_start,
                body_end=args.body_end,
                figure_scope=args.figure_scope,
                chunk_lines=args.chunk_lines,
                chunk_chars=args.chunk_chars,
                edition_id=args.edition_id,
                scope_file=args.scope_file,
            )
            _write_json(args.out, package)
            print(
                json.dumps(
                    {
                        "task_file": str(args.out),
                        "explicit_tasks": len(package["explicit_tasks"]),
                        "semantic_tasks": len(package["semantic_tasks"]),
                        "source_sha256": package["source"]["sha256"],
                    },
                    ensure_ascii=False,
                )
            )
        elif args.command == "slice":
            manifest = slice_task_package(
                args.tasks,
                args.out_dir,
                kb_root=kb_root,
                max_chars=args.max_chars,
                max_tasks=args.max_tasks,
            )
            print(
                json.dumps(
                    {
                        "shard_dir": str(args.out_dir),
                        "shards": manifest["shard_count"],
                        "tasks": manifest["task_count"],
                        "parent_task_package_sha256": manifest[
                            "parent_task_package_sha256"
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        elif args.command == "ingest":
            coverage = ingest_files(
                args.tasks,
                args.output,
                kb_root=kb_root,
                replace=args.replace,
            )
            print(
                json.dumps(
                    {
                        "work_id": coverage["work_id"],
                        "status": coverage["status"],
                        **coverage["counts"],
                    },
                    ensure_ascii=False,
                )
            )
        elif args.command == "verify":
            if bool(args.container) != bool(args.work):
                raise RhetoricError("--container and --work must be supplied together")
            if args.container and args.scope_file:
                raise RhetoricError(
                    "--scope-file is corpus-level; omit --container/--work for scoped verification"
                )
            errors = (
                verify_work(kb_root, args.container, args.work)
                if args.container
                else verify_all(kb_root, scope_file=args.scope_file)
            )
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print("rhetoric evidence verification passed")
        else:
            index = rebuild_global_index(kb_root, scope_file=args.scope_file)
            print(json.dumps({"occurrences": index["count"]}, ensure_ascii=False))
    except (RhetoricError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"[rhetoric_cards ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
