"""scene_review_schema_validator.py contract tests."""

from scene_review_schema_validator import validate_scene_review


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


def _yields_all_false() -> dict[str, bool]:
    return {yield_type: False for yield_type in YIELD_TYPES}


def test_yields_true_without_evidence_blocks():
    yields = _yields_all_false()
    yields["plot_change"] = True
    review = {
        "reader_yield_check": [
            {
                "text": "他在看。",
                "candidate_type": "<=10_micro_clause",
                "yields": yields,
                "yield_evidences": [],
                "verdict": "effective",
            }
        ]
    }

    result = validate_scene_review(review)

    assert result["valid"] is False
    assert "yield_evidences" in result["error"]
    assert "plot_change" in result["error"]


def test_yields_true_with_matching_evidence_passes():
    yields = _yields_all_false()
    yields["plot_change"] = True
    review = {
        "reader_yield_check": [
            {
                "text": "城破。",
                "candidate_type": "<=10_micro_clause",
                "yields": yields,
                "yield_evidences": [
                    {"yield_type": "plot_change", "reason": "城池陷落首次发生，改变战役走向"}
                ],
                "verdict": "effective",
            }
        ]
    }

    result = validate_scene_review(review)

    assert result["valid"] is True


def test_absent_listed_yields_leave_semantic_verdict_to_reviewer():
    review = {
        "reader_yield_check": [
            {
                "text": "他在看。",
                "candidate_type": "<=10_micro_clause",
                "yields": _yields_all_false(),
                "yield_evidences": [],
                "verdict": "effective",
            }
        ]
    }

    result = validate_scene_review(review)

    assert result["valid"] is True


def test_evidence_reason_requires_content_without_length_quota():
    yields = _yields_all_false()
    yields["plot_change"] = True
    review = {
        "reader_yield_check": [
            {
                "text": "x",
                "candidate_type": "<=10_micro_clause",
                "yields": yields,
                "yield_evidences": [{"yield_type": "plot_change", "reason": "城破首次发生"}],
            }
        ]
    }

    result = validate_scene_review(review)

    assert result["valid"] is True
    review["reader_yield_check"][0]["yield_evidences"][0]["reason"] = ""
    assert validate_scene_review(review)["valid"] is False
