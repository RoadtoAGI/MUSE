#!/usr/bin/env python3
"""snapshot_character.py — 卷收束角色快照骨架生成

把 `series/ledgers/characters/<char_id>/biography.yaml` 的**本卷 milestones**
与**上一卷快照**合并为 `snapshots/V##.yaml` 骨架，`extends` 指上一卷快照、
`delta` 字段留空，供卷收束环节调用蒸馏 subagent 后续填写。

本脚本不调 LLM（纯机械字段筛选 + YAML 骨架生成）。

用法：
    python3 snapshot_character.py --work-dir <works/<slug>/ 工作区根> \
        --volume V02 --char fangyan

"本卷 milestones" 判定：milestone.at 的章号（`C####` 或 `C####S##` 取前
5 位）落在 `series/volumes/V##.yaml` 卷纲 `chapters[].chapter_id` 集合内。

"上一卷"判定：按卷号数字序（V01<V02<...）小于本卷的已有快照文件
（`snapshots/V*.yaml`）中最大者；不存在 → 兜底 `V00`；`V00.yaml` 也不
存在 → 数据错（exit 1，需先经 character-system-design 产开工设计投影）。

幂等：目标快照 `snapshots/V##.yaml` 已存在 → 不覆盖（可能已被蒸馏环节
填充），stderr 提示 exit 0。

失败语义：
    0 — 完成，或目标快照已存在（幂等跳过）
    1 — 数据错：biography.yaml 缺失/解析失败 / 无 V00 基线 / 卷纲缺失或解析失败
    2 — 用法错：--volume 不匹配 `V\\d{2}`
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import yaml

from yaml_resilient import load_yaml_resilient

VOL_RE = re.compile(r"^V\d{2}$")
# milestone.at：C#### 或 C####S##，章号取前 5 位（C + 4 位数字）
MILESTONE_AT_CHAPTER_RE = re.compile(r"^(C\d{4})(S\d{2})?$")


class DataError(Exception):
    """biography / 卷纲 / 快照基线缺失或解析失败。"""


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_yaml(path: Path, data: dict) -> None:
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    atomic_write_text(path, content)


def load_yaml_required(path: Path, label: str) -> dict:
    """文件不存在或解析失败一律 DataError（区分 fail-fast 语义与缺字段 fallback）。"""
    if not path.exists():
        raise DataError(f"{label} 不存在: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        doc, report = load_yaml_resilient(text)
    except yaml.YAMLError as exc:
        raise DataError(f"{label} YAML 解析失败: {path}: {exc}") from exc
    if report.recovered_lines:
        sys.stderr.write(
            f"[snapshot_character] WARN: {path} 自动修复了双引号越界行 "
            f"{report.recovered_lines}\n"
        )
    if not isinstance(doc, dict):
        raise DataError(f"{label} 顶层必须是 mapping: {path}")
    return doc


def _volume_number(vol_id: str) -> int | None:
    m = re.match(r"^V(\d+)$", vol_id)
    return int(m.group(1)) if m else None


def find_previous_snapshot_id(snapshots_dir: Path, volume_id: str) -> str:
    """按卷号数字序找小于本卷的既有快照文件中最大者；无 → 兜底 V00。

    V00.yaml 缺失（既无更早快照也无 V00 基线）→ DataError（数据错，需先
    产出 character-system-design 开工设计投影）。
    """
    current_num = _volume_number(volume_id)
    best_num = None
    best_id = None
    if snapshots_dir.is_dir():
        for snap_path in snapshots_dir.glob("V*.yaml"):
            num = _volume_number(snap_path.stem)
            if num is None or (current_num is not None and num >= current_num):
                continue
            if best_num is None or num > best_num:
                best_num, best_id = num, snap_path.stem

    if best_id is not None:
        return best_id

    # 无更早快照 → 兜底 V00
    if (snapshots_dir / "V00.yaml").is_file():
        return "V00"

    raise DataError(
        f"{snapshots_dir}: 找不到早于 {volume_id} 的既有快照，且无 V00.yaml 基线"
        "（需先经 character-system-design 产开工设计投影）"
    )


def load_volume_chapter_ids(work_dir: Path, volume_id: str) -> set[str]:
    """读 series/volumes/V##.yaml，返回 chapters[].chapter_id 集合。"""
    volume_path = work_dir / "series" / "volumes" / f"{volume_id}.yaml"
    data = load_yaml_required(volume_path, "卷纲")
    chapter_ids: set[str] = set()
    for entry in data.get("chapters") or []:
        if isinstance(entry, dict) and entry.get("chapter_id"):
            chapter_ids.add(entry["chapter_id"])
    return chapter_ids


