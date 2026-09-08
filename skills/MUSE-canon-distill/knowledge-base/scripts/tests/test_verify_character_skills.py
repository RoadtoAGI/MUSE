"""verify_character_skills.py 的结构校验测试。

校验 4 项硬约束：
1. parse_locators(SKILL.md) 数量
2. count(key-dialogues.md sections) 数量
3. build-meta.yaml.locator_count
4. character_map.json 包含 {display_name: role_slug}

三处 locator 计数必须一致 + character_map 含对应条目，否则 fail。
"""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from verify_character_skills import (  # noqa: E402
    check_all_sections_have_locator,
    check_boundary_each_bullet_has_locator,
    check_claims,
    check_frontmatter_complete,
    check_review_log,
    check_role_slug_consistency,
    check_slug_format,
    collect_role_dirs,
    count_dialogue_sections,
    parse_frontmatter,
    parse_sections,
    verify_role,
)


_FULL_SKILL_TEMPLATE = """\
---
name: test-role
description: 测试角色 — 参考用
version: 1
allowed-tools: Read
---

# 测试角色

## 身份与处境

xxx 佐证：scenes/scene_01.md:L1-L3

## 核心欲望

xxx 佐证：scenes/scene_02.md:L1-L3

## 性格真相

xxx 佐证：scenes/scene_03.md:L1-L3

## 声音框架

xxx 佐证：scenes/scene_04.md:L1-L3

## 边界（Layer 0 硬规则）

- 边界 1 ← 佐证：scenes/scene_05.md:L1-L3
- 边界 2 ← 佐证：scenes/scene_06.md:L1-L3
- 边界 3 ← 佐证：scenes/scene_07.md:L1-L3

## 弧光（已完成）

xxx 佐证：scenes/scene_08.md:L1-L3
"""


_DEFAULT_LOCATOR_COUNT = 8  # 6 章节共 8 个 locator（边界 3 + 其他 5 各 1）


