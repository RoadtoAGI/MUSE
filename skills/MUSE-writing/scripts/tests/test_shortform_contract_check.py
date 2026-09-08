"""validate_shortform_contract.py + shortform-contract-check hook 测试。

覆盖：四类 basename 分派 / 正向 allowlist / 唯一性先于外键 / 外键存在性 /
禁键递归（183 退化四字段形态 = RED,剥 marker 转 task 说明 = GREEN）/ hook 端到端。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_shortform_contract import validate_file  # noqa: E402

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "shortform-contract-check.py"
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


# ---------- fixtures ----------

def _write(shortform: Path, name: str, data) -> Path:
    shortform.mkdir(parents=True, exist_ok=True)
    p = shortform / name
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def _valid_conception() -> dict:
    return {
        "premise": "一个守渡人发现渡口的规矩正在杀人",
        "core_value": "秩序↔良知",
        "genre": "乡土奇谭",
        "target_length": 6000,
        "requirements": ["至少包含一段完整对话", "结尾必须开放"],
    }


def _valid_characters() -> dict:
    return {
        "characters": [
            {
                "id": "shou-du-ren",
                "name": "守渡人",
                "desire": "守住渡口的规矩换取安稳",
                "pressure": "规矩开始要求他放走该拦的人",
                "voice": "短句，惜字如金，用渡口行话打比方",
                "voice_boundaries": ["不解释自己的动机"],
                "relationships": [{"with": "guo-ke", "nature": "被规矩要求拦下的人"}],
            },
            {
                "id": "guo-ke",
                "name": "过客",
                "desire": "在天亮前过河",
                "pressure": "身后有追兵，身上有秘密",
                "voice": "客气但句句试探",
            },
        ]
    }


def _valid_outline() -> dict:
    return {
        "spine": {
            "spine_statement": "守渡人为守规矩放走了不该放的人，最终以破规矩救回良知",
            "dramatic_question": "规矩和良知冲突时他选哪个",
            "ending_pressure": "追兵到渡口，规矩要求他交人",
        },
        "scenes": [
            {
                "scene_id": "S01",
                "pov": "shou-du-ren",
                "participants": ["shou-du-ren", "guo-ke"],
                "location_time": "渡口 / 深夜",
                "conflict": "过客求渡，规矩不许夜渡",
                "value_start": "规矩牢不可破",
                "value_end": "规矩第一次出现裂缝",
                "task": "让守渡人在拒绝中露出动摇",
                "handoff": "过客留下一句让守渡人整夜睡不着的话",
            },
            {
                "scene_id": "S02",
                "pov": "shou-du-ren",
                "participants": ["shou-du-ren", "guo-ke"],
                "location_time": "渡口 / 黎明",
                "conflict": "追兵将至，守渡人必须选边",
                "value_start": "规矩有裂缝",
                "value_end": "守渡人亲手破了规矩",
                "task": "把选择压到不可回避的一刻",
            },
        ],
    }


def _valid_ledger() -> dict:
    return {
        "inspirations": [
            {
                "id": "INS-001",
                "type": "pattern",
                "status": "adopted",
                "source": "用户素材：河工夜渡禁忌一则",
                "project_encoding": "化用为渡口夜渡规矩的由来",
            }
        ]
    }


# ---------- conception ----------

def test_conception_valid(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", _valid_conception())
    assert validate_file(p) == []


def test_conception_unknown_field_rejected(tmp_path):
    data = _valid_conception()
    data["craft_targets"] = {"dominant_carriers": ["物件"]}
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", data)
    errors = validate_file(p)
    assert any("未知字段" in e and "craft_targets" in e for e in errors)


def test_conception_target_length_must_be_int(tmp_path):
    data = _valid_conception()
    data["target_length"] = "六千字"
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", data)
    assert any("target_length" in e for e in validate_file(p))


# ---------- characters ----------

def test_characters_valid(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", _valid_characters())
    assert validate_file(p) == []


def test_characters_duplicate_id_rejected(tmp_path):
    data = _valid_characters()
    data["characters"][1]["id"] = "shou-du-ren"
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", data)
    assert any("重复" in e for e in validate_file(p))


def test_characters_non_slug_id_rejected(tmp_path):
    data = _valid_characters()
    data["characters"][0]["id"] = "守渡人"
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", data)
    assert any("kebab slug" in e for e in validate_file(p))


def test_characters_relationship_fk_miss(tmp_path):
    data = _valid_characters()
    data["characters"][0]["relationships"][0]["with"] = "bu-cun-zai"
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", data)
    assert any("外键无锚" in e for e in validate_file(p))


def test_characters_not_killed_by_outline_allowlist(tmp_path):
    """F2 回归：characters.yaml 不被 outline allowlist 误杀（basename 分派正确）。"""
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", _valid_characters())
    errors = validate_file(p)
    assert not any("spine" in e or "scenes" in e for e in errors)


# ---------- outline ----------

def _shortform_with_characters(tmp_path) -> Path:
    shortform = tmp_path / "pipeline" / "shortform"
    _write(shortform, "characters.yaml", _valid_characters())
    return shortform


def test_outline_valid_green(tmp_path):
    """GREEN 夹具：183 首写形态剥 marker 转单句 task 后通过。"""
    shortform = _shortform_with_characters(tmp_path)
    p = _write(shortform, "outline.yaml", _valid_outline())
    assert validate_file(p) == []


def test_outline_four_field_rich_structure_red(tmp_path):
    """RED 夹具：183 退化形态（L190 四字段富结构）任意深度被禁键递归拒绝。"""
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["task"] = None
    data["scenes"][0].pop("task")
    data["scenes"][0]["task"] = "占位"
    data["scenes"][0]["rendering"] = {"default": "summary"}
    data["scenes"][1]["physical_carrier"] = [{"text": "船篙", "function_link": "船篙→规矩"}]
    p = _write(shortform, "outline.yaml", data)
    errors = validate_file(p)
    assert any("rendering" in e and "禁键" in e for e in errors)
    assert any("physical_carrier" in e and "禁键" in e for e in errors)


def test_outline_marker_task_rejected(tmp_path):
    """双 marker 字符串形态（蓝图遗风）不再合法——task 须无设计 marker。"""
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["task"] = "[核心][main] 让守渡人在拒绝中露出动摇"
    p = _write(shortform, "outline.yaml", data)
    assert any("marker" in e for e in validate_file(p))


def test_outline_duplicate_scene_id_rejected(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][1]["scene_id"] = "S01"
    p = _write(shortform, "outline.yaml", data)
    assert any("重复" in e for e in validate_file(p))


def test_outline_pov_fk_miss(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["pov"] = "bu-cun-zai"
    p = _write(shortform, "outline.yaml", data)
    assert any("pov" in e and "人物 id" in e for e in validate_file(p))


def test_outline_missing_characters_is_order_violation(tmp_path):
    shortform = tmp_path / "pipeline" / "shortform"
    p = _write(shortform, "outline.yaml", _valid_outline())
    assert any("characters.yaml 缺失" in e for e in validate_file(p))


def test_outline_value_label_equality_is_not_a_semantic_verdict(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["value_end"] = data["scenes"][0]["value_start"]
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []


def test_outline_handoff_is_conditional(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0].pop("handoff")
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []


def test_outline_ins_ref_without_ledger_rejected(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["inspiration_refs"] = ["INS-001"]
    p = _write(shortform, "outline.yaml", data)
    assert any("inspiration_ledger.yaml 缺失" in e for e in validate_file(p))


def test_outline_ins_ref_candidate_rejected(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    ledger = _valid_ledger()
    ledger["inspirations"][0]["status"] = "candidate"
    _write(shortform, "inspiration_ledger.yaml", ledger)
    data = _valid_outline()
    data["scenes"][0]["inspiration_refs"] = ["INS-001"]
    p = _write(shortform, "outline.yaml", data)
    assert any("adopted" in e for e in validate_file(p))


def test_outline_ins_ref_adopted_green(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    _write(shortform, "inspiration_ledger.yaml", _valid_ledger())
    data = _valid_outline()
    data["scenes"][0]["inspiration_refs"] = ["INS-001"]
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []


# ---------- ledger ----------

def test_ledger_valid(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "inspiration_ledger.yaml", _valid_ledger())
    assert validate_file(p) == []


def test_ledger_bad_status_rejected(tmp_path):
    data = _valid_ledger()
    data["inspirations"][0]["status"] = "promoted"
    p = _write(tmp_path / "pipeline" / "shortform", "inspiration_ledger.yaml", data)
    assert any("status" in e for e in validate_file(p))


def test_ledger_duplicate_ins_id_rejected(tmp_path):
    data = _valid_ledger()
    data["inspirations"].append(dict(data["inspirations"][0]))
    p = _write(tmp_path / "pipeline" / "shortform", "inspiration_ledger.yaml", data)
    assert any("重复" in e for e in validate_file(p))


# ---------- 非契约产物名 ----------

def test_unknown_basename_rejected(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "notes.yaml", {"foo": "bar"})
    assert any("非短链契约产物名" in e for e in validate_file(p))


# ---------- hook 端到端（退出码契约：0=放行；2=阻断） ----------

def _run_hook(file_path: Path):
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(file_path)}}
    return subprocess.run(
        ["python3", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True,
        env={"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def test_hook_passes_valid_conception(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", _valid_conception())
    r = _run_hook(p)
    assert r.returncode == 0, r.stderr


def test_hook_blocks_invalid(tmp_path):
    data = _valid_conception()
    data["voice_gear"] = "dense"
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", data)
    r = _run_hook(p)
    assert r.returncode == 2
    assert "未知字段" in (r.stderr + r.stdout)


def test_hook_ignores_review_subdir(tmp_path):
    """shortform/review/ 子目录不归本 hook——审阅报告属主校验器是终验 gate。"""
    review = tmp_path / "pipeline" / "shortform" / "review"
    review.mkdir(parents=True)
    p = review / "short_story_review.r1.yaml"
    p.write_text("status: REVISE\n", encoding="utf-8")
    r = _run_hook(p)
    assert r.returncode == 0


def test_hook_ignores_other_pipeline_yaml(tmp_path):
    p = tmp_path / "pipeline"
    p.mkdir(parents=True)
    f = p / "phase5_scenes.yaml"
    f.write_text("sequence_expansions: []\n", encoding="utf-8")
    r = _run_hook(f)
    assert r.returncode == 0


def test_muse_hook_check_silently_skips_shortform(tmp_path):
    """全链 check-yaml-contract 软检对 shortform basename 无阻断（设计 §5.2 实核项）。"""
    p = _write(tmp_path / "pipeline" / "shortform", "conception.yaml", _valid_conception())
    script = PLUGIN_ROOT / "scripts" / "muse_hook_check.py"
    r = subprocess.run(
        ["python3", str(script), "yaml-contract", "--file", str(p)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def test_outline_multi_sentence_task_preserves_conditions(tmp_path):
    """多个句号不替代对任务内容的语义判断。"""
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["task"] = "两人尚未交换消息。让读者从错开的称呼察觉误会。"
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []



def test_outline_single_sentence_with_number_ok(tmp_path):
    """任务说明保留有用的数值条件。"""
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["task"] = "让守渡人在 1.5 米外看清对岸的灯灭掉。"
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []


def test_hook_upstream_edit_invalidating_outline_blocked(tmp_path):
    """上游联动重验：characters 改 id 使既有 outline 外键失效 → hook 阻断。"""
    shortform = tmp_path / "pipeline" / "shortform"
    _write(shortform, "characters.yaml", _valid_characters())
    _write(shortform, "outline.yaml", _valid_outline())
    # 上游改名：shou-du-ren → chuan-fu，outline 的 pov/participants 悬空
    data = _valid_characters()
    data["characters"][0]["id"] = "chuan-fu"
    data["characters"][0]["relationships"][0]["with"] = "guo-ke"
    chars = _write(shortform, "characters.yaml", data)
    r = _run_hook(chars)
    assert r.returncode == 2
    assert "上游联动" in (r.stderr + r.stdout)


def test_hook_upstream_edit_keeping_outline_valid_passes(tmp_path):
    """上游改动不破坏外键时正常放行。"""
    shortform = tmp_path / "pipeline" / "shortform"
    _write(shortform, "characters.yaml", _valid_characters())
    _write(shortform, "outline.yaml", _valid_outline())
    data = _valid_characters()
    data["characters"][0]["voice"] = "更短的句子，更长的沉默"
    chars = _write(shortform, "characters.yaml", data)
    r = _run_hook(chars)
    assert r.returncode == 0, r.stderr


def test_functional_character_needs_only_identity(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", {
        "characters": [{"id": "messenger", "name": "送信人"}],
    })
    assert validate_file(p) == []


def test_optional_character_context_is_typed_when_present(tmp_path):
    p = _write(tmp_path / "pipeline" / "shortform", "characters.yaml", {
        "characters": [{"id": "messenger", "name": "送信人", "voice": []}],
    })
    assert any("voice" in error for error in validate_file(p))


def test_narrator_position_does_not_require_a_fictional_character(tmp_path):
    shortform = _shortform_with_characters(tmp_path)
    data = _valid_outline()
    data["scenes"][0]["pov"] = "narrator:外部观察"
    data["scenes"][0]["task"] = "保留两人尚未交换消息的条件。\n让读者从错开的称呼察觉误会。"
    p = _write(shortform, "outline.yaml", data)
    assert validate_file(p) == []
    data["scenes"][0]["pov"] = "narrator:"
    p = _write(shortform, "outline.yaml", data)
    assert any("pov" in error for error in validate_file(p))
