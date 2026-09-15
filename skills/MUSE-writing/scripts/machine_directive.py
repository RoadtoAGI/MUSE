#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

from ai_policy import FAMILY_REGISTRY, RULE_TO_FAMILY, density_contract_max_count, effective_policy


M_OBJECTION_CLUSTERS = {"explanatory_detour", "silence_pause_cliche", "action_log"}
HIGH_SEVERITIES = {"high", "catastrophic", "major"}
GENERIC_FUNCTION_CLAIMS = (
    "节奏需要停顿",
    "强化氛围",
    "渲染气氛",
    "保留文学性",
    "这是 voice",
    "这是voice",
    "读者可能漏看",
    "美感",
    "留白",
    "顿挫",
)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _atomic_write_active_pair(
    directive_path: Path,
    directive: dict,
    ledger_path: Path,
    ledger: dict,
) -> None:
    """Replace both active projections from fully rendered temporary files.

    The shared active_revision_id lets consumers reject a torn pair if the
    process is interrupted between the two filesystem replaces.
    """
    directive_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    directive_tmp = directive_path.with_suffix(directive_path.suffix + ".tmp")
    ledger_tmp = ledger_path.with_suffix(ledger_path.suffix + ".tmp")
    try:
        directive_tmp.write_text(
            yaml.safe_dump(directive, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        ledger_tmp.write_text(
            yaml.safe_dump(ledger, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        os.replace(ledger_tmp, ledger_path)
        os.replace(directive_tmp, directive_path)
    finally:
        directive_tmp.unlink(missing_ok=True)
        ledger_tmp.unlink(missing_ok=True)


def _artifact_revision(work_dir: Path, lint_path: Path, lint: dict) -> dict:
    resolved = lint_path.resolve()
    try:
        artifact = str(resolved.relative_to(work_dir.resolve()))
    except ValueError:
        artifact = str(resolved)
    artifact_sha = hashlib.sha256(lint_path.read_bytes()).hexdigest()
    return {
        "artifact": artifact,
        "artifact_sha256": artifact_sha,
        "input_text_sha256": lint.get("input_text_sha256"),
    }


def _hit_record(hit: dict) -> dict:
    record = {
        "lint_id": hit.get("lint_id"),
        "family": hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule")),
        "rule": hit.get("rule"),
        "locator": copy.deepcopy(hit.get("locator")),
        "evidence_quote": hit.get("evidence_quote"),
    }
    if not isinstance(record["locator"], dict):
        start, end = hit.get("start"), hit.get("end")
        if isinstance(start, int) and isinstance(end, int):
            record["locator"] = {
                "start": start,
                "end": end,
                "span": hit.get("span"),
            }
    return record


def _entry_id(scene_id: str, family: str, idx: int, raw: dict) -> str:
    raw_id = raw.get("alert_id") or raw.get("lint_id")
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    return f"{scene_id}-{family}-{idx}"


def _classify_level(policy: dict, severity: str, family: str, cluster: str) -> str:
    if severity in HIGH_SEVERITIES:
        return "S"
    if severity == "medium":
        if family in M_OBJECTION_CLUSTERS or cluster in M_OBJECTION_CLUSTERS:
            return "M"
        sovereignty = policy.get("sovereignty")
        return sovereignty if sovereignty in {"S", "M", "L"} else "L"
    return "L"


def _repair_hint(family: str, lang: str = "zh") -> str:
    return effective_policy(family, lang).get("repair") or "按当前上下文修复已确认的阅读问题"


def _lint_path(work_dir: Path, scene_id: str, lint_suffix: str | None = None) -> Path:
    stem = f"{scene_id}.ai_filler"
    if lint_suffix:
        stem = f"{stem}.{lint_suffix}"
    return work_dir / "pipeline" / "review" / "lint" / f"{stem}.yaml"


def build_directive(
    work_dir: Path,
    scene_id: str,
    lint_suffix: str | None = None,
    *,
    lint_artifact: Path | None = None,
) -> tuple[dict, dict]:
    lint_path = lint_artifact or _lint_path(work_dir, scene_id, lint_suffix)
    lint = _load_yaml(lint_path)
    revision = _artifact_revision(work_dir, lint_path, lint)
    active_revision_id = revision["artifact_sha256"]
    scene_path = work_dir / "pipeline/scenes" / f"scene_{scene_id}.md"
    scene_text = scene_path.read_text(encoding="utf-8")
    actual_sha = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()
    if lint.get("input_text_sha256") != actual_sha:
        raise ValueError("machine directive requires lint for the current scene text")

    directive_entries = []
    ledger_entries = []
    seen_ids = set()
    idx = 1
    raw_hits = [
        hit
        for hit in (lint.get("hits", lint.get("lint_hits", [])) or [])
        if isinstance(hit, dict)
    ]
    hit_by_id = {
        hit.get("lint_id"): hit
        for hit in raw_hits
        if isinstance(hit.get("lint_id"), str) and hit.get("lint_id")
    }
    raw_hit_ids = [
        hit.get("lint_id")
        for hit in raw_hits
        if isinstance(hit.get("lint_id"), str) and hit.get("lint_id")
    ]
    if len(raw_hit_ids) != len(set(raw_hit_ids)):
        raise ValueError("lint hits contain duplicate lint_id values")
    lang = str(lint.get("language") or "zh")

    alerts = list(lint.get("cluster_alerts", []) or [])
    contract_levels = {}
    for family in sorted({hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
                          for hit in raw_hits} - {None}):
        policy = effective_policy(family, lang)
        if not policy.get("density_contract"):
            continue
        # Legacy contracts used Chinese character density; observe policies skip this branch.
        maximum = density_contract_max_count(policy, len(scene_text))
        if maximum is None:
            continue
        family_hits = [hit for hit in raw_hits
                       if (hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))) == family
                       and effective_policy(family, lang, hit.get("rule")).get("lifecycle") == "enforced"]
        over_budget = len(family_hits) > maximum
        contract_levels[family] = "S" if over_budget else "L"
        if over_budget:
            prior = next((a for a in alerts if isinstance(a, dict) and a.get("family") == family), {})
            alerts = [a for a in alerts if not isinstance(a, dict) or a.get("family") != family]
            alerts.append({**prior, "family": family,
                           "alert_id": prior.get("alert_id") or f"{scene_id}-{family}-density",
                           "hits": len(family_hits),
                           "hit_ids": [hit.get("lint_id") for hit in family_hits]})

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        family = str(alert.get("family") or alert.get("cluster") or "unknown")
        cluster = alert.get("cluster") or FAMILY_REGISTRY.get(family, {}).get("cluster", "")
        severity = str(alert.get("severity") or "low")
        policy = effective_policy(family, lang)
        level = (
            _classify_level(policy, severity, family, cluster)
            if policy.get("lifecycle") == "enforced"
            else "L"
        )
        level = contract_levels.get(family, level)
        entry_id = _entry_id(scene_id, family, idx, alert)
        raw_declared_hit_ids = alert.get("hit_ids")
        declared_hit_ids = (
            list(raw_declared_hit_ids)
            if isinstance(raw_declared_hit_ids, list)
            else []
        )
        if level in {"S", "M"}:
            if len(declared_hit_ids) != len(set(declared_hit_ids)):
                raise ValueError(f"duplicate hit ids in enforced alert {entry_id}")
            if not declared_hit_ids or any(
                not isinstance(hit_id, str) or not hit_id
                for hit_id in declared_hit_ids
            ):
                raise ValueError(
                    f"enforced alert {entry_id} requires non-empty unique hit_ids"
                )
            for hit_id in declared_hit_ids:
                hit = hit_by_id.get(hit_id)
                if hit is None:
                    raise ValueError(
                        f"enforced alert {entry_id} hit_ids missing lint hit: {hit_id}"
                    )
                hit_family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
                if hit_family != family:
                    raise ValueError(
                        f"enforced alert {entry_id} hit_ids family mismatch: {hit_id}"
                    )
                if effective_policy(
                    family,
                    lang,
                    hit.get("rule"),
                ).get("lifecycle") != "enforced":
                    raise ValueError(
                        f"enforced alert {entry_id} references non-enforced hit_id: {hit_id}"
                    )
            all_hit_ids = list(declared_hit_ids)
        else:
            all_hit_ids = [
                hit_id
                for hit_id in declared_hit_ids
                if isinstance(hit_id, str) and hit_id in hit_by_id
            ]
        hit_records = [
            _hit_record(hit_by_id[hit_id])
            for hit_id in all_hit_ids
            if hit_id in hit_by_id
        ]
        seen_ids.add(entry_id)
        idx += 1
        ledger_entry = {
            "id": entry_id,
            "family": family,
            "level": level,
            "status": "issued" if level in {"S", "M"} else "observed",
        }
        if level in {"S", "M"}:
            ledger_entry.update({
                "all_hit_ids": all_hit_ids,
                "exempted_hit_ids": [],
                "remaining_hit_ids": list(all_hit_ids),
                "hit_resolutions": [
                    {"hit_id": hit_id, "status": "pending"}
                    for hit_id in all_hit_ids
                ],
            })
            _assert_hit_partition(ledger_entry)
        ledger_entries.append(ledger_entry)
        if level not in {"S", "M"}:
            continue
        directive_entry = {
            "id": entry_id,
            "family": family,
            "cluster": cluster,
            "level": level,
            "severity": severity,
            "hits": alert.get("hits", alert.get("total_count", 0)),
            "all_hit_ids": all_hit_ids,
            "exempted_hit_ids": [],
            "remaining_hit_ids": list(all_hit_ids),
            "hit_records": hit_records,
            "repair_hint": _repair_hint(family, lang),
            "status": "pending",
        }
        _assert_hit_partition(directive_entry)
        directive_entries.append(directive_entry)

    observed_hit_ids: set[str] = set()
    for alert in lint.get("observed_alerts", []) or []:
        if not isinstance(alert, dict):
            continue
        family = str(alert.get("family") or alert.get("cluster") or "unknown")
        policy = effective_policy(family, lang)
        if policy.get("lifecycle") != "observe":
            raise ValueError(
                f"enforced family routed through observed_alerts: {family}"
            )
        if alert.get("blocking") not in {None, False}:
            raise ValueError(f"observed alert cannot be blocking: {family}")
        entry_id = _entry_id(scene_id, family, idx, alert)
        declared_hit_ids = alert.get("hit_ids")
        if (
            not isinstance(declared_hit_ids, list)
            or not declared_hit_ids
            or len(declared_hit_ids) != len(set(declared_hit_ids))
            or any(not isinstance(hit_id, str) or not hit_id for hit_id in declared_hit_ids)
        ):
            raise ValueError(
                f"observed alert {entry_id} requires non-empty unique hit_ids"
            )
        hit_records = []
        for hit_id in declared_hit_ids:
            if hit_id in observed_hit_ids:
                raise ValueError(f"observed hit appears in multiple alerts: {hit_id}")
            hit = hit_by_id.get(hit_id)
            if hit is None:
                raise ValueError(
                    f"observed alert {entry_id} hit_ids missing lint hit: {hit_id}"
                )
            hit_family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
            if hit_family != family:
                raise ValueError(
                    f"observed alert {entry_id} hit_ids family mismatch: {hit_id}"
                )
            if effective_policy(family, lang, hit.get("rule")).get("lifecycle") != "observe":
                raise ValueError(
                    f"observed alert {entry_id} references non-observe hit_id: {hit_id}"
                )
            record = _hit_record(hit)
            if not isinstance(record.get("locator"), dict) or not record.get("evidence_quote"):
                raise ValueError(f"observed alert {entry_id} hit is not locatable: {hit_id}")
            observed_hit_ids.add(hit_id)
            hit_records.append(record)
        ledger_entries.append({
            "id": entry_id,
            "family": family,
            "level": "L",
            "status": "observed",
            "all_hit_ids": list(declared_hit_ids),
            "hit_records": hit_records,
        })
        seen_ids.add(entry_id)
        idx += 1

    for hit in raw_hits:
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if not family:
            continue
        if hit.get("lint_id") in observed_hit_ids:
            continue
        entry_id = _entry_id(scene_id, family, idx, hit)
        if entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        idx += 1
        ledger_entries.append({
            "id": entry_id,
            "family": family,
            "level": "L",
            "status": "observed",
        })

    directive = {
        "scene_id": scene_id,
        "language": lang,
        "active_revision_id": active_revision_id,
        "lint_revision": revision,
        "stage": "post_lint",
        "dispatch_ready": False,
        "entries": directive_entries,
        "protected_regions": [],
    }
    ledger = {
        "scene_id": scene_id,
        "language": lang,
        "active_revision_id": active_revision_id,
        "lint_revision": revision,
        "entries": ledger_entries,
        "objection_results": [],
        "history": [],
    }
    return directive, ledger


def _archive_active(
    existing_directive: dict | None,
    existing_ledger: dict | None,
) -> list[dict]:
    if not existing_ledger:
        return []
    history = copy.deepcopy(existing_ledger.get("history", []) or [])
    entries = existing_ledger.get("entries", []) or []
    if not entries and not existing_directive:
        return history
    revision_id = (
        existing_ledger.get("active_revision_id")
        or (existing_directive or {}).get("active_revision_id")
    )
    if history and revision_id and history[-1].get("active_revision_id") == revision_id:
        return history
    history.append({
        "active_revision_id": revision_id,
        "lint_revision": copy.deepcopy(
            existing_ledger.get("lint_revision")
            or (existing_directive or {}).get("lint_revision")
        ),
        "entries": copy.deepcopy(entries),
        "directive_entries": copy.deepcopy((existing_directive or {}).get("entries", []) or []),
        "objection_results": copy.deepcopy(existing_ledger.get("objection_results", []) or []),
    })
    return history


def generate_initial(work_dir: Path, scene_id: str, lint_suffix: str | None = None) -> int:
    directive_path = work_dir / "pipeline" / "review" / f"{scene_id}.machine_directive.yaml"
    ledger_path = work_dir / "pipeline" / "review" / f"{scene_id}.machine_ledger.yaml"
    existing_directive = _load_yaml(directive_path) if directive_path.exists() else None
    existing_ledger = _load_yaml(ledger_path) if ledger_path.exists() else None
    if directive_path.exists() and lint_suffix is None:
        if (existing_directive or {}).get("stage") == "refreshed":
            print(
                f"[machine_directive] ERROR: refuse to overwrite refreshed directive: {directive_path}",
                file=sys.stderr,
            )
            return 2
    try:
        directive, ledger = build_directive(work_dir, scene_id, lint_suffix)
        ledger["history"] = _archive_active(existing_directive, existing_ledger)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[machine_directive] ERROR: {exc}", file=sys.stderr)
        return 2
    _atomic_write_active_pair(directive_path, directive, ledger_path, ledger)
    print(f"✅ {directive_path} · {len(directive['entries'])} entries")
    return 0


def _parse_protected_regions(summary_path: Path) -> list[dict]:
    if not summary_path.exists():
        return []
    regions = []
    current: dict | None = None
    patch_re = re.compile(r"\[(?P<patch_id>patch[^·\]]*?)\s*·\s*(?P<fields>[^\]]+)\]\**\s*(?P<location>.*)")
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        match = patch_re.search(line)
        if match:
            fields = [part.strip() for part in match.group("fields").split("·")]
            current = None
            if "applied" not in fields:
                continue
            issue = next((f.removeprefix("issue_id").strip(" =") for f in fields if f.startswith("issue_id")), None)
            current = {"patch_id": match.group("patch_id").strip(), "issue_id": issue,
                       "location": match.group("location").strip(), "preserve": ""}
            regions.append(current)
            continue
        if current is not None:
            preserve_match = re.search(r"preserve[:：]\s*(.+)$", line)
            if preserve_match:
                current["preserve"] = preserve_match.group(1).strip()
    return regions


def _entry_hit_records(entry: dict) -> list[dict]:
    return [
        record for record in (entry.get("hit_records", []) or [])
        if isinstance(record, dict) and record.get("lint_id")
    ]


def _record_matches_saved_quote(record: dict, evidence: str) -> bool:
    saved_quote = record.get("evidence_quote")
    if isinstance(saved_quote, str) and saved_quote:
        return evidence in saved_quote or saved_quote in evidence
    locator = record.get("locator")
    span = locator.get("span") if isinstance(locator, dict) else None
    return isinstance(span, str) and bool(span) and span in evidence


def _application_snapshots(prior_directive: dict, prior_ledger: dict) -> list[dict]:
    snapshots = [{"entries": prior_directive.get("entries", []) or []}]
    for revision in reversed(prior_ledger.get("history", []) or []):
        if isinstance(revision, dict):
            snapshots.append({"entries": revision.get("directive_entries", []) or []})
    return snapshots


def _find_application_entry(
    objection: dict,
    prior_directive: dict,
    prior_ledger: dict,
) -> tuple[dict | None, str | None]:
    target_hit_id = objection.get("target_hit_id")
    family = objection.get("family")
    evidence = str(objection.get("evidence_quote") or "")
    if not isinstance(target_hit_id, str) or not target_hit_id:
        return None, "target_hit_id_not_found"

    saw_target = False
    saw_family_mismatch = False
    saw_quote_mismatch = False
    saw_ambiguous = False
    for snapshot in _application_snapshots(prior_directive, prior_ledger):
        entries = [entry for entry in snapshot["entries"] if isinstance(entry, dict)]
        target_entries = [
            entry for entry in entries
            if target_hit_id in (entry.get("all_hit_ids", []) or [])
            or any(record.get("lint_id") == target_hit_id for record in _entry_hit_records(entry))
        ]
        if not target_entries:
            continue
        saw_target = True
        matching_family_entries = [entry for entry in target_entries if entry.get("family") == family]
        if not matching_family_entries:
            saw_family_mismatch = True
            continue

        family_records = [
            record
            for entry in entries
            if entry.get("family") == family
            for record in _entry_hit_records(entry)
        ]
        candidates = {
            record.get("lint_id")
            for record in family_records
            if _record_matches_saved_quote(record, evidence)
        }
        candidates.discard(None)
        if len(candidates) > 1:
            saw_ambiguous = True
            continue
        if len(candidates) == 1:
            if target_hit_id in candidates:
                return matching_family_entries[0], None
            saw_quote_mismatch = True

    if not saw_target:
        return None, "target_hit_id_not_found"
    if saw_ambiguous:
        return None, "evidence_quote_ambiguous"
    if saw_quote_mismatch:
        return None, "target_hit_mismatch"
    if saw_family_mismatch:
        return None, "family_mismatch"
    return None, "evidence_quote_not_found"


def _qualification_denial_reason(
    objection: dict,
    application_entry: dict,
    lang: str,
) -> str | None:
    if application_entry.get("level") != "M":
        return "target_entry_not_m"
    family = objection.get("family")
    if family != application_entry.get("family"):
        return "family_mismatch"
    if family not in M_OBJECTION_CLUSTERS:
        return "family_not_objection_allowed"

    device = objection.get("device_claim")
    policy = effective_policy(str(family), lang)
    if device not in policy.get("device_budget", {}):
        return "device_budget_not_cover_family"

    evidence = str(objection.get("evidence_quote") or "")
    if len(evidence) < 10:
        return "evidence_quote_too_short"

    function_claim = str(objection.get("function_claim") or "")
    if not function_claim:
        return "function_claim_empty"
    if len(function_claim) > 50:
        return "function_claim_too_long"
    if any(claim in function_claim for claim in GENERIC_FUNCTION_CLAIMS):
        return "function_claim_too_generic"
    return None


def _current_quote_candidates(
    directive: dict,
    family: str,
    evidence: str,
    scene_text: str,
) -> list[tuple[str, str]]:
    quote_spans = [
        (match.start(), match.end())
        for match in re.finditer(re.escape(evidence), scene_text)
    ]
    candidates = set()
    for entry in directive.get("entries", []) or []:
        if not isinstance(entry, dict) or entry.get("family") != family:
            continue
        for record in _entry_hit_records(entry):
            locator = record.get("locator")
            if not isinstance(locator, dict):
                continue
            start, end = locator.get("start"), locator.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if any(quote_start <= start and end <= quote_end for quote_start, quote_end in quote_spans):
                candidates.add((entry.get("id"), record.get("lint_id")))
    return sorted(
        (entry_id, hit_id)
        for entry_id, hit_id in candidates
        if isinstance(entry_id, str) and isinstance(hit_id, str)
    )


def _assert_hit_partition(entry: dict) -> None:
    all_ids = entry.get("all_hit_ids", []) or []
    exempted = entry.get("exempted_hit_ids", []) or []
    remaining = entry.get("remaining_hit_ids", []) or []
    if len(all_ids) != len(set(all_ids)):
        raise ValueError(f"duplicate hit ids in {entry.get('id')}")
    if set(exempted) & set(remaining):
        raise ValueError(f"overlapping hit partition in {entry.get('id')}")
    if set(all_ids) != set(exempted) | set(remaining):
        raise ValueError(f"incomplete hit partition in {entry.get('id')}")


def _apply_machine_objections(
    work_dir: Path,
    scene_id: str,
    prior_directive: dict,
    prior_ledger: dict,
    directive: dict,
    ledger: dict,
    scene_text: str,
) -> None:
    objection_path = work_dir / "pipeline" / "review" / f"{scene_id}.machine_objection.yaml"
    if not objection_path.exists():
        return

    try:
        objection_data = _load_yaml(objection_path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[machine_directive] WARN: objection skipped: {exc}", file=sys.stderr)
        return

    objections = objection_data.get("objections", []) or []
    if not isinstance(objections, list):
        print(
            f"[machine_directive] WARN: objection skipped: {objection_path} objections must be a list",
            file=sys.stderr,
        )
        return

    ledger_entries = ledger.get("entries", []) or []
    ledger_by_id = {
        entry.get("id"): entry
        for entry in ledger_entries
        if isinstance(entry, dict) and entry.get("id")
    }
    exempted_by_entry: dict[str, set[str]] = {}
    objection_results = []
    lang = str(directive.get("language") or "zh")
    for objection in objections:
        if not isinstance(objection, dict):
            continue
        target_hit_id = objection.get("target_hit_id")
        family = objection.get("family")
        evidence = str(objection.get("evidence_quote") or "")
        result = {
            "target_hit_id": target_hit_id,
            "application_hit_id": target_hit_id,
            "family": family,
            "evidence_quote": evidence,
            "status": "denied",
        }
        application_entry, reason = _find_application_entry(
            objection, prior_directive, prior_ledger
        )
        if reason is None and application_entry is not None:
            reason = _qualification_denial_reason(objection, application_entry, lang)
        candidates = []
        if reason is None:
            candidates = _current_quote_candidates(directive, family, evidence, scene_text)
            if not candidates:
                reason = "evidence_quote_not_found"
            elif len(candidates) > 1:
                reason = "evidence_quote_ambiguous"
        if reason is None:
            entry_id, current_hit_id = candidates[0]
            exempted_by_entry.setdefault(entry_id, set()).add(current_hit_id)
            result.update({
                "status": "granted",
                "current_hit_id": current_hit_id,
            })
        else:
            result["reason"] = reason
        objection_results.append(result)

    denied_by_family = {
        result.get("family"): result.get("reason")
        for result in objection_results
        if result.get("status") == "denied" and result.get("family")
    }
    for entry in directive.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        all_ids = list(entry.get("all_hit_ids", []) or [])
        exempted_set = exempted_by_entry.get(entry.get("id"), set())
        exempted = [hit_id for hit_id in all_ids if hit_id in exempted_set]
        remaining = [hit_id for hit_id in all_ids if hit_id not in exempted_set]
        entry["exempted_hit_ids"] = exempted
        entry["remaining_hit_ids"] = remaining
        fully_granted = bool(all_ids) and not remaining
        entry["status"] = "objection_granted" if fully_granted else "pending"
        _assert_hit_partition(entry)

        reducer = ledger_by_id.get(entry.get("id"))
        if reducer is None:
            continue
        reducer["all_hit_ids"] = list(all_ids)
        reducer["exempted_hit_ids"] = list(exempted)
        reducer["remaining_hit_ids"] = list(remaining)
        reducer["hit_resolutions"] = [
            {
                "hit_id": hit_id,
                "status": "objection_granted" if hit_id in exempted_set else "pending",
            }
            for hit_id in all_ids
        ]
        reducer["status"] = "objection_granted" if fully_granted else "issued"
        denial = denied_by_family.get(entry.get("family"))
        if denial:
            reducer["objection_denied_reason"] = denial
        else:
            reducer.pop("objection_denied_reason", None)
        _assert_hit_partition(reducer)

    ledger["objection_results"] = objection_results


def _atomic_copy_once(source_path: Path, destination_path: Path) -> None:
    if destination_path.exists():
        return
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination_path.with_suffix(destination_path.suffix + ".tmp")
    try:
        shutil.copyfile(source_path, tmp_path)
        os.replace(tmp_path, destination_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _snapshot_pre_dist_once(
    work_dir: Path,
    scene_id: str,
    lint_artifact: Path,
    scene_path: Path,
) -> None:
    pre_dist_path = _lint_path(work_dir, scene_id, "pre_dist")
    scene_snapshot_path = (
        work_dir / "pipeline" / "review" / "snapshots" / f"{scene_id}.pre_dist.md"
    )
    _atomic_copy_once(lint_artifact, pre_dist_path)
    _atomic_copy_once(scene_path, scene_snapshot_path)


def _validate_refresh_lint(lint: dict, scene_id: str, scene_text: str) -> None:
    lint_scene_id = lint.get("scene_id")
    if lint_scene_id not in {None, scene_id}:
        raise ValueError(
            f"lint scene_id {lint_scene_id!r} does not match requested scene {scene_id!r}"
        )
    expected_hash = lint.get("input_text_sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise ValueError("lint input hash is missing")
    current_hash = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()
    if expected_hash != current_hash:
        raise ValueError("lint input hash does not match current scene")


def refresh_directive(work_dir: Path, scene_id: str, lint_artifact: Path) -> int:
    directive_path = work_dir / "pipeline" / "review" / f"{scene_id}.machine_directive.yaml"
    ledger_path = work_dir / "pipeline" / "review" / f"{scene_id}.machine_ledger.yaml"
    scene_path = work_dir / "pipeline" / "scenes" / f"scene_{scene_id}.md"
    if not directive_path.exists():
        print(f"[machine_directive] ERROR: directive not found: {directive_path}", file=sys.stderr)
        return 2
    try:
        prior_directive = _load_yaml(directive_path)
        prior_ledger = _load_yaml(ledger_path)
        lint = _load_yaml(lint_artifact)
        scene_text = scene_path.read_text(encoding="utf-8")
        _validate_refresh_lint(lint, scene_id, scene_text)
        _snapshot_pre_dist_once(work_dir, scene_id, lint_artifact, scene_path)
        directive, ledger = build_directive(
            work_dir,
            scene_id,
            lint_artifact=lint_artifact,
        )
        ledger["history"] = _archive_active(prior_directive, prior_ledger)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[machine_directive] ERROR: {exc}", file=sys.stderr)
        return 2

    summary_path = work_dir / "pipeline" / f"scene_{scene_id}" / "revision_summary.md"
    try:
        _apply_machine_objections(
            work_dir,
            scene_id,
            prior_directive,
            prior_ledger,
            directive,
            ledger,
            scene_text,
        )
    except ValueError as exc:
        print(f"[machine_directive] ERROR: {exc}", file=sys.stderr)
        return 2
    directive["stage"] = "refreshed"
    directive["dispatch_ready"] = True
    directive["protected_regions"] = _parse_protected_regions(summary_path)
    _atomic_write_active_pair(directive_path, directive, ledger_path, ledger)
    print(f"✅ {directive_path} refreshed · {len(directive['protected_regions'])} protected_regions")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate machine directive from ai_filler lint output")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--lint-suffix", default=None)
    parser.add_argument("--lint-artifact", type=Path, default=None)
    args = parser.parse_args()

    if args.refresh and args.lint_suffix:
        print("[machine_directive] ERROR: --lint-suffix cannot be used with --refresh", file=sys.stderr)
        return 2

    if args.refresh and args.lint_artifact is None:
        print(
            "[machine_directive] ERROR: --lint-artifact is required with --refresh",
            file=sys.stderr,
        )
        return 2
    if not args.refresh and args.lint_artifact is not None:
        print(
            "[machine_directive] ERROR: --lint-artifact is only valid with --refresh",
            file=sys.stderr,
        )
        return 2

    if args.refresh:
        work_dir = args.work_dir.resolve()
        lint_artifact = args.lint_artifact
        if not lint_artifact.is_absolute():
            lint_artifact = work_dir / lint_artifact
        return refresh_directive(work_dir, args.scene_id, lint_artifact.resolve())
    return generate_initial(args.work_dir.resolve(), args.scene_id, args.lint_suffix)


if __name__ == "__main__":
    sys.exit(main())
