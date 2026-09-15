import hashlib
import sys
from pathlib import Path

import yaml


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_release_eligibility_module_exists():
    assert (SCRIPTS / "release_eligibility.py").exists()


def _admission(
    wd: Path,
    intent: str = "release",
    *,
    skipped: list[str] | None = None,
) -> dict:
    import release_eligibility as rel

    skipped = list(skipped or [])
    admission = {
        "schema_version": "release-eligibility-v1",
        "run_intent": intent,
        "phase7_admitted": True,
        "release_candidate": intent == "release" and not skipped,
        "skipped_checks": skipped,
        "protected_artifacts": [],
        "scenes": [{
            "scene_id": "S01",
            "scene_path": "pipeline/scenes/scene_S01.md",
            "human": {"closed": True},
            "machine": {"closed": True, "closure_modes": ["resolved"]},
        }],
        "reasons": [],
    }
    admission["input_fingerprints"] = rel.admission_input_manifest(
        wd, admission["scenes"]
    )
    return admission


def _workdir(tmp_path: Path, intent: str = "release", *, dirty: bool = False) -> Path:
    wd = tmp_path / intent
    (wd / "pipeline" / "audit").mkdir(parents=True)
    (wd / "pipeline" / "review").mkdir(parents=True)
    (wd / "pipeline" / "run_state.yaml").write_text(
        yaml.safe_dump({"run_intent": intent}), encoding="utf-8"
    )
    if dirty:
        text = "那把伞贴着这道门，那种声音穿过那层纸。\n" * 30
    else:
        text = (
            "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
            "三根竹骨断在同一侧，他不肯换新的伞架。" * 20
        )
    (wd / "story.md").write_text(text, encoding="utf-8")
    scenes_dir = wd / "pipeline" / "scenes"
    scenes_dir.mkdir(parents=True)
    (scenes_dir / "scene_S01.md").write_text(text, encoding="utf-8")
    (wd / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump({
            "scenes": [{
                "scene_id": "S01",
                "file_path": "pipeline/scenes/scene_S01.md",
            }],
        }),
        encoding="utf-8",
    )
    (wd / "pipeline" / "review" / "reader_review.yaml").write_text(
        yaml.safe_dump({"input_snapshot": "pipeline/review/snapshots/story.semantic.round1.md", "reader_findings": []}), encoding="utf-8"
    )
    _write_semantic_review(wd)
    return wd


def _write_semantic_review(
    wd: Path,
    *,
    status: str = "clear",
    review_round: int = 1,
    findings: list[dict] | None = None,
) -> None:
    if review_round == 1:
        report_name = "A_aesthetic.manuscript.yaml"
    elif review_round == 2:
        report_name = "A_aesthetic.manuscript.post_revision.yaml"
    else:
        raise ValueError("review_round must be 1 or 2")
    snapshot_relative = f"pipeline/review/snapshots/story.semantic.round{review_round}.md"
    snapshot = wd / snapshot_relative
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes((wd / "story.md").read_bytes())
    findings = list(findings or [])
    coverage_status = "findings" if status == "findings" else "clear"
    report = {
        "review_scope": "manuscript",
        "review_round": review_round,
        "input_snapshot": snapshot_relative,
        "semantic_review": status,
        "coverage": {"planning_trace_leakage": coverage_status},
        "review_findings": findings,
        "summary": {
            "total_issues": len(findings),
            "by_dimension": {"ai_pattern": len(findings)} if findings else {},
        },
    }
    (wd / "pipeline" / "review" / report_name).write_text(
        yaml.safe_dump(report, allow_unicode=True), encoding="utf-8"
    )


def _bind_reader_revision(wd: Path) -> None:
    """Provide the existing reader-to-revision binding when a test changes the story."""
    review = wd / "pipeline/review/reader_review.yaml"
    before = wd / "pipeline/review/snapshots/story.semantic.round1.md"
    quality = {
        "schema_version": "revision-quality-v1", "lane": "manuscript",
        "reader_review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "provenance": {
            "before": {"state": "fresh", "actual_text_sha256": hashlib.sha256(before.read_bytes()).hexdigest()},
            "after": {"state": "fresh", "actual_text_sha256": hashlib.sha256((wd / "story.md").read_bytes()).hexdigest()},
        },
        "protected_results": {"verdict": "PASS"},
    }
    (wd / "pipeline/revision_summary.md").write_text("status: complete\n当前反馈已处置。")
    (wd / "pipeline/review/manuscript_quality.reader.round1.yaml").write_text(yaml.safe_dump(quality))


