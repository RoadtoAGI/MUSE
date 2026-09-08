"""Shared checks for records rendered by serial context and checked by serial_lint.

Only supplied milestone/tentpole rows are checked. Empty collections remain valid;
genre vocabulary and judgments about the source text stay with their existing owners.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


CHAPTER_RE = re.compile(r"^C\d{4}$")
MILESTONE_RE = re.compile(r"^(C\d{4})(S\d{2})?$")
PUBLISHED_FILE_RE = re.compile(r"^(V\d+)(C\d{4})\.md$")


def _read_mapping(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: YAML 解析失败: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: 顶层必须为映射")
    return data


def load_chapter_anchors(work_dir: Path) -> dict[str, dict]:
    """Locate real chapter resources without requiring a historical chapter workspace.

    Imported chapters use their manifest-backed published source. Materialized
    chapters use chapter_card.yaml. A scene suffix is checked only when the card
    supplies an explicit nonempty scene index.
    """
    anchors: dict[str, dict] = {}
    for path in sorted((work_dir / "series" / "volumes").glob("*.yaml")):
        volume = _read_mapping(path)
        volume_id = volume.get("volume_id") or path.stem
        for row in volume.get("chapters") or []:
            if not isinstance(row, dict) or not CHAPTER_RE.fullmatch(str(row.get("chapter_id", ""))):
                continue
            cid = row["chapter_id"]
            if cid in anchors:
                raise ValueError(f"{path}: chapter_id={cid} 在卷纲重复，无法确定章锚归属")
            anchors[cid] = dict(volume_id=volume_id, materialized=False, published=False, scenes=None)

    for path in sorted((work_dir / "chapters").glob("*/*/chapter_card.yaml")):
        cid, volume_id = path.parent.name, path.parent.parent.name
        if not CHAPTER_RE.fullmatch(cid):
            continue
        card = _read_mapping(path)
        if card.get("chapter_id") != cid:
            raise ValueError(f"{path}: chapter_id 与所在章目录不一致")
        info = anchors.setdefault(cid, dict(volume_id=volume_id, materialized=False, published=False, scenes=None))
        if info["volume_id"] != volume_id:
            raise ValueError(f"{path}: 章目录与卷纲归属不一致")
        info["materialized"] = True
        plan = card.get("scene_plan") or {}
        scenes = plan.get("scenes") if isinstance(plan, dict) else None
        if isinstance(scenes, list) and scenes:
            info["scenes"] = {str(scene) for scene in scenes}

    manifest_path = work_dir / "published" / "manifest.yaml"
    manifest = _read_mapping(manifest_path)
    for row in manifest.get("entries") or []:
        if not isinstance(row, dict):
            continue
        cid, filename = row.get("chapter_id"), row.get("file")
        match = PUBLISHED_FILE_RE.fullmatch(str(filename or ""))
        if not match or match.group(2) != cid or not (manifest_path.parent / filename).is_file():
            continue
        volume_id = match.group(1)
        info = anchors.setdefault(cid, dict(volume_id=volume_id, materialized=False, published=False, scenes=None))
        if info["volume_id"] != volume_id:
            raise ValueError(f"{manifest_path}: {filename} 与卷纲归属不一致")
        info["published"] = True
    return anchors


def _rows(rows: Any, label: str) -> tuple[list, list[str]]:
    if rows is None:
        return [], []
    if not isinstance(rows, list):
        return [], [f"{label} 必须为列表"]
    return rows, []


def _required_text(row: dict, fields: tuple[str, ...], label: str) -> list[str]:
    missing = [name for name in fields if not isinstance(row.get(name), str) or not row[name].strip()]
    return [f"{label} 缺少非空文本字段: {', '.join(missing)}"] if missing else []


def validate_milestones(rows: Any, anchors: dict[str, dict]) -> list[str]:
    """Validate supplied biography rows, leaving kind extensions unrestricted."""
    items, errors = _rows(rows, "milestones")
    for i, row in enumerate(items):
        label = f"milestones[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{label} 必须为映射")
            continue
        errors.extend(_required_text(row, ("at", "kind", "before", "after", "evidence"), label))
        at = row.get("at")
        match = MILESTONE_RE.fullmatch(at) if isinstance(at, str) else None
        if not match:
            errors.append(f"{label}.at 必须为 C#### 或 C####S##，实为 {at!r}")
            continue
        cid, scene = match.groups()
        info = anchors.get(cid)
        if not info or not (info.get("materialized") or info.get("published")):
            errors.append(f"{label}.at={at} 未指向已发布来源或已有章卡")
        elif scene and info.get("scenes") is not None and scene not in info["scenes"]:
            errors.append(f"{label}.at={at} 不在该章 scene_plan.scenes 索引中")
    return errors


def validate_tentpoles(rows: Any, anchors: dict[str, dict], volume_id: str) -> list[str]:
    """Accept unresolved plans; concrete anchors must resolve within this volume."""
    items, errors = _rows(rows, "tentpoles")
    for i, row in enumerate(items):
        label = f"tentpoles[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{label} 必须为映射")
            continue
        errors.extend(_required_text(row, ("beat", "value_shift", "anchor"), label))
        anchor = row.get("anchor")
        if anchor == "unresolved":
            continue
        if not isinstance(anchor, str) or not CHAPTER_RE.fullmatch(anchor):
            errors.append(f"{label}.anchor 必须为 unresolved 或 C####，实为 {anchor!r}")
            continue
        info = anchors.get(anchor)
        if not info or info.get("volume_id") != volume_id:
            errors.append(f"{label}.anchor={anchor} 未指向本卷 {volume_id} 的章")
        elif not (info.get("materialized") or info.get("published")):
            errors.append(f"{label}.anchor={anchor} 尚未物化或发布，应保留 unresolved")
    return errors
