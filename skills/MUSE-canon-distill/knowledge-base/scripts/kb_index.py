"""每作品索引定位与读写(novels JSON / dramas JSONL,medium-aware)。

权威优先级:作品目录下 `dramatic_scene_index.jsonl` 优先于 `scene_index.json`
(两者并存时 JSON 视为历史快照,只读不写回)。写回保持原格式:JSON 写数组,
JSONL 每行一个对象。medium 按容器目录判定(novels → novel / dramas → drama),
不按索引文件名判——legacy 索引的剧目仍按 drama 字段集标注。
"""

from __future__ import annotations

import json
from pathlib import Path

CONTAINER_DIRS = ("novels", "dramas")
DRAMA_INDEX = "dramatic_scene_index.jsonl"
NOVEL_INDEX = "scene_index.json"


def index_path_of(work_dir: Path) -> Path | None:
    """作品目录 → 权威索引路径(JSONL 优先);无索引返回 None。"""
    jsonl = work_dir / DRAMA_INDEX
    if jsonl.exists():
        return jsonl
    js = work_dir / NOVEL_INDEX
    return js if js.exists() else None


def medium_of(index_path: Path) -> str:
    """'novel' | 'drama',按容器目录判定。"""
    return "drama" if index_path.parent.parent.name == "dramas" else "novel"


def iter_work_indexes(kb_root: Path, name_filter: str | None = None) -> list[Path]:
    """全库(novels + dramas)权威索引路径,按路径排序。"""
    paths: list[Path] = []
    for container in CONTAINER_DIRS:
        root = kb_root / container
        if not root.exists():
            continue
        for work_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            if name_filter and name_filter not in work_dir.name:
                continue
            index_path = index_path_of(work_dir)
            if index_path is not None:
                paths.append(index_path)
    return sorted(paths)


def find_index_path(kb_root: Path, work: str) -> Path | None:
    """按作品名精确定位权威索引(目录名全等)。"""
    for container in CONTAINER_DIRS:
        work_dir = kb_root / container / work
        if work_dir.is_dir():
            index_path = index_path_of(work_dir)
            if index_path is not None:
                return index_path
    return None


def load_index(index_path: Path) -> list[dict]:
    text = index_path.read_text(encoding="utf-8")
    if index_path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def craft_notes_paths(work_dir: Path) -> dict[str, Path]:
    """逐场景标注位置：索引显式声明优先，兼容既有默认目录。"""
    paths = {
        path.stem[len("scene_"):-len("_beats")]: path.with_suffix(".md")
        for path in sorted((work_dir / "craft_notes").glob("scene_*_beats.*"))
        if path.suffix in {".md", ".yaml"}
    }
    index_path = index_path_of(work_dir)
    if index_path:
        for entry in load_index(index_path):
            if entry.get("scene_id") and entry.get("craft_notes_file"):
                paths[entry["scene_id"]] = work_dir / entry["craft_notes_file"]
    return paths


def save_index(index_path: Path, entries: list[dict]) -> None:
    if index_path.suffix == ".jsonl":
        payload = "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n"
    else:
        payload = json.dumps(entries, ensure_ascii=False, indent=2)
    tmp = index_path.parent / (index_path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(index_path)
