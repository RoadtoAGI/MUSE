from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_phase5_r10 import scan_scene_task_concreteness  # noqa: E402


SCAN_FIXTURES = [
    (
        {
            "abstract_function": "自欺装置首次裂缝",
            "physical_carrier": [{"text": "杯沿停在唇边却没喝", "function_link": "杯沿→自欺裂缝"}],
            "reader_yield": ["关系压力"],
            "rendering": {"default": "summary", "expand_only_if": "动作改变关系"},
        },
        "pass",
        "合法 dramatic carrier",
    ),
    (
        {
            "abstract_function": "自欺装置首次裂缝",
            "physical_carrier": [{"text": "他第一次开漆匣", "function_link": "开匣→自欺裂缝"}],
            "reader_yield": ["自欺破裂"],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "abstract_function 含装置名 + physical_carrier 合法",
    ),
    (
        {
            "abstract_function": "自欺装置首次裂缝",
            "physical_carrier": [{"text": "自欺装置首次呈现", "function_link": "装置→呈现"}],
            "reader_yield": ["自欺破裂"],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "physical_carrier 内容不由词表硬判",
    ),
    (
        {
            "abstract_function": "...",
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "physical_carrier 缺失合法",
    ),
    (
        {
            "abstract_function": "self_persuasion_running",
            "physical_carrier": [
                {"text": "裴怀璧端起酒杯", "function_link": ""},
                {"text": "他喝一口", "function_link": ""},
                {"text": "放下酒杯", "function_link": ""},
                {"text": "看了一眼窗外", "function_link": ""},
                {"text": "敲桌", "function_link": ""},
            ],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "anti-action_log 5 行扁平 + function_link 空",
    ),
    (
        {
            "abstract_function": "ritual_unfolding",
            "physical_carrier": [
                {"text": "他叠诗稿成方块", "function_link": "诗稿→自欺仪式"},
                {"text": "他放进漆匣", "function_link": "放匣→仪式确认"},
                {"text": "他合匣", "function_link": "合匣→不可逆"},
            ],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "3 行扁平 + function_link 非空 → 放行",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "...", "function_link": "..."}],
            "reader_yield": [],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "reader_yield 空 list",
    ),
    (
        {
            "abstract_function": "反应得体",
            "physical_carrier": [{"text": "...", "function_link": "..."}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "评估性形容词作 task",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "language_boundaries 落地", "function_link": "..."}],
            "reader_yield": ["language_boundaries 落地带来的认知变化"],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "carrier 与 reader_yield 接受开放语义文本",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "一息后压上端砚", "function_link": "..."}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "时间标记 + 物件",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "火药装置被搬上案", "function_link": "..."}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "R1 F4 实体名+具体修饰",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "边界线被第一次越过", "function_link": "..."}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "R1 F4 边界 作实体名",
    ),
    (
        {
            "abstract_function": "装置完成",
            "physical_carrier": [{"text": "...", "function_link": "..."}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "abstract_function pattern A",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "他叠诗稿成方块", "function_link": "TODO"}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "pass",
        "function_link 不做内容黑名单判定",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "他叠诗稿成方块", "function_link": ""}],
            "reader_yield": ["..."],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "function_link 空",
    ),
    (
        {
            "abstract_function": "让读者意识到两人的判断已经分岔",
            "physical_carrier": [],
            "reader_yield": ["读者重新理解这次联盟的代价"],
            "rendering": {"default": "summary", "expand_only_if": "正文需要可见承载"},
        },
        "pass",
        "physical_carrier 空 list 合法",
    ),
    (
        {
            "abstract_function": "...",
            "physical_carrier": [{"text": "   ", "function_link": "承载关系压力"}],
            "reader_yield": ["关系压力变化"],
            "rendering": {"default": "summary", "expand_only_if": "..."},
        },
        "error",
        "carrier text 去空白后为空",
    ),
]


def test_scan_scene_task_concreteness_all_fixtures():
    for task, expected, comment in SCAN_FIXTURES:
        result = scan_scene_task_concreteness(task)
        assert result["status"] == expected, f"{comment}: expected {expected}, got {result}"


def test_phase5_contract_selects_carriers_by_consequence_and_defaults_to_reader_orientation():
    root = Path(__file__).resolve().parents[4]
    skill = (root / "skills/MUSE-writing/skills/phase5-scene-arrangement/SKILL.md").read_text(encoding="utf-8")
    schema = (
        root / "skills/MUSE-writing/skills/phase5-scene-arrangement/references/output-schema.md"
    ).read_text(encoding="utf-8")

    assert "先写 `reader_yield`" in skill
    assert "换成同类通用实现后" in skill
    assert "声音暴露位置" in skill
    assert "本场已经规划发生的具体变化" in skill
    assert "潜在收益不触发展开" in skill
    assert "临时补造事故、威胁或解释句" in skill
    assert "潜在效率、潜在安全和职业习惯不构成展开条件" in schema
    assert "动作次序与过程本身承载本场实际发生的局部逆转" in schema
    assert "完成最低读者定向" in skill
    assert "不默认隐藏终极成因" in skill
    assert "用边际叙事增量收敛载体集合" in skill
    assert "同一 `reader_yield` 是复核信号" in skill
    assert "只复述同一结果的 task 或 carrier 合并" in skill
    assert "多人共同施压、证词累积、仪式复沓、喜剧节奏、形式回环" in skill
    assert "承担来源复用义务时" in skill
    assert "选择播报、回答复述、程序确认或母题回收" in skill
    assert "不要产生去重台账或新字段" in skill
    assert "专业程序的每一步实际改变安全窗口" in skill
    assert "同场 task 产生相同 `reader_yield` 时复核" in schema
    assert "来源复用时保留" in schema


def test_validate_phase5_r10_cli_exits_zero_for_valid_yaml(tmp_path: Path):
    phase5 = tmp_path / "phase5_scenes.yaml"
    phase5.write_text(
        yaml.safe_dump(
            {
                "scenes": [
                    {
                        "scene_id": "S01",
                        "scene_tasks": [SCAN_FIXTURES[0][0]],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "skills/MUSE-writing/scripts/validate_phase5_r10.py",
            str(phase5),
            "--scan-scene-tasks",
        ],
        cwd=Path(__file__).resolve().parents[4],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_validate_phase5_r10_cli_exits_two_with_error_details(tmp_path: Path):
    phase5 = tmp_path / "phase5_scenes.yaml"
    phase5.write_text(
        yaml.safe_dump(
            {
                "sequence_expansions": [
                    {
                        "seq_id": "ARC1-SEQ1",
                        "scenes": [
                            {
                                "scene_id": "S01",
                                "scene_tasks": [SCAN_FIXTURES[12][0], SCAN_FIXTURES[14][0]],
                            }
                        ],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "skills/MUSE-writing/scripts/validate_phase5_r10.py",
            str(phase5),
            "--scan-scene-tasks",
        ],
        cwd=Path(__file__).resolve().parents[4],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "scene S01 task[0]" in result.stderr
    assert "abstract_function pattern A" in result.stderr
    assert "physical_carrier[0].function_link 必须是非空 str" in result.stderr
