"""按 SKILL.md 中的原文引用定位切片，生成 references/key-dialogues.md 并更新 character_map.json。

用法：
    python build_character_references.py \\
        --novel-dir path/to/novels/书名 \\
        --skill-file path/to/characters/role-slug/SKILL.md \\
        --role-slug role-slug \\
        --display-name 中文名

定位格式（在 SKILL.md 文本中）：
    {relative-path}:L{start}-L{end}
例：
    scenes/scene_S01.md:L2-L4
    full_text.md:L1023-L1080
多定位可以在同一行用逗号分隔。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LOCATOR_PATTERN = re.compile(r"([\w\-/.]+\.md):L(\d+)-L(\d+)")


def parse_locators(skill_content: str) -> list[tuple[str, int, int]]:
    """从 SKILL.md 文本中提取所有原文引用定位，去重保序。"""
    matches = LOCATOR_PATTERN.findall(skill_content)
    seen: set[tuple[str, int, int]] = set()
    result: list[tuple[str, int, int]] = []
    for path, start, end in matches:
        key = (path, int(start), int(end))
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def extract_snippet(file_path: Path, start_line: int, end_line: int) -> str:
    """按 1-based 行号 [start_line, end_line] 从文件中切出原文片段。

    - 越界（end_line 超过文件总行数）抛 IndexError
    - start_line < 1 或 start_line > end_line 抛 ValueError
    """
    if start_line < 1 or start_line > end_line:
        raise ValueError(
            f"{file_path}: 无效的行号区间 L{start_line}-L{end_line}"
        )
    lines = file_path.read_text(encoding="utf-8").splitlines()
    if end_line > len(lines):
        raise IndexError(
            f"{file_path}: L{end_line} 超出文件总行数 {len(lines)}"
        )
    return "\n".join(lines[start_line - 1:end_line])


def build_references(
    novel_dir: Path | None,
    skill_file: Path,
    role_slug: str,
    display_name: str,
    *,
    scenes_base: Path | None = None,
    character_map_path: Path | None = None,
) -> None:
    """端到端：解析 SKILL.md 定位 → 切片 → 写 key-dialogues.md → 更新 character_map.json。

    路径解析优先级（两种调用模式）：
    - 知识库模式：传 novel_dir，scenes_base 默认 = novel_dir，character_map_path 默认
      = {novel_dir}/characters/character_map.json
    - 续写工作区模式：novel_dir=None，必须显式传 scenes_base；character_map_path
      不传则**跳过 map 更新**（不产出 map 文件）

    显式传入的 scenes_base / character_map_path 会覆盖 novel_dir 的默认推导。

    先完整解析并切片所有片段（任何失败立即抛异常，不产半成品），
    最后才写目标文件，保证失败路径下目标目录不出现中间态。
    """
    if not skill_file.exists():
        raise FileNotFoundError(f"SKILL.md 不存在：{skill_file}")

    # 路径解析：scenes_base 必须能确定
    effective_scenes_base = scenes_base if scenes_base is not None else novel_dir
    if effective_scenes_base is None:
        raise ValueError(
            "必须传入 scenes_base 或 novel_dir 其一作为 locator 解析基准"
        )

    # character_map 位置：显式 > novel_dir 默认 > None（跳过）
    if character_map_path is not None:
        map_file: Path | None = character_map_path
    elif novel_dir is not None:
        map_file = novel_dir / "characters" / "character_map.json"
    else:
        map_file = None  # 续写工作区不传 map → 跳过

    skill_content = skill_file.read_text(encoding="utf-8")
    locators = parse_locators(skill_content)

    if not locators:
        raise ValueError(
            f"SKILL.md 未解析到任何引用定位（期望格式 path:L{{start}}-L{{end}}）：{skill_file}"
        )

    # 第一轮：全部切片到内存；任何失败在此抛出，不写任何目标文件
    sections: list[str] = []
    for rel_path, start, end in locators:
        source = effective_scenes_base / rel_path
        if not source.exists():
            raise FileNotFoundError(f"定位指向的文件不存在：{source}")
        snippet = extract_snippet(source, start, end)
        sections.append(f"### {rel_path}:L{start}-L{end}\n\n{snippet}\n")

    # 预读 character_map.json（如 map_file 非 None 且文件存在则先 parse）
    mapping: dict = {}
    if map_file is not None and map_file.exists():
        try:
            mapping = json.loads(map_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"character_map.json 解析失败：{map_file} ({e})") from e
        if not isinstance(mapping, dict):
            raise ValueError(f"character_map.json 顶层必须是对象：{map_file}")

    # 第二轮：写目标文件（走到这里意味着所有切片、JSON 解析都成功）
    refs_dir = skill_file.parent / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    header = f"# {display_name} · 关键原文引用\n\n"
    (refs_dir / "key-dialogues.md").write_text(header + "\n".join(sections), encoding="utf-8")

    # map 更新（map_file is None → 跳过）
    if map_file is not None:
        mapping[display_name] = role_slug
        map_file.parent.mkdir(parents=True, exist_ok=True)
        map_file.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "按 SKILL.md 中的原文引用定位切片生成 references/key-dialogues.md。\n"
            "两种模式：\n"
            "  A) 知识库：--novel-dir（scenes 和 map 位置从 novel-dir 推导）\n"
            "  B) 续写工作区：--scenes-base 指定 locator 解析基准；\n"
            "     --character-map 可选指定 map 位置，不传则跳过 map 更新"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--skill-file", required=True, type=Path)
    parser.add_argument("--role-slug", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--novel-dir",
        type=Path,
        help="知识库小说根目录；scenes_base 和 character_map 默认从此推导",
    )
    parser.add_argument(
        "--scenes-base",
        type=Path,
        help=(
            "locator 解析基准（覆盖 --novel-dir 默认值）。\n"
            "续写工作区模式下必传。"
        ),
    )
    parser.add_argument(
        "--character-map",
        type=Path,
        help=(
            "character_map.json 显式位置（覆盖 --novel-dir 默认值）。\n"
            "续写工作区模式下不传则跳过 map 更新。"
        ),
    )
    args = parser.parse_args()

    if args.novel_dir is None and args.scenes_base is None:
        print(
            "ERROR: 必须传入 --novel-dir 或 --scenes-base 其一",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        build_references(
            novel_dir=args.novel_dir,
            skill_file=args.skill_file,
            role_slug=args.role_slug,
            display_name=args.display_name,
            scenes_base=args.scenes_base,
            character_map_path=args.character_map,
        )
    except (FileNotFoundError, IndexError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