def _build_role(tmp_path: Path, *, locator_count_in_meta: int | None = None,
                key_dialogue_sections: int | None = None,
                map_has_entry: bool = True) -> tuple[Path, Path]:
    """搭一个最小的可校验角色目录，六章节齐全 + 每章节有 locator + 边界每条有 locator。

    默认 happy path：8 个 locator（匹配 _FULL_SKILL_TEMPLATE），
    8 个 key-dialogues sections，build-meta locator_count=8，character_map 含条目。
    """
    novel_dir = tmp_path / "novel"
    chars_dir = novel_dir / "characters"
    role_dir = chars_dir / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    # SKILL.md：六章节齐全，共 8 个 locator（每非边界章 1 个，边界 3 个 bullet 各 1 个）
    (role_dir / "SKILL.md").write_text(_FULL_SKILL_TEMPLATE, encoding="utf-8")

    # key-dialogues.md：默认 8 个 section 与 locator 对齐
    n_sections = key_dialogue_sections if key_dialogue_sections is not None else _DEFAULT_LOCATOR_COUNT
    sections = "\n".join(
        f"### scenes/scene_{i:02d}.md:L1-L3\n\nline content {i}\n"
        for i in range(1, n_sections + 1)
    )
    (refs_dir / "key-dialogues.md").write_text(
        f"# 测试角色 · 关键原文引用\n\n{sections}", encoding="utf-8"
    )

    # build-meta.yaml：默认 locator_count=8
    n_meta = locator_count_in_meta if locator_count_in_meta is not None else _DEFAULT_LOCATOR_COUNT
    meta_content = f"""\
mode: reference
display_name: 测试角色
role_slug: test-role
source_novel: 测试小说
locator_count: {n_meta}
"""
    (role_dir / "build-meta.yaml").write_text(meta_content, encoding="utf-8")

    # character_map.json
    if map_has_entry:
        mapping = {"测试角色": "test-role"}
    else:
        mapping = {"别人": "other-role"}
    (chars_dir / "character_map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return novel_dir, role_dir


def test_count_dialogue_sections(tmp_path):
    f = tmp_path / "key.md"
    f.write_text("""\
# header
### scenes/scene_01.md:L2-L4

content 1

### scenes/scene_02.md:L5-L7

content 2
""", encoding="utf-8")
    assert count_dialogue_sections(f) == 2


def test_count_dialogue_sections_ignores_other_h3(tmp_path):
    f = tmp_path / "key.md"
    f.write_text("""\
### scenes/scene_01.md:L2-L4
content
### 普通三级标题（不是 locator 格式）
content
""", encoding="utf-8")
    assert count_dialogue_sections(f) == 1


def test_verify_role_all_pass(tmp_path):
    novel_dir, role_dir = _build_role(tmp_path)
    issues = verify_role(novel_dir, role_dir)
    assert issues == []


def test_verify_role_locator_vs_section_mismatch(tmp_path):
    # SKILL.md 有 8 个 locator（默认），但 key-dialogues 只有 2 个 section
    novel_dir, role_dir = _build_role(tmp_path, key_dialogue_sections=2)
    issues = verify_role(novel_dir, role_dir)
    assert any("locator" in i and "section" in i for i in issues)
    assert any("8" in i and "2" in i for i in issues)


def test_verify_role_meta_locator_count_mismatch(tmp_path):
    # SKILL.md 实际 3 个 locator，但 build-meta 写 7
    novel_dir, role_dir = _build_role(tmp_path, locator_count_in_meta=7)
    issues = verify_role(novel_dir, role_dir)
    assert any("build-meta" in i for i in issues)


def test_verify_role_missing_map_entry(tmp_path):
    novel_dir, role_dir = _build_role(tmp_path, map_has_entry=False)
    issues = verify_role(novel_dir, role_dir)
    assert any("character_map" in i for i in issues)


def test_verify_role_missing_skill_md(tmp_path):
    novel_dir, role_dir = _build_role(tmp_path)
    (role_dir / "SKILL.md").unlink()
    issues = verify_role(novel_dir, role_dir)
    assert any("SKILL.md" in i for i in issues)


def test_verify_role_corrupt_meta_top_level_list(tmp_path):
    """build-meta.yaml 顶层是 list（不是 dict）→ 不应崩溃，应报 issue。"""
    novel_dir, role_dir = _build_role(tmp_path)
    (role_dir / "build-meta.yaml").write_text("- a\n- b\n", encoding="utf-8")
    issues = verify_role(novel_dir, role_dir)
    assert any("build-meta.yaml" in i and "mapping" in i for i in issues)


def test_verify_role_corrupt_meta_top_level_scalar(tmp_path):
    """build-meta.yaml 顶层是 scalar → 不应崩溃，应报 issue。"""
    novel_dir, role_dir = _build_role(tmp_path)
    (role_dir / "build-meta.yaml").write_text("just a string\n", encoding="utf-8")
    issues = verify_role(novel_dir, role_dir)
    assert any("build-meta.yaml" in i and "mapping" in i for i in issues)


def test_verify_role_corrupt_map_top_level_list(tmp_path):
    """character_map.json 顶层是 list（不是 object）→ 不应崩溃，应报 issue。"""
    novel_dir, role_dir = _build_role(tmp_path)
    map_file = novel_dir / "characters" / "character_map.json"
    map_file.write_text('["test-role"]', encoding="utf-8")
    issues = verify_role(novel_dir, role_dir)
    assert any("character_map.json" in i and "object" in i for i in issues)


def test_collect_role_dirs_skips_non_skill_dirs(tmp_path):
    """collect_role_dirs 必须跳过不含 SKILL.md 的子目录（如旧分组目录）。"""
    chars_dir = tmp_path / "characters"
    chars_dir.mkdir()

    # 真角色目录（含 SKILL.md）
    (chars_dir / "guo-jing").mkdir()
    (chars_dir / "guo-jing" / "SKILL.md").write_text("# 郭靖", encoding="utf-8")
    (chars_dir / "huang-rong").mkdir()
    (chars_dir / "huang-rong" / "SKILL.md").write_text("# 黄蓉", encoding="utf-8")

    # 旧分组目录（无 SKILL.md，模拟射雕的 "主角与镜像/" "五绝/" 等）
    (chars_dir / "主角与镜像").mkdir()
    (chars_dir / "主角与镜像" / "郭靖.md").write_text("# 郭靖（旧画像）", encoding="utf-8")
    (chars_dir / "五绝").mkdir()
    (chars_dir / "五绝" / "黄药师.md").write_text("# 黄药师", encoding="utf-8")

    # 散文件（不应被当目录处理）
    (chars_dir / "character_map.json").write_text("{}", encoding="utf-8")

    result = collect_role_dirs(chars_dir)
    assert sorted(d.name for d in result) == ["guo-jing", "huang-rong"]


def test_collect_role_dirs_empty_when_no_role_artifacts(tmp_path):
    """只含散 .md 文件的目录（旧分组目录式样）不应被收。"""
    chars_dir = tmp_path / "characters"
    chars_dir.mkdir()
    (chars_dir / "old-group").mkdir()
    (chars_dir / "old-group" / "notes.md").write_text("not a skill", encoding="utf-8")
    assert collect_role_dirs(chars_dir) == []


def test_collect_role_dirs_captures_corrupt_role_with_only_meta(tmp_path):
    """损坏角色目录：build-meta.yaml 存在但 SKILL.md 缺失 → 必须被收，
    交给 verify_role 准确报"SKILL.md 不存在"，避免静默跳过损坏状态。"""
    chars_dir = tmp_path / "characters"
    chars_dir.mkdir()
    corrupt_dir = chars_dir / "corrupt-role"
    corrupt_dir.mkdir()
    (corrupt_dir / "build-meta.yaml").write_text("display_name: 损坏\n", encoding="utf-8")

    result = collect_role_dirs(chars_dir)
    assert [d.name for d in result] == ["corrupt-role"]


def test_collect_role_dirs_captures_partial_role_with_only_key_dialogues(tmp_path):
    """损坏角色目录：仅 references/key-dialogues.md 存在 → 必须被收。"""
    chars_dir = tmp_path / "characters"
    chars_dir.mkdir()
    partial_dir = chars_dir / "partial-role"
    refs_dir = partial_dir / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "key-dialogues.md").write_text("# 部分", encoding="utf-8")

    result = collect_role_dirs(chars_dir)
    assert [d.name for d in result] == ["partial-role"]


