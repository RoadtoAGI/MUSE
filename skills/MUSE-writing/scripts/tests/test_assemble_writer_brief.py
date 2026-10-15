"""assemble_writer_brief.py --shortform：简报各节、必保内容、meta 标记、披露梯与取范文参数。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import assemble_writer_brief as awb
import verify_shortform_review_complete as vsrc
from validate_shortform_contract import validate_file

SCRIPT = Path(__file__).resolve().parents[1] / "assemble_writer_brief.py"

WINDOW = ('<exemplar_window novel="狂病-莫千回" scene="KR-S03" source="莫千回《狂病-莫千回》狂人日志" chars="{n}">\n'
          "{text}\n</exemplar_window>")


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _run(tmp_path: Path, *, exemplar_chars: int | None = 1200, reuse: bool = False,
         requirements: list[str] | None = None, materials: str | None = "素材原文：第一行\n第二行 # 不是标题") -> Path:
    work = tmp_path / "run"
    shortform = work / "pipeline" / "shortform"
    (shortform / "review").mkdir(parents=True)
    conception = {
        "premise": "末世第三个月，程序员许诚逐层搜一栋废弃写字楼找吃的",
        "core_value": "体面↔求生", "genre": "末世", "target_length": 3000, "narration_person": "first",
        "language": "zh",
        "style_directives": ["口语独白，像在跟熟人说话"],
        "requirements": requirements if requirements is not None else ["主角必须是程序员", "结尾停在天台"],
    }
    if materials:
        conception["reference_materials"] = materials
    if reuse:
        conception["canon_reference_profile"] = {"user_reference_materials": [
            {"work": "狂病", "stance": "prefer", "reuse_mode": "maximize_apt_reuse"}]}
    _dump(shortform / "conception.yaml", conception)
    _dump(shortform / "characters.yaml", {"characters": [
        {"id": "xu-cheng", "name": "许诚", "desire": "活过这个月", "pressure": "断粮三天",
         "voice": "爱用代码打比方但会自嘲", "voice_samples": ["这楼跟屎山代码一样。", "饿了，真饿了。", "先活着再说。"],
         "relationships": [{"with": "lao-zhou", "nature": "前同事，欠他一顿饭"}]},
        {"id": "lao-zhou", "name": "老周"},
    ]})
    _dump(shortform / "outline.yaml", {
        "spine": {"spine_statement": "求生", "dramatic_question": "能否找到吃的", "ending_pressure": "天台"},
        "scenes": [{"scene_id": "S01", "pov": "xu-cheng", "participants": ["xu-cheng", "lao-zhou"],
                    "location_time": "写字楼十二层，傍晚", "conflict": "饿与怕被看见的体面",
                    "value_start": "还端着", "value_end": "放下了", "task": "让他在茶水间翻到老周藏的饼干",
                    "handoff": "饼干只剩半包", "inspiration_refs": ["INS-001"]}],
    })
    _dump(shortform / "inspiration_ledger.yaml", {"inspirations": [
        {"id": "INS-001", "type": "pattern", "status": "adopted", "source": "狂病 KR-S03",
         "project_encoding": "日记体自嘲压住恐惧"}]})
    if exemplar_chars is not None:
        text = "我把手电咬在嘴里往上走。" * (exemplar_chars // 12)
        (shortform / "reference_pack.md").write_text(
            'query: "q"\nfilters: lang=zh\nresults: 1 — 狂病-莫千回 KR-S03\nchars: 1200（预算 6000）\n\n'
            + WINDOW.format(n=len(text), text=text) + "\n", encoding="utf-8")
    return work


def _review(work: Path, n: int, findings: list[dict], status: str = "REVISE") -> None:
    _dump(work / "pipeline/shortform/review" / f"short_story_review.r{n}.yaml",
          {"story_sha256": "x", "status": status, "findings": findings})


def _finding(dimension: str, subkind: str | None = None) -> dict:
    f = {"severity": "MAJOR", "dimension": dimension, "quote": "他显得复杂而沉重。", "note": "只给结论"}
    if subkind:
        f["subkind"] = subkind
    return f


def _brief(work: Path) -> str:
    return (work / "pipeline/shortform/writer_brief.md").read_text(encoding="utf-8")


def _meta(work: Path) -> dict:
    return yaml.safe_load((work / "pipeline/shortform/brief_meta.yaml").read_text(encoding="utf-8"))


def test_sections_in_order_and_must_keep_content_verbatim(tmp_path):
    long_req = "每一条要求都必须原样出现" * 40
    work = _run(tmp_path, requirements=["主角必须是程序员", long_req])
    awb.assemble_shortform(work, usage="范文日记体的自嘲可借；范文的感染者设定不采用。")
    brief = _brief(work)
    heads = [line[3:] for line in brief.splitlines() if line.startswith("## ")]
    assert heads == list(awb.SECTIONS)
    assert "主角必须是程序员" in brief and long_req in brief
    assert "素材原文：第一行\n第二行 # 不是标题" in brief
    assert "<exemplar_window" in brief and "本篇可以怎样用：范文日记体的自嘲可借" in brief
    assert brief.index("## 范文") < brief.index("## 条目") < brief.index("## 指令")


def test_projection_has_no_field_names(tmp_path):
    work = _run(tmp_path)
    awb.assemble_shortform(work)
    events = _brief(work).split("## 事件")[1].split("## 范文")[0]
    for field in ("value_start", "value_end", "task", "handoff", "location_time", "spine_statement"):
        assert field not in _brief(work)
    assert "开场时还端着，场末放下了。" in events
    assert "借用机制：日记体自嘲压住恐惧。" in events
    assert "示范句：「这楼跟屎山代码一样。」" in _brief(work)
    assert "与老周：前同事，欠他一顿饭" in _brief(work)


def test_events_keep_task_and_handoff_lines_verbatim(tmp_path):
    # task 与 handoff 承载一致性事实（谁知道什么、数字、物件去向、时间）：逐行原样进简报，各起一行
    work = _run(tmp_path)
    path = work / "pipeline/shortform/outline.yaml"
    outline = yaml.safe_load(path.read_text(encoding="utf-8"))
    task = "老周不知道许诚拿走了饼干。\n饼干原有三包，许诚吃掉一包半\n- 天黑前回到十二层"
    handoff = "剩下的半包装进左边口袋；老周第二天才发现柜子空了"
    outline["scenes"][0].update(task=task, handoff=handoff)
    _dump(path, outline)
    awb.assemble_shortform(work)
    events = _brief(work).split("## 事件")[1].split("## 范文")[0].strip().splitlines()
    assert events[0].startswith("- S01｜") and all(line.startswith("  ") for line in events[1:])
    body = [line.strip() for line in events[1:]]
    for line in task.splitlines():
        assert any(b.startswith(line) for b in body)
    assert any(b.startswith("后文承接：" + handoff) for b in body)


def test_meta_counts_and_flags(tmp_path):
    work = _run(tmp_path, exemplar_chars=1200)
    awb.assemble_shortform(work)
    meta = _meta(work)
    assert set(meta["sections"]) == set(awb.SECTIONS)
    assert meta["total"] == sum(meta["sections"].values())
    assert meta["exemplar"] == "windows" and meta["exemplar_windows"] == 1
    assert meta["exemplar_ratio"] >= 0.5 and meta["exemplar_short"] is False
    small = _run(tmp_path / "small", exemplar_chars=120)
    awb.assemble_shortform(small)
    assert _meta(small)["exemplar_short"] is True and "作者要求" in _meta(small)["exemplar_short_reason"]


@pytest.mark.parametrize("setup, reason", [
    ("missing", "不存在"),
    ("empty", "检索无结果：register=colloquial 清空候选"),
    ("full", "不是范文窗口渲染"),
])
def test_exemplar_none_records_reason(tmp_path, setup, reason):
    work = _run(tmp_path, exemplar_chars=None)
    pack = work / "pipeline/shortform/reference_pack.md"
    if setup == "empty":
        pack.write_text('query: "q"\nfilters: x\nresults: 0 — register=colloquial 清空候选\nchars: 0（预算 6000）\n',
                        encoding="utf-8")
    elif setup == "full":
        pack.write_text("# 短篇名著参考包\n\nresults: 2\n<usage_protocol>\n</usage_protocol>\n", encoding="utf-8")
    awb.assemble_shortform(work)
    meta = _meta(work)
    assert meta["exemplar"] == "none" and reason in meta["exemplar_reason"]
    assert "本篇无范文，按人物声音与示范句写。" in _brief(work)


def test_disclosure_entry_after_first_round_then_full_after_second(tmp_path):
    work = _run(tmp_path)
    awb.assemble_shortform(work)
    assert _brief(work).split("## 条目")[1].split("## 指令")[0].strip() == "无"

    _review(work, 1, [_finding("文本质量", "abstract_judgment_without_action"), _finding("冲突")])
    awb.assemble_shortform(work)
    entries = _brief(work).split("## 条目")[1].split("## 指令")[0]
    assert "abstract_judgment_without_action" in entries and "抽象判断" in entries
    assert "全文：" not in entries
    state = yaml.safe_load((work / "pipeline/shortform/disclosure_state.yaml").read_text(encoding="utf-8"))
    item = state["unlocked"][0]
    assert (item["rung"], item["active"], item["since"], item["last_seen"]) == ("entry", True, "r2", "r1")
    assert len(state["unlocked"]) == 1  # 冲突是设计层维度，不附写作条目

    _review(work, 2, [_finding("文本质量", "abstract_judgment_without_action")])
    awb.assemble_shortform(work)
    entries = _brief(work).split("## 条目")[1].split("## 指令")[0]
    assert "全文：prose-craft/references/ai-cliche-patterns.md#信息与焦点" in entries
    state = yaml.safe_load((work / "pipeline/shortform/disclosure_state.yaml").read_text(encoding="utf-8"))
    assert state["unlocked"][0]["rung"] == "full" and state["unlocked"][0]["history"][-1] == {"full": "r3"}
    assert "条目注明“全文”的，动笔前读那一处。" in _brief(work)


def test_unknown_subkind_falls_back_to_dimension_entry(tmp_path):
    work = _run(tmp_path)
    _review(work, 1, [_finding("文本质量", "carrier_missing"), _finding("人物声音")])
    awb.assemble_shortform(work)
    items = [e["item"] for e in _meta(work)["entries"] if e["attached"]]
    assert "prose-craft/references/prose-rules.md#叙述层高风险候选" in items
    assert "dialogue-craft/references/voice-and-dialogue.md#声音差异" in items


def test_entries_section_respects_total_cap(tmp_path, monkeypatch):
    work = _run(tmp_path)
    _review(work, 1, [_finding("文本质量", "planning_trace_leakage"), _finding("POV"), _finding("叙事组织")])
    rules = awb._load(awb.RULES_PATH)
    rules["shortform"]["entries_cap"] = 200
    monkeypatch.setattr(awb, "_load", lambda p, _orig=awb._load: rules if p == awb.RULES_PATH else _orig(p))
    awb.assemble_shortform(work)
    record = _meta(work)["entries"]
    assert any(not e["attached"] and e["reason"] == "超过条目节上限" for e in record)


def test_reuse_exception_and_retrieval_args(tmp_path):
    work = _run(tmp_path, reuse=True)
    awb.assemble_shortform(work)
    brief = _brief(work)
    instruction = brief.split("## 指令")[1]
    assert "越像范文越好" in instruction and "合适就直接用" in instruction and "一律不用" not in instruction
    assert "作者要求尽量复用《狂病》的原文。" in instruction
    args = awb.retrieval_args(work)
    assert "--lang zh --original-only --person first --budget-chars 6000 --render exemplar --shortform-pack" in args
    assert "--canon-reference-profile" in args
    assert "--style-hint '第一人称；口语独白，像在跟熟人说话；类型：末世'" in args


def test_reuse_scope_names_work_uses_and_avoided_domains(tmp_path):
    work = _run(tmp_path)
    _set_conception(work, canon_reference_profile={
        "avoid_domains": ["reveal_structure"],
        "user_reference_materials": [
            {"work": "遮天", "stance": "prefer", "reuse_mode": "maximize_apt_reuse",
             "intended_domains": ["world_rule", "protagonist_archetype"]},
            {"work": "红楼梦", "stance": "prefer", "reuse_mode": "style_only"}]})
    awb.assemble_shortform(work)
    brief = _brief(work)
    instruction = brief.split("## 指令")[1]
    assert "作者要求尽量复用《遮天》的原文，用于世界规则、主角原型，不用于揭示结构。" in instruction
    assert "《红楼梦》作者定为只借文风。" in instruction


def test_instruction_sets_punctuation_by_language_and_navigation_is_attached(tmp_path):
    work = _run(tmp_path)
    awb.assemble_shortform(work)
    brief = _brief(work)
    assert "对白的节奏与归属方式" in brief and "引号等标点按本篇语言的通行写法" in brief
    nav = brief.split("## 手法导航")[1].split("## 条目")[0]
    assert "- 节拍：压力中的动作与反应怎样推进" in nav and "- 声音差异：多人声线趋同时" in nav
    assert "](" not in nav and "案例与全文" not in nav
    assert 0 < _meta(work)["sections"]["手法导航"] <= 800


def test_conception_changed_after_retrieval_is_flagged(tmp_path):
    import os
    work = _run(tmp_path)
    _set_conception(work, narration_person="third")
    pack = work / "pipeline/shortform/reference_pack.md"
    later = pack.stat().st_mtime + 60  # 同一秒内写的两个文件 mtime 可能相等，显式拉开
    os.utime(work / "pipeline/shortform/conception.yaml", (later, later))
    awb.assemble_shortform(work)
    assert any("取范文之后改过" in w for w in _meta(work)["warnings"])


def test_cli_rejects_unbuilt_scopes(tmp_path):
    work = _run(tmp_path)
    result = subprocess.run([sys.executable, str(SCRIPT), "--scene-id", "S01", "--work-dir", str(work)],
                            capture_output=True, text=True)
    assert result.returncode == 2 and "--shortform" in result.stderr


def test_generated_files_are_not_hand_written(tmp_path):
    work = _run(tmp_path)
    awb.assemble_shortform(work)
    errors = validate_file(work / "pipeline/shortform/disclosure_state.yaml")
    assert errors and "assemble_writer_brief.py" in errors[0]


def test_review_schema_accepts_subkind_and_register_dimension():
    report = {"story_sha256": "x", "status": "PASS", "findings": [
        _finding("文本质量", "stock_speech_tag") | {"severity": "MINOR"},
        _finding("范文语域") | {"severity": "MINOR"},
    ]}
    assert vsrc._validate_report_schema(report, "r1") == []
    report["findings"].append(_finding("文本质量", "made_up_kind"))
    report["findings"].append(_finding("冲突", "stock_speech_tag"))
    errors = vsrc._validate_report_schema(report, "r1")
    assert any("made_up_kind" in e for e in errors) and any("只用于 文本质量" in e for e in errors)


def _set_conception(work: Path, **changes) -> None:
    path = work / "pipeline/shortform/conception.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    _dump(path, data)


def test_delivery_language_comes_from_conception_not_text(tmp_path):
    # 中文设计、英文交付：检索语言与简报连接词跟 language 走
    work = _run(tmp_path)
    _set_conception(work, language="en")
    assert awb.retrieval_args(work).startswith("--lang en ")
    awb.assemble_shortform(work)
    assert "Narration: first person" in _brief(work)
    meta = _meta(work)
    assert meta["language"] == "en" and not any("缺 language" in w for w in meta.get("warnings", []))


def test_old_conception_without_language_is_inferred_with_warning(tmp_path):
    work = _run(tmp_path)
    _set_conception(work, language=None)
    awb.assemble_shortform(work)
    meta = _meta(work)
    assert meta["language"] == "zh"
    assert any("缺 language" in w for w in meta["warnings"])
