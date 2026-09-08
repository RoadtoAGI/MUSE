import json
import os
import subprocess
from pathlib import Path

import yaml


HOOK = Path(__file__).resolve().parents[2] / "hooks/check-reviser-patch.sh"


def _run_hook(work_dir: Path):
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": "reviser", "scene_id": "S01", "work_dir": str(work_dir)}}).encode(),
        capture_output=True,
        timeout=30,
    )


def _run_realistic_hook(project_dir: Path, scene_id: str):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "reviser",
            "scene_id": scene_id,
            "prompt": f"为场景 {scene_id} 执行 patch",
        },
    }
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload, ensure_ascii=False).encode(),
        capture_output=True,
        timeout=30,
        env=env,
    )


def test_check_reviser_patch_ambiguous_sentence_requires_line_range(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text("她说了那一个字。\n她说了那一个字。\n", encoding="utf-8")
    (scene_dir / "patch_directive.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "patches": [{
            "patch_kind": "rewrite_sentence",
            "anchor_quote": "她说了那一个字。",
            "rewrite_directive": {
                "semantic_function": "x",
                "preserve": ["x"],
                "remove_patterns": ["x"],
                "target_style": "x",
                "max_sentences": 1,
            },
        }],
    }, allow_unicode=True), encoding="utf-8")
    result = _run_hook(work)
    assert result.returncode == 2
    assert b"line_range" in result.stderr or b"location" in result.stderr


def test_check_reviser_patch_rewrite_span_missing_old_span_blocks(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text("她说了那一个字。她走开了。\n", encoding="utf-8")
    (scene_dir / "patch_directive.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "patches": [{
            "patch_kind": "rewrite_span",
            "anchor_quote_start": "她说了那一个字。",
            "anchor_quote_end": "她走开了。",
            "location": {"line_range": [1, 1]},
            "rewrite_directive": {
                "semantic_function": "x",
                "preserve": ["x"],
                "remove_patterns": ["x"],
                "target_style": "x",
                "max_sentences": 4,
            },
        }],
    }, allow_unicode=True), encoding="utf-8")
    result = _run_hook(work)
    assert result.returncode == 2
    assert b"old_span" in result.stderr


def test_check_reviser_patch_rewrite_span_inconsistent_anchors_blocks(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text("她说了那一个字。她走开了。\n", encoding="utf-8")
    (scene_dir / "patch_directive.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "patches": [{
            "patch_kind": "rewrite_span",
            "anchor_quote_start": "她说了那一个字。",
            "anchor_quote_end": "她走开了。",
            "old_span": "完全不同的文本。",
            "location": {"line_range": [1, 1]},
            "rewrite_directive": {
                "semantic_function": "x",
                "preserve": ["x"],
                "remove_patterns": ["x"],
                "target_style": "x",
                "max_sentences": 4,
            },
        }],
    }, allow_unicode=True), encoding="utf-8")
    result = _run_hook(work)
    assert result.returncode == 2


