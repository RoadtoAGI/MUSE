#!/usr/bin/env python3
"""按 phase6_development.yaml 的 scenes 顺序拼接连载章 draft.md。

用法：python3 assemble_story.py <chapter_work_dir>
索引中的 file_path 定位本章 pipeline/scenes/ 内的 Markdown 正文。
所有场景可读且非空后原子替换 draft.md；输入失败时保留原稿。
审阅是否完成仍由现有章流程及 verify-review-complete hook 负责。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import yaml


class AssemblyError(Exception):
    """索引或场景不完整，不能生成章稿。"""


def assemble(work_dir: Path) -> tuple[str, int]:
    work_dir = work_dir.resolve()
    if not work_dir.is_dir():
        raise AssemblyError(f"章工作区不存在：{work_dir}")
    index_path = work_dir / "pipeline" / "phase6_development.yaml"
    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssemblyError(f"{index_path} 顶层必须为映射")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise AssemblyError(f"{index_path} 必须含非空 scenes 列表")

    scene_root = (work_dir / "pipeline" / "scenes").resolve()
    scene_ids: set[str] = set()
    scene_paths: set[Path] = set()
    parts: list[str] = []
    for number, entry in enumerate(scenes, 1):
        if not isinstance(entry, dict):
            raise AssemblyError(f"scenes 第 {number} 项必须为映射")
        scene_id = entry.get("scene_id") or entry.get("id")
        if not isinstance(scene_id, str) or not scene_id.strip():
            raise AssemblyError(f"scenes 第 {number} 项缺 scene_id")
        if scene_id in scene_ids:
            raise AssemblyError(f"scene_id 重复：{scene_id}")
        file_path = entry.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            raise AssemblyError(f"{scene_id} 缺 file_path")
        scene_path = (work_dir / file_path).resolve()
        if scene_path != (scene_root / f"scene_{scene_id}.md").resolve():
            raise AssemblyError(f"{scene_id} 的 file_path 与审阅正文不一致：{file_path}")
        if (
            not scene_path.is_relative_to(work_dir)
            or not scene_path.is_relative_to(scene_root)
            or scene_path.suffix.lower() != ".md"
        ):
            raise AssemblyError(f"{scene_id} 的 file_path 须定位本章 pipeline/scenes/ 内的 Markdown：{file_path}")
        if not scene_path.is_file():
            raise AssemblyError(f"{scene_id} 场景文件不存在：{scene_path}")
        if scene_path in scene_paths:
            raise AssemblyError(f"多个索引项指向同一场景文件：{file_path}")
        content = scene_path.read_text(encoding="utf-8")
        if not content.strip():
            raise AssemblyError(f"{scene_id} 场景文件为空：{scene_path}")
        scene_ids.add(scene_id)
        scene_paths.add(scene_path)
        parts.append(content.rstrip("\n"))
    return "\n\n".join(parts) + "\n", len(parts)


def write_draft(output_path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_path.parent,
            prefix=".draft-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(output_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python3 assemble_story.py <chapter_work_dir>", file=sys.stderr)
        return 1
    work_dir = Path(sys.argv[1]).resolve()
    try:
        draft, count = assemble(work_dir)
        output_path = work_dir / "draft.md"
        write_draft(output_path, draft)
    except (AssemblyError, OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        print(f"[assemble_story ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"draft.md 已生成：{count} 个场景，{len(draft)} 字符 → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