def _scaffold_protected_scene(wd: Path, *, with_literal: bool = False) -> str:
    from protected_integrity import (
        append_declaration_snapshot,
        scene_sha256,
        verify_post_revision_review,
    )

    story = (
        (wd / "story.md").read_text(encoding="utf-8").rstrip("\n")
        + "伞柄内侧刻着乙未三月。"
    )
    scene_dir = wd / "pipeline" / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "scene_S01.md").write_text(story, encoding="utf-8")
    (wd / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump({
            "scenes": [{
                "scene_id": "S01",
                "file_path": "pipeline/scenes/scene_S01.md",
            }],
        }),
        encoding="utf-8",
    )
    (wd / "story.md").write_text(story + "\n", encoding="utf-8")
    quote = "伞柄内侧刻着乙未三月"
    relation = {
        "relation_id": "R1",
        "patch_id": "patch_01",
        "type": "causality",
        "expected": "刻字内容保持",
        "before_quote": quote,
    }
    tokens = []
    if with_literal:
        tokens.append({
            "token_id": "T1",
            "patch_id": "patch_01",
            "source": "old_span",
            "raw": "乙未三月",
            "match_mode": "exact",
            "accepted_forms": [],
            "scope": "patch_span",
        })
    append_declaration_snapshot(
        wd,
        "S01",
        "round1",
        tokens=tokens,
        relations=[relation],
    )
    start = story.index(quote)
    relation_record = {
        "relation_id": "R1",
        "patch_id": "patch_01",
        "preserved": True,
        "after_quote": quote,
        "reason": "因果载体保持",
        "current_span": {"start": start, "end": start + len(quote)},
        "scene_sha": scene_sha256(story),
    }
    detail_dir = wd / "pipeline" / "scene_S01"
    detail_dir.mkdir(parents=True, exist_ok=True)
    (detail_dir / "revision_summary.md").write_text(
        "**status**: complete\n\n"
        "1. **[patch_01 · applied · patch_kind=rewrite_sentence]** keep\n"
        f"   - new_span：{quote}\n",
        encoding="utf-8",
    )
    review_dir = wd / "pipeline" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "scene_S01.post_revision.yaml").write_text(
        yaml.safe_dump({
            "scene_id": "S01",
            "verdict": "PASS",
            "protected_integrity_gate": {
                "evaluated": True,
                "gate_pass": True,
                "literal_gate": "pass",
                "relation_review_required": True,
                "relation_verifications": [relation_record],
            },
        }),
        encoding="utf-8",
    )
    rc, report = verify_post_revision_review(wd, "S01")
    assert rc == 0, report
    return quote


def _bound_admission(rel, wd: Path) -> dict:
    _write_semantic_review(wd)
    admission = _admission(wd)
    admission["protected_artifacts"] = rel.protected_artifact_manifest(wd)
    return admission