def test_check_reviser_patch_snapshots_protected_declarations_before_partial_pruning(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    scene_text = "甲没有下令。她仍是十七岁。\n"
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text(
        scene_text,
        encoding="utf-8",
    )
    directive = {
        "scene_id": "S01",
        "review_round": "post_revision_round1",
        "patches": [{
            "patch_id": "patch_01",
            "patch_kind": "rewrite_sentence",
            "anchor_quote": "甲没有下令。她仍是十七岁。",
            "location": {"line_range": [1, 1]},
            "rewrite_directive": {
                "semantic_function": "保持否定极性与年龄事实",
                "preserve": ["否定极性", "年龄"],
                "remove_patterns": ["解释性判断"],
                "target_style": "定点重写",
                "max_sentences": 1,
                "protected_tokens": [{
                    "token_id": "T-S01-age",
                    "patch_id": "patch_01",
                    "source": "old_span",
                    "raw": "十七岁",
                    "match_mode": "exact",
                    "accepted_forms": [],
                    "scope": "patch_span",
                }],
            },
            "protected_relations": [{
                "relation_id": "R-S01-polarity",
                "patch_id": "patch_01",
                "type": "polarity",
                "expected": "甲没有下令",
                "before_quote": "甲没有下令。",
            }],
        }],
    }
    patch_path = scene_dir / "patch_directive.yaml"
    patch_path.write_text(
        yaml.safe_dump(directive, allow_unicode=True),
        encoding="utf-8",
    )

    result = _run_hook(work)

    assert result.returncode == 0, result.stderr.decode()
    integrity_path = scene_dir / "protected_integrity.yaml"
    state = yaml.safe_load(integrity_path.read_text(encoding="utf-8"))
    assert [item["token_id"] for item in state["declaration_snapshots"][0]["tokens"]] == [
        "T-S01-age"
    ]
    assert [
        item["relation_id"] for item in state["declaration_snapshots"][0]["relations"]
    ] == ["R-S01-polarity"]
    assert state["relation_verifications"][0]["relation_id"] == "R-S01-polarity"
    assert state["relation_verifications"][0]["after_quote"] == "甲没有下令。"
    assert state["relation_verifications"][0]["reason"] == "declaration_before_quote_seed"

    # partial reviser removes the applied patch from the pending directive. The
    # authoritative snapshot remains unchanged and continues to carry both IDs.
    directive["patches"] = []
    patch_path.write_text(
        yaml.safe_dump(directive, allow_unicode=True),
        encoding="utf-8",
    )
    rerun = _run_hook(work)
    assert rerun.returncode == 0, rerun.stderr.decode()
    after_prune = yaml.safe_load(integrity_path.read_text(encoding="utf-8"))
    assert after_prune == state


def test_runtime_hook_snapshots_after_discovering_pipeline_root(tmp_path):
    """真实 Agent 输入无 work_dir 时，发现 run 后仍须执行 declaration snapshot。"""
    work = tmp_path / "results" / "run-01"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "甲没有下令。她仍是十七岁。\n",
        encoding="utf-8",
    )
    (scene_dir / "patch_directive.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "review_round": "post_revision_round1",
            "patches": [{
                "patch_id": "patch_01",
                "patch_kind": "rewrite_sentence",
                "anchor_quote": "甲没有下令。她仍是十七岁。",
                "location": {"line_range": [1, 1]},
                "rewrite_directive": {
                    "semantic_function": "保持年龄事实",
                    "preserve": ["年龄"],
                    "remove_patterns": ["解释性判断"],
                    "target_style": "定点重写",
                    "max_sentences": 1,
                    "protected_tokens": [{
                        "token_id": "T-S01-age",
                        "patch_id": "patch_01",
                        "source": "old_span",
                        "raw": "十七岁",
                        "match_mode": "exact",
                        "accepted_forms": [],
                        "scope": "scene",
                    }],
                },
            }],
        }, allow_unicode=True),
        encoding="utf-8",
    )

    result = _run_realistic_hook(tmp_path, "S01")

    assert result.returncode == 0, result.stderr.decode()
    assert (scene_dir / "protected_integrity.yaml").exists()


def test_check_reviser_patch_rejects_protected_item_bound_to_other_patch(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "甲没有下令。她仍是十七岁。\n",
        encoding="utf-8",
    )
    (scene_dir / "patch_directive.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "patches": [{
            "patch_id": "patch_01",
            "patch_kind": "rewrite_sentence",
            "anchor_quote": "甲没有下令。她仍是十七岁。",
            "location": {"line_range": [1, 1]},
            "rewrite_directive": {
                "semantic_function": "x",
                "preserve": ["x"],
                "remove_patterns": ["x"],
                "target_style": "x",
                "max_sentences": 1,
                "protected_tokens": [{
                    "token_id": "T-S01-age",
                    "patch_id": "patch_other",
                    "source": "old_span",
                    "raw": "十七岁",
                    "match_mode": "exact",
                    "accepted_forms": [],
                    "scope": "scene",
                }],
            },
        }],
    }, allow_unicode=True), encoding="utf-8")

    result = _run_hook(work)

    assert result.returncode == 2
    assert b"patch_binding_mismatch" in result.stderr