def test_verify_role_reports_corrupt_dir_missing_skill(tmp_path):
    """端到端：collect_role_dirs 收损坏目录后，verify_role 应报缺 SKILL.md。"""
    chars_dir = tmp_path / "characters"
    chars_dir.mkdir()
    corrupt_dir = chars_dir / "corrupt-role"
    corrupt_dir.mkdir()
    (corrupt_dir / "build-meta.yaml").write_text(
        "display_name: 损坏\nlocator_count: 5\n", encoding="utf-8"
    )

    collected = collect_role_dirs(chars_dir)
    assert len(collected) == 1
    issues = verify_role(tmp_path, collected[0])
    assert any("SKILL.md 不存在" in i for i in issues)


# ---- 新硬约束：每章节至少 1 locator + 边界每条 bullet 有 locator ----

def test_parse_sections_all_six_found():
    sections = parse_sections(_FULL_SKILL_TEMPLATE)
    assert set(sections.keys()) == {"身份", "核心欲望", "性格真相", "声音框架", "边界", "弧光"}


def test_parse_sections_missing_section_absent_from_dict():
    skill = _FULL_SKILL_TEMPLATE.replace("## 核心欲望\n\nxxx 佐证：scenes/scene_02.md:L1-L3\n\n", "")
    sections = parse_sections(skill)
    assert "核心欲望" not in sections
    assert "身份" in sections


def test_check_all_sections_have_locator_happy():
    sections = parse_sections(_FULL_SKILL_TEMPLATE)
    assert check_all_sections_have_locator(sections) == []


def test_check_all_sections_have_locator_missing_one():
    # 把 声音框架 的 locator 去掉
    skill = _FULL_SKILL_TEMPLATE.replace(
        "xxx 佐证：scenes/scene_04.md:L1-L3", "xxx（无佐证）"
    )
    sections = parse_sections(skill)
    issues = check_all_sections_have_locator(sections)
    assert any("声音框架" in i for i in issues)


