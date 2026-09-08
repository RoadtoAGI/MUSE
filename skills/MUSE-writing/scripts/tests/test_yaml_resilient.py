"""yaml_resilient.py — LLM 产 yaml 常见 quote 越界的消费端 graceful recovery 测试。

恢复 pattern：`<key>: "...内嵌\"...\"..."` 形式的双引号 scalar 含未转义内 `"`
→ 升级为 block scalar `<key>: |\n  ...内嵌"..."...`。

非恢复目标（不动）：
- 已转义 `\\"`
- block scalar `|` / folded `>` 中的引号
- 单引号 scalar 中的双引号
- 真 schema 错（缺字段 / 错缩进）→ 应直接 raise
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yaml_resilient import load_yaml_resilient, RecoveryReport  # noqa: E402


# ---------- 恢复目标：双引号 scalar 含未转义内 " ----------

def test_single_inner_pair_recovered():
    """value_start: "...已"妥善"处理..."  ——  S05 实际病灶。"""
    text = (
        'scene_id: S05\n'
        'value_start: "沈砚秋已三日前出长安。裴怀璧未亲送。裴自以为已"妥善"处理。"\n'
    )
    doc, report = load_yaml_resilient(text)
    assert doc["value_start"].startswith("沈砚秋")
    assert '"妥善"' in doc["value_start"]
    assert report.recovered_lines == [2]


def test_multiple_inner_pairs_recovered():
    """key: "a"b"c"d"e"  ——  多对内嵌。"""
    text = 'k: "外"内1"中"内2"尾"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["k"] == '外"内1"中"内2"尾'
    assert report.recovered_lines == [1]


def test_trailing_inner_quote_recovered():
    """key: "...处理"."  ——  内嵌引号贴近右端。"""
    text = 'k: "他说"是"。"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["k"] == '他说"是"。'
    assert report.recovered_lines == [1]


# ---------- 不动的合法 yaml（确保 happy path 不退化）----------

def test_already_escaped_passes_through():
    text = 'k: "a\\"b\\"c"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["k"] == 'a"b"c'
    assert report.recovered_lines == []


def test_block_scalar_with_inner_quotes_untouched():
    """block scalar 不需要转义，恢复函数不能误改。"""
    text = 'k: |\n  含"内嵌"的多行\n  也算正常\n'
    doc, report = load_yaml_resilient(text)
    assert '"内嵌"' in doc["k"]
    assert report.recovered_lines == []


def test_single_quoted_scalar_with_inner_double_untouched():
    """单引号包双引号是合法 yaml。"""
    text = "k: '含\"内嵌\"双引号'\n"
    doc, report = load_yaml_resilient(text)
    assert doc["k"] == '含"内嵌"双引号'
    assert report.recovered_lines == []


def test_normal_yaml_no_changes():
    """完全合法、无引号坑的常规 yaml。"""
    text = 'scenes:\n  - id: S01\n    title: 测试场\n'
    doc, report = load_yaml_resilient(text)
    assert doc["scenes"][0]["id"] == "S01"
    assert report.recovered_lines == []


# ---------- F3：list item 形式恢复 ----------

def test_list_item_inner_quote_recovered():
    """`- "a"内"b"` —— 列表项含未转义内引号。"""
    text = 'preserve:\n  - "外"内"尾"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["preserve"] == ['外"内"尾']
    assert report.recovered_lines == [2]


def test_list_item_with_trailing_plain_text_recovered():
    """`- "quoted"（中文括号补语）` —— 531 实战 case。"""
    text = (
        'preserve:\n'
        '  - "裴怀璧端起酒杯，只端着，没喝"\n'
        '  - "远处乐工的调弦声也歇了"（可保留此环境细节，去掉解释性后半句）\n'
    )
    doc, report = load_yaml_resilient(text)
    assert len(doc["preserve"]) == 2
    assert doc["preserve"][0] == '裴怀璧端起酒杯，只端着，没喝'
    assert '远处乐工的调弦声也歇了' in doc["preserve"][1]
    assert '可保留此环境细节' in doc["preserve"][1]
    assert report.recovered_lines == [3]  # 只第二条 broken


def test_list_item_well_quoted_no_trailing_untouched():
    """普通合法列表 quoted item 不应被改。"""
    text = 'items:\n  - "正常 quoted scalar"\n  - "another one"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["items"] == ['正常 quoted scalar', 'another one']
    assert report.recovered_lines == []


def test_list_item_escaped_inner_quote_untouched():
    """`- "a\\"b"` —— 转义内引号是合法 yaml。"""
    text = 'items:\n  - "外\\"中\\"尾"\n'
    doc, report = load_yaml_resilient(text)
    assert doc["items"] == ['外"中"尾']
    assert report.recovered_lines == []


def test_list_item_single_quoted_untouched():
    """单引号包双引号是合法 yaml。"""
    text = "items:\n  - '外\"内\"尾'\n"
    doc, report = load_yaml_resilient(text)
    assert doc["items"] == ['外"内"尾']
    assert report.recovered_lines == []


def test_mixed_mapping_value_and_list_item_broken_recovered():
    """同文档既有 mapping value 双引号 broken，也有 list item broken。"""
    text = (
        'scene:\n'
        '  value_start: "沈砚秋已三日前出长安。裴自以为已"妥善"处理。"\n'
        '  preserve:\n'
        '    - "远处乐工的调弦声也歇了"（环境细节）\n'
    )
    doc, report = load_yaml_resilient(text)
    assert '"妥善"' in doc['scene']['value_start']
    assert '环境细节' in doc['scene']['preserve'][0]
    assert sorted(report.recovered_lines) == [2, 4]


# ---------- 不可恢复：真 schema / 结构错应 raise ----------

def test_bad_indentation_still_raises():
    """缩进错乱 ≠ quote escape 问题，不应被自救吞掉。"""
    text = 'a:\n  b: 1\n c: 2\n'  # b 和 c 缩进不一致
    with pytest.raises(yaml.YAMLError):
        load_yaml_resilient(text)


# ---------- 集成：模拟 S05 真实样本 ----------

def test_phase5_scenes_with_s05_quote_bug_recovers():
    """模拟 531/phase5_scenes.yaml S05 病灶——只动 value_start / value_end 两行。"""
    text = (
        'scenes:\n'
        '  - scene_id: S05\n'
        '    title: "未送"\n'
        '    value_start: "沈砚秋已三日前出长安。裴自以为已"妥善"处理。"\n'
        '    value_end: "崔元礼问怎不去送持正。裴以\'送字过重\'拨开。"\n'
        '    pov: 裴怀璧\n'
    )
    doc, report = load_yaml_resilient(text)
    scenes = doc["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "S05"
    assert '"妥善"' in scenes[0]["value_start"]
    assert "送字过重" in scenes[0]["value_end"]
    assert report.recovered_lines == [4]  # 只 value_start 是 broken；value_end 单引号合法
