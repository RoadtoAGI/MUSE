#!/usr/bin/env python3
"""章审阅完整性 gate。用于发布和装配前检查当前场景审阅与真实 pending。

exit 0 表示审阅完成或明确 skip_review 生效；输入缺失/损坏和未闭合均 exit 2。
缺 Phase 6 可由有效 skip_review 明确授权；存在但损坏的场景索引不可跳过。
统计命中不产生审阅义务；已发出的修订指令必须完成或由有效语义理由处置。
"""
from __future__ import annotations
import sys
from pathlib import Path

VALID_VERDICTS = {"PASS", "PATCH", "ROLLBACK", "REWRITE"}
EMPTY_REASONS = {"", "skip", "manual_choice", "none", "n/a", "todo", "tbd"}


def _warn(msg: str) -> None:
    print(f"[verify_review_complete WARN] {msg}", file=sys.stderr)


def _fail(msg: str, detail: list[str] | None = None) -> int:
    print(f"[verify_review_complete] ❌ {msg}", file=sys.stderr)
    if detail:
        for line in detail:
            print(f"  {line}", file=sys.stderr)
    print(
        "  ↳ 必须先 dispatch consistency-reviewer + scene-reviewer 走完 §1.5，或在",
        file=sys.stderr,
    )
    print(
        "    pipeline/audit/skip_review.yaml 声明 escape hatch "
        "（reason: \"<具体可审计>\" + risk_acknowledged: true）",
        file=sys.stderr,
    )
    print(
        "  ↳ 详见 serial-chapter-writing/references/"
        "execution-protocol.md §1.5",
        file=sys.stderr,
    )
    return 2


def _ai_pattern_gate_closed(
    post_revision: dict, current_machine_channel: bool = False,
) -> tuple[bool, str | None]:
    gate = post_revision.get("ai_pattern_gate")
    if not isinstance(gate, dict):
        return True, None
    if str(gate.get("reviewer_gate") or "").lower() == "fail":
        return False, "reviewer_gate_fail"
    if current_machine_channel:
        return True, None  # 当前机器通道已单独核验；不重用修订时的机器快照。
    machine_gate = str(gate.get("machine_gate") or "").lower()
    if machine_gate != "fail":
        return True, None
    override = gate.get("override") or {}
    if not isinstance(override, dict):
        return False, "machine_fail_no_override"
    if bool(override.get("applied")) and (override.get("override_reason") or "").strip():
        return True, None
    return False, "machine_fail_no_override"


def _check_lint_ledger(review_dir: Path, scene_id: str, verdict: str, yaml_module) -> tuple[bool, str]:
    """Rn+2 O3: ledger hard gate + malformed YAML 处理。
    Returns: (is_hard_fail, reason)。is_hard_fail=False 且 reason 非空 -> WARN advisory。
    """
    machine_ledger_path = review_dir / f"{scene_id}.machine_ledger.yaml"
    if machine_ledger_path.exists():
        try:
            machine_ledger = yaml_module.safe_load(
                machine_ledger_path.read_text(encoding="utf-8")
            ) or {}
        except (yaml_module.YAMLError, OSError) as exc:
            return True, f"{scene_id}: machine_ledger 读取失败: {exc}"
        if not isinstance(machine_ledger, dict) or not isinstance(machine_ledger.get("entries"), list):
            return True, f"{scene_id}: machine_ledger 必须含 entries 列表"
        if machine_ledger.get("scene_id") != scene_id:
            return True, f"{scene_id}: machine_ledger scene_id 不匹配"
        return False, ""

    ledger_path = review_dir / f"scene_{scene_id}.lint_resolution_ledger.yaml"
    requires_hard = ledger_path.exists()

    if not ledger_path.exists():
        msg = f"scene_{scene_id}: lint_resolution_ledger.yaml 缺失"
        if requires_hard:
            return True, f"{msg}（verdict={verdict} 或含 cluster/high hit）— hard fail"
        _warn(f"{msg}（advisory only）")
        return False, ""

    try:
        ledger = yaml_module.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
    except yaml_module.YAMLError as exc:
        return True, f"scene_{scene_id}: ledger malformed YAML — hard fail: {exc}"

    if not isinstance(ledger, dict):
        return True, f"{scene_id}: ledger 必须为映射"
    if not isinstance(ledger.get("v1_triage"), (dict, list)):
        msg = f"scene_{scene_id}: ledger 缺 v1_triage"
        if requires_hard:
            return True, f"{msg} — hard fail"
        _warn(f"{msg}（advisory only）")
        return False, ""

    updates = ledger.get("post_revision_updates")
    if updates is not None and not isinstance(updates, (dict, list)):
        return True, f"scene_{scene_id}: post_revision_updates 格式异常 — hard fail"

    return False, ""