def milestone_chapter_id(at: str) -> str | None:
    """从 milestone.at（`C####` 或 `C####S##`）提取裸章号；不匹配 → None。"""
    if not isinstance(at, str):
        return None
    m = MILESTONE_AT_CHAPTER_RE.match(at)
    return m.group(1) if m else None


def filter_milestones_in_volume(milestones: list, chapter_ids: set[str]) -> list:
    in_volume = []
    for milestone in milestones:
        if not isinstance(milestone, dict):
            continue
        chapter_id = milestone_chapter_id(milestone.get("at"))
        if chapter_id is not None and chapter_id in chapter_ids:
            in_volume.append(dict(milestone))
    return in_volume


def build_snapshot_skeleton(
    char_id: str, volume_id: str, extends: str, milestones_in_volume: list,
) -> dict:
    return {
        "schema_version": 1,
        "char_id": char_id,
        "volume_id": volume_id,
        "extends": extends,
        "milestones_in_volume": milestones_in_volume,
        "delta": {
            "state": None,
            "relationships": [],
            "capabilities": [],
            "voice_shift": None,
        },
    }


def run(work_dir: Path, volume_id: str, char_id: str) -> tuple[Path, bool]:
    """返回 (输出路径, 是否幂等跳过)。"""
    char_dir = work_dir / "series" / "ledgers" / "characters" / char_id
    biography_path = char_dir / "biography.yaml"
    snapshots_dir = char_dir / "snapshots"
    output_path = snapshots_dir / f"{volume_id}.yaml"

    if output_path.is_file():
        return output_path, True

    biography = load_yaml_required(biography_path, f"{char_id} biography.yaml")
    chapter_ids = load_volume_chapter_ids(work_dir, volume_id)
    extends = find_previous_snapshot_id(snapshots_dir, volume_id)

    milestones = biography.get("milestones") or []
    milestones_in_volume = filter_milestones_in_volume(milestones, chapter_ids)

    skeleton = build_snapshot_skeleton(char_id, volume_id, extends, milestones_in_volume)
    manifest_path = work_dir / "published" / "manifest.yaml"
    if manifest_path.is_file():
        manifest = load_yaml_required(manifest_path, "published manifest")
        published = [e for e in manifest.get("entries") or []
                     if isinstance(e, dict) and e.get("chapter_id") in chapter_ids]
        if published:
            if any(type(e.get("published_seq")) is not int for e in published):
                raise DataError("manifest published_seq 缺失或非法")
            skeleton["through_chapter"] = max(published, key=lambda e: e["published_seq"])["chapter_id"]
    atomic_write_yaml(output_path, skeleton)
    return output_path, False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--work-dir", required=True, type=Path, help="works/<slug>/ 工作区根")
    parser.add_argument("--volume", required=True, help="卷号，如 V02")
    parser.add_argument("--char", required=True, help="角色 char_id")
    args = parser.parse_args()

    work_dir: Path = args.work_dir.resolve()
    if not work_dir.is_dir():
        print(f"[snapshot_character] ERROR: --work-dir 不存在或不是目录: {work_dir}", file=sys.stderr)
        return 2

    if not VOL_RE.match(args.volume):
        print(f"[snapshot_character] ERROR: --volume 必须匹配 V\\d{{2}}，实为 {args.volume!r}", file=sys.stderr)
        return 2

    try:
        output_path, skipped = run(work_dir, args.volume, args.char)
    except DataError as exc:
        print(f"[snapshot_character] ERROR: {exc}", file=sys.stderr)
        return 1

    if skipped:
        print(
            f"[snapshot_character] 已存在，跳过（幂等）: {output_path}", file=sys.stderr,
        )
    else:
        print(f"[snapshot_character] snapshot skeleton written: {output_path}", file=sys.stderr)
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
