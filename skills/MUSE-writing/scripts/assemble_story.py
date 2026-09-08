#!/usr/bin/env python3
"""
assemble_story.py — 按 phase6_development.yaml 中的场景顺序将场景文件拼接为 story.md

用法：
    python ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_story.py <work_dir>

输入：
    <work_dir>/pipeline/phase6_development.yaml  — 场景索引（含 file_path 字段）
    <work_dir>/pipeline/scenes/scene_*.md        — 各场景正文

输出：
    <work_dir>/story.md  — 拼接后的完整正文
"""

import os
import sys
import tempfile
from pathlib import Path

from release_eligibility import strict_phase6_scenes


def assemble(work_dir: Path) -> int:
    work_dir = work_dir.resolve()
    output_path = work_dir / "story.md"
    try:
        scenes = strict_phase6_scenes(work_dir)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    parts = []
    try:
        for scene in scenes:
            scene_path = work_dir / scene["scene_path"]
            text = scene_path.read_text(encoding="utf-8")
            if not text.strip():
                print(f"错误：场景正文为空：{scene_path}", file=sys.stderr)
                return 1
            parts.append(text.rstrip("\n"))
    except OSError as exc:
        print(f"错误：读取场景失败：{exc}", file=sys.stderr)
        return 1

    story = "\n\n".join(parts) + "\n"
    try:
        if output_path.exists():
            if output_path.read_text(encoding="utf-8") == story:
                print(f"✓ 已有 story.md 与场景装配一致：{output_path}")
                return 0
            print("错误：已有 story.md 与场景装配不同，保留当前整合稿；请从全文阶段恢复或明确处理重装配。", file=sys.stderr)
            return 1
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=work_dir, delete=False) as handle:
            handle.write(story)
            temp_path = Path(handle.name)
        try:
            # 独占发布初始稿，避免执行期间新产生的整合稿被替换。
            os.link(temp_path, output_path)
        finally:
            temp_path.unlink(missing_ok=True)
    except OSError as exc:
        print(f"错误：写入 story.md 失败：{exc}", file=sys.stderr)
        return 1
    print(f"✓ story.md 已生成：{len(parts)} 个场景，{len(story)} 字符 → {output_path}")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python assemble_story.py <work_dir>", file=sys.stderr)
        return 1
    return assemble(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
