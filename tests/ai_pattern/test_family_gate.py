import pathlib
import subprocess
import sys

import yaml

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _run_gate(tmp_path, before, after):
    before_path = tmp_path / "before.yaml"
    after_path = tmp_path / "after.yaml"
    before_path.write_text(yaml.safe_dump(before, allow_unicode=True))
    after_path.write_text(yaml.safe_dump(after, allow_unicode=True))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "family_gate.py"),
            "--before",
            str(before_path),
            "--after",
            str(after_path),
        ],
        text=True,
        capture_output=True,
    )
    return result.returncode


def test_new_observed_family_is_diagnostic(tmp_path):
    before = {"cluster_alerts": [{"family": "micro_punchline_cadence", "severity": "high"}], "hits": []}
    after = {"cluster_alerts": [{"family": "silence_pause_cliche", "severity": "medium"}], "hits": []}

    assert _run_gate(tmp_path, before, after) == 0
    # Referencing through another form remains a contextual-review candidate.
    before["cluster_alerts"][0]["family"] = "dummy_pronoun"
    after["cluster_alerts"][0]["family"] = "demonstrative_classifier"
    assert _run_gate(tmp_path, before, after) == 0


def test_shrunk_families_pass(tmp_path):
    before = {
        "cluster_alerts": [
            {"family": "micro_punchline_cadence", "severity": "high"},
            {"family": "lexical_cliche", "severity": "medium"},
        ],
        "hits": [],
    }
    after = {"cluster_alerts": [{"family": "lexical_cliche", "severity": "low"}], "hits": []}

    assert _run_gate(tmp_path, before, after) == 0


def test_family_vector_uses_canonical_count_density_and_severity():
    import family_gate

    data = {
        "density": {"total_chars": 500},
        "hits": [
            {"family": "action_log", "severity": "low", "lint_id": "h1"},
            {"family": "action_log", "severity": "high", "lint_id": "h2"},
            {"family": "action_log", "severity": "high", "lint_id": "h3", "dedup_supporting": True},
            {"family": "micro_punchline_cadence", "rule": "narrative_micro_label", "lint_id": "h4"},
        ],
    }
    vector = family_gate.family_vector(data, lang="zh")
    assert vector["action_log"] == {"count": 2, "density": 4.0, "severity": "high"}
    assert "micro_punchline_cadence" not in vector


def test_referential_count_changes_remain_contextual_observations():
    import family_gate

    before = {"density": {"total_chars": 1000}, "hits": [
        {"family": "dummy_pronoun", "severity": "medium", "lint_id": "a1"},
        {"family": "dummy_pronoun", "severity": "medium", "lint_id": "a2"},
        {"family": "demonstrative_classifier", "severity": "low", "lint_id": "d1"},
    ]}
    after = {"density": {"total_chars": 1000}, "hits": [
        {"family": "dummy_pronoun", "severity": "low", "lint_id": "a1"},
        {"family": "demonstrative_classifier", "severity": "high", "lint_id": "d1"},
        {"family": "demonstrative_classifier", "severity": "high", "lint_id": "d2"},
    ]}
    report = family_gate.evaluate_regression(before, after, {"dummy_pronoun"}, lang="zh")
    assert report["verdict"] == "PASS"
    assert report["families"]["dummy_pronoun"]["decision"] == "observe_only"
    assert report["families"]["demonstrative_classifier"]["decision"] == "observe_only"

    failed = family_gate.evaluate_regression(after, before, {"dummy_pronoun"}, lang="zh")
    assert failed["verdict"] == "PASS"
    assert failed["families"]["dummy_pronoun"]["decision"] == "observe_only"


def test_observe_family_is_report_only_in_regression_gate():
    import family_gate

    before = {"density": {"total_chars": 100}, "hits": []}
    after = {"density": {"total_chars": 100}, "hits": [
        {"family": "meta_language_leak", "severity": "high", "lint_id": "m1"}
    ]}
    report = family_gate.evaluate_regression(before, after, set(), lang="zh")
    assert report["verdict"] == "PASS"
    assert report["families"]["meta_language_leak"]["decision"] == "observe_only"


def test_observe_rule_inside_enforced_family_does_not_create_regression(monkeypatch):
    import family_gate

    real_effective_policy = family_gate.effective_policy

    def mixed_policy(family, lang, rule=None):
        if family == "action_log" and rule == "observed_subtype":
            return {"lifecycle": "observe"}
        return real_effective_policy(family, lang, rule)

    monkeypatch.setattr(family_gate, "effective_policy", mixed_policy)
    before = {"density": {"total_chars": 1000}, "hits": []}
    after = {"density": {"total_chars": 1000}, "hits": [{
        "family": "action_log",
        "rule": "observed_subtype",
        "severity": "high",
        "lint_id": "observe-1",
    }]}

    report = family_gate.evaluate_regression(before, after, set(), lang="zh")

    assert report["verdict"] == "PASS"
    assert "action_log" not in report["families"]
