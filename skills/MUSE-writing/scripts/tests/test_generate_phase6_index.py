"""generate_phase6_index.py 测试

回归 codex r-code IMPORTANT #1 / codex-advice 2026-04-26 Issue 1：
phase5_scenes.yaml 含 sequence_expansions + arc_progression 两段时，
旧正则解析会让 arc_progression 里的 `- scene_id` 覆盖 sequence_id 全归 Q3；
本套测试锁住 184 真实形态 + 几种边界。
"""

from pathlib import Path
import subprocess
import sys
import yaml
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import generate_phase6_index as g


def test_184_realistic_shape_three_sequences(tmp_path):
    """184 真实形态：3 sequence × 1 scene + arc_progression 段
    旧 bug：S01/S02/S03 全部被标 sequence_id=Q3
    修复后：S01→Q1, S02→Q2, S03→Q3"""
    yml = {
        "sequence_expansions": [
            {
                "sequence_id": "Q1",
                "arc_id": "A1",
                "sequence_title": "青灯渡初局",
                "scenes": [{
                    "scene_id": "S01",
                    "sequence_id": "Q1",
                    "title": "青灯渡照影",
                    "pov": "yang-guo",
                }],
            },
            {
                "sequence_id": "Q2",
                "arc_id": "A2",
                "sequence_title": "听雨铺新盟",
                "scenes": [{
                    "scene_id": "S02",
                    "sequence_id": "Q2",
                    "title": "听雨铺白衣",
                    "pov": "xiaolongnu",
                }],
            },
            {
                "sequence_id": "Q3",
                "arc_id": "A3",
                "sequence_title": "照影坞外阵",
                "scenes": [{
                    "scene_id": "S03",
                    "sequence_id": "Q3",
                    "title": "照影坞夜破阵",
                    "pov": "xiaolongnu",
                }],
            },
        ],
        "arc_progression": [
            {"arc_id": "A1", "scenes": [{"scene_id": "S01"}, {"scene_id": "S03"}]},
            {"arc_id": "A2", "scenes": [{"scene_id": "S02"}]},
        ],
    }
    p = tmp_path / "phase5.yaml"
    p.write_text(yaml.safe_dump(yml, allow_unicode=True))

    scenes = g.parse_phase5_scenes(p)
    by_id = {s["scene_id"]: s for s in scenes}

    # 应只有 3 场（来自 sequence_expansions），不含 arc_progression 重复
    assert len(scenes) == 3
    assert by_id["S01"]["sequence_id"] == "Q1"
    assert by_id["S02"]["sequence_id"] == "Q2"
    assert by_id["S03"]["sequence_id"] == "Q3"
    assert by_id["S01"]["arc_id"] == "A1"
    assert by_id["S02"]["arc_id"] == "A2"
    assert by_id["S03"]["arc_id"] == "A3"


@pytest.mark.parametrize("sequence_key", ["seq_id", "sequence_id"])
def test_scene_inherits_sequence_when_scene_lacks_sequence_id(tmp_path, sequence_key):
    """scene 自己没 sequence_id 时继承 sequence_expansions 项的"""
    yml = {
        "sequence_expansions": [
            {
                sequence_key: "Q5",
                "arc_id": "A5",
                "scenes": [{"scene_id": "SX"}],  # 没自己的 sequence_id
            },
        ],
    }
    p = tmp_path / "phase5.yaml"
    p.write_text(yaml.safe_dump(yml))
    scenes = g.parse_phase5_scenes(p)
    assert len(scenes) == 1
    assert scenes[0]["sequence_id"] == "Q5"
    assert scenes[0]["arc_id"] == "A5"


def test_multiple_scenes_per_sequence(tmp_path):
    """一个 sequence 含多场——每场都正确归属"""
    yml = {
        "sequence_expansions": [
            {
                "sequence_id": "Q1",
                "scenes": [
                    {"scene_id": "S01a", "sequence_id": "Q1"},
                    {"scene_id": "S01b", "sequence_id": "Q1"},
                ],
            },
            {
                "sequence_id": "Q2",
                "scenes": [{"scene_id": "S02", "sequence_id": "Q2"}],
            },
        ],
    }
    p = tmp_path / "phase5.yaml"
    p.write_text(yaml.safe_dump(yml))
    scenes = g.parse_phase5_scenes(p)
    by_id = {s["scene_id"]: s["sequence_id"] for s in scenes}
    assert by_id == {"S01a": "Q1", "S01b": "Q1", "S02": "Q2"}


def test_empty_phase5_returns_empty(tmp_path):
    p = tmp_path / "phase5.yaml"
    p.write_text("")
    assert g.parse_phase5_scenes(p) == []


def test_index_preserves_design_order_and_existing_notes(tmp_path):
    """部分正文已经写入时仍按设计顺序保留全部场景和已填摘要。"""
    pipeline = tmp_path / "pipeline"
    scenes_dir = pipeline / "scenes"
    scenes_dir.mkdir(parents=True)
    design = {"sequence_expansions": [
        {"seq_id": "Q2", "arc_id": "A1", "scenes": [{"scene_id": "S03", "title": '标题含"引号"'}]},
        {"seq_id": "Q1", "arc_id": "A1", "scenes": [{"scene_id": "S01"}, {"scene_id": "S02"}]},
    ]}
    (pipeline / "phase5_scenes.yaml").write_text(yaml.safe_dump(design, allow_unicode=True))
    for sid in ("S01", "S03", "S99"):
        (scenes_dir / f"scene_{sid}.md").write_text("一二三 four five 六七八")
    (pipeline / "phase6_development.yaml").write_text(yaml.safe_dump({"scenes": [
        {"scene_id": "S03", "summary": "已填摘要", "beats": [{"action": "已填节拍"}]},
        {"scene_id": "S99", "summary": "旧场景"},
    ]}, allow_unicode=True))
    script = Path(__file__).parent.parent / "generate_phase6_index.py"
    result = subprocess.run(["python3", str(script), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    parsed = yaml.safe_load((pipeline / "phase6_development.yaml").read_text())
    entries = parsed["scenes"]
    assert [item["scene_id"] for item in entries] == ["S03", "S01", "S02"]
    assert [item["sequence_id"] for item in entries] == ["Q2", "Q1", "Q1"]
    assert entries[0]["summary"] == "已填摘要"
    assert entries[0]["beats"] == [{"action": "已填节拍"}]
    assert entries[0]["title"] == '标题含"引号"'
    assert entries[2]["approximate_words"] == 0
    assert entries[2]["file_path"] == "pipeline/scenes/scene_S02.md"
    assert parsed["total_word_count"] == sum(item["approximate_words"] for item in entries)


def test_duplicate_scene_id_rejected(tmp_path):
    path = tmp_path / "phase5.yaml"
    path.write_text(yaml.safe_dump({"sequence_expansions": [
        {"seq_id": "Q1", "scenes": [{"scene_id": "S01"}, {"scene_id": "S01"}]},
    ]}))
    with pytest.raises(ValueError, match="Duplicate scene_id"):
        g.parse_phase5_scenes(path)
