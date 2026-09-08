"""
Rn+3 联合 smoke：验证 INS-* 能闭环从 candidates → promote → ledger → phase YAML → writer 输入 → review 检测。
"""
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_phase5_r10 import verify_inspiration_refs  # noqa: E402
from verify_phase2_assets import verify_canon_archetype  # noqa: E402


FIXTURE_DIR = Path(__file__).parent / "fixtures"
LEDGER_FIXTURE = FIXTURE_DIR / "inspiration_ledger_smoke.yaml"
PHASE2_FIXTURE = FIXTURE_DIR / "phase2_with_archetype.yaml"
PHASE5_FIXTURE = FIXTURE_DIR / "phase5_with_inspiration_refs.yaml"


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_smoke_ledger_fixture_has_pattern_and_archetype():
    ledger = _load(LEDGER_FIXTURE)
    types = {card["type"] for card in ledger["inspirations"]}
    assert types == {"pattern", "archetype"}
    for card in ledger["inspirations"]:
        assert card["status"] in ("accepted", "bound", "candidate", "retired")
        assert card["source"]["verified_by"]


def test_smoke_phase2_archetype_passes_hard_gate_shape():
    """phase2 fixture 保留引用缺失与融合边界的诊断。"""
    phase2 = _load(PHASE2_FIXTURE)
    ledger = _load(LEDGER_FIXTURE)
    findings = verify_canon_archetype(phase2, ledger)
    codes = {finding["code"] for finding in findings}
    assert "canon_archetype_ledger_id_missing" in codes
    assert "canon_archetype_secondary_missing_merge_boundary" not in codes


def test_smoke_phase5_inspiration_refs_partial_match():
    """phase5 fixture S07 引用 INS-001；ledger 中同卡绑定 S12，触发双向不匹配。"""
    phase5 = _load(PHASE5_FIXTURE)
    ledger = _load(LEDGER_FIXTURE)
    findings = verify_inspiration_refs(phase5, ledger)
    codes = {finding["code"] for finding in findings}
    assert "inspiration_refs_bidirectional_missing" in codes


def test_smoke_d7_closure_no_cross_plugin_link():
    """D7 闭包：本轮新增 MUSE-writing 改动文件不含跨 plugin 物理路径 link。"""
    result = subprocess.run(
        [
            "grep", "-rnE",
            r"\]\([^)]*MUSE-canon-distill|\]\([^)]*knowledge-base/novels",
            "skills/MUSE-writing/skills/story-writing",
            "skills/MUSE-writing/skills/phase0-conception",
            "skills/MUSE-writing/skills/phase2-character",
            "skills/MUSE-writing/skills/phase3-spine",
            "skills/MUSE-writing/skills/phase5-scene-arrangement",
            "skills/MUSE-writing/skills/writer",
            "skills/MUSE-writing/skills/story-review",
            "skills/MUSE-writing/skills/design-validation",
            "skills/MUSE-writing/agents/canon-researcher.md",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[4],
    )
    assert result.stdout == "", f"D7 闭包破损：{result.stdout}"
