"""TDD tests for build_character_references.py."""
import json
import sys
from pathlib import Path

import pytest

# Ensure the scripts dir is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# -------- Group 1: parse_locators --------

def test_parse_locators_simple():
    from build_character_references import parse_locators

    skill_content = """
## 声音框架
说话简洁。佐证：scenes/scene_S01.md:L2-L4
"""
    result = parse_locators(skill_content)
    assert result == [("scenes/scene_S01.md", 2, 4)]


def test_parse_locators_multiple():
    from build_character_references import parse_locators

    skill_content = "佐证：scenes/scene_S01.md:L2-L4, scenes/scene_S02.md:L5-L7"
    result = parse_locators(skill_content)
    assert result == [
        ("scenes/scene_S01.md", 2, 4),
        ("scenes/scene_S02.md", 5, 7),
    ]


def test_parse_locators_deduplication():
    from build_character_references import parse_locators

    skill_content = """
scenes/scene_S01.md:L2-L4
scenes/scene_S01.md:L2-L4
"""
    result = parse_locators(skill_content)
    assert result == [("scenes/scene_S01.md", 2, 4)]


# -------- Group 2: extract_snippet --------

def test_extract_snippet(tmp_path):
    from build_character_references import extract_snippet

    scene = tmp_path / "scene.md"
    scene.write_text("\n".join([f"line {i}" for i in range(1, 11)]) + "\n")

    result = extract_snippet(scene, 2, 4)
    assert result == "line 2\nline 3\nline 4"


def test_extract_snippet_out_of_range(tmp_path):
    from build_character_references import extract_snippet

    scene = tmp_path / "scene.md"
    scene.write_text("line 1\nline 2\n")

    with pytest.raises(IndexError):
        extract_snippet(scene, 1, 99)


# -------- Group 3: build_references (end-to-end) --------

def test_build_references_end_to_end(tmp_path):
    from build_character_references import build_references

    novel_dir = tmp_path / "novel"
    scenes = novel_dir / "scenes"
    scenes.mkdir(parents=True)
    (scenes / "scene_S01.md").write_text(
        "\n".join(f"line {i}" for i in range(1, 11)) + "\n"
    )

    chars_dir = novel_dir / "characters" / "test-role"
    chars_dir.mkdir(parents=True)
    (chars_dir / "SKILL.md").write_text("佐证：scenes/scene_S01.md:L2-L4")

    build_references(
        novel_dir=novel_dir,
        skill_file=chars_dir / "SKILL.md",
        role_slug="test-role",
        display_name="测试角色",
    )

    refs_file = chars_dir / "references" / "key-dialogues.md"
    assert refs_file.exists()
    content = refs_file.read_text()
    assert "scenes/scene_S01.md:L2-L4" in content
    assert "line 2\nline 3\nline 4" in content

    map_file = novel_dir / "characters" / "character_map.json"
    assert json.loads(map_file.read_text()) == {"测试角色": "test-role"}


def test_build_references_missing_source_file(tmp_path):
    from build_character_references import build_references

    novel_dir = tmp_path / "novel"
    (novel_dir / "scenes").mkdir(parents=True)  # but scene_X 不存在

    chars_dir = novel_dir / "characters" / "ghost"
    chars_dir.mkdir(parents=True)
    (chars_dir / "SKILL.md").write_text("佐证：scenes/nonexistent.md:L1-L2")

    with pytest.raises(FileNotFoundError):
        build_references(
            novel_dir=novel_dir,
            skill_file=chars_dir / "SKILL.md",
            role_slug="ghost",
            display_name="幽灵",
        )

    # 失败时不产出半成品文件
    assert not (chars_dir / "references" / "key-dialogues.md").exists()
    assert not (novel_dir / "characters" / "character_map.json").exists()


