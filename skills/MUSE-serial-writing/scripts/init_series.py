#!/usr/bin/env python3
"""init_series.py — 连载系列新作工作区骨架初始化

按 serial-outline workspace-schema 建 works/<slug>/ 目录树 + 落位初始 YAML：
  - series/story_bible.yaml：从模板落位占位（后续共创立项对话整篇覆盖）
  - series/series_state.yaml：写真正的初始状态机（不沿用模板示例中途态）
  - series/ledgers/{threads,world_facts}.yaml：append-only 台账，新工作区写真空结构
    （不沿用模板示例行——避免虚构条目混入真实项目的台账真值源）
  - series/ledgers/characters/：留空目录（char_id 待 phase2 产出角色档案后才存在）
  - published/manifest.yaml：发布序真值，新工作区写真空结构

Usage:
    python3 init_series.py --slug my-series --works-root works/
    python3 init_series.py --slug my-series --works-root works/ --title "我的连载"

stdout 末行输出工作区绝对路径，供 orchestrator 作为后续 series 操作的 work_dir。

模板定位优先级：
    1. 环境变量 CLAUDE_PLUGIN_ROOT（plugin 安装态）
    2. 脚本自身路径相对回溯（开发态 monorepo 路径）

失败语义：已存在同 slug / slug 格式非法 / 模板目录找不到 → exit 2（阻断）。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# works/<slug>/ 骨架子目录（series/story_bible.yaml 与 series/series_state.yaml
# 落在 series/ 下，series/ 本身随首个文件写入一并创建，此处只列不随文件写入
# 自动创建的目录）
SKELETON_SUBDIRS = [
    "series/volumes",
    "series/digests",
    "series/ledgers",
    "series/ledgers/characters",
    "series/decisions",
    "series/worldbook",
    "series/character-skills",
    "chapters",
    "published",
]


def validate_slug(slug: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        print(
            f"[init_series ERROR] --slug 必须是 ASCII kebab-case（如 my-series），实为：{slug!r}",
            file=sys.stderr,
        )
        sys.exit(2)


def validate_title(title: str | None) -> None:
    if title is not None and ("\n" in title or "\r" in title):
        print(
            f"[init_series ERROR] --title 不能含换行符（\\n 或 \\r）",
            file=sys.stderr,
        )
        sys.exit(2)


def find_templates_root() -> Path:
    """定位 serial-outline references/templates/ 目录。

    优先级：
      1. 环境变量 CLAUDE_PLUGIN_ROOT（plugin 安装态，${CLAUDE_PLUGIN_ROOT}/skills/...）
      2. 脚本自身路径相对回溯（开发态 monorepo 路径）
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = Path(plugin_root) / "skills" / "serial-outline" / "references" / "templates"
        if candidate.is_dir():
            return candidate

    here = Path(__file__).resolve().parents[1]
    candidate = here / "skills" / "serial-outline" / "references" / "templates"
    if candidate.is_dir():
        return candidate

    print("[init_series ERROR] 无法定位 serial-outline 模板目录", file=sys.stderr)
    print(
        "  尝试过：env CLAUDE_PLUGIN_ROOT/skills/serial-outline/references/templates；"
        "脚本相对路径 <plugin_root>/skills/serial-outline/references/templates",
        file=sys.stderr,
    )
    sys.exit(2)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_yaml(path: Path, data) -> None:
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    atomic_write_text(path, content)


def copy_story_bible(templates_root: Path, dest: Path, title: str | None) -> None:
    """落位 story_bible.yaml 模板占位（frozen/intent 由后续共创立项对话整篇覆盖）。

    title 非空时在头部注释后插入一行标题注释，不改动 schema 字段结构。
    """
    src = templates_root / "story_bible.yaml"
    if not src.is_file():
        print(f"[init_series ERROR] 模板缺失: {src}", file=sys.stderr)
        sys.exit(2)
    text = src.read_text(encoding="utf-8")
    if title:
        lines = text.splitlines(keepends=True)
        lines.insert(1, f"# 系列名：{title}\n")
        text = "".join(lines)
    atomic_write_text(dest, text)


def build_series_state(slug: str) -> dict:
    """新工作区的真正初始状态机（全部字段按 workspace-schema 初始态语义写死，
    不沿用模板示例中的"进行中"态）。"""
    return {
        "schema_version": 1,
        "work_slug": slug,
        "collaboration_mode": "volume",
        "active_session": None,
        "cursor": {
            "volume": None,
            "working_chapter": None,
            "stage": "breaking",
        },
        "pending": None,
        "buffer": {
            "drafted_unpublished": [],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--slug", required=True, help="工作区 slug（ASCII kebab-case，必填）")
    ap.add_argument("--works-root", default="works/", help="works 根目录（默认 works/）")
    ap.add_argument("--title", help="系列标题（可选；写入 story_bible.yaml 头部注释）")
    args = ap.parse_args()

    validate_slug(args.slug)
    validate_title(args.title)

    works_root = Path(args.works_root)
    works_root.mkdir(parents=True, exist_ok=True)
    works_root = works_root.resolve()
    work_dir = works_root / args.slug

    if work_dir.exists():
        print(f"[init_series ERROR] 工作区已存在：{work_dir}", file=sys.stderr)
        sys.exit(2)

    templates_root = find_templates_root()

    for sub in SKELETON_SUBDIRS:
        (work_dir / sub).mkdir(parents=True, exist_ok=True)

    if os.environ.get("MUSE_NEW_WORK_TEMPLATE"):
        from muse_runtime.bootstrap import initialize_new_work
        initialize_new_work(work_dir)

    copy_story_bible(templates_root, work_dir / "series" / "story_bible.yaml", args.title)
    atomic_write_yaml(work_dir / "series" / "series_state.yaml", build_series_state(args.slug))

    # 类型档案与设定集注册表：写"待判定/真空"结构，不落模板示例值——
    # substrate 等由大纲 S1 类型判定后覆盖；worldbook 分册由 S2 按 genre-pack 实例化
    atomic_write_yaml(
        work_dir / "series" / "genre_profile.yaml",
        {
            "schema_version": 1,
            "substrate": None,
            "engine": {"primary": None, "secondary": None},
            "mainline_type": None,
            "tags": [],
            "pacing_contract": None,
            "benchmark": [],
            "substrate_config": {},
        },
    )
    atomic_write_yaml(
        work_dir / "series" / "worldbook" / "index.yaml",
        {"schema_version": 1, "sections": []},
    )

    # 三台账：append-only 真值源，新工作区写真空结构（不沿用模板示例行）
    atomic_write_yaml(
        work_dir / "series" / "ledgers" / "threads.yaml",
        {"schema_version": 1, "threads": []},
    )
    atomic_write_yaml(
        work_dir / "series" / "ledgers" / "world_facts.yaml",
        {"schema_version": 1, "facts": []},
    )
    # series/ledgers/characters/ 留空：char_id 待 phase2 产出角色档案后才存在，
    # 无法预先落位 biography.yaml（其路径是 characters/<char_id>/biography.yaml）

    atomic_write_yaml(
        work_dir / "published" / "manifest.yaml",
        {"schema_version": 1, "entries": [], "revisions": []},
    )

    print(f"[init_series] 工作区已建：{work_dir}", file=sys.stderr)
    print(work_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
