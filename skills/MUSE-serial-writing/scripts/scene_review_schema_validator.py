"""Schema checks for scene-reviewer output."""

from dataclasses import dataclass


YIELD_TYPES = [
    "plot_change",
    "danger_change",
    "tactical_change",
    "character_choice",
    "relationship_shift",
    "world_rule",
    "sensory_irreplaceable",
    "formal_function",
]


@dataclass
class PassValidationResult:
    valid: bool
    reason: str = ""


# Explicit revision updates must close; statistical alerts alone do not create issues.
ALLOWED_RESOLVED_STATUSES = frozenset({"patched", "merged_into_higher", "migration_verified"})


def _is_post_revision_review(review: dict) -> bool:
    return (review.get("review_stage") == "post_revision"
            or str(review.get("review_round") or "").startswith("post_revision"))


def _collect_carrier_function_links(scene_card: dict | None) -> set[str]:
    """Rn+2 R1 F4 fix: physical_carrier 真实字段 = {text, function_link}（无 id）。
    367 实证 physical_carrier 嵌在 scene_tasks 内层；兼容顶层 + 嵌套两种位置。
    """
    result: set[str] = set()
    if not scene_card:
        return result
    for pc in scene_card.get("physical_carrier") or []:
        if isinstance(pc, dict) and pc.get("function_link"):
            result.add(pc["function_link"])
    for task in scene_card.get("scene_tasks") or []:
        if not isinstance(task, dict):
            continue
        for pc in task.get("physical_carrier") or []:
            if isinstance(pc, dict) and pc.get("function_link"):
                result.add(pc["function_link"])
    return result


def validate_post_revision_pass(
    review: dict,
    ledger: dict,
    lint_v2: dict,
    scene_card: dict | None = None,
) -> PassValidationResult:
    """Validate declared legacy resolutions; current machine/patch channels own closure.

    Candidate frequency and severity do not establish a prose defect. Existing
    resolution records still need a closed status and valid retained-function
    evidence. Explicit enforced policies keep their required hit closure.
    """
    if review.get("verdict") != "PASS" or not _is_post_revision_review(review):
        return PassValidationResult(valid=True)
    if not isinstance(ledger, dict) or not isinstance(lint_v2, dict):
        return PassValidationResult(False, "legacy review inputs 必须为 mapping")

    updates = ledger.get("post_revision_updates") or {}
    if isinstance(updates, list):
        flattened = {}
        for item in updates:
            if not isinstance(item, dict):
                return PassValidationResult(False, "post_revision_updates 项必须为 mapping")
            nested = item.get("updates")
            if isinstance(nested, dict):
                flattened.update(nested)
            elif isinstance(nested, list):
                for entry in nested:
                    if isinstance(entry, dict) and entry.get("lint_id"):
                        flattened[entry["lint_id"]] = entry
            elif item.get("lint_id"):
                flattened[item["lint_id"]] = item
        updates = flattened
    if not isinstance(updates, dict):
        return PassValidationResult(False, "post_revision_updates 必须为 mapping 或列表")

    required_hits: set[str] = set()
    for hid in required_hits:
        if hid not in updates:
            return PassValidationResult(False, f"enforced hit {hid} 缺少修订闭合记录")

    valid_function_links = _collect_carrier_function_links(scene_card)
    for hid, entry in updates.items():
        if not isinstance(entry, dict):
            return PassValidationResult(False, f"hit {hid} 修订记录必须为 mapping")
        status = entry.get("status")
        if status in ALLOWED_RESOLVED_STATUSES:
            continue
        if hid in required_hits:
            return PassValidationResult(False, f"enforced hit {hid} 尚未解决: {status}")
        if status == "formal_function_exempted":
            link = entry.get("carrier_function_link")
            if link and link in valid_function_links:
                continue
            return PassValidationResult(False, f"hit {hid} 缺有效 carrier_function_link")
        if status in {"observed", "observed_not_patched"} and str(entry.get("reason") or "").strip():
            continue
        return PassValidationResult(False, f"hit {hid} 修订状态未闭合或缺保留依据: {status}")
    return PassValidationResult(valid=True)


def validate_scene_review(review: dict) -> dict:
    for index, reader_yield in enumerate(review.get("reader_yield_check", [])):
        yields = reader_yield.get("yields", {})
        evidences = reader_yield.get("yield_evidences", [])
        evidence_types = {
            evidence.get("yield_type")
            for evidence in evidences
            if isinstance(evidence, dict)
        }

        for yield_type in YIELD_TYPES:
            if yields.get(yield_type) is True and yield_type not in evidence_types:
                return {
                    "valid": False,
                    "error": (
                        f"reader_yield_check[{index}].yields.{yield_type}=true "
                        "但 yield_evidences 无对应项"
                    ),
                }

        for evidence_index, evidence in enumerate(evidences):
            reason = evidence.get("reason", "") if isinstance(evidence, dict) else ""
            if not isinstance(reason, str) or not reason.strip():
                return {
                    "valid": False,
                    "error": (
                        f"reader_yield_check[{index}].yield_evidences"
                        f"[{evidence_index}].reason 需说明原文作用"
                    ),
                }

    return {"valid": True}