def test_check_reviser_patch_requires_stable_application_identity(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "她把旧伞放回门边。\n",
        encoding="utf-8",
    )
    (scene_dir / "patch_directive.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "patches": [{
                "patch_id": "patch_01",
                "patch_kind": None,
                "anchor_quote": "她把旧伞放回门边。",
            }],
        }, allow_unicode=True),
        encoding="utf-8",
    )

    result = _run_hook(work)

    assert result.returncode == 2
    assert b"application_id required" in result.stderr


def test_check_reviser_patch_rejects_duplicate_patch_ids(tmp_path):
    work = tmp_path / "work"
    scene_dir = work / "pipeline" / "scene_S01"
    scene_dir.mkdir(parents=True)
    (work / "pipeline" / "scenes").mkdir(parents=True)
    (work / "pipeline" / "scenes" / "scene_S01.md").write_text(
        "她把旧伞放回门边。\n",
        encoding="utf-8",
    )
    (scene_dir / "patch_directive.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "application_id": "scene_review_round1",
            "patches": [
                {"patch_id": "patch_01", "patch_kind": None},
                {"patch_id": "patch_01", "patch_kind": None},
            ],
        }),
        encoding="utf-8",
    )

    result = _run_hook(work)

    assert result.returncode == 2
    assert b"duplicate patch_id" in result.stderr


def _empty_patch(work, sid="S01"):
    scene = work / "pipeline/scenes" / f"scene_{sid}.md"
    scene.parent.mkdir(parents=True, exist_ok=True)
    scene.write_text("雨停了。\n", encoding="utf-8")
    patch = work / "pipeline" / f"scene_{sid}" / "patch_directive.yaml"
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text(yaml.safe_dump({"scene_id": sid, "application_id": "round1", "patches": []}), encoding="utf-8")
    return patch


def test_hook_uses_explicit_work_dir_and_current_scene(tmp_path):
    selected = tmp_path / "results/selected run"
    other = tmp_path / "results/other run"
    _empty_patch(selected)
    _empty_patch(selected, "S02").write_text("patches: [broken", encoding="utf-8")
    _empty_patch(other).write_text("patches: [broken", encoding="utf-8")
    result = _run_hook(selected)
    assert result.returncode == 0, result.stderr.decode()


def test_hook_rejects_ambiguous_legacy_scene_instead_of_choosing_latest(tmp_path):
    _empty_patch(tmp_path / "results/first")
    _empty_patch(tmp_path / "results/second")
    result = _run_realistic_hook(tmp_path, "S01")
    assert result.returncode == 2
    assert "work_dir" in result.stderr.decode()


def test_non_reviser_dispatch_does_not_validate_or_snapshot_patches(tmp_path):
    patch = _empty_patch(tmp_path)
    patch.write_text("patches: [broken", encoding="utf-8")
    payload = {"tool_name": "Agent", "tool_input": {"subagent_type": "writer", "work_dir": str(tmp_path), "scene_id": "S01"}}
    result = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 0
    assert not (patch.parent / "protected_integrity.yaml").exists()


def test_unique_rewrite_anchor_needs_no_sentence_quota_or_line_range(tmp_path):
    _empty_patch(tmp_path)
    patch = tmp_path / "pipeline/scene_S01/patch_directive.yaml"
    patch.write_text(yaml.safe_dump({
        "scene_id": "S01", "application_id": "round1",
        "patches": [{"patch_id": "patch_01", "source": "scene_review",
                     "patch_kind": "rewrite_sentence", "anchor_quote": "雨停了。",
                     "rewrite_directive": {"semantic_function": "交代雨止", "preserve": ["雨止"],
                                           "remove_patterns": [], "target_style": "沿原文"}}],
    }, allow_unicode=True), encoding="utf-8")
    result = _run_hook(tmp_path)
    assert result.returncode == 0, result.stderr.decode()


def test_unbound_review_request_leaves_existing_run_untouched(tmp_path):
    _empty_patch(tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    payload = {"tool_name": "Agent", "tool_input": {
        "subagent_type": "general-purpose", "prompt": "审查 scene_S01 的修订规则",
        "work_dir": str(tmp_path), "scene_id": "S01"}}
    result = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 0
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
