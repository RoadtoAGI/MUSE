"""Legacy M objection compatibility; only the S case uses a current enforced family."""
import hashlib
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import machine_directive as md


@pytest.fixture(autouse=True)
def legacy_m_policy(monkeypatch):
    """Keep historical M-artifact handling testable without changing runtime policy."""
    current = md.effective_policy

    def policy(family, lang, rule=None):
        result = current(family, lang, rule)
        if lang == "zh" and family in {
            "silence_pause_cliche", "figurative_debt", "state_persistence_template"
        }:
            result = {**result, "lifecycle": "enforced", "sovereignty": "M",
                      "device_budget": {"naked_line": 1.0}, "density_contract": False}
        return result

    monkeypatch.setattr(md, "effective_policy", policy)


SCENE_ID = "S02"
SCENE_TEXT = "他没有再说什么，烟在指间烧到了滤嘴。她停了一下，望向门外。"
QUOTE_A = "他没有再说什么，烟在指间烧到了滤嘴。"
QUOTE_B = "她停了一下，望向门外。"


def _span(text: str, needle: str, occurrence: int = 0) -> tuple[int, int]:
    start = -1
    cursor = 0
    for _ in range(occurrence + 1):
        start = text.index(needle, cursor)
        cursor = start + len(needle)
    return start, start + len(needle)


def _hit(
    lint_id: str,
    text: str,
    needle: str,
    *,
    family: str = "silence_pause_cliche",
    rule: str = "stock_silence_pause_phrase",
    occurrence: int = 0,
) -> dict:
    start, end = _span(text, needle, occurrence)
    return {
        "lint_id": lint_id,
        "rule": rule,
        "family": family,
        "start": start,
        "end": end,
        "span": text[start:end],
        "locator": {"start": start, "end": end, "span": text[start:end]},
        "evidence_quote": text[max(0, start - 4):min(len(text), end + 16)],
    }


def _alert(alert_id: str, family: str, hit_ids: list[str], *, severity: str = "medium") -> dict:
    return {
        "alert_id": alert_id,
        "cluster": family,
        "family": family,
        "severity": severity,
        "hits": len(hit_ids),
        "hit_ids": hit_ids,
    }


