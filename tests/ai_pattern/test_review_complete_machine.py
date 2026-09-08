import sys
import hashlib
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _base(tmp_path, directive_status=None, gate_verdict=None, ledger_status="issued"):
    wd = tmp_path / "run"
    review = wd / "pipeline" / "review"
    (review / "lint").mkdir(parents=True)
    (wd / "pipeline" / "scenes").mkdir(parents=True)
    (wd / "pipeline").mkdir(exist_ok=True)
    (wd / "pipeline" / "phase6_development.yaml").write_text(
        yaml.safe_dump(
            {"scenes": [{"scene_id": "S01", "file_path": "pipeline/scenes/scene_S01.md"}]}
        ),
        encoding="utf-8",
    )
    (wd / "pipeline" / "scenes" / "scene_S01.md").write_text("正文", encoding="utf-8")
    (wd / "pipeline" / "run_state.yaml").write_text(
        yaml.safe_dump({"run_intent": "release"}), encoding="utf-8"
    )
    (review / "scene_S01.yaml").write_text(
        yaml.safe_dump({"scene_id": "S01", "verdict": "PASS", "written_by": "scene-reviewer"}),
        encoding="utf-8",
    )
    for sfx in ("ai_filler", "lexical_stats", "dialogue"):
        payload = {"cluster_alerts": [], "hits": []}
        if sfx == "ai_filler":
            payload.update({
                "language": "zh",
                "input_text_sha256": hashlib.sha256("正文".encode("utf-8")).hexdigest(),
            })
        (review / "lint" / f"S01.{sfx}.yaml").write_text(
            yaml.safe_dump(payload), encoding="utf-8"
        )
    lint_path = review / "lint" / "S01.ai_filler.yaml"
    artifact_sha = hashlib.sha256(lint_path.read_bytes()).hexdigest()
    lint_revision = {
        "artifact": "pipeline/review/lint/S01.ai_filler.yaml",
        "artifact_sha256": artifact_sha,
        "input_text_sha256": hashlib.sha256("正文".encode("utf-8")).hexdigest(),
    }
    (review / "A_aesthetic.yaml").write_text("findings: []\n", encoding="utf-8")
    (review / "S01.machine_ledger.yaml").write_text(
        yaml.safe_dump(
            {
                "scene_id": "S01",
                "active_revision_id": artifact_sha,
                "lint_revision": lint_revision,
                "entries": [
                    {
                        "id": "S01-x-1",
                        "family": "x",
                        "level": "S",
                        "status": ledger_status,
                        "all_hit_ids": ["S01-x-hit-1"],
                        "exempted_hit_ids": [],
                        "remaining_hit_ids": ["S01-x-hit-1"],
                        "hit_resolutions": [
                            {"hit_id": "S01-x-hit-1", "status": "pending"}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    if directive_status:
        (review / "S01.machine_directive.yaml").write_text(
            yaml.safe_dump(
                {
                    "scene_id": "S01",
                    "active_revision_id": artifact_sha,
                    "lint_revision": lint_revision,
                    "stage": "refreshed",
                    "dispatch_ready": True,
                    "entries": [
                        {
                            "id": "S01-x-1",
                            "family": "x",
                            "level": "S",
                            "severity": "high",
                            "hits": 3,
                            "repair_hint": "x",
                            "status": directive_status,
                            "all_hit_ids": ["S01-x-hit-1"],
                            "exempted_hit_ids": [],
                            "remaining_hit_ids": ["S01-x-hit-1"],
                        }
                    ],
                    "protected_regions": [],
                }
            ),
            encoding="utf-8",
        )
    if gate_verdict:
        (review / "S01.distribution_gate.yaml").write_text(
            yaml.safe_dump({"scene_id": "S01", "attempt": 1, "verdict": gate_verdict, "checks": []}),
            encoding="utf-8",
        )
    return wd


def test_machine_ledger_substitutes_lint_resolution_ledger(tmp_path):
    import verify_review_complete as vrc

    assert vrc.check(_base(tmp_path)) == 0


def test_licensed_observed_alert_does_not_block_release_admission(tmp_path):
    """普通观察信号保持来源可追溯；当前语义审阅通过后允许准入。"""
    import verify_review_complete as vrc

    wd = _base(tmp_path)
    review = wd / "pipeline" / "review"
    text = "他没说话。"
    (wd / "pipeline/scenes/scene_S01.md").write_text(text, encoding="utf-8")
    input_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lint_path = review / "lint/S01.ai_filler.yaml"
    lint_path.write_text(yaml.safe_dump({
        "scene_id": "S01",
        "language": "zh",
        "input_text_sha256": input_sha,
        "hits": [{
            "lint_id": "S01-silence-001",
            "rule": "stock_silence_pause_phrase",
            "family": "silence_pause_cliche",
            "locator": {"start": 1, "end": 4, "span": "没说话"},
            "evidence_quote": text,
        }],
        "cluster_alerts": [],
        "observed_alerts": [{
            "alert_id": "S01-silence_pause_cliche-observed-1",
            "family": "silence_pause_cliche",
            "cluster": "silence_pause_cliche",
            "blocking": False,
            "hit_ids": ["S01-silence-001"],
        }],
    }, allow_unicode=True), encoding="utf-8")
    artifact_sha = hashlib.sha256(lint_path.read_bytes()).hexdigest()
    revision = {
        "artifact": "pipeline/review/lint/S01.ai_filler.yaml",
        "artifact_sha256": artifact_sha,
        "input_text_sha256": input_sha,
    }
    (review / "S01.machine_ledger.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "active_revision_id": artifact_sha,
        "lint_revision": revision,
        "entries": [{
            "id": "S01-silence_pause_cliche-observed-1",
            "family": "silence_pause_cliche",
            "level": "L",
            "status": "observed",
            "all_hit_ids": ["S01-silence-001"],
            "hit_records": [{
                "lint_id": "S01-silence-001",
                "family": "silence_pause_cliche",
                "rule": "stock_silence_pause_phrase",
                "locator": {"start": 1, "end": 4, "span": "没说话"},
                "evidence_quote": text,
            }],
        }],
    }, allow_unicode=True), encoding="utf-8")

    assert vrc.check(wd) == 0
    eligibility = yaml.safe_load(
        (wd / "pipeline/audit/release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert eligibility["admission"]["release_candidate"] is True


def test_pending_directive_blocks(tmp_path):
    import verify_review_complete as vrc

    assert vrc.check(_base(tmp_path, directive_status="pending")) != 0


def test_gate_pass_does_not_shortcut_pending_entry(tmp_path):
    import verify_review_complete as vrc

    assert vrc.check(_base(tmp_path, directive_status="pending", gate_verdict="PASS")) != 0


def test_escalated_machine_entry_blocks_admission(tmp_path):
    import verify_review_complete as vrc

    assert vrc.check(_base(tmp_path, directive_status="pending", ledger_status="escalated")) != 0


def test_never_engaged_machine_channel_blocks(tmp_path):
    # 短文本中的真实指代命中超出作者密度合同，缺 directive 应阻断。
    import verify_review_complete as vrc

    wd = _base(tmp_path)
    review = wd / "pipeline" / "review"
    text = "他把那东西收进柜底。"
    (wd / "pipeline/scenes/scene_S01.md").write_text(text, encoding="utf-8")
    input_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lint_path = review / "lint/S01.ai_filler.yaml"
    hit_id = "S01-dummy-001"
    lint_path.write_text(yaml.safe_dump({
        "scene_id": "S01",
        "language": "zh",
        "input_text_sha256": input_sha,
        "cluster_alerts": [],
        "hits": [{
            "lint_id": hit_id,
            "rule": "dummy_pronoun",
            "family": "dummy_pronoun",
            "locator": {"start": 2, "end": 5, "span": "那东西"},
            "evidence_quote": text,
        }],
    }, allow_unicode=True), encoding="utf-8")
    artifact_sha = hashlib.sha256(lint_path.read_bytes()).hexdigest()
    (review / "S01.machine_ledger.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "active_revision_id": artifact_sha,
        "lint_revision": {
            "artifact": "pipeline/review/lint/S01.ai_filler.yaml",
            "artifact_sha256": artifact_sha,
            "input_text_sha256": input_sha,
        },
        "entries": [{
            "id": "S01-dummy_pronoun-density",
            "family": "dummy_pronoun",
            "level": "S",
            "status": "issued",
            "all_hit_ids": [hit_id],
            "exempted_hit_ids": [],
            "remaining_hit_ids": [hit_id],
            "hit_resolutions": [{"hit_id": hit_id, "status": "pending"}],
        }],
    }, allow_unicode=True), encoding="utf-8")

    assert vrc.check(wd) != 0
    eligibility = yaml.safe_load(
        (wd / "pipeline/audit/release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert eligibility["admission"]["reasons"] == [
        "S01:machine:enforced_alert_without_directive"
    ]


def test_never_engaged_but_v1_clean_passes(tmp_path):
    # v1 无 alert、无 directive -> 不构成旁路，放行
    import importlib
    import verify_review_complete as vrc
    importlib.reload(vrc)
    assert vrc.check(_base(tmp_path)) == 0


def test_torn_active_revision_pair_blocks_admission(tmp_path):
    import verify_review_complete as vrc

    wd = _base(tmp_path, directive_status="resolved", ledger_status="resolved")
    ledger_path = wd / "pipeline/review/S01.machine_ledger.yaml"
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    ledger["active_revision_id"] = "0" * 64
    ledger_path.write_text(yaml.safe_dump(ledger), encoding="utf-8")

    assert vrc.check(wd) != 0
    eligibility = yaml.safe_load(
        (wd / "pipeline/audit/release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert "active_revision_mismatch" in eligibility["admission"]["reasons"][0]


def test_active_revision_must_match_lint_artifact_bytes(tmp_path):
    import verify_review_complete as vrc

    wd = _base(tmp_path, directive_status="resolved", ledger_status="resolved")
    lint_path = wd / "pipeline/review/lint/S01.ai_filler.yaml"
    lint = yaml.safe_load(lint_path.read_text(encoding="utf-8"))
    lint["extra"] = "tampered after refresh"
    lint_path.write_text(yaml.safe_dump(lint), encoding="utf-8")

    assert vrc.check(wd) != 0
    eligibility = yaml.safe_load(
        (wd / "pipeline/audit/release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert any(
        "active_revision_artifact_hash_mismatch" in reason
        for reason in eligibility["admission"]["reasons"]
    )


def test_invalid_hit_partition_blocks_admission(tmp_path):
    import verify_review_complete as vrc

    wd = _base(tmp_path, directive_status="resolved", ledger_status="resolved")
    directive_path = wd / "pipeline/review/S01.machine_directive.yaml"
    directive = yaml.safe_load(directive_path.read_text(encoding="utf-8"))
    directive["entries"][0]["exempted_hit_ids"] = ["S01-x-hit-1"]
    directive_path.write_text(yaml.safe_dump(directive), encoding="utf-8")

    assert vrc.check(wd) != 0
    eligibility = yaml.safe_load(
        (wd / "pipeline/audit/release_eligibility.yaml").read_text(encoding="utf-8")
    )
    assert any(
        "active_hit_partition_invalid" in reason
        for reason in eligibility["admission"]["reasons"]
    )
