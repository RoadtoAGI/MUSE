from __future__ import annotations

import argparse
import importlib


dq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.dialogue_query")


def _args(**overrides):
    values = {
        "medium": "novel",
        "relationship": "parent_child",
        "power": "parent_over_child",
        "pressure": "family_honor",
        "speech_action": "dismiss",
        "cooperation": "refusing_premise",
        "capacity": "full",
        "query": "复述关键词后驳回",
        "include_monologue": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_structured_match_returns_behavior_example_without_copy_mandate():
    event = {
        "event_id": "drama:书:S01:e01",
        "event_type": "interaction",
        "work_id": "drama:书",
        "medium": "novel",
        "scene_id": "S01",
        "event_file": "novels/书/dialogue/events/scene_S01.yaml",
        "annotation": {"review_status": "source_checked"},
        "context": {
            "relationship": "parent_child",
            "power": "parent_over_child",
            "pressure": "family_honor",
        },
        "turns": [
            {
                "speaker_label": "甲",
                "text": "你所谓的诚意？",
                "source_locator": "scenes/scene_S01.md:L1",
                "speech_action": "probe",
                "cooperation": "controlling",
                "capacity": "full",
            },
            {
                "speaker_label": "乙",
                "text": "算了。",
                "source_locator": "scenes/scene_S01.md:L2",
                "speech_action": "dismiss",
                "cooperation": "refusing_premise",
                "capacity": "full",
            },
        ],
        "transferable_mechanism": "复述关键词后驳回。",
    }

    score, reasons = dq.score_event(event, _args())
    second_event = dict(event)
    second_event["event_id"] = "drama:书乙:S01:e01"
    second_event["work_id"] = "drama:书乙"
    rendered = dq.render_reference(
        scene_id="S09",
        role_slug="role-a",
        matches=[(event, reasons), (second_event, reasons)],
    )

    assert score > 10
    assert "status: MATCH" in rendered
    assert "迁移机制：复述关键词后驳回。" in rendered
    assert "source_locators: scenes/scene_S01.md:L1, scenes/scene_S01.md:L2" in rendered
    assert "不迁移示例人物的姓名、经历、专有称谓、标志性原句或固定口癖" in rendered
    assert "reuse_mandate: true" not in rendered


def test_no_match_is_explicit_and_does_not_invent_an_exemplar():
    rendered = dq.render_reference(scene_id="S09", role_slug="role-a", matches=[])

    assert "status: NO_MATCH" in rendered
    assert "<dialogue_exemplar>" not in rendered


def test_candidate_annotation_is_not_available_to_runtime_retrieval():
    event = {
        "event_type": "interaction",
        "annotation": {"review_status": "candidate"},
        "medium": "novel",
        "context": {"relationship": "parent_child"},
    }

    score, reasons = dq.score_event(event, _args())

    assert score == -1.0
    assert reasons == []


def test_text_only_query_cannot_force_a_few_shot_match():
    args = _args(relationship="", pressure="", speech_action="")

    matches, reason, eligible, sources = dq.decide_matches([], args, top_k=2)

    assert matches == []
    assert reason == "missing_required_fields:relationship,pressure,speech_action"
    assert eligible == 0
    assert sources == 0


def test_single_compatible_event_can_supply_a_candidate():
    event = {
        "event_id": "novel:书甲:S01:e01",
        "event_type": "interaction",
        "work_id": "novel:书甲",
        "medium": "novel",
        "annotation": {"review_status": "source_checked"},
        "context": {
            "relationship": "parent_child",
            "power": "parent_over_child",
            "pressure": "family_honor",
        },
        "turns": [
            {
                "speech_action": "dismiss",
                "cooperation": "refusing_premise",
                "capacity": "full",
            }
        ],
    }

    matches, reason, eligible, sources = dq.decide_matches([event], _args(), top_k=2)

    assert len(matches) == 1
    assert reason == "compatible_event"
    assert eligible == 1
    assert sources == 1

    rendered = dq.render_reference(
        scene_id="S09", role_slug="role-a", matches=[(event, ["relationship"])]
    )
    assert "status: MATCH" in rendered
    assert "<dialogue_exemplar>" in rendered


def test_two_compatible_independent_works_enable_diverse_few_shot():
    events = []
    for work in ("novel:书甲", "novel:书乙"):
        events.append(
            {
                "event_id": f"{work}:S01:e01",
                "event_type": "interaction",
                "work_id": work,
                "medium": "novel",
                "annotation": {"review_status": "source_checked"},
                "context": {
                    "relationship": "parent_child",
                    "power": "parent_over_child",
                    "pressure": "family_honor",
                },
                "turns": [
                    {
                        "speech_action": "dismiss",
                        "cooperation": "refusing_premise",
                        "capacity": "full",
                    }
                ],
            }
        )

    matches, reason, eligible, sources = dq.decide_matches(events, _args(), top_k=2)

    assert [event["work_id"] for event, _ in matches] == ["novel:书乙", "novel:书甲"]
    assert reason == "compatible_event"
    assert eligible == 2
    assert sources == 2


def test_fields_are_compared_in_their_own_scope():
    event = {
        "event_id": "novel:书甲:S01:e01",
        "event_type": "interaction",
        "work_id": "novel:书甲",
        "medium": "novel",
        "annotation": {"review_status": "source_checked"},
        "context": {
            "relationship": "roommates",
            "power": "symmetric",
            "pressure": "mortal_coercion",
        },
        "turns": [
            {
                "speech_action": "coordinate_chores",
                "cooperation": "cooperative",
                "capacity": "full",
            }
        ],
        "outcome": {"relationship_cost": "low"},
    }
    args = _args(
        relationship="roommates",
        power="symmetric",
        pressure="low",
        speech_action="coordinate_chores",
        cooperation="cooperative",
    )

    score, reasons = dq.score_event(event, args)

    assert score == -1.0
    assert reasons == []


def test_turn_filters_cannot_be_assembled_from_different_speakers():
    event = {
        "event_type": "interaction", "medium": "novel",
        "annotation": {"review_status": "source_checked"},
        "context": {"relationship": "peer", "pressure": "concealment"},
        "turns": [
            {"turn_id": "t1", "speaker_id": "a", "speech_action": "probe", "capacity": "full"},
            {"turn_id": "t2", "speaker_id": "b", "speech_action": "dismiss", "capacity": "strained"},
        ],
    }
    args = _args(relationship="peer", power="", pressure="concealment", speech_action="probe", cooperation="", capacity="strained")
    assert dq.score_event(event, args)[0] == -1
    args.capacity = "full"
    score, reasons = dq.score_event(event, args)
    assert score > 0
    assert "target_turn:t1" in reasons
