#!/usr/bin/env python3
"""verify_patch_directive_traceability.py — patch_directive 溯源校验

orchestrator 在 dispatch reviser 前调用，校验 patch_directive 引用的问题
仍存在于当前正文（防 reviser 已删句子但 patch 仍引用）+ 不引用 user_accepted
findings（防误改用户接受的残留）。

1. 单句 patch 用 anchor_quote，rewrite_span 用 old_span 与首尾锚。原文须能
   唯一定位；重复片段须由 location.line_range 消歧。不设字符长度门槛。
2. patch.issue_id / patch.issue 不得引用 C 组**显式 user_accepted / next_round_only**
   finding：category ∈ {user_accepted_as_known_issue, next_round_only}、
   suggestion 含同类标记、或 escalation_decision.user_accepted_findings[]。
   **裸 status=persists 不入黑名单**——persists 可能是当前轮要修的问题。

接口：
    python3 verify_patch_directive_traceability.py --scene-id S01 --pipeline-root <path>

退出码：
    0 — 所有 patch 都可追溯（含 patch_directive.yaml 不存在的合法状况）
    1 — 任一 patch 引述 stale 或引用 user_accepted finding
"""
import argparse
import sys
from pathlib import Path

import yaml





def _user_accepted_blacklist(c_yaml_path: Path):
    """从 C 组 yaml 派生 user_accepted issue_id 黑名单（plan v9 §11.3 校验 2）

    v9 codex review IMPORTANT #2 修订：只认显式 user_accepted/next_round_only 标记。
    **裸 `status=persists` 不入黑名单**——persists 表示"问题仍未解决"，可能是当前轮要修
    的问题，不是用户接受。误把所有 persists 当 user_accepted 会让正常 patch 被错误拦截。

    黑名单收纳信号：
    - issue.category ∈ {"user_accepted_as_known_issue", "next_round_only"}
    - issue.suggestion 文本含 "user_accepted_as_known_issue" / "next_round_only"
    - escalation_decision.user_accepted_findings[] 列出
    """
    blacklist = set()
    if not c_yaml_path.exists():
        return blacklist
    try:
        data = yaml.safe_load(c_yaml_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return blacklist

    accept_signals = ("user_accepted_as_known_issue", "next_round_only")
    for issue in data.get("issues", []) or []:
        if not isinstance(issue, dict):
            continue
        category = (issue.get("category") or "").strip()
        suggestion = (issue.get("suggestion") or "").strip()
        is_accepted = (
            category in accept_signals
            or any(s in suggestion for s in accept_signals)
        )
        if is_accepted:
            iid = issue.get("issue_id")
            if iid:
                blacklist.add(str(iid).strip())

    esc = data.get("escalation_decision") or {}
    for entry in esc.get("user_accepted_findings", []) or []:
        if isinstance(entry, dict) and entry.get("issue_id"):
            blacklist.add(str(entry["issue_id"]).strip())
        elif isinstance(entry, str):
            blacklist.add(entry.strip())

    return blacklist


def _verify_patch(patch: dict, scene_md_text: str, blacklist: set):
    """单个 patch 校验，返回 list[failure_dict]（空 list 表示通过）"""
    failures = []

    anchor = patch.get("old_span") if patch.get("patch_kind") == "rewrite_span" else patch.get("anchor_quote")
    if not isinstance(anchor, str) or not anchor.strip():
        failures.append({"failure": "missing_anchor_quote", "detail": "缺少当前原文锚点", "patch_issue_id": patch.get("issue_id")})
    elif anchor not in scene_md_text:
        failures.append({"failure": "anchor_quote_not_in_scene_md", "missing_quote": anchor[:80], "patch_issue_id": patch.get("issue_id")})
    else:
        location = patch.get("location") or {}
        bounds = location.get("line_range") if isinstance(location, dict) else None
        valid_range = isinstance(bounds, list) and len(bounds) == 2 and all(type(n) is int for n in bounds) and 1 <= bounds[0] <= bounds[1] <= len(scene_md_text.splitlines())
        if bounds is not None and not valid_range:
            failures.append({"failure": "invalid_line_range"})
        elif valid_range:
            selected = "\n".join(scene_md_text.splitlines()[bounds[0]-1:bounds[1]])
            if selected.count(anchor) != 1:
                failures.append({"failure": "anchor_not_unique_in_line_range"})
        elif scene_md_text.count(anchor) != 1:
            failures.append({"failure": "ambiguous_anchor_quote"})
        if patch.get("patch_kind") == "rewrite_span":
            start, end = patch.get("anchor_quote_start"), patch.get("anchor_quote_end")
            if not isinstance(start, str) or not start or not isinstance(end, str) or not end or not anchor.strip().startswith(start) or not anchor.strip().endswith(end):
                failures.append({"failure": "span_boundary_mismatch"})

    # 校验 2：user_accepted 黑名单
    issue_id = (patch.get("issue_id") or "").strip()
    issue_text = patch.get("issue") or ""
    for blacklisted_id in blacklist:
        if blacklisted_id in issue_id or blacklisted_id in issue_text:
            failures.append({
                "failure": "referenced_user_accepted_finding",
                "blacklisted_id": blacklisted_id,
                "patch_issue_id": issue_id,
            })

    return failures


def verify(pipeline_root: Path, scene_id: str,
           text_path: Path = None, source_filter: str = None):
    """返回 (status, patch_directive_rel_path, findings_list)

    text_path: override canonical scene md 路径（e.g. Step 4.5 用 draft.md）；
               None 时回落到 pipeline/scenes/scene_{id}.md。
    source_filter: 只校验 patch.source 匹配该值的 patch；None 表示校验全部。
    """
    patch_path = pipeline_root / "pipeline" / f"scene_{scene_id}" / "patch_directive.yaml"
    rel_path = f"pipeline/scene_{scene_id}/patch_directive.yaml"

    if not patch_path.exists():
        return "ok", rel_path, []  # PASS 路径下无 patch_directive 是合法

    try:
        patch_data = yaml.safe_load(patch_path.read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        return "failed", rel_path, [{
            "failure": "patch_directive_unreadable",
            "detail": str(e),
        }]

    patches = patch_data.get("patches") or []
    if not patches:
        return "ok", rel_path, []

    # text_path override: Step 4.5 hook 传 draft.md；默认用 canonical scenes/ 路径
    scene_md_path = Path(text_path) if text_path is not None else (
        pipeline_root / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    )
    if not scene_md_path.exists():
        return "failed", rel_path, [{
            "failure": "scene_md_missing",
            "detail": f"{scene_md_path} 不存在",
        }]
    scene_md_text = scene_md_path.read_text()

    blacklist = _user_accepted_blacklist(
        pipeline_root / "pipeline" / "review" / "C_structural_consistency.yaml"
    )

    all_failures = []
    for i, patch in enumerate(patches):
        if not isinstance(patch, dict):
            continue
        # source_filter: 跳过 source 不匹配的 patch
        if source_filter is not None:
            patch_source = (patch.get("source") or "").strip()
            if patch_source != source_filter:
                continue
        for f in _verify_patch(patch, scene_md_text, blacklist):
            f["patch_index"] = i
            all_failures.append(f)

    status = "ok" if not all_failures else "failed"
    return status, rel_path, all_failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--pipeline-root", required=True)
    parser.add_argument(
        "--text-path", default=None,
        help="Override canonical scene md 路径（e.g. Step 4.5 用 pipeline/scene_{id}/draft.md）",
    )
    parser.add_argument(
        "--source-filter", default=None,
        metavar="SOURCE",
        help="只校验 patch.source 等于该值的 patch（如 scene_review / manual）；缺省校验全部",
    )
    args = parser.parse_args()

    status, rel_path, findings = verify(
        Path(args.pipeline_root), args.scene_id,
        text_path=args.text_path,
        source_filter=args.source_filter,
    )
    payload = {
        "status": status,
        "scene_id": args.scene_id,
        "patch_directive_path": rel_path,
        "findings": findings,
        "total_failures": len(findings),
    }
    yaml.safe_dump(payload, sys.stdout, allow_unicode=True, sort_keys=False)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
