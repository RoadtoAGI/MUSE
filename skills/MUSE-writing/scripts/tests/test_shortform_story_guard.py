"""reuse_overlap.py、shortform_story_guard.py 与 check-design-token-leak.sh 的短链正文分派。"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

import reuse_overlap
import shortform_story_guard as guard

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "check-design-token-leak.sh"
PLUGIN_ROOT = Path(__file__).resolve().parents[2]

EXEMPLAR = (
    "夜里落了一场大雪。庄稼人被厚厚的积雪封堵在家里，除了清扫庭院和门口的积雪再没有什么事情好做。"
    "鹿三早早起来了，已经扫除了马号院子里的积雪，晒土场也清扫了，磨房门口的雪也扫得一干二净。"
)
CLEAN = (
    "许诚把手电咬在嘴里，一层一层往上摸。三楼的茶水间早被人翻过，柜门敞着，只剩半包受潮的方糖。"
    "他把方糖揣进兜里，听见楼上有人在拖桌子。\n\n"
) * 20


def _run_dir(tmp_path: Path, story: str, *, target: int | None = None, reuse: bool | str = False) -> Path:
    work = tmp_path / "run"
    shortform = work / "pipeline" / "shortform"
    shortform.mkdir(parents=True)
    conception = {"premise": "末世程序员逐层搜食物", "core_value": "求生↔体面", "genre": "末世",
                  "target_length": target or guard.count_units(story)[0], "narration_person": "third"}
    if reuse:
        conception["canon_reference_profile"] = {"user_reference_materials": [
            {"work": reuse if isinstance(reuse, str) else "白鹿原", "stance": "prefer",
             "reuse_mode": "maximize_apt_reuse"}]}
    (shortform / "conception.yaml").write_text(yaml.safe_dump(conception, allow_unicode=True), encoding="utf-8")
    (shortform / "characters.yaml").write_text(
        yaml.safe_dump({"characters": [{"id": "xu-cheng", "name": "许诚"}]}, allow_unicode=True), encoding="utf-8")
    (shortform / "writer_brief.md").write_text(
        "## 范文\n\n<exemplar_window novel=\"白鹿原\" scene=\"S01\" source=\"陈忠实《白鹿原》\" chars=\"90\">\n"
        f"{EXEMPLAR}\n</exemplar_window>\n\n## 指令\n\n写全文。\n", encoding="utf-8")
    (work / "story.md").write_text(story, encoding="utf-8")
    return work


def _hook(path: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
    return subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True, text=True, env=env)


# ---- reuse_overlap ----

def test_overlap_measures_longest_run_and_coverage():
    draft = "他想了想。" + EXEMPLAR[:20] + "然后转身出门。" * 30
    result = reuse_overlap.measure(draft, EXEMPLAR)
    assert result.longest == 19  # 前 20 字去掉一个句号
    assert result.violated
    assert result.spans and result.spans[0]["line"] == 1


def test_overlap_ignores_punctuation_and_allows_names():
    draft = "鹿三，早早起来了！" + "他转身出门。" * 50
    assert reuse_overlap.measure(draft, EXEMPLAR).longest < reuse_overlap.FRAGMENT_MIN
    exemplar = "白嘉轩拄着一根棍子走向银白的田野"
    copied = "白嘉轩拄着一根棍子走向银白的田野"
    assert reuse_overlap.measure(copied, exemplar).violated
    assert not reuse_overlap.measure(copied, exemplar, ["白嘉轩", "银白的田野"]).violated


def test_overlap_english_counts_words():
    exemplar = "He sat in the living room trying to read and the music of Schonberg was playing loudly."
    draft = "She came home late. He sat in the living room trying to read and the music of Schonberg played."
    result = reuse_overlap.measure(draft, exemplar)
    assert result.unit == "词" and result.longest == 14


def test_overlap_reads_only_exemplar_windows():
    raw = "## 指令\n不要抄写。\n<exemplar_window novel=\"甲\" scene=\"S1\">\n窗口原文\n</exemplar_window>\n"
    assert reuse_overlap.exemplar_text(raw).strip() == "窗口原文"


# ---- guard ----

def test_guard_flags_design_tokens_with_line_numbers(tmp_path):
    work = _run_dir(tmp_path, CLEAN + "他想起 spine_statement 里写过的话。\n" + CLEAN)
    problems = guard.check(work / "story.md")
    assert any("spine_statement" in p and ":41:" in p for p in problems)


@pytest.mark.parametrize("line", ["入场处境：他饿了三天。", "INS-003 的物件出现了。", "value_end: 求生", "[核心]他推门"])
def test_guard_token_kinds(tmp_path, line):
    work = _run_dir(tmp_path, CLEAN + line + "\n")
    assert any("[设计用词]" in p for p in guard.check(work / "story.md"))


def test_guard_ordinary_words_pass(tmp_path):
    work = _run_dir(tmp_path, CLEAN + "这是一个关键转折，他心里清楚。\n")
    assert guard.check(work / "story.md") == []


def test_guard_flags_copied_exemplar(tmp_path):
    work = _run_dir(tmp_path, CLEAN + EXEMPLAR[:16] + "他想。\n")
    problems = guard.check(work / "story.md")
    assert any("[范文重合]" in p for p in problems)


def test_guard_skips_overlap_when_author_authorized_reuse(tmp_path):
    work = _run_dir(tmp_path, CLEAN + EXEMPLAR + "\n", reuse=True)
    assert not any("[范文重合]" in p for p in guard.check(work / "story.md"))


def test_reuse_authorization_only_covers_that_work(tmp_path):
    # 授权复用《红楼梦》，抄的却是《白鹿原》的窗口：照查
    work = _run_dir(tmp_path, CLEAN + EXEMPLAR + "\n", reuse="红楼梦")
    assert any("[范文重合]" in p for p in guard.check(work / "story.md"))


@pytest.mark.parametrize("line", ["这些话他想说但不会直说，等父亲关上门，才把信递给姐姐。",
                                  "他等着她的动作或停顿，好判断自己该不该再问一句。",
                                  "屏幕只剩一条报错：handoff failed。许诚拔下网线，又插了回去。"])
def test_guard_ordinary_prose_with_same_words_passes(tmp_path, line):
    work = _run_dir(tmp_path, CLEAN + line + "\n")
    assert guard.check(work / "story.md") == []


@pytest.mark.parametrize("line", ["想说但不会直说：他其实怕她走。", "## 台词候选", "- 动作或停顿：攥紧撬棍",
                                  "handoff: 老秦留在十七楼"])
def test_guard_flags_rehearsal_headings_and_key_lines(tmp_path, line):
    work = _run_dir(tmp_path, CLEAN + line + "\n")
    assert any("[设计用词]" in p for p in guard.check(work / "story.md"))


def test_guard_length_only_outside_thirty_percent(tmp_path):
    units = guard.count_units(CLEAN)[0]
    assert guard.check(_run_dir(tmp_path / "a", CLEAN, target=int(units * 1.25)) / "story.md") == []
    problems = guard.check(_run_dir(tmp_path / "b", CLEAN, target=units * 2) / "story.md")
    assert any("[字数]" in p for p in problems)


def test_guard_format(tmp_path):
    work = _run_dir(tmp_path, "---\ntitle: x\n---\n" + CLEAN + "<!-- 备注 -->\n")
    problems = guard.check(work / "story.md")
    assert any("frontmatter" in p for p in problems) and any("HTML 注释" in p for p in problems)


# ---- hook 分派（计划 2-1 的三个夹具）----

def test_hook_exit_codes_for_three_fixtures(tmp_path):
    leak = _run_dir(tmp_path / "leak", CLEAN + "spine_statement：活下去。\n")
    copied = _run_dir(tmp_path / "copied", CLEAN + EXEMPLAR[:14] + "\n")  # 去标点后连续 13 字
    clean = _run_dir(tmp_path / "clean", CLEAN)

    r = _hook(leak / "story.md")
    assert r.returncode == 2 and "story.md:41:" in r.stderr and "spine_statement" in r.stderr
    r = _hook(copied / "story.md")
    assert r.returncode == 2 and "与范文连续重合 13 字" in r.stderr
    assert _hook(clean / "story.md").returncode == 0


def test_hook_ignores_story_outside_short_chain(tmp_path):
    story = tmp_path / "story.md"
    story.write_text("spine_statement", encoding="utf-8")
    assert _hook(story).returncode == 0