def test_check_all_sections_have_locator_optional_arc_absent():
    skill = _FULL_SKILL_TEMPLATE.replace(
        "## 弧光（已完成）\n\nxxx 佐证：scenes/scene_08.md:L1-L3\n", ""
    )
    sections = parse_sections(skill)
    issues = check_all_sections_have_locator(sections)
    assert issues == []


def test_check_all_sections_have_locator_identity_required():
    sections = {"声音框架": "见 full_text.md:L1-L2"}
    assert check_all_sections_have_locator(sections) == ["缺失必备章节：身份"]


def test_section_cannot_borrow_locator_from_unrelated_heading():
    sections = parse_sections("## 身份与处境\n无来源断言\n## 备注\nfull_text.md:L1-L2\n")
    assert check_all_sections_have_locator(sections) == ["章节 '身份' 无原文引用定位"]


def test_check_boundary_each_bullet_has_locator_happy():
    sections = parse_sections(_FULL_SKILL_TEMPLATE)
    assert check_boundary_each_bullet_has_locator(sections["边界"]) == []


def test_check_boundary_each_bullet_has_locator_one_missing():
    # 把第 2 条边界的 locator 去掉
    skill = _FULL_SKILL_TEMPLATE.replace(
        "- 边界 2 ← 佐证：scenes/scene_06.md:L1-L3",
        "- 边界 2 ← （无佐证）",
    )
    sections = parse_sections(skill)
    issues = check_boundary_each_bullet_has_locator(sections["边界"])
    assert len(issues) == 1
    assert "边界 2" in issues[0] or "第 2 条" in issues[0]


def test_check_boundary_handles_multiline_bullets():
    """边界 bullet 常跨多行，locator 在续行——应该被认出。"""
    body = """\
- 边界 A，跨行说明继续……
  ← 佐证：scenes/scene_01.md:L1-L3

- 边界 B，跨行
  ← 佐证：scenes/scene_02.md:L5-L7
"""
    assert check_boundary_each_bullet_has_locator(body) == []


def test_verify_role_catches_section_missing_locator(tmp_path):
    """集成：SKILL.md 缺 locator 的章节应被 verify_role 报出。"""
    novel_dir = tmp_path / "novel"
    chars_dir = novel_dir / "characters"
    role_dir = chars_dir / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    # 把声音框架的 locator 去掉
    broken = _FULL_SKILL_TEMPLATE.replace(
        "xxx 佐证：scenes/scene_04.md:L1-L3", "xxx"
    )
    (role_dir / "SKILL.md").write_text(broken, encoding="utf-8")
    (role_dir / "build-meta.yaml").write_text(
        "display_name: 测试角色\nrole_slug: test-role\nlocator_count: 7\n",
        encoding="utf-8",
    )
    (refs_dir / "key-dialogues.md").write_text(
        "# 测试角色\n\n" + "\n".join(
            f"### scenes/scene_{i:02d}.md:L1-L3\n\ncontent\n" for i in [1,2,3,5,6,7,8]
        ),
        encoding="utf-8",
    )
    (chars_dir / "character_map.json").write_text(
        json.dumps({"测试角色": "test-role"}, ensure_ascii=False), encoding="utf-8"
    )

    issues = verify_role(novel_dir, role_dir)
    assert any("声音框架" in i for i in issues)


def test_verify_role_dir_mode_happy(tmp_path):
    """新增 role-dir 模式：直接指向角色目录，跳过 novel-dir 结构。"""
    # 搭一个"续写工作区"典型结构：角色在任意路径，无 character_map
    workspace = tmp_path / "results" / "personal" / "model" / "女生节系列"
    role_dir = workspace / "distilled" / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    (role_dir / "SKILL.md").write_text(_FULL_SKILL_TEMPLATE, encoding="utf-8")
    (refs_dir / "key-dialogues.md").write_text(
        "# 测试角色\n\n" + "\n".join(
            f"### scenes/scene_{i:02d}.md:L1-L3\n\ncontent\n"
            for i in range(1, _DEFAULT_LOCATOR_COUNT + 1)
        ),
        encoding="utf-8",
    )
    (role_dir / "build-meta.yaml").write_text(
        f"display_name: 测试角色\nrole_slug: test-role\nlocator_count: {_DEFAULT_LOCATOR_COUNT}\n",
        encoding="utf-8",
    )

    # role-dir 模式下无 character_map 应视为跳过而非 fail
    issues = verify_role(novel_dir=None, role_dir=role_dir, character_map_path=None)
    assert issues == []


