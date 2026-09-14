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


def test_group_reference_preserves_receivers_knowledge_reply_and_result():
    event = {
        "event_type": "group_exchange",
        "participants": [
            {"character_id": "a", "display_name": "甲", "knowledge_boundary": "以为钥匙还在乙处", "position": "unneeded_metadata"},
            {"character_id": "b", "display_name": "乙", "knowledge_boundary": "知道钥匙已交给丙"},
            {"character_id": "c", "display_name": "丙"},
        ],
        "turns": [
            {"turn_id": "t1", "speaker_id": "a", "addressee_ids": ["b"], "text": "钥匙呢？"},
            {"turn_id": "t2", "speaker_id": "c", "addressee_ids": ["b"], "text": "先别说。"},
            {"turn_id": "t3", "speaker_id": "b", "addressee_ids": ["a", "c"], "response_to": "t1", "text": "我已经交出去了。"},
            {"turn_id": "t4", "speaker_id": "c", "addressee_ids": [], "text": "那就来不及了。"},
        ],
        "outcome": {"visible_result": "甲转向丙索取钥匙", "relationship_cost": "unneeded_cost_enum"},
        "transferable_mechanism": "跨过插话回答原问，迫使旁人进入交涉。",
    }
    text = dq.render_reference(scene_id="S01", role_slug="role-a", matches=[(event, [])])

    assert "来源知情条件（甲）：以为钥匙还在乙处" in text
    assert "来源知情条件（乙）：知道钥匙已交给丙" in text
    assert "[t1] 甲（接收：乙）：钥匙呢？" in text
    assert "[t3] 乙（接收：甲、丙；回应：t1）：我已经交出去了。" in text
    assert "[t4] 丙（接收未明）：那就来不及了。" in text
    assert "来源结果：甲转向丙索取钥匙" in text
    assert "迁移机制：跨过插话回答原问" in text
    assert "unneeded_metadata" not in text and "unneeded_cost_enum" not in text


def test_ordinary_adjacent_exchange_remains_concise():
    event = {
        "participants": [
            {"character_id": "a", "display_name": "甲", "knowledge_boundary": ""},
            {"character_id": "b", "display_name": "乙"},
        ],
        "turns": [
            {"turn_id": "t1", "speaker_id": "a", "addressee_ids": ["b"], "text": "先坐下吧。"},
            {"turn_id": "t2", "speaker_id": "b", "addressee_ids": ["a"], "response_to": "t1", "text": "好。"},
        ],
    }
    assert dq.render_source_exchange(event) == [
        "<dialogue_exemplar>", "甲：先坐下吧。", "乙：好。", "</dialogue_exemplar>",
    ]


def test_self_response_keeps_the_internal_turn_reference():
    event = {"turns": [
        {"turn_id": "t1", "speaker_id": "a", "speaker_label": "甲", "addressee_ids": ["a"], "text": "也许还有机会。"},
        {"turn_id": "t2", "speaker_id": "a", "speaker_label": "甲", "addressee_ids": ["a"], "response_to": "t1", "text": "可他已经走了。"},
    ]}
    text = "\n".join(dq.render_source_exchange(event))
    assert "[t1] 甲（接收：甲）：也许还有机会。" in text
    assert "[t2] 甲（接收：甲；回应：t1）：可他已经走了。" in text


def test_explicit_unknown_receiver_is_preserved_for_all_event_types():
    for event_type in ("interaction", "group_exchange", "monologue", "soliloquy"):
        event = {
            "event_type": event_type,
            "turns": [{"speaker_label": "甲", "addressee_ids": [], "text": "要下雨了。"}],
        }
        assert "甲（接收未明）：要下雨了。" in dq.render_source_exchange(event)
        del event["turns"][0]["addressee_ids"]
        assert dq.render_source_exchange(event) == [
            "<dialogue_exemplar>", "甲：要下雨了。", "</dialogue_exemplar>",
        ]
