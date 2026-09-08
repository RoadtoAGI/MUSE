from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
import rhetoric_retrieval as rr  # noqa: E402


def _card(
    occurrence_id: str,
    *,
    text: str,
    quality: str = "exemplary",
    path: str = "novels/三体/rhetoric/occurrences/card.yaml",
    locator: str = "L10",
) -> dict:
    container, work = Path(path).parts[:2]
    return {
        "occurrence_id": occurrence_id,
        "work_id": f"{container}:{work}",
        "occurrence_file": path,
        "source_locator": f"full_text.md:{locator}",
        "figure_type": "simile",
        "quote": text,
        "tenor": "不可见的压力",
        "vehicle": text,
        "ground": "同一变化路径",
        "image_mechanism": text,
        "property_alignment": "起点相同；运动方向相同；结果相同",
        "context_alignment": "符合观察者当时的经验",
        "narrative_function": "让抽象变化可见",
        "transfer_rule": "选择变化路径同构的日常物",
        "failure_boundary": "路径不同便失效",
        "quality_assessment": quality,
    }


def _write_index(kb: Path, cards: list[dict]) -> None:
    path = kb / "rhetoric" / "occurrence_index.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": rr.INDEX_SCHEMA,
                "scope_status": "complete",
                "occurrences": cards,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_missing_and_malformed_index_degrade_to_empty(tmp_path):
    assert rr.load_occurrences(tmp_path) == []
    path = tmp_path / "rhetoric" / "occurrence_index.json"
    path.parent.mkdir()
    path.write_text("{bad", encoding="utf-8")
    assert rr.load_occurrences(tmp_path) == []
    path.write_text(
        json.dumps(
            {
                "schema_version": rr.INDEX_SCHEMA,
                "scope_status": "unscoped_derived",
                "occurrences": [_card("unsafe", text="未验证")],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert rr.load_occurrences(tmp_path) == []


def test_select_returns_only_positive_high_quality_matches(tmp_path):
    cards = [
        _card("b", text="冰激凌摊薄飞船"),
        _card("a", text="冰激凌摊薄飞船", quality="effective", locator="L11"),
        _card("c", text="王冠毒蛇"),
        _card("d", text="冰激凌摊薄飞船", quality="functional"),
    ]
    _write_index(tmp_path, cards)

    selected = rr.select_rhetoric_cards(
        tmp_path,
        "飞船摊薄",
        [{"file": "novels/测试/scenes/S01.md", "description": "二维展开"}],
    )

    assert [item["occurrence_id"] for item in selected] == ["b", "a"]
    assert rr.select_rhetoric_cards(tmp_path, "完全无关词", []) == []


def test_scene_metadata_supports_manual_selection_and_limit(tmp_path):
    cards = [_card(str(index), text=f"暴雨雷声压迫{index}") for index in range(5)]
    _write_index(tmp_path, cards)

    selected = rr.select_rhetoric_cards(
        tmp_path,
        "",
        [{"file": "novels/测试/scenes/S01.md", "tags": ["暴雨", "雷声"]}],
        limit=3,
    )

    assert len(selected) == 3
    assert [item["occurrence_id"] for item in selected] == ["0", "1", "2"]


def test_medium_isolation(tmp_path):
    prose = _card("prose", text="雷声压迫")
    drama = _card(
        "drama",
        text="雷声压迫",
        path="dramas/雷雨/rhetoric/occurrences/card.yaml",
    )
    _write_index(tmp_path, [prose, drama])

    prose_pick = rr.select_rhetoric_cards(
        tmp_path,
        "雷声压迫",
        [{"source_medium": "novel", "file": "novels/书/scenes/S.md"}],
    )
    drama_pick = rr.select_rhetoric_cards(
        tmp_path,
        "雷声压迫",
        [{"source_medium": "stage_play", "file": "dramas/剧/scenes/S.md"}],
    )

    assert [item["occurrence_id"] for item in prose_pick] == ["prose"]
    assert [item["occurrence_id"] for item in drama_pick] == ["drama"]


def test_source_checked_classic_exemplars_join_learning_pool(tmp_path):
    rhetoric = tmp_path / "rhetoric"
    rhetoric.mkdir()
    source = tmp_path / "dramas" / "雷雨" / "full_text.md"
    source.parent.mkdir(parents=True)
    source.write_text("\n" * 9 + "天空布满恶相的黑云\n", encoding="utf-8")
    scope_path = rhetoric / "corpus_scope.yaml"
    scope_path.write_text(
        json.dumps(
            {
                "corpus": [
                    {
                        "title": "雷雨",
                        "container": "dramas",
                        "work": "雷雨",
                        "source_file": "full_text.md",
                        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "start_line": 1,
                        "end_line": 10,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (rhetoric / "classics_rhetoric_exemplars.yaml").write_text(
        json.dumps(
            {
                "schema_version": "rhetoric-learning-exemplars/v1",
                "status": "source_checked",
                "scope_manifest": "corpus_scope.yaml",
                "scope_manifest_sha256": hashlib.sha256(scope_path.read_bytes()).hexdigest(),
                "cards": [
                    {
                        "card_id": "thunder",
                        "work": "雷雨",
                        "source_locator": "full_text.md:L10",
                        "figure_type": "personification",
                        "quote": "天空布满恶相的黑云",
                        "vividness": {
                            "sensory_channels": ["视觉", "听觉"],
                            "mechanism": "雷云获得面相和逼近动作",
                        },
                        "aptness": {
                            "mappings": ["黑云对应秘密", "雷声对应冲突逼近"],
                            "context_fit": "舞台声光兑现修辞",
                            "failure_boundary": "天气不替人物作伦理选择",
                        },
                        "narrative_function": "环境成为施压角色",
                        "transfer_rule": "舞台修辞要能转成声光动作",
                        "quality_assessment": "exemplary",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    selected = rr.select_rhetoric_cards(
        tmp_path,
        "黑云雷声逼近",
        [{"source_medium": "stage_play"}],
    )

    assert [item["occurrence_id"] for item in selected] == ["thunder"]
    assert selected[0]["property_alignment"] == "黑云对应秘密；雷声对应冲突逼近"

    source.write_text("\n" * 9 + "正文已经漂移\n", encoding="utf-8")
    assert rr.load_classic_exemplars(tmp_path) == []


def test_render_contains_actionable_fields():
    rendered = "\n".join(rr.render_rhetoric_cards([_card("x", text="冰激凌摊薄")]))

    assert rendered.startswith("<rhetoric_cards")
    assert "形象机制" in rendered
    assert "属性对应" in rendered
    assert "迁移规则" in rendered
    assert "失效边界" in rendered
    assert rendered.endswith("</rhetoric_cards>")