def test_verify_role_dir_mode_with_explicit_map(tmp_path):
    """role-dir 模式下可通过 --character-map 显式指定 map 位置。"""
    workspace = tmp_path / "workspace"
    role_dir = workspace / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    (role_dir / "SKILL.md").write_text(_FULL_SKILL_TEMPLATE, encoding="utf-8")
    (refs_dir / "key-dialogues.md").write_text(
        "# 测试\n\n" + "\n".join(
            f"### scenes/scene_{i:02d}.md:L1-L3\n\ncontent\n"
            for i in range(1, _DEFAULT_LOCATOR_COUNT + 1)
        ),
        encoding="utf-8",
    )
    (role_dir / "build-meta.yaml").write_text(
        f"display_name: 测试角色\nrole_slug: test-role\nlocator_count: {_DEFAULT_LOCATOR_COUNT}\n",
        encoding="utf-8",
    )

    # map 文件放在任意路径
    map_path = workspace / "shared-map.json"
    map_path.write_text(
        json.dumps({"测试角色": "test-role"}, ensure_ascii=False), encoding="utf-8"
    )

    issues = verify_role(novel_dir=None, role_dir=role_dir, character_map_path=map_path)
    assert issues == []


def test_verify_role_dir_mode_with_map_mismatch(tmp_path):
    """role-dir 模式下传了 map 但 map 条目错 → 报 issue。"""
    role_dir = tmp_path / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    (role_dir / "SKILL.md").write_text(_FULL_SKILL_TEMPLATE, encoding="utf-8")
    (refs_dir / "key-dialogues.md").write_text(
        "# 测试\n\n" + "\n".join(
            f"### scenes/scene_{i:02d}.md:L1-L3\n\ncontent\n"
            for i in range(1, _DEFAULT_LOCATOR_COUNT + 1)
        ),
        encoding="utf-8",
    )
    (role_dir / "build-meta.yaml").write_text(
        f"display_name: 测试角色\nrole_slug: test-role\nlocator_count: {_DEFAULT_LOCATOR_COUNT}\n",
        encoding="utf-8",
    )

    map_path = tmp_path / "wrong-map.json"
    map_path.write_text(
        json.dumps({"别人": "other"}, ensure_ascii=False), encoding="utf-8"
    )

    issues = verify_role(novel_dir=None, role_dir=role_dir, character_map_path=map_path)
    assert any("character_map" in i for i in issues)


def test_verify_role_catches_boundary_bullet_missing_locator(tmp_path):
    """集成：边界某条 bullet 无 locator 应被 verify_role 报出。"""
    novel_dir = tmp_path / "novel"
    chars_dir = novel_dir / "characters"
    role_dir = chars_dir / "test-role"
    refs_dir = role_dir / "references"
    refs_dir.mkdir(parents=True)

    # 去掉边界第 3 条的 locator
    broken = _FULL_SKILL_TEMPLATE.replace(
        "- 边界 3 ← 佐证：scenes/scene_07.md:L1-L3",
        "- 边界 3 ← （漏写佐证）",
    )
    (role_dir / "SKILL.md").write_text(broken, encoding="utf-8")
    (role_dir / "build-meta.yaml").write_text(
        "display_name: 测试角色\nrole_slug: test-role\nlocator_count: 7\n",
        encoding="utf-8",
    )
    (refs_dir / "key-dialogues.md").write_text(
        "# 测试角色\n\n" + "\n".join(
            f"### scenes/scene_{i:02d}.md:L1-L3\n\ncontent\n" for i in [1,2,3,4,5,6,8]
        ),
        encoding="utf-8",
    )
    (chars_dir / "character_map.json").write_text(
        json.dumps({"测试角色": "test-role"}, ensure_ascii=False), encoding="utf-8"
    )

    issues = verify_role(novel_dir, role_dir)
    assert any("边界" in i and "locator" in i for i in issues)


# ==================== Layer 4: review-log.yaml gate ====================

