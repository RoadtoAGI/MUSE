"""tests for verify_patch_directive_traceability.py — patch_directive 溯源校验

按 plan v9 §11.3 实证驱动判据 + v9.1 黑名单收紧：
- 校验 1：patch 必须有 anchor_quote 字段，且可唯一定位当前
  pipeline/scenes/scene_{id}.md（防 reviser 已删句子但 patch 仍引用）；
  anchor_quote 缺失时报 missing_anchor_quote（不再接受旧 schema 嵌引号兼容路径）
- 校验 2：patch.issue_id / patch.issue 不得引用 C 组**显式 user_accepted /
  next_round_only finding**——category ∈ {user_accepted_as_known_issue, next_round_only}、
  suggestion 含同类标记、或 escalation_decision.user_accepted_findings[]。
  **裸 status=persists 不入黑名单**——persists 可能是当前轮要修的 C 组问题。
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "verify_patch_directive_traceability.py"


def _make_pipeline(tmp_path: Path, scene_id: str = "S01",
                   scene_md: str = "正文 L1\n",
                   patches: list = None,
                   c_issues: list = None):
    """构造最小 pipeline 目录用于 traceability 校验"""
    root = tmp_path / "pipeline"
    (root / "scenes").mkdir(parents=True, exist_ok=True)
    (root / "scenes" / f"scene_{scene_id}.md").write_text(scene_md)
    scene_dir = root / f"scene_{scene_id}"
    scene_dir.mkdir(parents=True, exist_ok=True)
    if patches is not None:
        (scene_dir / "patch_directive.yaml").write_text(yaml.safe_dump({
            "source": "scene_review",
            "scene_id": scene_id,
            "patches": patches,
        }, allow_unicode=True))
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    if c_issues is not None:
        (review / "C_structural_consistency.yaml").write_text(yaml.safe_dump({
            "issues": c_issues,
        }, allow_unicode=True))
    return tmp_path


def _run(pipeline_root: Path, scene_id: str = "S01"):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scene-id", scene_id,
         "--pipeline-root", str(pipeline_root)],
        capture_output=True, text=True)
    parsed = yaml.safe_load(result.stdout) if result.stdout.strip() else {}
    return result.returncode, parsed


def test_all_quotes_hit_scene_md(tmp_path):
    """patch anchor_quote 命中 scene_md → 退出 0"""
    scene_md = "L1\n他看向坡下暮色，雨后山气压得很低，道路远处有渡口方向的风，湿而腥。\nL3\n"
    patches = [{
        "anchor_quote": "他看向坡下暮色，雨后山气压得很低",
        "location": "末段",
        "issue": "禁用内省套式（A003）",
        "suggested_action": "删整句",
        "issue_id": "A-哲理金句-末段+A003",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 0
    assert out["status"] == "ok"
    assert out["total_failures"] == 0


def test_quote_not_in_scene_md_reviser_already_deleted(tmp_path):
    """184 实证：patch anchor_quote 已被 reviser 删除 → 退出 1（anchor_quote_not_in_scene_md）"""
    scene_md = "L1\n小龙女只看一眼，便知伤口形态。\n"
    patches = [{
        "anchor_quote": "重处如山压，轻处也有回锋",
        "location": "L43",
        "issue": "保留此句式（A005）",
        "suggested_action": "删句",
        "issue_id": "A005-抽象判断-L43",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    assert out["status"] == "failed"
    failures = out["findings"]
    assert any(f["failure"] == "anchor_quote_not_in_scene_md" for f in failures)
    assert any("重处如山压" in (f.get("missing_quote") or "") for f in failures)


def test_anchor_quote_hits_scene_md_with_chinese_text(tmp_path):
    """anchor_quote 中文文本命中 scene_md → 退出 0"""
    scene_md = "L1\n这是一段重要的对白，他想着\n"
    patches = [{
        "anchor_quote": "这是一段重要的对白",
        "location": "L1",
        "issue": "判断套式使用过频",
        "suggested_action": "改写",
        "issue_id": "A-test",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 0


def test_missing_anchor_quote_field(tmp_path):
    """patch 无 anchor_quote 字段 → 退出 1（missing_anchor_quote）"""
    scene_md = "L1\n正文里没有这种引述\n"
    patches = [{
        "location": "L1",
        "issue": "短词重复",
        "suggested_action": "删",
        "issue_id": "A-test",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1  # 无 anchor_quote → missing_anchor_quote
    assert any(f["failure"] == "missing_anchor_quote" for f in out["findings"])


def test_user_accepted_blacklist_blocks_patch(tmp_path):
    """patch.issue_id 引用 C 组 user_accepted（suggestion 含 user_accepted_as_known_issue
    显式标记）→ 退出 1"""
    scene_md = "L1\n这是一段足够长的引述能进入校验。\n"  # 提供合法引述
    patches = [{
        "anchor_quote": "这是一段足够长的引述能进入校验",
        "location": "L1",
        "issue": "C001 篇幅不够",
        "suggested_action": "扩充",
        "issue_id": "C001-篇幅",
    }]
    c_issues = [{
        "issue_id": "C001",
        "category": "scene_underweight",
        "status": "persists",
        "suggestion": "user_accepted_as_known_issue（Option A 显式接受）",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches, c_issues=c_issues)
    code, out = _run(root)
    assert code == 1
    failures = out["findings"]
    assert any(f["failure"] == "referenced_user_accepted_finding" for f in failures)
    assert any("C001" in (f.get("blacklisted_id") or "") for f in failures)


def test_persists_without_user_accepted_signal_not_blocked(tmp_path):
    """v9 codex IMPORTANT #2 负例：status=persists 但无 user_accepted 信号
    （仍是当前要修的问题）→ 不入黑名单，patch 正常通过"""
    scene_md = "L1\n这是一段足够长的引述能进入校验。\n"
    patches = [{
        "anchor_quote": "这是一段足够长的引述能进入校验",
        "location": "L1",
        "issue": "对应 C005 当前要修的问题",
        "suggested_action": "改",
        "issue_id": "C005-当前-L1",
    }]
    c_issues = [{
        "issue_id": "C005",
        "category": "scene_boundary",
        "status": "persists",        # 仅 persists，无 user_accepted 信号
        "suggestion": "本轮 reviser 将处理",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches, c_issues=c_issues)
    code, out = _run(root)
    assert code == 0  # persists 单独不应触发 blacklist
    assert out["total_failures"] == 0


def test_category_user_accepted_blocks_patch(tmp_path):
    """v9 codex IMPORTANT #2：category=user_accepted_as_known_issue 直接入黑名单"""
    scene_md = "L1\n这是一段足够长的引述能进入校验。\n"
    patches = [{
        "anchor_quote": "这是一段足够长的引述能进入校验",
        "location": "L1",
        "issue": "C006 已被用户接受",
        "suggested_action": "改",
        "issue_id": "C006-blocked-L1",
    }]
    c_issues = [{
        "issue_id": "C006",
        "category": "user_accepted_as_known_issue",  # 显式 category 即接受
        "status": "persists",
        "suggestion": "保留",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches, c_issues=c_issues)
    code, out = _run(root)
    assert code == 1
    assert any(f["failure"] == "referenced_user_accepted_finding" for f in out["findings"])


def test_missing_anchor_quote_fails(tmp_path):
    """patch 无 anchor_quote 字段 → 退出 1（missing_anchor_quote）"""
    scene_md = "L1\n正文\n"
    patches = [{
        "location": "L23",                    # 无 anchor_quote
        "issue": "AI 口癖重复",
        "suggested_action": "删",
        "issue_id": "A-vague",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    failures = out["findings"]
    assert any(f["failure"] == "missing_anchor_quote" for f in failures)


def test_user_accepted_blacklist_via_issue_text(tmp_path):
    """patch.issue 文本中含黑名单 issue_id → 退出 1"""
    scene_md = "L1\n场景内有这段合法引述用于锚定测试。\n"
    patches = [{
        "anchor_quote": "场景内有这段合法引述用于锚定测试",
        "location": "全场",
        "issue": "对应 C002 总字数问题",
        "suggested_action": "扩",
        "issue_id": "A-某问题-L1",  # patch 自己 id 不含 C002
    }]
    c_issues = [{
        "issue_id": "C002",
        "category": "total_wordcount",
        "status": "persists",
        "suggestion": "user_accepted_as_known_issue",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches, c_issues=c_issues)
    code, out = _run(root)
    assert code == 1
    failures = out["findings"]
    assert any(f["failure"] == "referenced_user_accepted_finding" for f in failures)


def test_no_patch_directive_yaml_passes(tmp_path):
    """patch_directive.yaml 不存在（如 PASS 路径）→ 退出 0"""
    scene_md = "L1\n场景\n"
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=None)
    code, out = _run(root)
    assert code == 0
    assert out["status"] == "ok"


def test_multiple_patches_partial_failure_lists_all(tmp_path):
    """多个 patch 部分失败 → total_failures > 0 且 findings 全列出"""
    scene_md = "L1\n第一段保留的引述：渡口方向的风，湿而腥\nL3\n"
    patches = [
        {
            "anchor_quote": "渡口方向的风，湿而腥",  # 命中 scene_md
            "location": "L1",
            "issue": "保留",
            "suggested_action": "保留",
            "issue_id": "A-保留-L1",
        },
        {
            "anchor_quote": "已经被删除的句子说什么呢",  # 不在 scene_md
            "location": "L3",
            "issue": "stale",
            "suggested_action": "del",
            "issue_id": "A-stale-L3",
        },
        {
            "anchor_quote": "这是另一段足够长的引述用于校验",  # 不在 scene_md
            "location": "全场",
            "issue": "对应 C001 问题",
            "suggested_action": "扩",
            "issue_id": "A-third-L5",
        },
    ]
    c_issues = [{
        "issue_id": "C001",
        "category": "user_accepted_as_known_issue",  # 显式 category 触发黑名单（不靠 status）
        "status": "persists",
        "suggestion": "保留",
    }]
    # patch 1 通过；patch 2 anchor_quote_not_in_scene_md（引述 stale）；
    # patch 3 anchor_quote_not_in_scene_md（"这是另一段..."不在 scene_md）+
    # referenced_user_accepted_finding（issue 含 C001）
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches, c_issues=c_issues)
    code, out = _run(root)
    assert code == 1
    failure_types = {f["failure"] for f in out["findings"]}
    assert "anchor_quote_not_in_scene_md" in failure_types
    assert "referenced_user_accepted_finding" in failure_types
    assert out["total_failures"] >= 3


def test_output_yaml_parseable_with_all_fields(tmp_path):
    """stdout 是 YAML，含 status / scene_id / patch_directive_path / findings / total_failures"""
    scene_md = "L1\n"
    patches = [{
        "anchor_quote": "已不存在的句子很长啊",
        "location": "L1",
        "issue": "stale",
        "suggested_action": "del",
        "issue_id": "A-test",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    assert "status" in out and "scene_id" in out
    assert "patch_directive_path" in out and "findings" in out
    assert "total_failures" in out
    assert isinstance(out["findings"], list)


# ---------------------------------------------------------------------------
# anchor_quote 显式字段（P0-4 round 2026-05-04）
# ---------------------------------------------------------------------------

def test_anchor_quote_hits_scene_md(tmp_path):
    """patch 用 anchor_quote 字段，引述命中 scene_md → 通过"""
    scene_md = "L1\n他看向坡下暮色，雨后山气压得很低。\nL3\n"
    patches = [{
        "anchor_quote": "他看向坡下暮色，雨后山气压得很低",
        "location": "末段附近",
        "issue": "重复氛围铺陈",
        "suggested_action": "保留前句、删后半句",
        "issue_id": "A-test",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 0
    assert out["status"] == "ok"
    assert out["total_failures"] == 0


def test_short_anchor_must_still_exist(tmp_path):
    """短锚与长锚都必须存在于正文。"""
    scene_md = "L1\n短\n"
    patches = [{
        "anchor_quote": "短句",
        "location": "L1",
        "issue": "x",
        "suggested_action": "y",
        "issue_id": "A-1",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    failure_types = {f["failure"] for f in out["findings"]}
    assert "anchor_quote_not_in_scene_md" in failure_types


def test_anchor_quote_not_in_scene_md(tmp_path):
    """anchor_quote 长度足够但未命中 scene_md → anchor_quote_not_in_scene_md"""
    scene_md = "L1\n他看向坡下暮色，雨后山气压得很低。\n"
    patches = [{
        "anchor_quote": "这句话原文里完全不存在的引述",
        "location": "L1",
        "issue": "x",
        "suggested_action": "y",
        "issue_id": "A-1",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    failure_types = {f["failure"] for f in out["findings"]}
    assert "anchor_quote_not_in_scene_md" in failure_types


def test_no_anchor_quote_field_reports_missing(tmp_path):
    """无 anchor_quote 字段时（即使 location 字段内嵌引述）→ missing_anchor_quote，不再接受旧 schema"""
    scene_md = "L1\n他看向坡下暮色，雨后山气压得很低。\n"
    patches = [{
        # 没有 anchor_quote 字段；location 字段内嵌引号——旧 schema，不再接受
        "location": "末段（'他看向坡下暮色，雨后山气压得很低'）",
        "issue": "x",
        "suggested_action": "y",
        "issue_id": "A-1",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    failure_types = {f["failure"] for f in out["findings"]}
    assert "missing_anchor_quote" in failure_types


def test_no_anchor_quote_plain_fields(tmp_path):
    """无 anchor_quote 字段（location/issue 无引述）→ missing_anchor_quote"""
    scene_md = "L1\n"
    patches = [{
        "location": "L23",
        "issue": "无引述也无 anchor_quote",
        "suggested_action": "del",
        "issue_id": "A-1",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 1
    failure_types = {f["failure"] for f in out["findings"]}
    assert "missing_anchor_quote" in failure_types


def test_anchor_quote_takes_precedence_over_legacy(tmp_path):
    """同时有 anchor_quote 与 location 嵌引述时，以 anchor_quote 为准（命中即通过）"""
    scene_md = "L1\n他看向坡下暮色，雨气压得很低。\n"
    patches = [{
        "anchor_quote": "他看向坡下暮色，雨气压得很低",  # ≥8 字命中
        "location": "末段（'文中根本没有这句完全错误的引述'）",  # 旧式不命中——anchor 优先时此字段被忽略
        "issue": "x",
        "suggested_action": "y",
        "issue_id": "A-1",
    }]
    root = _make_pipeline(tmp_path, scene_md=scene_md, patches=patches)
    code, out = _run(root)
    assert code == 0


def test_short_unique_anchor_and_repeated_anchor_disambiguation(tmp_path):
    root = _make_pipeline(tmp_path, scene_md="停。\n走。\n停。\n", patches=[{"anchor_quote": "走。"}])
    assert _run(root)[0] == 0
    root = _make_pipeline(tmp_path, scene_md="停。\n走。\n停。\n", patches=[{"anchor_quote": "停。"}])
    assert _run(root)[0] == 1
    root = _make_pipeline(tmp_path, scene_md="停。\n走。\n停。\n", patches=[{"anchor_quote": "停。", "location": {"line_range": [3, 3]}}])
    assert _run(root)[0] == 0


def test_rewrite_span_uses_its_own_explicit_anchors(tmp_path):
    patch = {"patch_kind": "rewrite_span", "old_span": "停。\n走。", "anchor_quote_start": "停。", "anchor_quote_end": "走。", "location": {"line_range": [1, 2]}}
    root = _make_pipeline(tmp_path, scene_md="停。\n走。\n", patches=[patch])
    assert _run(root)[0] == 0
    patch["anchor_quote_end"] = "等。"
    root = _make_pipeline(tmp_path, scene_md="停。\n走。\n", patches=[patch])
    assert _run(root)[0] == 1