def test_build_references_merges_existing_map(tmp_path):
    """再次跑相同角色应幂等覆盖；其他条目保留。"""
    from build_character_references import build_references

    novel_dir = tmp_path / "novel"
    scenes = novel_dir / "scenes"
    scenes.mkdir(parents=True)
    (scenes / "scene_S01.md").write_text("a\nb\nc\n")

    chars_dir = novel_dir / "characters"
    chars_dir.mkdir(parents=True)
    (chars_dir / "character_map.json").write_text(
        json.dumps({"老角色": "old-role"}, ensure_ascii=False) + "\n"
    )

    role_dir = chars_dir / "new-role"
    role_dir.mkdir()
    (role_dir / "SKILL.md").write_text("佐证：scenes/scene_S01.md:L1-L2")

    build_references(
        novel_dir=novel_dir,
        skill_file=role_dir / "SKILL.md",
        role_slug="new-role",
        display_name="新角色",
    )

    mapping = json.loads((chars_dir / "character_map.json").read_text())
    assert mapping == {"老角色": "old-role", "新角色": "new-role"}


# -------- Group 4: 续写工作区模式（--scenes-base / --character-map） --------

def test_build_references_with_scenes_base_and_custom_map(tmp_path):
    """续写工作区模式：scenes 和 map 路径完全自定义，不依赖 novel-dir 结构。"""
    from build_character_references import build_references

    # 续写工作区：角色在 results/personal/.../女生节系列/distilled/
    workspace = tmp_path / "results" / "personal" / "model" / "女生节系列"
    role_dir = workspace / "distilled" / "ye-wenjie"
    role_dir.mkdir(parents=True)
    (role_dir / "SKILL.md").write_text(
        "佐证：scenes/scene_S01.md:L1-L2", encoding="utf-8"
    )

    # scenes 在完全独立的路径（比如知识库目录）
    scenes_base = tmp_path / "kb" / "novels" / "三体Ⅰ"
    (scenes_base / "scenes").mkdir(parents=True)
    (scenes_base / "scenes" / "scene_S01.md").write_text("line1\nline2\n")

    # character_map 在又一个独立位置
    map_path = workspace / "shared-character-map.json"

    build_references(
        novel_dir=None,
        skill_file=role_dir / "SKILL.md",
        role_slug="ye-wenjie",
        display_name="叶文洁",
        scenes_base=scenes_base,
        character_map_path=map_path,
    )

    # key-dialogues 切出来
    refs_file = role_dir / "references" / "key-dialogues.md"
    assert refs_file.exists()
    assert "line1\nline2" in refs_file.read_text()

    # map 落在自定义位置
    assert map_path.exists()
    assert json.loads(map_path.read_text()) == {"叶文洁": "ye-wenjie"}


def test_build_references_scenes_base_without_map_skips_map_update(tmp_path):
    """续写工作区模式下不传 character_map_path → 跳过 map 更新。"""
    from build_character_references import build_references

    role_dir = tmp_path / "role-dir"
    role_dir.mkdir()
    (role_dir / "SKILL.md").write_text(
        "佐证：scenes/scene_S01.md:L1-L2", encoding="utf-8"
    )

    scenes_base = tmp_path / "scenes-base"
    (scenes_base / "scenes").mkdir(parents=True)
    (scenes_base / "scenes" / "scene_S01.md").write_text("a\nb\n")

    build_references(
        novel_dir=None,
        skill_file=role_dir / "SKILL.md",
        role_slug="test",
        display_name="测试",
        scenes_base=scenes_base,
        character_map_path=None,
    )

    # key-dialogues 切出来
    assert (role_dir / "references" / "key-dialogues.md").exists()
    # map 未被创建（工作区内没有 character_map.json 任何痕迹）
    assert not any(p.name == "character_map.json" for p in tmp_path.rglob("*"))


def test_build_references_legacy_novel_dir_still_works(tmp_path):
    """向后兼容：只传 --novel-dir 仍可工作（scenes_base 和 map 位置都从 novel-dir 推导）。"""
    from build_character_references import build_references

    novel_dir = tmp_path / "novel"
    (novel_dir / "scenes").mkdir(parents=True)
    (novel_dir / "scenes" / "scene_S01.md").write_text("a\nb\n")

    chars = novel_dir / "characters"
    role_dir = chars / "test"
    role_dir.mkdir(parents=True)
    (role_dir / "SKILL.md").write_text("佐证：scenes/scene_S01.md:L1-L2")

    build_references(
        novel_dir=novel_dir,
        skill_file=role_dir / "SKILL.md",
        role_slug="test",
        display_name="测试",
    )

    # key-dialogues 和 map 都在 novel-dir 下
    assert (role_dir / "references" / "key-dialogues.md").exists()
    assert (chars / "character_map.json").exists()