def _write_review_log(role_dir: Path, reviews: list[dict]) -> None:
    import yaml
    role_dir.mkdir(parents=True, exist_ok=True)
    content = {"role_slug": role_dir.name, "reviews": reviews}
    (role_dir / "review-log.yaml").write_text(
        yaml.safe_dump(content, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_check_review_log_absent_file_passes(tmp_path):
    """review-log.yaml 不存在 → 视为 OK（没审过就没审过，不阻塞）。"""
    role_dir = tmp_path / "role"
    role_dir.mkdir()
    assert check_review_log(role_dir) == []


def test_check_review_log_all_high_resolved(tmp_path):
    role_dir = tmp_path / "role"
    _write_review_log(role_dir, [
        {"id": "R001", "reviewer": "codex", "date": "2026-04-13",
         "severity": "high", "type": "direct_fact_error",
         "claim": "X", "location": "SKILL.md L1",
         "status": "resolved", "resolution": "commit abc123"},
    ])
    assert check_review_log(role_dir) == []


def test_check_review_log_unresolved_high_fails(tmp_path):
    role_dir = tmp_path / "role"
    _write_review_log(role_dir, [
        {"id": "R001", "reviewer": "codex", "date": "2026-04-13",
         "severity": "high", "type": "direct_fact_error",
         "claim": "空明拳硬伤", "location": "SKILL.md L29",
         "status": "unresolved", "resolution": None},
    ])
    issues = check_review_log(role_dir)
    assert len(issues) == 1
    assert "R001" in issues[0]
    assert "unresolved" in issues[0] or "未解决" in issues[0]


def test_check_review_log_medium_unresolved_does_not_fail(tmp_path):
    """medium/low 级别 unresolved 不 fail（只 high 是 gate）。"""
    role_dir = tmp_path / "role"
    _write_review_log(role_dir, [
        {"id": "R001", "severity": "medium", "type": "overfitting",
         "claim": "某处微调", "location": "SKILL.md L10",
         "status": "unresolved"},
        {"id": "R002", "severity": "low", "type": "other",
         "claim": "小瑕疵", "location": "SKILL.md L20",
         "status": "unresolved"},
    ])
    assert check_review_log(role_dir) == []


def test_check_review_log_wontfix_with_resolution_passes(tmp_path):
    """wontfix 但填了 resolution → 视为 resolved，不 fail。"""
    role_dir = tmp_path / "role"
    _write_review_log(role_dir, [
        {"id": "R001", "severity": "high", "type": "direct_fact_error",
         "claim": "X", "location": "SKILL.md L1",
         "status": "wontfix", "resolution": "已讨论，决定不改——理由 xxx"},
    ])
    assert check_review_log(role_dir) == []


def test_check_review_log_wontfix_without_resolution_fails(tmp_path):
    """wontfix 但没填 resolution → fail（必须给出不改的理由）。"""
    role_dir = tmp_path / "role"
    _write_review_log(role_dir, [
        {"id": "R001", "severity": "high", "type": "direct_fact_error",
         "claim": "X", "location": "SKILL.md L1",
         "status": "wontfix", "resolution": None},
    ])
    issues = check_review_log(role_dir)
    assert len(issues) == 1
    assert "R001" in issues[0]


def test_check_review_log_yaml_parse_error(tmp_path):
    role_dir = tmp_path / "role"
    role_dir.mkdir()
    (role_dir / "review-log.yaml").write_text("not: valid: yaml: [", encoding="utf-8")
    issues = check_review_log(role_dir)
    assert any("review-log.yaml" in i and ("解析" in i or "parse" in i.lower()) for i in issues)


def test_check_review_log_top_level_not_dict(tmp_path):
    role_dir = tmp_path / "role"
    role_dir.mkdir()
    (role_dir / "review-log.yaml").write_text("- a\n- b\n", encoding="utf-8")
    issues = check_review_log(role_dir)
    assert any("顶层" in i or "mapping" in i for i in issues)


# ==================== Layer 4: claims.yaml gate ====================

def _write_claims(role_dir: Path, claims: list[dict]) -> None:
    import yaml
    role_dir.mkdir(parents=True, exist_ok=True)
    content = {"role_slug": role_dir.name, "claims": claims}
    (role_dir / "claims.yaml").write_text(
        yaml.safe_dump(content, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_check_claims_absent_file_passes(tmp_path):
    role_dir = tmp_path / "role"
    role_dir.mkdir()
    assert check_claims(role_dir) == []


def test_check_claims_all_verified_passes(tmp_path):
    role_dir = tmp_path / "role"
    _write_claims(role_dir, [
        {"id": "C001", "text": "X 教 Y 武功", "type": "mentor_of_skill",
         "source_locators": ["scenes/scene_01.md:L1-L3"],
         "confidence": "high",
         "verification_required": True,
         "verification_status": "verified",
         "verification_sources": [
             {"url": "https://zh.wikipedia.org/wiki/X", "quote": "X 教 Y 武功"},
             {"url": "https://baike.baidu.com/X", "quote": "X 教 Y 武功"},
         ]},
    ])
    assert check_claims(role_dir) == []


def test_check_claims_required_unresolved_fails(tmp_path):
    role_dir = tmp_path / "role"
    _write_claims(role_dir, [
        {"id": "C001", "text": "空明拳由周伯通传", "type": "mentor_of_skill",
         "source_locators": ["scenes/scene_06.md:L1-L3"],
         "verification_required": True,
         "verification_status": "unresolved"},
    ])
    issues = check_claims(role_dir)
    assert len(issues) == 1
    assert "C001" in issues[0]


def test_check_claims_required_disputed_without_sources_or_note_fails(tmp_path):
    """disputed 但缺 sources + 缺 resolution_note 应至少 fail（多条 issue）。"""
    role_dir = tmp_path / "role"
    _write_claims(role_dir, [
        {"id": "C001", "text": "X", "type": "lineage",
         "verification_required": True,
         "verification_status": "disputed"},
    ])
    issues = check_claims(role_dir)
    assert len(issues) >= 1
    assert all("C001" in i for i in issues)


def test_check_claims_not_required_any_status_passes(tmp_path):
    """verification_required: false 的 claim 不进 gate。"""
    role_dir = tmp_path / "role"
    _write_claims(role_dir, [
        {"id": "C001", "text": "弧光轨迹...", "type": "arc_trajectory",
         "verification_required": False,
         "verification_status": "unresolved"},  # 无视
    ])
    assert check_claims(role_dir) == []


# ==================== verify_role 集成：子检查开关 ====================

def test_verify_role_check_review_log_only_skips_structure(tmp_path):
    """只跑 --check-review-log 时，不校验结构问题。"""
    novel_dir, role_dir = _build_role(tmp_path, key_dialogue_sections=2)
    # 结构问题存在（section count mismatch），但我们只查 review-log
    _write_review_log(role_dir, [
        {"id": "R001", "severity": "high", "type": "other",
         "claim": "X", "location": "SKILL.md L1",
         "status": "resolved", "resolution": "OK"},
    ])
    issues = verify_role(novel_dir, role_dir, checks={"review_log"})
    assert all("locator" not in i and "section" not in i for i in issues)


def test_verify_role_default_runs_all_checks(tmp_path):
    """不传 checks 参数默认全部运行（structure + review_log + claims）。"""
    novel_dir, role_dir = _build_role(tmp_path)  # 结构全通过
    _write_review_log(role_dir, [
        {"id": "R001", "severity": "high", "status": "unresolved",
         "type": "direct_fact_error", "claim": "X", "location": "X"},
    ])
    issues = verify_role(novel_dir, role_dir)  # 默认全开
    # 应包含 review-log 的 issue
    assert any("R001" in i for i in issues)


# ==================== Layer 1 补强（codex Finding 2：frontmatter / slug / role_slug 一致性）====================

class TestFrontmatterComplete:
    def test_all_four_fields_passes(self):
        content = "---\nname: x\ndescription: y\nversion: 1\nallowed-tools: Read\n---\n\n# x"
        assert check_frontmatter_complete(content) == []

    def test_missing_frontmatter_fails(self):
        content = "# x\n\n## 身份\n...\n"
        issues = check_frontmatter_complete(content)
        assert len(issues) == 1
        assert "frontmatter" in issues[0]

    def test_missing_one_field_fails(self):
        content = "---\nname: x\ndescription: y\nversion: 1\n---\n\n# x"  # 缺 allowed-tools
        issues = check_frontmatter_complete(content)
        assert len(issues) == 1
        assert "allowed-tools" in issues[0]

    def test_empty_field_treated_as_missing(self):
        content = "---\nname: x\ndescription:\nversion: 1\nallowed-tools: Read\n---\n\n# x"
        issues = check_frontmatter_complete(content)
        assert "description" in issues[0]

    def test_parse_frontmatter_returns_dict(self):
        content = "---\nname: x\nversion: 1\n---\n\n# x"
        assert parse_frontmatter(content) == {"name": "x", "version": 1}

    def test_parse_frontmatter_missing_returns_none(self):
        assert parse_frontmatter("# x\n") is None


class TestSlugFormat:
    def test_valid_slug_passes(self):
        assert check_slug_format("guo-jing") == []
        assert check_slug_format("role-01") == []
        assert check_slug_format("ab") == []

    def test_chinese_fails(self):
        issues = check_slug_format("弥沙")
        assert len(issues) == 1
        assert "弥沙" in issues[0]

    def test_uppercase_fails(self):
        assert check_slug_format("GuoJing") != []

    def test_starts_with_digit_fails(self):
        assert check_slug_format("1role") != []

    def test_trailing_hyphen_fails(self):
        assert check_slug_format("role-") != []

    def test_single_char_fails(self):
        """SLUG_PATTERN 要求 ≥ 2 字符。"""
        assert check_slug_format("a") != []

    def test_underscore_fails(self):
        assert check_slug_format("role_a") != []


class TestRoleSlugConsistency:
    def test_all_match_passes(self):
        issues = check_role_slug_consistency(
            "guo-jing", {"role_slug": "guo-jing"}, {"name": "guo-jing"}
        )
        assert issues == []

    def test_build_meta_mismatch_fails(self):
        issues = check_role_slug_consistency(
            "guo-jing", {"role_slug": "弥沙"}, None
        )
        assert len(issues) == 1
        assert "弥沙" in issues[0]
        assert "build-meta" in issues[0]

    def test_frontmatter_mismatch_fails(self):
        issues = check_role_slug_consistency(
            "guo-jing", None, {"name": "wrong-name"}
        )
        assert len(issues) == 1
        assert "wrong-name" in issues[0]
        assert "frontmatter" in issues[0]

    def test_missing_both_passes(self):
        """meta 和 frontmatter 都 None → 其他 gate 会报，本函数不重复报。"""
        assert check_role_slug_consistency("x", None, None) == []


def test_verify_role_fails_on_chinese_dir_name(tmp_path):
    """集成：codex Finding 2 真实场景——characters/弥沙/ 目录名违规。"""
    novel_dir, role_dir = _build_role(tmp_path)
    # 重命名目录为中文
    new_role_dir = role_dir.parent / "弥沙"
    role_dir.rename(new_role_dir)
    # build-meta 里 role_slug 保持原值（不一致）
    issues = verify_role(novel_dir, new_role_dir)
    assert any("弥沙" in i and "slug" in i for i in issues)


def test_verify_role_fails_on_missing_frontmatter(tmp_path):
    novel_dir, role_dir = _build_role(tmp_path)
    skill = role_dir / "SKILL.md"
    content = skill.read_text(encoding="utf-8")
    # 剥掉 frontmatter
    content_no_fm = content.split("---\n", 2)[-1]
    skill.write_text(content_no_fm, encoding="utf-8")
    issues = verify_role(novel_dir, role_dir)
    assert any("frontmatter" in i for i in issues)


def test_canonical_role_does_not_require_claims(tmp_path):
    """目标版本原文参考不因 canonical 标签强制生成联网清单。"""
    novel_dir, role_dir = _build_role(tmp_path)
    (novel_dir / "novel-meta.yaml").write_text("canonical: true\n")
    from verify_character_skills import main
    from unittest.mock import patch
    import pytest
    with patch("sys.argv", ["verify", "--novel-dir", str(novel_dir), "--role", role_dir.name, "--check-claims"]):
        with pytest.raises(SystemExit) as result:
            main()
    assert result.value.code == 0
