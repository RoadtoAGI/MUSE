#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from ai_policy import AGGREGATION_ONLY_RULES, RULE_TO_FAMILY, density_contract_max_count, effective_policy

SEVERITY_RANK = {"": 0, "low": 1, "medium": 2, "high": 3, "major": 3, "catastrophic": 4}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _families(data: dict) -> set[str]:
    families: set[str] = set()
    for alert in data.get("cluster_alerts", []) or []:
        if not isinstance(alert, dict):
            continue
        family = alert.get("family") or alert.get("cluster")
        if family:
            families.add(str(family))
    for hit in data.get("hits", []) or data.get("lint_hits", []) or []:
        if not isinstance(hit, dict):
            continue
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if family:
            families.add(str(family))
    return families


def _max_severity(values: list[str]) -> str:
    return max(values or [""], key=lambda value: SEVERITY_RANK.get(value, 0))


def family_vector(data: dict, *, lang: str) -> dict[str, dict]:
    """Build the canonical count/density/severity vector for one lint artifact."""
    hits = data.get("hits") or data.get("lint_hits") or []
    by_family: dict[str, list[dict]] = {}
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        family = hit.get("family") or RULE_TO_FAMILY.get(hit.get("rule"))
        if not family or hit.get("dedup_supporting") or hit.get("rule") in AGGREGATION_ONLY_RULES:
            continue
        rule = hit.get("rule")
        if rule and effective_policy(str(family), lang, str(rule))["lifecycle"] != "enforced":
            continue
        by_family.setdefault(str(family), []).append(hit)

    alerts_by_family: dict[str, list[dict]] = {}
    for alert in data.get("cluster_alerts", []) or []:
        if not isinstance(alert, dict):
            continue
        family = alert.get("family") or alert.get("cluster")
        rule = alert.get("rule")
        if (
            family
            and (
                not rule
                or effective_policy(str(family), lang, str(rule))["lifecycle"]
                == "enforced"
            )
        ):
            alerts_by_family.setdefault(str(family), []).append(alert)

    total_chars = (
        (data.get("density") or {}).get("total_chars")
        or (data.get("whole_text") or {}).get("total_chars")
        or 1000
    )
    char_k = max(float(total_chars) / 1000.0, 0.001)
    vector: dict[str, dict] = {}
    for family in sorted(set(by_family) | set(alerts_by_family)):
        family_hits = by_family.get(family, [])
        alerts = alerts_by_family.get(family, [])
        count = len(family_hits)
        if not family_hits and alerts:
            count = max(int(a.get("hits", a.get("total_count", 1)) or 1) for a in alerts)
        alert_density = max(
            (float(a.get("density")) for a in alerts if isinstance(a.get("density"), (int, float))),
            default=None,
        )
        severities = [str(h.get("severity") or "") for h in family_hits]
        severities.extend(str(a.get("severity") or "") for a in alerts)
        vector[family] = {
            "count": count,
            "density": round(alert_density if alert_density is not None else count / char_k, 4),
            "severity": _max_severity(severities),
        }
    return vector


def _worsened(before: dict, after: dict) -> bool:
    return (
        after["count"] > before["count"]
        or after["density"] > before["density"]
        or SEVERITY_RANK.get(after["severity"], 0) > SEVERITY_RANK.get(before["severity"], 0)
    )


def evaluate_regression(
    before: dict,
    after: dict,
    target_families: set[str],
    *,
    lang: str,
) -> dict:
    before_vector = family_vector(before, lang=lang)
    after_vector = family_vector(after, lang=lang)
    families: dict[str, dict] = {}
    blocking: list[str] = []
    zero = {"count": 0, "density": 0.0, "severity": ""}

    for family in sorted(set(before_vector) | set(after_vector) | set(target_families)):
        old = before_vector.get(family, zero)
        new = after_vector.get(family, zero)
        policy = effective_policy(family, lang)
        lifecycle = policy["lifecycle"]
        units = (after.get("density") or {}).get("total_chars") or (after.get("whole_text") or {}).get("total_chars")
        maximum = density_contract_max_count(policy, units) if isinstance(units, int) and units > 0 else None
        if lifecycle != "enforced":
            decision = "observe_only"
        elif old["count"] == 0 and new["count"] > 0:
            decision = "new_family"
            blocking.append(family)
        elif family in target_families:
            if maximum is not None and new["count"] <= maximum:
                decision = "target_contract_satisfied"
            elif new["count"] == 0 or (old["count"] > 0 and new["count"] < old["count"]):
                decision = "target_converged"
            elif old["count"] == 0 and new["count"] == 0:
                decision = "target_absent"
            else:
                decision = "target_not_converged"
                blocking.append(family)
        elif _worsened(old, new):
            decision = "observe_non_target_worsening"
        else:
            decision = "stable_or_improved"
        families[family] = {
            "before": dict(old),
            "after": dict(new),
            "lifecycle": lifecycle,
            "target": family in target_families,
            "decision": decision,
        }

    return {
        "verdict": "FAIL" if blocking else "PASS",
        "language": lang,
        "blocking_families": sorted(set(blocking)),
        "families": families,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hard gate for family migration after distribution rewrite")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--target-family", action="append", default=[])
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    try:
        before = _load_yaml(args.before)
        after = _load_yaml(args.after)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"[family_gate] ERROR: {exc}", file=sys.stderr)
        return 2

    report = evaluate_regression(before, after, set(args.target_family), lang=args.lang)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    if report["verdict"] == "FAIL":
        print("FAIL families: " + ", ".join(report["blocking_families"]))
        return 1

    print("PASS family_non_regression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
