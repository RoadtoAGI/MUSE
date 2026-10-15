from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import yaml


ar = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.annotate_register")

KB = ar.KB_ROOT


def _scene(kb_work: Path, sid: str, text: str) -> dict:
    (kb_work / "scenes").mkdir(parents=True, exist_ok=True)
    (kb_work / "scenes" / f"scene_{sid}.md").write_text(text, encoding="utf-8")
    return {"scene_id": sid, "file": f"scenes/scene_{sid}.md", "lang": "zh"}


def _work(tmp_path: Path, name: str, scenes: dict[str, str], card: dict | None) -> Path:
    work = tmp_path / "kb" / "novels" / name
    work.mkdir(parents=True)
    rows = [_scene(work, sid, text) for sid, text in scenes.items()]
    (work / "scene_index.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    if card is not None:
        (work / "style_card.yaml").write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")
    return work


FIRST_PERSON = "我推开门，屋里没人。我在桌边坐下，我想起昨天的事，我又站起来。" * 20
THIRD_PERSON = "他推开门，屋里没人。他在桌边坐下，想起昨天的事，又站起来走到窗前。" * 20


def test_body_text_skips_scene_headers():
    text = "# 场景 S01：雪夜\n**出处**：《某书》第2章\n---\n\n夜里落了一场大雪。\n\n<!-- 注释 -->\n他出门。"
    assert ar.body_text(text) == "夜里落了一场大雪。\n他出门。"


def test_split_quoted_pairs_quotes_across_lines():
    outside, inside = ar.split_quoted("他说。\n“你给我坐下。\n这么着急，明智吗？”\n我没动。")
    assert "坐下" in inside and "明智吗" in inside
    assert "我没动" in outside and "坐下" not in outside


def test_unclosed_quote_does_not_swallow_scene():
    outside, inside = ar.split_quoted("“第一段没有闭合\n" + "他走了很远的路。" * 50)
    assert "他走了很远的路" in outside
    assert inside == ""


def test_person_first_and_third_from_narration():
    assert ar.classify_person(ar.features(FIRST_PERSON, "zh")) == "first"
    assert ar.classify_person(ar.features(THIRD_PERSON, "zh")) == "third"


def test_first_person_inside_quotes_is_ignored():
    text = "他推开门说：“我来了，我饿了，我要吃饭。”屋里没人应他。" * 20
    assert ar.classify_person(ar.features(text, "zh")) == "third"


def test_english_person_counts_pronouns_outside_quotes():
    first = "I walked to the door and I opened it. My hands were cold. " * 30
    third = 'He walked to the door. "I am here," he said. His hands were cold. ' * 30
    assert ar.classify_person(ar.features(first, "en")) == "first"
    assert ar.classify_person(ar.features(third, "en")) == "third"


def test_register_unset_for_uncalibrated_language():
    assert ar.classify_register(ar.features("He walked home. " * 50, "en")) is None


def test_colloquial_markers_counted_in_narration_only():
    spoken = "他说：“你吃了吗？咱们走吧，啥也别管了呢。”" * 30
    monologue = "咱们先说好啊，这事儿反正就这么着吧，你也别管了，说白了就是没辙呢。" * 30
    assert ar.features(spoken, "zh").markers_per_1k == 0.0
    assert ar.classify_register(ar.features(monologue, "zh")) == "colloquial"


def test_annotate_work_writes_four_fields_and_override(tmp_path):
    work = _work(tmp_path, "书甲", {"S01": FIRST_PERSON, "S02": THIRD_PERSON},
                 {"novel": "书甲", "lang": "zh", "original_lang": "zh", "narrative_person_override": "third"})
    rows = ar.annotate_work(work / "scene_index.json")
    saved = json.loads((work / "scene_index.json").read_text(encoding="utf-8"))
    assert rows == saved
    for row in saved:
        assert set(ar.FIELDS) <= set(row)
        assert row["original_lang"] == "zh"
        assert row["narrative_person"] == "third"  # 作品级覆盖优先于启发式
        assert 0.0 <= row["dialogue_ratio"] <= 1.0


def test_drama_has_no_narrator_and_reads_work_meta(tmp_path):
    work = tmp_path / "kb" / "dramas" / "剧甲"
    rows = [_scene(work, "A1S1", "周朴园：我问你，你是谁？\n鲁侍萍：我是从前侍候老太太的。\n（静场）\n" * 20)]
    (work / "dramatic_scene_index.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (work / "work-meta.yaml").write_text("language: zh\noriginal_language: zh\n", encoding="utf-8")
    row = ar.annotate_work(work / "dramatic_scene_index.jsonl")[0]
    assert row["narrative_person"] is None
    assert row["register"] is None
    assert row["original_lang"] == "zh"
    assert row["dialogue_ratio"] > 0.8


@pytest.mark.parametrize(
    "card, expected",
    [
        ({"author": "司汤达", "lang": "zh", "translator": "罗新璋"}, "fr"),
        ({"author": "东野圭吾", "lang": "zh", "translator": ""}, "ja"),
        ({"author": "陈忠实", "lang": "zh", "translator": ""}, "zh"),
        ({"author": "Richard Matheson", "lang": "en"}, "en"),
        ({"author": "某译者笔下的作家", "lang": "zh", "translator": "某人"}, None),
    ],
)
def test_prefill_decision(card, expected):
    assert ar.prefill_decision(card)[0] == expected


def test_prefill_inserts_after_lang_line_and_keeps_layout(tmp_path):
    work = tmp_path / "kb" / "novels" / "书乙"
    work.mkdir(parents=True)
    original = "novel: 书乙\nauthor: 陈忠实\nlang: zh\ntranslator: ''\ndiction: 关中口语\n"
    (work / "style_card.yaml").write_text(original, encoding="utf-8")
    assert ar.prefill_original_lang(tmp_path / "kb") == 0
    assert (work / "style_card.yaml").read_text(encoding="utf-8") == original.replace(
        "lang: zh\n", "lang: zh\noriginal_lang: zh\n")
    ar.prefill_original_lang(tmp_path / "kb")  # 已有值不重复写
    assert (work / "style_card.yaml").read_text(encoding="utf-8").count("original_lang") == 1


# ---- 现库标定回归：用知识库里的真实场景，库里没有该作品时跳过 ----

def _kb_scene(work: str, scene_id: str) -> tuple[Path, dict]:
    path = KB / "novels" / work / "scene_index.json"
    if not path.exists():
        pytest.skip(f"知识库无 {work}")
    entry = next((e for e in json.loads(path.read_text(encoding="utf-8")) if e["scene_id"] == scene_id), None)
    if entry is None:
        pytest.skip(f"{work} 无 {scene_id}")
    return path.parent / entry["file"], entry


def test_kb_kuangbing_diary_is_first_person():
    scene, _ = _kb_scene("狂病-莫千回", "XX-S02")
    assert ar.classify_person(ar.features(scene.read_text(encoding="utf-8"), "zh")) == "first"


def test_kb_the_road_needs_override(tmp_path):
    scene, entry = _kb_scene("长路", "scene_02")
    text = scene.read_text(encoding="utf-8")
    assert ar.classify_person(ar.features(text, "zh")) == "first"  # 对白不加引号，启发式会误判
    work = _work(tmp_path, "长路", {"scene_02": text},
                 {"lang": "zh", "original_lang": "en", "narrative_person_override": "third"})
    assert ar.annotate_work(work / "scene_index.json")[0]["narrative_person"] == "third"


def test_kb_shediao_is_literary():
    scene, _ = _kb_scene("射雕英雄传", "S29")
    assert ar.classify_register(ar.features(scene.read_text(encoding="utf-8"), "zh")) == "literary"


def test_embedded_first_person_letter_is_mixed():
    # 第三人称叙述里嵌一封第一人称书信：整场"我"的密度够 first，段落占比低于 0.45
    third = ["他推开门，屋里很冷。", "她没有回头，只是把灯拧亮了些。", "他在桌边坐下。",
             "她把信推到他面前。", "他看了很久。", "她说外面又下雪了。"] * 2
    letter = ["我写这封信的时候，我的手一直在抖，我不知道我还能撑多久。"] * 4
    text = "\n\n".join(third + letter)
    feat = ar.features(text, "zh")
    assert feat.first_person_per_1k >= ar.ZH_FIRST_PER_1K
    assert ar.classify_person(feat) == "mixed"


def test_first_person_narrator_describing_others_stays_first():
    # 旁观者叙述：一半段落写别人，"我"仍在场
    paras = ["我看着他走进来。", "他把帽子挂上，没说话。", "我给他倒了杯茶，我知道他有话要说。",
             "她在门口站了一会儿。", "我起身去关窗。", "他终于开口了。"] * 3
    feat = ar.features("\n\n".join(paras), "zh")
    assert ar.classify_person(feat) == "first"


def test_kb_i_am_legend_letter_scene_is_mixed():
    scene, entry = _kb_scene("I Am Legend", "S10")
    assert ar.classify_person(ar.features(scene.read_text(encoding="utf-8"), entry.get("lang", "en"))) == "mixed"