def _write_lint(wd: Path, name: str, text: str, hits: list[dict], alerts: list[dict]) -> Path:
    path = wd / "pipeline" / "review" / "lint" / name
    path.write_text(
        yaml.safe_dump(
            {
                "scene_id": SCENE_ID,
                "language": "zh",
                "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "hits": hits,
                "cluster_alerts": alerts,
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


def _mk_workdir(
    tmp_path,
    text: str,
    hits: list[dict],
    alerts: list[dict],
    objections: list[dict] | None,
    *,
    devices=("naked_line",),
) -> tuple[Path, Path]:
    wd = tmp_path / "run"
    (wd / "pipeline" / "review" / "lint").mkdir(parents=True)
    (wd / "pipeline" / "scenes").mkdir(parents=True)
    (wd / "pipeline" / "scene_S02").mkdir(parents=True)
    (wd / "pipeline" / "scenes" / "scene_S02.md").write_text(text, encoding="utf-8")
    (wd / "pipeline" / "phase5_scenes.yaml").write_text(
        yaml.safe_dump(
            {"scenes": [{"scene_id": SCENE_ID, "literary_device": list(devices)}]},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    lint_path = _write_lint(wd, "S02.ai_filler.yaml", text, hits, alerts)
    assert md.generate_initial(wd, SCENE_ID) == 0
    if objections is not None:
        (wd / "pipeline" / "review" / "S02.machine_objection.yaml").write_text(
            yaml.safe_dump({"scene_id": SCENE_ID, "objections": objections}, allow_unicode=True),
            encoding="utf-8",
        )
    return wd, lint_path


def _refresh(wd: Path, lint_path: Path, *, expected_returncode: int = 0):
    result = md.refresh_directive(wd, SCENE_ID, lint_path)
    assert result == expected_returncode
    if expected_returncode:
        return result
    directive = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.machine_directive.yaml").read_text()
    )
    ledger = yaml.safe_load(
        (wd / "pipeline" / "review" / "S02.machine_ledger.yaml").read_text()
    )
    return directive, ledger


def _objection(target_hit_id: str, family: str, evidence_quote: str, **overrides) -> dict:
    data = {
        "target_hit_id": target_hit_id,
        "family": family,
        "device_claim": "naked_line",
        "evidence_quote": evidence_quote,
        "function_claim": "克制裸句承载对峙压力",
    }
    data.update(overrides)
    return data


def _silence_fixture(two_hits: bool = True):
    hits = [_hit("S02-stock-001", SCENE_TEXT, "没有再说什么")]
    if two_hits:
        hits.append(_hit("S02-stock-002", SCENE_TEXT, "停了一下"))
    alert = _alert(
        "S02-silence_pause_cliche-1",
        "silence_pause_cliche",
        [hit["lint_id"] for hit in hits],
    )
    return hits, [alert]


def test_partial_objection_keeps_entry_and_enforces_remaining_hit(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", QUOTE_A)],
    )

    directive, ledger = _refresh(wd, lint_path)

    entry = directive["entries"][0]
    assert entry["all_hit_ids"] == ["S02-stock-001", "S02-stock-002"]
    assert entry["exempted_hit_ids"] == ["S02-stock-001"]
    assert entry["remaining_hit_ids"] == ["S02-stock-002"]
    assert entry["status"] == "pending"
    assert directive["active_revision_id"] == ledger["active_revision_id"]
    reducer = next(item for item in ledger["entries"] if item["id"] == entry["id"])
    assert reducer["status"] == "issued"
    assert {item["hit_id"]: item["status"] for item in reducer["hit_resolutions"]} == {
        "S02-stock-001": "objection_granted",
        "S02-stock-002": "pending",
    }


def test_full_objection_keeps_entry_as_objection_granted(tmp_path):
    hits, alerts = _silence_fixture(two_hits=False)
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", QUOTE_A)],
    )

    directive, ledger = _refresh(wd, lint_path)

    entry = directive["entries"][0]
    assert entry["exempted_hit_ids"] == ["S02-stock-001"]
    assert entry["remaining_hit_ids"] == []
    assert entry["status"] == "objection_granted"
    reducer = next(item for item in ledger["entries"] if item["id"] == entry["id"])
    assert reducer["status"] == "objection_granted"


def test_objection_on_current_referential_s_hit_is_denied(tmp_path):
    text = "它没有再动，烟在门边慢慢散去。"
    hit = _hit("S02-dummy-001", text, "它", family="dummy_pronoun", rule="dummy_pronoun")
    alert = _alert("S02-dummy_pronoun-1", "dummy_pronoun", [hit["lint_id"]])
    wd, lint_path = _mk_workdir(
        tmp_path, text, [hit], [alert],
        [_objection("S02-dummy-001", "dummy_pronoun", text)],
    )
    directive, ledger = _refresh(wd, lint_path)
    assert directive["entries"][0]["level"] == "S"
    assert directive["entries"][0]["exempted_hit_ids"] == []
    assert ledger["objection_results"][0]["reason"] == "target_entry_not_m"


def test_objection_on_non_allowlisted_m_family_is_denied(tmp_path):
    hit = _hit(
        "S02-simile-001",
        SCENE_TEXT,
        "没有再说什么",
        family="figurative_debt",
        rule="short_simile_debt",
    )
    alert = _alert("S02-figurative_debt-1", "figurative_debt", [hit["lint_id"]])
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        [hit],
        [alert],
        [_objection("S02-simile-001", "figurative_debt", QUOTE_A)],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["level"] == "M"
    assert directive["entries"][0]["exempted_hit_ids"] == []
    assert ledger["objection_results"][0]["reason"] == "family_not_objection_allowed"


def test_objection_cannot_borrow_allowlisted_cluster_from_another_family(tmp_path):
    hit = _hit(
        "S02-state-001",
        SCENE_TEXT,
        "没有再说什么",
        family="state_persistence_template",
        rule="state_persistence_tag",
    )
    alert = _alert(
        "S02-state_persistence_template-1",
        "state_persistence_template",
        [hit["lint_id"]],
    )
    alert["cluster"] = "silence_pause_cliche"
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        [hit],
        [alert],
        [_objection("S02-state-001", "state_persistence_template", QUOTE_A)],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["level"] == "M"
    assert directive["entries"][0]["exempted_hit_ids"] == []
    assert ledger["objection_results"][0]["reason"] == "family_not_objection_allowed"


def test_target_hit_id_and_quote_mismatch_is_denied(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", QUOTE_B)],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["exempted_hit_ids"] == []
    assert ledger["objection_results"][0]["reason"] == "target_hit_mismatch"


def test_repeated_quote_with_two_family_hits_is_ambiguous(tmp_path):
    repeated = "他停了一下，望向门外。他停了一下，望向门外。"
    quote = "他停了一下，望向门外。"
    hits = [
        _hit("S02-stock-001", repeated, "停了一下", occurrence=0),
        _hit("S02-stock-002", repeated, "停了一下", occurrence=1),
    ]
    alerts = [_alert(
        "S02-silence_pause_cliche-1",
        "silence_pause_cliche",
        [hit["lint_id"] for hit in hits],
    )]
    wd, lint_path = _mk_workdir(
        tmp_path,
        repeated,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", quote)],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["exempted_hit_ids"] == []
    assert ledger["objection_results"][0]["reason"] == "evidence_quote_ambiguous"


def test_extended_quote_can_uniquely_select_one_repeated_hit(tmp_path):
    repeated = "甲说，他停了一下，望向门外。乙说，他停了一下，望向门外。"
    quote = "甲说，他停了一下，望向门外。"
    hits = [
        _hit("S02-stock-001", repeated, "停了一下", occurrence=0),
        _hit("S02-stock-002", repeated, "停了一下", occurrence=1),
    ]
    # 申请轮 lint 记录的 quote 也携带能区分两处命中的上下文。
    hits[0]["evidence_quote"] = quote
    hits[1]["evidence_quote"] = "乙说，他停了一下，望向门外。"
    alerts = [_alert(
        "S02-silence_pause_cliche-1",
        "silence_pause_cliche",
        [hit["lint_id"] for hit in hits],
    )]
    wd, lint_path = _mk_workdir(
        tmp_path,
        repeated,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", quote)],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["exempted_hit_ids"] == ["S02-stock-001"]
    assert ledger["objection_results"][0]["status"] == "granted"


def test_unlisted_eligible_device_with_evidence_is_granted_and_generic_claim_denied(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    objections = [
        _objection(
            "S02-stock-001",
            "silence_pause_cliche",
            QUOTE_A,
            device_claim="naked_line",
        ),
        _objection(
            "S02-stock-002",
            "silence_pause_cliche",
            QUOTE_B,
            function_claim="节奏需要停顿",
        ),
    ]
    wd, lint_path = _mk_workdir(
        tmp_path, SCENE_TEXT, hits, alerts, objections, devices=()
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["exempted_hit_ids"] == ["S02-stock-001"]
    assert ledger["objection_results"][0]["status"] == "granted"
    assert ledger["objection_results"][1]["reason"] == "function_claim_too_generic"


def test_two_same_family_hit_objections_are_each_adjudicated(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    wd, lint_path = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [
            _objection("S02-stock-001", "silence_pause_cliche", QUOTE_A),
            _objection("S02-stock-002", "silence_pause_cliche", QUOTE_B),
        ],
    )

    directive, ledger = _refresh(wd, lint_path)

    assert directive["entries"][0]["exempted_hit_ids"] == [
        "S02-stock-001",
        "S02-stock-002",
    ]
    assert directive["entries"][0]["remaining_hit_ids"] == []
    assert [result["status"] for result in ledger["objection_results"]] == [
        "granted",
        "granted",
    ]


def test_cross_round_quote_maps_to_new_id_without_bare_id_inheritance(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    wd, _ = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", QUOTE_A)],
    )
    reordered = [
        _hit("S02-stock-001", SCENE_TEXT, "停了一下"),
        _hit("S02-stock-002", SCENE_TEXT, "没有再说什么"),
    ]
    current_lint = _write_lint(
        wd,
        "S02.ai_filler.v2.yaml",
        SCENE_TEXT,
        reordered,
        [_alert(
            "S02-silence_pause_cliche-1",
            "silence_pause_cliche",
            [hit["lint_id"] for hit in reordered],
        )],
    )

    directive, ledger = _refresh(wd, current_lint)

    entry = directive["entries"][0]
    assert entry["exempted_hit_ids"] == ["S02-stock-002"]
    assert entry["remaining_hit_ids"] == ["S02-stock-001"]
    result = ledger["objection_results"][0]
    assert result["application_hit_id"] == "S02-stock-001"
    assert result["current_hit_id"] == "S02-stock-002"


def test_quote_loss_retracts_previous_exemption(tmp_path):
    hits, alerts = _silence_fixture(two_hits=True)
    wd, first_lint = _mk_workdir(
        tmp_path,
        SCENE_TEXT,
        hits,
        alerts,
        [_objection("S02-stock-001", "silence_pause_cliche", QUOTE_A)],
    )
    first_directive, _ = _refresh(wd, first_lint)
    assert first_directive["entries"][0]["exempted_hit_ids"] == ["S02-stock-001"]

    revised_text = "她停了一下，望向门外。"
    (wd / "pipeline" / "scenes" / "scene_S02.md").write_text(revised_text, encoding="utf-8")
    revised_hit = _hit("S02-stock-001", revised_text, "停了一下")
    revised_lint = _write_lint(
        wd,
        "S02.ai_filler.v3.yaml",
        revised_text,
        [revised_hit],
        [_alert("S02-silence_pause_cliche-1", "silence_pause_cliche", [revised_hit["lint_id"]])],
    )

    directive, ledger = _refresh(wd, revised_lint)

    entry = directive["entries"][0]
    assert entry["exempted_hit_ids"] == []
    assert entry["remaining_hit_ids"] == ["S02-stock-001"]
    assert ledger["objection_results"][0]["reason"] == "evidence_quote_not_found"
