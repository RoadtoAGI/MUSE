import copy
import hashlib
import ast
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _hit(rule: str, lint_id: str, start: int) -> dict:
    return {
        "rule": rule,
        "lint_id": lint_id,
        "start": start,
        "end": start + 6,
        "text": "不是甲而是乙",
        "pattern": rule,
        "severity": "medium",
    }


def test_lint_aggregation_excludes_observe_rule_before_canonical_dedup(monkeypatch):
    import ai_filler_lint as lint
    import ai_policy

    monkeypatch.setitem(
        ai_policy.FAMILY_MANIFEST["lexical_cliche"]["policy"], "zh",
        {**copy.deepcopy(ai_policy.PRE_CONTRACT_POLICY_BASELINE[("lexical_cliche", "zh")]),
         "pre_contract": True, "rules": {}},
    )
    rules = ai_policy.FAMILY_MANIFEST["contrastive_negation_assertion"]["policy"]["zh"]["rules"]
    monkeypatch.setitem(rules, "contrastive_negation_assertion", {"lifecycle": "observe"})
    hits = [
        _hit("contrastive_negation_assertion", "c1", 0),
        _hit("parallel_negation", "p1", 0),
        _hit("contrastive_negation_assertion", "c2", 20),
        _hit("parallel_negation", "p2", 20),
    ]

    alerts = lint.aggregate_cluster_alerts(hits, "S01", "甲" * 100, lang="zh")

    assert [a["family"] for a in alerts] == ["lexical_cliche"]
    assert {h["lint_id"] for h in hits if h.get("policy_lifecycle") == "observe"} == {"c1", "c2"}
    assert all(not h.get("dedup_supporting") for h in hits if h["lint_id"] in {"p1", "p2"})


def test_enforced_alert_ids_exclude_observe_rule_hits(monkeypatch):
    import ai_filler_lint as lint
    import ai_policy

    monkeypatch.setitem(
        ai_policy.FAMILY_MANIFEST["lexical_cliche"]["policy"], "zh",
        {**copy.deepcopy(ai_policy.PRE_CONTRACT_POLICY_BASELINE[("lexical_cliche", "zh")]),
         "pre_contract": True, "rules": {}},
    )
    rules = ai_policy.FAMILY_MANIFEST["lexical_cliche"]["policy"]["zh"]["rules"]
    monkeypatch.setitem(rules, "parallel_negation", {"lifecycle": "observe"})
    hits = [
        _hit("keyword_ai_cliche", f"k{index}", index * 20)
        for index in range(4)
    ]
    hits.append(_hit("parallel_negation", "observe-1", 100))

    alerts = lint.aggregate_cluster_alerts(hits, "S01", "甲" * 1000, lang="zh")

    assert len(alerts) == 1
    assert alerts[0]["total_count"] == 4
    assert alerts[0]["hit_ids"] == ["k0", "k1", "k2", "k3"]
    assert "observe-1" not in alerts[0]["supporting_hit_ids"]


def test_rule_executor_registry_matches_declared_languages():
    import ai_filler_lint as lint
    import ai_policy

    for lang in ("zh", "en"):
        expected = {
            rule for rule, record in ai_policy.RULE_REGISTRY.items()
            if lang in record["languages"]
        }
        assert set(lint.RULE_EXECUTORS[lang]) == expected


def test_lint_artifact_binds_input_text_hash():
    import ai_filler_lint as lint

    text = "窗外的雨落在青石板上。"
    report = lint.analyze(text, scene_id="S01", lang="zh")
    assert report["input_text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_runtime_consumers_do_not_import_derived_policy_views():
    forbidden = {
        "BASELINE_EXEMPT_FAMILIES",
        "DEVICE_BUDGET_CLASSES",
        "FAMILY_DENSITY_BASELINE",
        "FAMILY_SOVEREIGNTY",
        "OBSERVE_ONLY_FAMILIES",
        "PER_FAMILY_OVERRIDE",
    }
    consumers = (
        "ai_filler_lint.py",
        "calibrate_baselines.py",
        "machine_directive.py",
        "wholetext_gate.py",
        "family_gate.py",
        "distribution_gate.py",
    )
    leaks = []
    for name in consumers:
        tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = {alias.name for alias in node.names}
                for symbol in sorted(imported & forbidden):
                    leaks.append(f"{name}:{symbol}")
    assert leaks == []
