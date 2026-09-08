#!/usr/bin/env python3
"""Merge per-work scene indexes into the aggregate embeddings/scene_index.json.

聚合索引合并（唯一写入方）：以 per-novel / per-drama 索引为源重建聚合行——
novel 字段以目录名为准（消灭"·/-"显示名漂移），双名字段兼容归一
（participants→characters、craft_notes 路径→has_craft_notes+craft_notes_file，原字段保留），
style_profile 透传；输出按 (novel, scene_id) 确定性排序、idx 重编号、原子写。
幂等：同一输入连跑两次输出 byte-identical。
合并后须重跑 build_embeddings（增量按身份复用，见其 --bootstrap 说明）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

try:
    from . import kb_index
except ImportError:
    import kb_index

KB_ROOT = Path(__file__).resolve().parent.parent

MEDIUM_BY_TREE = {"novels": "novel", "dramas": "stage_play"}


def _load_rows(index_path: Path) -> list[dict]:
    text = index_path.read_text(encoding="utf-8")
    if index_path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = json.loads(text)
    if isinstance(rows, dict):
        rows = rows.get("scenes", rows.get("entries", []))
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _work_index_path(work_dir: Path) -> Path | None:
    """与知识库查询、标注共用权威索引定位。"""
    return kb_index.index_path_of(work_dir)


def _read_mapping(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[merge] 无法读取元数据 {path}: {exc}", file=sys.stderr)
        return {}
    return value if isinstance(value, dict) else {}


def _normalize(row: dict, *, tree: str, novel_dir: str, medium: str, genre=None) -> dict:
    entry = dict(row)
    entry["novel"] = novel_dir
    entry.setdefault("source_medium", medium)
    if not entry.get("lang") and entry.get("language"):
        entry["lang"] = entry["language"]
    if not entry.get("genre") and genre:
        entry["genre"] = genre
    if "characters" not in entry:
        participants = entry.get("participants", entry.get("characters_on_stage"))
        if isinstance(participants, list):
            entry["characters"] = list(participants)
    craft = entry.get("craft_notes")
    if isinstance(craft, str) and craft:
        entry.setdefault("craft_notes_file", craft)
        entry["has_craft_notes"] = True
    # per-novel 源的 file 字段以作品目录为相对根（如 "scenes/scene_01.md"）；
    # 聚合层消费方（read_scene_text 等）按 KB_ROOT 相对路径解析，须补前缀。
    # 已带前缀（某些源可能已是 KB_ROOT 相对）时不重复添加，保持幂等。
    file_field = entry.get("file")
    if isinstance(file_field, str) and file_field and not file_field.startswith(f"{tree}/"):
        entry["file"] = f"{tree}/{novel_dir}/{file_field}"
    return entry


def collect(kb_root: Path) -> list[dict]:
    merged: list[dict] = []
    for tree, medium in MEDIUM_BY_TREE.items():
        base = kb_root / tree
        if not base.is_dir():
            continue
        for work_dir in sorted(base.iterdir()):
            if not work_dir.is_dir():
                continue
            index_path = _work_index_path(work_dir)
            if index_path is None:
                continue
            try:
                rows = _load_rows(index_path)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[merge] 跳过 {index_path}: {exc}", file=sys.stderr)
                continue
            meta = _read_mapping(work_dir / "work-meta.yaml")
            phase0 = _read_mapping(work_dir / "pipeline" / "phase0_conception.yaml")
            genre = phase0.get("genre")
            if isinstance(genre, dict):
                genre = genre.get("primary")
            merged.extend(
                _normalize(
                    row, tree=tree, novel_dir=work_dir.name,
                    medium=meta.get("source_medium") or medium, genre=genre,
                )
                for row in rows
                if row.get("scene_id")
            )
    merged.sort(key=lambda e: (e["novel"], str(e.get("scene_id"))))
    for i, entry in enumerate(merged):
        entry["idx"] = i
    return merged


def merge(kb_root: str | Path = KB_ROOT, *, dry_run: bool = False) -> int:
    kb_root = Path(kb_root)
    out_path = kb_root / "embeddings" / "scene_index.json"
    merged = collect(kb_root)

    old_keys: set[tuple] = set()
    if out_path.exists():
        try:
            old_keys = {
                (e.get("novel"), e.get("scene_id"))
                for e in json.loads(out_path.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, OSError):
            old_keys = set()
    new_keys = {(e["novel"], e["scene_id"]) for e in merged}
    added, removed = new_keys - old_keys, old_keys - new_keys
    print(
        f"[merge] 合并 {len(merged)} 行（原聚合 {len(old_keys)}）：新增 {len(added)}、移除 {len(removed)}"
    )
    if dry_run:
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kb", default=str(KB_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return merge(Path(args.kb), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
