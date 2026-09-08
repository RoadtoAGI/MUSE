"""muse_hook_check.py 对可选 prose_risk_contract 的格式校验测试。

整个字段缺失合法；字段存在时，校验 `used` 与既有 list 字段的机械
格式。校验保持 yaml-contract 既有 WARN-only 行为。
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "muse_hook_check.py"


def _run(file_path: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "yaml-contract", "--file", str(file_path)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _write_phase5(tmp_path: Path, scenes_yaml: str) -> Path:
    """写一份最小可解析的 phase5_scenes.yaml，scenes_yaml 段插到 sequence_expansions[0].scenes 下。"""
    p = tmp_path / "phase5_scenes.yaml"
    p.write_text(
        f"sequence_expansions:\n"
        f"  - sequence_id: Q1\n"
        f"    arc_id: arc_01\n"
        f"    scenes:\n"
        f"{scenes_yaml}\n",
        encoding="utf-8",
    )
    return p


def test_phase5_all_scenes_have_explicit_prose_risk_contract_passes(tmp_path):
    """所有 scene 都显式声明 used: true|false → 无 prose_risk_contract WARN。"""
    scenes = """\
      - scene_id: S01
        title: 开场
        prose_risk_contract:
          used: false
      - scene_id: S02
        title: 转场
        prose_risk_contract:
          used: true
          risk_families: [action_log]
"""
    p = _write_phase5(tmp_path, scenes)
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" not in err


def test_phase5_scene_missing_prose_risk_contract_passes(tmp_path):
    """scene 缺 prose_risk_contract 字段是合法常态。"""
    scenes = """\
      - scene_id: S01
        title: 开场
        prose_risk_contract:
          used: false
      - scene_id: S02
        title: 转场
"""
    p = _write_phase5(tmp_path, scenes)
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" not in err


def test_phase5_scene_prose_risk_contract_missing_used_warns(tmp_path):
    """scene 有 prose_risk_contract 但缺 used 字段 → WARN。"""
    scenes = """\
      - scene_id: S01
        title: 开场
        prose_risk_contract:
          risk_families: [action_log]
"""
    p = _write_phase5(tmp_path, scenes)
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" in err
    assert "used" in err
    assert "S01" in err


def test_phase5_scene_prose_risk_contract_invalid_list_warns(tmp_path):
    """既有 list 字段为 scalar 时只报格式 WARN。"""
    scenes = """\
      - scene_id: S01
        title: 开场
        prose_risk_contract:
          used: true
          risk_families: action_log
"""
    p = _write_phase5(tmp_path, scenes)
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" in err
    assert "列表字段" in err
    assert "S01" in err


def test_phase5_all_scenes_missing_prose_risk_contract_pass(tmp_path):
    """多 scene 全缺时也不生成场景级风险警告。"""
    scenes = """\
      - scene_id: S01
        title: A
      - scene_id: S02
        title: B
      - scene_id: S03
        title: C
"""
    p = _write_phase5(tmp_path, scenes)
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" not in err


def test_non_phase5_yaml_not_scanned_for_prose_risk_contract(tmp_path):
    """phase0/phase4 等非 phase5 文件不触发 prose_risk_contract scan。"""
    p = tmp_path / "phase4_structure.yaml"
    p.write_text("arc_expansions:\n  - arc_id: arc_01\n", encoding="utf-8")
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" not in err


def test_phase5_top_level_scenes_form_also_supported(tmp_path):
    """open-muse 平铺 scenes[] 形式中的 optional 语义一致。"""
    p = tmp_path / "phase5_scenes.yaml"
    p.write_text(
        "sequence_expansions: []\n"
        "scenes:\n"
        "  - scene_id: S01\n"
        "    title: 平铺开场\n",
        encoding="utf-8",
    )
    rc, out, err = _run(p)
    assert rc == 0
    assert "prose_risk_contract" not in err


def test_scene_card_compliance_parses_writer_projection_labels(tmp_path):
    card = tmp_path / "scene_card.md"
    scene = tmp_path / "scene_S01.md"
    card.write_text(
        "**视角角色**: 阿青\n"
        "**叙述方式**: first\n"
        "**在场人物**: a-qing\n",
        encoding="utf-8",
    )
    scene.write_text("我把剑横在门前。\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "scene-card-compliance",
            "--scene-card",
            str(card),
            "--scene-text",
            str(scene),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "未解析到 narration_style / pov" not in proc.stderr