def test_write_admission_is_atomic_and_clears_old_terminal(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    path = wd / "pipeline" / "audit" / "release_eligibility.yaml"
    path.write_text(yaml.safe_dump({"admission": {"old": True}, "terminal": {"outcome": "released"}}))
    admission = _admission(wd)

    rel.write_admission(wd, admission)

    state = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert state == {"admission": admission}
    assert not path.with_suffix(".yaml.tmp").exists()


def test_release_live_pass_writes_released_terminal_and_validates(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    rel.write_admission(wd, _admission(wd))
    assert rel.finalize(wd) == 0

    state = rel.load_state(wd)
    terminal = state["terminal"]
    assert terminal["outcome"] == "released"
    assert terminal["release_eligible"] is True
    assert terminal["admission_sha256"] == rel.canonical_digest(state["admission"])
    assert terminal["story_sha256"] == hashlib.sha256((wd / "story.md").read_bytes()).hexdigest()
    assert terminal["semantic_review"]["status"] == "clear"
    assert terminal["overall_aigc"] == "clear"
    assert rel.validate_release(wd) == (True, "released")


def test_finalizer_requires_current_semantic_review(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    (wd / "pipeline" / "review" / "A_aesthetic.manuscript.yaml").unlink()
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["reason"] == "semantic_review_incomplete"
    assert terminal["semantic_review"]["status"] == "not_run"
    assert terminal["overall_aigc"] == "incomplete"


def test_semantic_findings_are_quality_failure_even_if_revision_claims_complete(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _write_semantic_review(
        wd,
        status="findings",
        findings=[{
            "dimension": "ai_pattern",
            "subkind": "planning_trace_leakage",
            "scene_id": None,
            "location": "第一节与第三节",
            "evidence_quote": "他先确认边界。她随后确认答案。",
            "source": "story",
            "issue": "多个角色共享同一确认与结算结构",
            "suggestion": "按角色欲望与实际后果重组两段",
        }],
    )
    (wd / "pipeline" / "revision_summary.md").write_text(
        "status: complete\n\n已执行修订。\n", encoding="utf-8"
    )
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 1
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "quality_failed"
    assert terminal["reason"] == "live_semantic_review_findings"
    assert terminal["overall_aigc"] == "findings"


def test_semantic_review_becomes_stale_after_story_change(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    (wd / "story.md").write_text(
        (wd / "story.md").read_text(encoding="utf-8") + "\n他又补了一句。\n",
        encoding="utf-8",
    )
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["semantic_review"]["status"] == "stale"
    assert terminal["overall_aigc"] == "incomplete"


def test_current_post_revision_semantic_review_supersedes_stale_initial_report(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _write_semantic_review(
        wd,
        status="findings",
        findings=[{
            "dimension": "ai_pattern",
            "subkind": "planning_trace_leakage",
            "scene_id": None,
            "location": "第一节与第三节",
            "evidence_quote": "他先确认边界。她随后确认答案。",
            "source": "story",
            "issue": "初审问题",
            "suggestion": "删除重复确认并重组选择",
        }],
    )
    (wd / "story.md").write_text(
        (wd / "story.md").read_text(encoding="utf-8") + "\n雨停了。\n",
        encoding="utf-8",
    )
    _write_semantic_review(wd, review_round=2)
    _bind_reader_revision(wd)
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 0
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["semantic_review"]["review_round"] == 2
    assert terminal["overall_aigc"] == "clear"


def test_unchanged_round_two_cannot_clear_round_one_findings(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _write_semantic_review(
        wd,
        status="findings",
        findings=[{
            "dimension": "ai_pattern",
            "subkind": "planning_trace_leakage",
            "scene_id": "S01",
            "location": "第一节与第三节",
            "evidence_quote": "他先确认边界。她随后确认答案。",
            "source": "story",
            "issue": "相同正文仍有跨段确认与结算结构",
            "suggestion": "先改变正文结构，再执行修后复审",
        }],
    )
    _write_semantic_review(wd, review_round=2)
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 1
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "quality_failed"
    assert terminal["semantic_review"]["status"] == "findings"
    assert terminal["semantic_review"]["review_round"] == 1


def test_planning_trace_coverage_requires_typed_finding_and_matches_it(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    base_finding = {
        "dimension": "voice_consistency",
        "subkind": None,
        "scene_id": None,
        "location": "第一节与第三节",
        "evidence_quote": "两个人都用同一套确认句。",
        "source": "story",
        "issue": "跨角色声音趋同",
        "suggestion": "按各自关系目的重写",
    }
    _write_semantic_review(wd, status="findings", findings=[base_finding])
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["semantic_review"]["status"] == "incomplete"
    assert terminal["semantic_review"]["reason"] == "semantic_review_invalid"

    report_path = wd / "pipeline" / "review" / "A_aesthetic.manuscript.yaml"
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    report["review_findings"][0].update({
        "dimension": "ai_pattern",
        "subkind": "planning_trace_leakage",
    })
    report["coverage"]["planning_trace_leakage"] = "clear"
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True), encoding="utf-8")

    assert rel.finalize(wd) == 2
    assert rel.load_state(wd)["terminal"]["semantic_review"]["status"] == "incomplete"


def test_finalizer_requires_reader_review_or_auditable_skip(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    (wd / "pipeline" / "review" / "reader_review.yaml").unlink()
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["reason"] == "reader_review_incomplete"
    assert terminal["reader_review"]["reason"] == "reader_review_missing"

    (wd / "pipeline" / "audit" / "reader_review_skip.yaml").write_text(
        yaml.safe_dump({"reason": "evaluation window cannot support reader dispatch"}),
        encoding="utf-8",
    )
    assert rel.finalize(wd) == 0
    assert rel.validate_release(wd) == (True, "released")


def test_finalizer_requires_nonempty_reader_findings_to_reach_current_story(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    review_path = wd / "pipeline" / "review" / "reader_review.yaml"
    review_path.write_text(
        yaml.safe_dump({"input_snapshot": "pipeline/review/snapshots/story.semantic.round1.md", "reader_findings": [{"location": "结尾"}]}),
        encoding="utf-8",
    )
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 2
    assert rel.load_state(wd)["terminal"]["reader_review"]["reason"] == (
        "reader_revision_artifact_missing"
    )

    (wd / "pipeline" / "revision_summary.md").write_text(
        "status: complete\n\nreader finding 已处置。\n", encoding="utf-8"
    )
    story_sha = hashlib.sha256((wd / "story.md").read_bytes()).hexdigest()
    quality = {
        "schema_version": "revision-quality-v1",
        "lane": "manuscript",
        "reader_review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "provenance": {
            "before": {"state": "fresh", "actual_text_sha256": story_sha},
            "after": {"state": "fresh", "actual_text_sha256": story_sha},
        },
        "protected_results": {"verdict": "PASS"},
    }
    (wd / "pipeline" / "review" / "manuscript_quality.reader.round1.yaml").write_text(
        yaml.safe_dump(quality), encoding="utf-8"
    )

    assert rel.finalize(wd) == 0
    assert rel.load_state(wd)["terminal"]["reader_review"]["status"] == "revised"
    assert rel.validate_release(wd) == (True, "released")


def test_release_live_pass_binds_protected_integrity_when_declared(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _scaffold_protected_scene(wd, with_literal=True)
    rel.write_admission(wd, _bound_admission(rel, wd))

    assert rel.finalize(wd) == 0

    terminal = rel.load_state(wd)["terminal"]
    assert terminal["protected_integrity"]["verdict"] == "PASS"
    assert terminal["protected_integrity"]["literal_results"][0]["found"] is True
    assert rel.validate_release(wd) == (True, "released")


def test_finalizer_rejects_protected_sidecar_deleted_after_admission(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _scaffold_protected_scene(wd, with_literal=True)
    integrity_path = wd / "pipeline" / "scene_S01" / "protected_integrity.yaml"
    admission = _admission(wd)
    admission["protected_artifacts"] = [{
        "scene_id": "S01",
        "path": "pipeline/scene_S01/protected_integrity.yaml",
        "sha256": hashlib.sha256(integrity_path.read_bytes()).hexdigest(),
    }]
    rel.write_admission(wd, admission)
    integrity_path.unlink()

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "escalated"
    assert terminal["reason"] == "protected_artifacts_changed"


def test_finalizer_rejects_manuscript_edit_over_active_relation(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    quote = _scaffold_protected_scene(wd)
    (wd / "story.md").write_text(
        (wd / "story.md").read_text(encoding="utf-8").replace(
            quote,
            "伞柄内侧已经磨平",
            1,
        ),
        encoding="utf-8",
    )
    rel.write_admission(wd, _bound_admission(rel, wd))

    assert rel.finalize(wd) == 2

    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "escalated"
    assert terminal["reason"] == "protected_integrity_failed"
    assert terminal["protected_integrity"]["verdict"] == "FAIL"
    assert "manuscript_relation_span_overlap" in terminal["protected_integrity"]["reason"]


def test_finalizer_rejects_ambiguous_manuscript_relation_anchor(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    quote = _scaffold_protected_scene(wd)
    with (wd / "story.md").open("a", encoding="utf-8") as handle:
        handle.write(f"\n附记：{quote}。\n")
    rel.write_admission(wd, _bound_admission(rel, wd))

    assert rel.finalize(wd) == 2

    protected = rel.load_state(wd)["terminal"]["protected_integrity"]
    assert protected["verdict"] == "FAIL"
    assert "manuscript_active_anchor_ambiguous" in protected["reason"]


def test_finalizer_rejects_manuscript_literal_loss(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _scaffold_protected_scene(wd, with_literal=True)
    (wd / "story.md").write_text(
        (wd / "story.md").read_text(encoding="utf-8").replace(
            "乙未三月",
            "旧日年月",
        ),
        encoding="utf-8",
    )
    rel.write_admission(wd, _bound_admission(rel, wd))

    assert rel.finalize(wd) == 2

    protected = rel.load_state(wd)["terminal"]["protected_integrity"]
    assert protected["verdict"] == "FAIL"
    assert "manuscript_literal_not_found" in protected["reason"]


def test_non_release_intents_and_human_skip_complete_without_release(tmp_path):
    import release_eligibility as rel

    for intent in ("smoke", "evaluation"):
        wd = _workdir(tmp_path, intent)
        rel.write_admission(wd, _admission(wd, intent))
        assert rel.finalize(wd) == 1
        terminal = rel.load_state(wd)["terminal"]
        assert terminal["outcome"] == "completed_not_releasable"
        assert terminal["release_eligible"] is False

    wd = _workdir(tmp_path / "skipped", "release")
    rel.write_admission(wd, _admission(wd, "release", skipped=["scene_review"]))
    assert rel.finalize(wd) == 1
    assert rel.load_state(wd)["terminal"]["outcome"] == "completed_not_releasable"


def test_live_failure_overrules_stale_pass_report(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path, dirty=True)
    _write_semantic_review(wd, status="findings", findings=[{
        "dimension": "ai_pattern", "subkind": "planning_trace_leakage",
        "scene_id": None, "location": "全文", "source": "story",
        "evidence_quote": "那把伞贴着这道门，那种声音穿过那层纸。", "issue": "整句反复出现而无新的承接或叙述作用",
        "suggestion": "补足读者理解所需对象并合并无作用重复",
    }])
    stale = wd / "pipeline" / "review" / "wholetext_gate.yaml"
    stale.write_text(yaml.safe_dump({"verdict": "PASS", "input_story_sha256": "old"}))
    rel.write_admission(wd, _admission(wd))

    assert rel.finalize(wd) == 1
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "quality_failed"
    assert terminal["wholetext"]["verdict"] == "REVIEW"
    assert terminal["semantic_review"]["status"] == "findings"


def test_consumer_rejects_terminal_after_story_or_admission_mutation(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    rel.write_admission(wd, _admission(wd))
    assert rel.finalize(wd) == 0

    (wd / "story.md").write_text((wd / "story.md").read_text() + "又添一句。")
    ok, reason = rel.validate_release(wd)
    assert not ok and reason == "story_hash_mismatch"

    # Restore by re-finalizing, then mutate admission without re-finalizing.
    _write_semantic_review(wd, review_round=2)
    _bind_reader_revision(wd)
    assert rel.finalize(wd) == 0
    state = rel.load_state(wd)
    state["admission"]["reasons"].append("late mutation")
    rel.atomic_write_state(wd, state)
    ok, reason = rel.validate_release(wd)
    assert not ok and reason == "admission_digest_mismatch"


def test_consumer_rejects_protected_state_mutation_after_terminal(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    _scaffold_protected_scene(wd, with_literal=True)
    rel.write_admission(wd, _bound_admission(rel, wd))
    assert rel.finalize(wd) == 0

    integrity_path = wd / "pipeline" / "scene_S01" / "protected_integrity.yaml"
    state = yaml.safe_load(integrity_path.read_text(encoding="utf-8"))
    state["declaration_snapshots"][0]["tokens"][0]["raw"] = "被篡改"
    integrity_path.write_text(yaml.safe_dump(state, allow_unicode=True), encoding="utf-8")

    assert rel.validate_release(wd) == (
        False,
        "protected_artifact_manifest_mismatch",
    )


def test_finalizer_rejects_internally_inconsistent_admission(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    forged = _admission(wd)
    forged["scenes"][0]["machine"] = {
        "closed": False,
        "entry_states": ["pending"],
    }
    # A stale/forged summary boolean cannot override the per-check result.
    forged["phase7_admitted"] = True
    forged["release_candidate"] = True
    rel.write_admission(wd, forged)

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "escalated"
    assert terminal["release_eligible"] is False
    assert terminal["reason"] == "admission_invalid"


def test_finalizer_rejects_unknown_skip_and_candidate_mismatch(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    forged = _admission(wd)
    forged["skipped_checks"] = ["machine_directive"]
    forged["release_candidate"] = True
    rel.write_admission(wd, forged)

    assert rel.finalize(wd) == 2
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["outcome"] == "escalated"
    assert terminal["reason"] == "admission_invalid"


def test_repeated_admission_preserves_terminal(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    admission = _admission(wd)
    # 首次尚无状态文件；相同入场检查不能清除已产生的终态。
    rel.write_admission(wd, admission)
    state = {"admission": admission, "terminal": {"outcome": "released"}}
    rel.atomic_write_state(wd, state)
    rel.write_admission(wd, admission)
    assert rel.load_state(wd) == state


def test_empty_reader_report_requires_current_text_or_bound_revision(tmp_path):
    import release_eligibility as rel

    wd = _workdir(tmp_path)
    review = wd / "pipeline/review/reader_review.yaml"
    before_sha = hashlib.sha256((wd / "story.md").read_bytes()).hexdigest()
    assert rel._reader_review_state(wd, before_sha)["status"] == "clean"
    (wd / "story.md").write_text("当前稿有一处 A 审阅提出的修改。", encoding="utf-8")
    after_sha = hashlib.sha256((wd / "story.md").read_bytes()).hexdigest()
    assert rel._reader_review_state(wd, after_sha)["status"] == "incomplete"
    (wd / "pipeline/revision_summary.md").write_text("status: complete\nA 问题已修订。", encoding="utf-8")
    quality = {
        "schema_version": "revision-quality-v1", "lane": "manuscript",
        "reader_review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "provenance": {
            "before": {"state": "fresh", "actual_text_sha256": before_sha},
            "after": {"state": "fresh", "actual_text_sha256": after_sha},
        },
        "protected_results": {"verdict": "PASS"},
    }
    (wd / "pipeline/review/manuscript_quality.reader.round1.yaml").write_text(yaml.safe_dump(quality))
    assert rel._reader_review_state(wd, after_sha)["status"] == "revised"
    data = yaml.safe_load(review.read_text())
    data["reader_findings"] = [{"location": "新增反馈"}]
    review.write_text(yaml.safe_dump(data))
    assert rel._reader_review_state(wd, after_sha)["status"] == "incomplete"


def test_review_signals_use_current_semantic_result(tmp_path):
    import release_eligibility as rel
    wd = _workdir(tmp_path)
    (wd / "story.md").write_text("他怔了怔。\n她没说话。\n不是恐惧，是认出来了。\n" * 30)
    _write_semantic_review(wd)
    rel.write_admission(wd, _admission(wd))
    assert rel.finalize(wd) == 0
    terminal = rel.load_state(wd)["terminal"]
    assert terminal["wholetext"]["verdict"] == "REVIEW"
    assert terminal["overall_aigc"] == "clear"
    assert rel.validate_release(wd)[0]
    _write_semantic_review(wd, status="findings", findings=[{"dimension": "ai_pattern", "subkind": "planning_trace_leakage", "scene_id": None, "location": "全文", "source": "story", "evidence_quote": "他怔了怔。", "issue": "角色反应持续重复且无新作用", "suggestion": "保留必要认识并重组"}])
    assert rel.finalize(wd) == 1