def _check_machine_channel(review_dir: Path, scene_id: str, yaml_module) -> tuple[bool, str]:
    directive_path = review_dir / f"{scene_id}.machine_directive.yaml"
    if not directive_path.exists():
        return False, ""

    try:
        directive = yaml_module.safe_load(directive_path.read_text(encoding="utf-8")) or {}
    except (yaml_module.YAMLError, OSError) as exc:
        return True, f"{scene_id}: machine_directive 读取失败: {exc}"

    if (not isinstance(directive, dict)
            or directive.get("scene_id") != scene_id
            or not isinstance(directive.get("entries"), list)):
        return True, f"{scene_id}: machine_directive 的 scene_id / entries 无效"
    entries = directive["entries"]
    if any(not isinstance(entry, dict) or not isinstance(entry.get("id"), str)
           or not entry["id"] or entry.get("status") not in {"pending", "resolved", "escalated"}
           for entry in entries):
        return True, f"{scene_id}: machine_directive 条目 id / status 无效"
    if any(entry["status"] == "escalated" for entry in entries):
        return True, f"{scene_id}: machine directive 有待决 escalated 条目"
    pending_ids = [entry["id"] for entry in entries if entry["status"] == "pending"]
    if not pending_ids:
        return False, ""

    ledger_path = review_dir / f"{scene_id}.machine_ledger.yaml"
    if ledger_path.exists():
        try:
            ledger = yaml_module.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
        except (yaml_module.YAMLError, OSError) as exc:
            return True, f"{scene_id}: machine_ledger 读取失败: {exc}"
        if (not isinstance(ledger, dict) or ledger.get("scene_id") != scene_id
                or not isinstance(ledger.get("entries"), list)):
            return True, f"{scene_id}: machine_ledger 的 scene_id / entries 无效"
        ledger_status_by_id = {
            entry.get("id"): entry.get("status")
            for entry in ledger["entries"]
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        blocking = [entry_id for entry_id in pending_ids
                    if ledger_status_by_id.get(entry_id) not in {"resolved", "objection_granted"}]
        if blocking:
            # 旧 distribution PASS 文件不能盖过本次仍 issued 的条目。
            return True, f"{scene_id}: machine directive pending 未消费: {blocking}"
        return False, ""

    # 只有旧 gate、尚无 machine ledger 的产物沿原兼容契约读取。
    gate_path = review_dir / f"{scene_id}.distribution_gate.yaml"
    if gate_path.exists():
        try:
            gate = yaml_module.safe_load(gate_path.read_text(encoding="utf-8")) or {}
        except (yaml_module.YAMLError, OSError) as exc:
            return True, f"{scene_id}: distribution_gate 读取失败: {exc}"
        if isinstance(gate, dict) and gate.get("verdict") == "PASS":
            return False, ""
    return True, f"{scene_id}: machine directive pending 未消费: {pending_ids}"


def _skip_review_valid(work_dir: Path, yaml_module) -> bool:
    path = work_dir / "pipeline" / "audit" / "skip_review.yaml"
    if not path.exists():
        return False
    try:
        data = yaml_module.safe_load(path.read_text(encoding="utf-8"))
    except (yaml_module.YAMLError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    reason = data.get("reason")
    return (isinstance(reason, str) and reason.strip().lower() not in EMPTY_REASONS
            and data.get("risk_acknowledged") is True)


def _input_fail(message: str) -> int:
    print(f"[verify_review_complete] 输入无效：{message}", file=sys.stderr)
    return 2


def check(work_dir: Path) -> int:
    try:
        import yaml
    except ImportError:
        return _input_fail("PyYAML 不可用")
    work_dir = work_dir.resolve()
    if not work_dir.is_dir():
        return _input_fail(f"工作目录不存在：{work_dir}")
    dev_yaml = work_dir / "pipeline" / "phase6_development.yaml"
    if not dev_yaml.exists():
        return 0 if _skip_review_valid(work_dir, yaml) else _input_fail("缺 phase6_development.yaml 且无有效 skip_review")
    try:
        dev_data = yaml.safe_load(dev_yaml.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        return _input_fail(f"{dev_yaml}: {exc}")
    if not isinstance(dev_data, dict) or not isinstance(dev_data.get("scenes"), list) or not dev_data["scenes"]:
        return _input_fail("Phase 6 必须含非空 scenes 列表")
    scene_ids = []
    for scene in dev_data["scenes"]:
        if not isinstance(scene, dict):
            return _input_fail("每个场景必须为映射")
        sid = scene.get("scene_id") or scene.get("id")
        if not isinstance(sid, str) or not sid.strip() or sid != sid.strip() or Path(sid).name != sid or sid in {".", ".."} or "\\" in sid:
            return _input_fail(f"场景 ID 无效：{sid!r}")
        if scene.get("id") and scene.get("scene_id") and scene["id"] != scene["scene_id"]:
            return _input_fail(f"场景 ID 别名冲突：{sid}")
        if sid in scene_ids:
            return _input_fail(f"场景 ID 重复：{sid}")
        scene_ids.append(sid)
        expected = work_dir / "pipeline" / "scenes" / f"scene_{sid}.md"
        declared = scene.get("file_path") or str(expected.relative_to(work_dir))
        if not isinstance(declared, str) or (work_dir / declared).resolve() != expected.resolve():
            return _input_fail(f"{sid}: file_path 与受审场景不一致")
        if not expected.is_file():
            return _input_fail(f"缺场景正文：{expected}")

    # 1. 收集缺失 / verdict 异常的场景
    review_dir = work_dir / "pipeline" / "review"
    missing: list[str] = []
    invalid_verdict: list[tuple[str, str]] = []
    escalated_unclosed: list[tuple[str, str]] = []
    patch_not_applied: list[str] = []
    patch_no_post_revision: list[str] = []
    rollback_no_post_revision: list[tuple[str, str]] = []
    ai_gate_unclosed: list[tuple[str, str]] = []
    ledger_hard_fail: list[tuple[str, str]] = []
    machine_channel_unclosed: list[tuple[str, str]] = []
    post_revision_pass_unclosed: list[tuple[str, str]] = []

    for sid in scene_ids:
        review_yaml = review_dir / f"scene_{sid}.yaml"
        if not review_yaml.exists():
            missing.append(sid)
            continue
        try:
            r = yaml.safe_load(review_yaml.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError) as e:
            _warn(f"scene_{sid}.yaml 读取失败: {e}（视为缺失）")
            missing.append(sid)
            continue

        if not isinstance(r, dict) or r.get("scene_id") != sid:
            invalid_verdict.append((sid, "报告结构或 scene_id 无效"))
            continue
        verdict = str(r.get("verdict") or "").upper()
        written_by = r.get("written_by", "")
        review_incomplete = bool(r.get("review_incomplete"))

        if verdict == "ESCALATED" or review_incomplete or r.get("missing_inputs") or written_by in {"orchestrator_input_gate", "orchestrator_fastpath_gate"}:
            if written_by in {"orchestrator_input_gate", "orchestrator_fastpath_gate"} or review_incomplete:
                escalated_unclosed.append((sid, written_by or "review_incomplete"))
                continue
            escalated_unclosed.append((sid, "escalated_misuse"))
            continue

        if verdict not in VALID_VERDICTS:
            invalid_verdict.append((sid, verdict or "<空>"))
            continue

        # Rn+2 O3 + R1 F2: ledger hard gate（所有 valid verdict 通用）
        hard_fail, reason = _check_lint_ledger(review_dir, sid, verdict, yaml)
        if hard_fail:
            ledger_hard_fail.append((sid, reason))
            continue

        hard_fail, reason = _check_machine_channel(review_dir, sid, yaml)
        if hard_fail:
            machine_channel_unclosed.append((sid, reason))
            continue

        post_rev = review_dir / f"scene_{sid}.post_revision.yaml"
        needs_post = verdict in {"PATCH", "ROLLBACK", "REWRITE"}
        if verdict == "PATCH":
            applied = work_dir / "pipeline" / f"scene_{sid}" / "patch_directive.applied.yaml"
            if not applied.exists():
                patch_not_applied.append(sid)
                continue
        if needs_post or post_rev.exists():
            try:
                pr = yaml.safe_load(post_rev.read_text(encoding="utf-8")) or {}
            except (yaml.YAMLError, OSError):
                pr = {}
            if (not isinstance(pr, dict)
                    or pr.get("scene_id") != sid
                    or str(pr.get("verdict") or "").upper() != "PASS"
                    or pr.get("missing_inputs")
                    or pr.get("review_incomplete")
                    or pr.get("written_by") in {"orchestrator_input_gate", "orchestrator_fastpath_gate"}):
                if verdict == "PATCH":
                    patch_no_post_revision.append(sid)
                else:
                    rollback_no_post_revision.append((sid, verdict))
                continue

            # 旧报告中的明确语义失败不能被机器通过覆盖。
            targeted = pr.get("targeted_span_gate") or {}
            patches = (targeted.get("per_patch") or []) if isinstance(targeted, dict) else []
            if not isinstance(patches, list):
                post_revision_pass_unclosed.append((sid, "targeted_span_gate.per_patch 必须为列表"))
                continue
            if any(isinstance(p, dict) and (
                    p.get("semantic_function_preserved") is False
                    or p.get("contract_conflict_observed") is True) for p in patches):
                post_revision_pass_unclosed.append((sid, "post verdict=PASS 与补丁语义失败冲突"))
                continue

            current_machine_channel = (
                (review_dir / f"{sid}.machine_ledger.yaml").exists()
                and (review_dir / f"{sid}.machine_directive.yaml").exists()
            )
            gate_closed, gate_reason = _ai_pattern_gate_closed(pr, current_machine_channel)
            if not gate_closed:
                ai_gate_unclosed.append((sid, gate_reason or "ai_pattern_gate"))
                continue
            if current_machine_channel:
                continue  # 当前机器通道已在上方校验，无需旧 lint_resolution_ledger。

            from scene_review_schema_validator import validate_post_revision_pass
            ledger_path = review_dir / f"scene_{sid}.lint_resolution_ledger.yaml"
            lint_v2_path = review_dir / "lint" / f"{sid}.ai_filler.v2.yaml"
            phase5_path = work_dir / "pipeline" / "phase5_scenes.yaml"
            try:
                ledger_data = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
                lint_v2_data = yaml.safe_load(lint_v2_path.read_text(encoding="utf-8")) if lint_v2_path.exists() else {}
                phase5_data = yaml.safe_load(phase5_path.read_text(encoding="utf-8")) if phase5_path.exists() else {}
            except (yaml.YAMLError, OSError) as exc:
                post_revision_pass_unclosed.append((sid, f"旧复审输入读取失败: {exc}"))
                continue
            scene_card_equiv = next(
                (s for s in (phase5_data or {}).get("scenes") or []
                 if isinstance(s, dict) and (s.get("id") or s.get("scene_id")) == sid),
                {},
            )
            pr_check = validate_post_revision_pass(pr, ledger_data, lint_v2_data, scene_card=scene_card_equiv)
            if not pr_check.valid:
                post_revision_pass_unclosed.append((sid, pr_check.reason))

    if (
        not missing
        and not invalid_verdict
        and not escalated_unclosed
        and not patch_not_applied
        and not patch_no_post_revision
        and not rollback_no_post_revision
        and not ai_gate_unclosed
        and not ledger_hard_fail
        and not machine_channel_unclosed
        and not post_revision_pass_unclosed
    ):
        return 0  # §1.5 完整，放行

    # 用户明确跳过审阅的既有通道；输入有效性已在前面检查。
    if _skip_review_valid(work_dir, yaml):
        return 0

    # 3. 阻断 + 输出诊断
    detail = []
    if missing:
        detail.append(f"缺少 review/scene_*.yaml：{missing}")
    if invalid_verdict:
        detail.append(
            "verdict 不在 {PASS,PATCH,ROLLBACK,REWRITE}: "
            + ", ".join(f"scene_{s}={v}" for s, v in invalid_verdict)
        )
    if escalated_unclosed:
        detail.append(
            f"ESCALATED 未闭合（input_gate 失败 / review_incomplete）: "
            + ", ".join(f"scene_{s}({reason})" for s, reason in escalated_unclosed)
        )
    if patch_not_applied:
        detail.append(f"PATCH verdict 但 patch_directive.applied.yaml 缺失: {patch_not_applied}")
    if patch_no_post_revision:
        detail.append(f"PATCH 未闭合（缺 post_revision PASS）: {patch_no_post_revision}")
    if rollback_no_post_revision:
        detail.append(
            "场景复审未闭合（缺当前 post_revision PASS）: "
            + ", ".join(f"scene_{s}({v})" for s, v in rollback_no_post_revision)
        )
    if ai_gate_unclosed:
        detail.append(
            "复审语义或旧机器结果未闭合: "
            + ", ".join(f"scene_{s}({reason})" for s, reason in ai_gate_unclosed)
        )
    if ledger_hard_fail:
        detail.append(f"ledger hard fail: {ledger_hard_fail}")
    if machine_channel_unclosed:
        detail.append(f"machine channel 未闭合: {machine_channel_unclosed}")
    if post_revision_pass_unclosed:
        detail.append(f"post-revision PASS 准入未闭合: {post_revision_pass_unclosed}")

    return _fail(
        "§1.5 场景审阅链路未跑完，发布 / 拼接被阻断",
        detail,
    )


def main() -> int:
    if len(sys.argv) < 2:
        return _input_fail("用法: verify_review_complete.py <work_dir>")
    return check(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    sys.exit(main())
