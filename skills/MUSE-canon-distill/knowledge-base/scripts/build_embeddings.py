#!/usr/bin/env python3
"""Build content/style embedding channels for the knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb_index  # noqa: E402

load_dotenv()

EMBEDDING_MODEL = os.getenv("MUSE_KB_EMBEDDING_MODEL") or "text-embedding-3-small"
BASE_URL = os.getenv("MUSE_KB_BASE_URL") or os.getenv("API_BASE_URL") or "https://your-compatible-endpoint.example/v1"
API_KEY = os.getenv("MUSE_KB_API_KEY") or ""
BATCH_SIZE = 64

KB_ROOT = Path(__file__).resolve().parent.parent


def _embeddings_dir(kb_root: Path) -> Path:
    path = kb_root / "embeddings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_global_index(kb_root: Path) -> list[dict]:
    path = kb_root / "embeddings" / "scene_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _read_scene_text(kb_root: Path, entry: dict) -> str:
    rel = entry.get("file", "")
    path = kb_root / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _load_work_annotations(kb_root: Path, entry: dict) -> dict:
    rel = Path(entry.get("file", ""))
    if len(rel.parts) >= 2:
        work_dir = kb_root / rel.parts[0] / rel.parts[1]
    else:
        work_dir = kb_root / "novels" / entry.get("novel", "")

    annotations: dict = {"style_profiles": {}, "style_card": None}
    index_path = kb_index.index_path_of(work_dir)
    if index_path is not None:
        for item in kb_index.load_index(index_path):
            if item.get("scene_id") and item.get("style_profile"):
                annotations["style_profiles"][item["scene_id"]] = item["style_profile"]

    card_path = work_dir / "style_card.yaml"
    if card_path.exists():
        card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
        if isinstance(card, dict):
            annotations["style_card"] = card
    return annotations


def style_text_for_entry(kb_root: Path, entry: dict) -> str:
    """Style text surface: scene style_profile values plus work style_card values."""
    annotations = _load_work_annotations(kb_root, entry)
    profile = annotations["style_profiles"].get(entry.get("scene_id")) or entry.get("style_profile")
    if not isinstance(profile, dict):
        return ""

    parts: list[str] = []
    for blob in (profile, annotations.get("style_card")):
        if not isinstance(blob, dict):
            continue
        for value in blob.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value)
    return " ".join(parts)


def build_embed_input(scene: dict, text: str) -> str:
    parts: list[str] = []
    if scene.get("description"):
        parts.append(scene["description"])
    elif scene.get("dramatic_purpose"):
        parts.append(scene["dramatic_purpose"])
    if scene.get("tags"):
        parts.append("标签: " + ", ".join(scene["tags"]))
    if scene.get("subtext"):
        parts.append("潜台词: " + ", ".join(scene["subtext"]))
    if scene.get("characters"):
        parts.append("角色: " + ", ".join(scene["characters"]))
    elif scene.get("characters_on_stage"):
        parts.append("在场: " + ", ".join(scene["characters_on_stage"]))
    if scene.get("novel"):
        parts.append(f"作品: {scene['novel']}")
    if scene.get("source_medium") and scene["source_medium"] != "novel":
        parts.append(f"形态: {scene['source_medium']}")
    if scene.get("conflict_type"):
        parts.append(f"冲突: {scene['conflict_type']}")
    elif scene.get("conflict_axis"):
        parts.append(f"冲突轴: {scene['conflict_axis']}")
    if text:
        parts.append(text[:4000])
    return "\n".join(parts)


def _default_embed(texts: list[str], *, model: str = EMBEDDING_MODEL) -> np.ndarray:
    if not API_KEY:
        raise RuntimeError("API key 未配置：请设置 MUSE_KB_API_KEY")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        for attempt in range(1, 4):
            try:
                response = client.embeddings.create(model=model, input=batch)
                vectors.extend(item.embedding for item in response.data)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5)
    return np.array(vectors, dtype=np.float32)


def _embed_texts(texts: list[str], embed_fn=None) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    raw = embed_fn(texts) if embed_fn is not None else _default_embed(texts)
    return np.asarray(raw, dtype=np.float32)


def _target_rows(index: list[dict], novel: str | None) -> list[int]:
    if not novel:
        return list(range(len(index)))
    return [i for i, entry in enumerate(index) if novel in entry.get("novel", "")]


SNAPSHOT_NAME = "scene_index.prev.json"


def _fingerprint(path: Path) -> dict:
    data = path.read_bytes()
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _load_snapshot(kb_root: Path) -> dict | None:
    path = kb_root / "embeddings" / SNAPSHOT_NAME
    if not path.exists():
        return None
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return snap if isinstance(snap, dict) else None


def _update_snapshot(kb_root: Path, index: list[dict], npy_path: Path) -> None:
    """构建成功后原子更新快照：index 快照 + 本通道 npy 指纹。"""
    path = kb_root / "embeddings" / SNAPSHOT_NAME
    snap = _load_snapshot(kb_root) or {}
    snap["index"] = index
    fingerprints = snap.get("fingerprints") or {}
    fingerprints[npy_path.name] = _fingerprint(npy_path)
    snap["fingerprints"] = fingerprints
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _identity(entry: dict) -> tuple:
    return (entry.get("novel"), entry.get("scene_id"))


def _carry_prior(kb_root: Path, out_path: Path, index: list[dict], dim: int) -> np.ndarray:
    """按 (novel, scene_id) 身份从上次成功构建搬运向量。

    快照缺失或 npy 指纹失配 → 全部按未命中处理（零向量），stderr 明示——
    位置复用只允许经 --bootstrap 显式领养（见 bootstrap_snapshot）。
    """
    result = np.zeros((len(index), dim), dtype=np.float32)
    if dim == 0 or not out_path.exists():
        return result
    snap = _load_snapshot(kb_root)
    recorded = (snap or {}).get("fingerprints", {}).get(out_path.name)
    if snap and recorded == _fingerprint(out_path):
        old_arr = np.load(out_path)
        if old_arr.ndim == 2 and old_arr.shape[1] == dim:
            id_to_row = {_identity(e): i for i, e in enumerate(snap.get("index", []))}
            for new_i, entry in enumerate(index):
                old_i = id_to_row.get(_identity(entry))
                if old_i is not None and old_i < old_arr.shape[0]:
                    result[new_i] = old_arr[old_i]
        return result
    reason = "缺快照" if snap is None else "指纹失配"
    print(
        f"[build_embeddings] {out_path.name} {reason}：既有向量不复用（全未命中）；"
        f"存量首跑请先执行 --bootstrap 领养现有向量",
        file=sys.stderr,
    )
    return result


def bootstrap_snapshot(kb_root: str | Path = KB_ROOT) -> int:
    """一次性存量迁移：行数相等时按位置领养现有 npy 并写出快照（零 embed 成本）。"""
    kb_root = Path(kb_root)
    index = _load_global_index(kb_root)
    adopted = 0
    for name in ("scene_embeddings.npy", "style_embeddings.npy"):
        npy_path = kb_root / "embeddings" / name
        if not npy_path.exists():
            print(f"[bootstrap] {name} 不存在，跳过", file=sys.stderr)
            continue
        arr = np.load(npy_path)
        if arr.shape[0] != len(index):
            print(
                f"[bootstrap] {name} 行数 {arr.shape[0]} ≠ 索引 {len(index)}，拒绝位置领养",
                file=sys.stderr,
            )
            return 2
        _update_snapshot(kb_root, index, npy_path)
        adopted += 1
    print(f"[bootstrap] 已领养 {adopted} 个通道并写出 {SNAPSHOT_NAME}")
    return 0 if adopted else 2


def build_style_channel(kb_root: str | Path = KB_ROOT, *, embed_fn=None, novel: str | None = None) -> np.ndarray:
    kb_root = Path(kb_root)
    index = _load_global_index(kb_root)
    out_path = _embeddings_dir(kb_root) / "style_embeddings.npy"
    rows = _target_rows(index, novel)

    texts_by_row = [(row, style_text_for_entry(kb_root, index[row])) for row in rows]
    nonempty = [(row, text) for row, text in texts_by_row if text.strip()]
    embedded = _embed_texts([text for _, text in nonempty], embed_fn=embed_fn) if nonempty else None

    dim = None
    if embedded is not None and embedded.size:
        dim = int(embedded.shape[1])
    elif out_path.exists():
        dim = int(np.load(out_path).shape[1])
    if dim is None:
        dim = 0

    if novel is None:
        result = np.zeros((len(index), dim), dtype=np.float32)
    else:
        result = _carry_prior(kb_root, out_path, index, dim)
        for row in rows:
            if result.shape[1] > 0:
                result[row] = 0

    if embedded is not None and embedded.size:
        for pos, (row, _) in enumerate(nonempty):
            result[row] = embedded[pos]

    np.save(out_path, result)
    _update_snapshot(kb_root, index, out_path)
    return result


def build_content_channel(kb_root: str | Path = KB_ROOT, *, embed_fn=None, novel: str | None = None) -> np.ndarray:
    kb_root = Path(kb_root)
    index = _load_global_index(kb_root)
    out_path = _embeddings_dir(kb_root) / "scene_embeddings.npy"
    rows = _target_rows(index, novel)
    texts = [build_embed_input(index[row], _read_scene_text(kb_root, index[row])) for row in rows]
    embedded = _embed_texts(texts, embed_fn=embed_fn)

    dim = int(embedded.shape[1]) if embedded.size else None
    if dim is None:
        dim = int(np.load(out_path).shape[1]) if out_path.exists() else 0

    if novel is None:
        result = np.zeros((len(index), dim), dtype=np.float32)
    else:
        result = _carry_prior(kb_root, out_path, index, dim)
    if embedded.size:
        for pos, row in enumerate(rows):
            result[row] = embedded[pos]
    np.save(out_path, result)
    _update_snapshot(kb_root, index, out_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build KB content/style embedding channels")
    parser.add_argument("--channel", choices=("content", "style", "all"), default="all")
    parser.add_argument("--novel")
    parser.add_argument("--kb-root", default=str(KB_ROOT))
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="一次性存量迁移：行数相等时按位置领养现有 npy 并写出快照，不做任何嵌入",
    )
    args = parser.parse_args(argv)

    kb_root = Path(args.kb_root)
    if args.bootstrap:
        return bootstrap_snapshot(kb_root)
    if args.channel in {"content", "all"}:
        content = build_content_channel(kb_root, novel=args.novel)
        print(f"content_embeddings: {content.shape}")
    if args.channel in {"style", "all"}:
        style = build_style_channel(kb_root, novel=args.novel)
        print(f"style_embeddings: {style.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
