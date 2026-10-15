"""手法导航与条目（设计 §8.2）：按锚点取条目，首段是完整说法；导航与静态规则字数。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import craft_entries
import package_lint

SKILLS = Path(__file__).resolve().parents[2] / "skills"
NAV_LINK = re.compile(r"\]\((references/[^)#]+\.md#[^)]+)\)")


def _nav_refs(skill: str) -> list[str]:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    return [f"{skill}/{ref}" for ref in NAV_LINK.findall(text)]


@pytest.mark.parametrize("skill", ["prose-craft", "dialogue-craft"])
def test_every_navigation_line_resolves_to_entry_with_complete_first_paragraph(skill):
    refs = _nav_refs(skill)
    assert len(refs) >= 7
    for ref in refs:
        entry = craft_entries.resolve(ref)
        first = entry.paragraphs[0]
        assert not first.startswith(("#", "-", "|", ">")), ref
        assert first.rstrip().endswith(("。", "）", "」")), (ref, first[-20:])
        assert entry.units <= craft_entries.ENTRY_CAP or len(entry.paragraphs) == 1


@pytest.mark.parametrize("ref, starts", [
    ("prose-craft/references/ai-cliche-patterns.md#narrator_self_corrects", "无依据的自知"),
    ("prose-craft/references/ai-cliche-patterns.md#emotion_naming_under_face_loss", "无依据的自知"),
    ("prose-craft/references/ai-cliche-patterns.md#planning_trace_leakage", "设计字段交付事实"),
    ("story-review/references/A_aesthetic-micro_language.md#stock_speech_tag", "用库存语气标签"),
])
def test_table_rows_and_bracketed_ids_are_anchors(ref, starts):
    assert craft_entries.resolve(ref).paragraphs[0].startswith(starts)


def test_entry_takes_whole_paragraphs_up_to_cap():
    entry = craft_entries.resolve("prose-craft/references/prose-rules.md#信息与过程取舍", cap=150)
    assert len(entry.paragraphs) == 1  # 首段超过 150 也整段保留，不截半段
    full = craft_entries.resolve("prose-craft/references/prose-rules.md#信息与过程取舍", cap=10_000)
    assert len(full.paragraphs) > 1 and full.paragraphs[0] == entry.paragraphs[0]


def test_unknown_anchor_raises():
    with pytest.raises(KeyError):
        craft_entries.resolve("prose-craft/references/prose-rules.md#不存在的条目")


def test_entry_files_keep_old_section_anchors_for_existing_links():
    nav = (SKILLS / "prose-craft" / "SKILL.md").read_text(encoding="utf-8")
    assert "## 组织场景与段落" in nav  # 其他技能链接 SKILL.md#组织场景与段落 仍能落到对应导航小节


def test_static_budget_counts_body_without_frontmatter_and_link_targets():
    text = "---\nname: x\ndescription: 很长的描述不计入\n---\n\n# 标题\n\n[条目](references/a.md#锚点文字)：说明"
    assert package_lint.static_units(text) == 2 + 2 + 2  # 标题、条目、说明
    assert package_lint.static_units("Write the scene in plain words only.") == round(7 / 0.6)


def test_static_budgets_warn_only_when_enforced(tmp_path, monkeypatch, capsys):
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("字" * 300, encoding="utf-8")
    monkeypatch.setattr(package_lint, "STATIC_BUDGETS", ((("a.md", "b.md"), 500, True), (("a.md",), 100, False)))
    assert package_lint.scan_static_budgets(tmp_path) == 1
    err = capsys.readouterr().err
    assert "字数 a.md: 300" in err and "600 / 500 超出" in err and "（只打印）" in err
