"""Read legacy character names through the actual assembler without editing ledgers."""
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("identity_serial_context", SCRIPTS / "assemble_serial_context.py")
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


def put(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def named_persona(root, char_id, name, legacy=False):
    path = root / "series/ledgers/characters" / char_id / "persona.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if legacy else f"---\nname: {name}\nthrough_chapter: C0001\n---\n"
    path.write_text(f"{prefix}# {name}\n值守渡口。\n", encoding="utf-8")
    return path


def fixture(root, legacy=False):
    put(root, "series/story_bible.yaml", dict(frozen=dict(premise="渡口交班")))
    put(root, "series/volumes/V01.yaml", dict(volume_id="V01", tentpoles=[], chapters=[
        dict(chapter_id="C0001", status="published", unit="U01", logline="两名值守员交接"),
        dict(chapter_id="C0002", status="outline", unit="U01", logline="检查渡口照明"),
    ]))
    put(root, "published/manifest.yaml", dict(entries=[dict(chapter_id="C0001", published_seq=1, file="V01C0001.md")]))
    (root / "published/V01C0001.md").write_text("# 第1章\n许禾与陆宁交班。\n", encoding="utf-8")
    card = put(root, "chapters/V01/C0002/chapter_card.yaml", dict(
        chapter_id="C0002", prev_chapter="C0001", pov="许禾",
        recap_inputs=dict(characters=["许禾", "陆宁"], locations=[], items=["油箱"]),
    ))
    named_persona(root, "keeper", "许禾", legacy)
    named_persona(root, "assistant", "陆宁", legacy)
    facts = [
        dict(entity="keeper", kind="state", attribute="职责", value="负责灯房", established_at="C0001"),
        dict(entity="许禾", kind="relation", attribute="relation:陆宁", value="共同值守", established_at="C0001"),
        dict(entity="keeper", kind="secret", attribute="备用油位置", value="箱底留有一壶备用油", established_at="C0001", known_by=[dict(char_id="许禾", learned_at="C0001")]),
        dict(entity="keeper", kind="secret", attribute="遗失钥匙去向", value="镇所另藏了一把钥匙", established_at="C0001", known_by=[dict(char_id="陆宁", learned_at="C0001")]),
        dict(entity="许禾（值班员）", kind="state", attribute="近似名称", value="不应模糊匹配的人物材料", established_at="C0001"),
    ]
    paths = [put(root, f"series/ledgers/{filename}.yaml", dict(facts=facts)) for filename in ("world_facts", "facts_current")]
    return card, paths


@pytest.mark.parametrize("legacy", [False, True])
def test_unique_names_reach_author_facts_and_knowledge_receipts_without_ledger_mutation(tmp_path, legacy):
    _, paths = fixture(tmp_path, legacy)
    originals = {path: path.read_bytes() for path in paths}
    output = context.run(tmp_path, "C0002", 12000, 12).read_text(encoding="utf-8")
    assert "keeper · 职责: 负责灯房" in output
    assert "keeper · relation:assistant: 共同值守" in output
    assert "箱底留有一壶备用油" in output
    assert "镇所另藏了一把钥匙" in output
    assert "已登记知情者: keeper@C0001" in output
    assert "已登记知情者: assistant@C0001" in output
    assert "不应模糊匹配的人物材料" not in output
    assert "### keeper" in output and "### assistant" in output
    assert all(path.read_bytes() == original for path, original in originals.items())


@pytest.mark.parametrize("opening", [True, False])
def test_author_intent_survives_assembly_and_budget_without_becoming_character_state(tmp_path, opening):
    fixture(tmp_path)
    chapter_id = "C0001" if opening else "C0002"
    bible = put(tmp_path, "series/story_bible.yaml", dict(
        frozen=dict(premise="渡口交班", creative_anchors=dict(
            core_value="共同承担后果", primary_drive="information",
            controlling_idea=None, unique_angle="同一记录从不同经历获得不同含义",
            style_directives=["保留平静观察", "叙述采用第三人称"],
        )),
        intent=dict(current_thrust="本章追查照明中断的原因", open_questions=["是否在下一卷离开渡口？"]),
    ))
    original = bible.read_bytes()
    if opening:
        put(tmp_path, "published/manifest.yaml", dict(entries=[]))
        put(tmp_path, "chapters/V01/C0001/chapter_card.yaml", dict(
            chapter_id=chapter_id, prev_chapter=None, recap_inputs={},
        ))
    # Even below the irreducible context size, author decisions remain available.
    output = context.run(tmp_path, chapter_id, 1, 12).read_text(encoding="utf-8")
    author, people = output.split("## 角色现状", 1)
    for value in ("共同承担后果", "同一记录从不同经历获得不同含义", "保留平静观察", "本章追查照明中断的原因"):
        assert value in author and value not in people
    question_section = author.split("### 未决问题", 1)[1]
    assert "是否在下一卷离开渡口？" in question_section
    assert "表达方向：None" not in author
    assert bible.read_bytes() == original


def test_duplicate_display_name_requires_explicit_identity(tmp_path):
    _, paths = fixture(tmp_path)
    named_persona(tmp_path, "other_keeper", "许禾")
    originals = {path: path.read_bytes() for path in paths}
    with pytest.raises(context.DataError, match="多个 char_id"):
        context.run(tmp_path, "C0002", 12000, 12)
    assert all(path.read_bytes() == original for path, original in originals.items())
    assert not (tmp_path / "chapters/V01/C0002/pipeline/serial_context.md").exists()


def test_same_id_selected_as_character_and_item_is_rejected(tmp_path):
    card, paths = fixture(tmp_path)
    data = yaml.safe_load(card.read_text())
    data["recap_inputs"]["items"] = ["keeper"]
    card.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    originals = {path: path.read_bytes() for path in paths}
    with pytest.raises(context.DataError, match="人物与非人物"):
        context.run(tmp_path, "C0002", 12000, 12)
    assert all(path.read_bytes() == original for path, original in originals.items())


def test_item_sharing_display_name_keeps_its_own_entity(tmp_path):
    card, paths = fixture(tmp_path)
    facts = [
        dict(entity="keeper", kind="state", attribute="职责", value="负责灯房", established_at="C0001"),
        dict(entity="许禾", kind="item", attribute="印章", value="木质印章刻着许禾二字", established_at="C0001"),
    ]
    for path in paths:
        path.write_text(yaml.safe_dump(dict(facts=facts), allow_unicode=True), encoding="utf-8")
    originals = {path: path.read_bytes() for path in paths}
    people = context.run(tmp_path, "C0002", 12000, 12).read_text(encoding="utf-8")
    assert "负责灯房" in people
    assert "木质印章刻着许禾二字" not in people
    data = yaml.safe_load(card.read_text())
    data["recap_inputs"]["characters"] = []
    data["recap_inputs"]["items"] = ["许禾"]
    card.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    item = context.run(tmp_path, "C0002", 12000, 12).read_text(encoding="utf-8")
    assert "许禾 · 印章: 木质印章刻着许禾二字" in item
    assert "keeper · 职责" not in item
    assert all(path.read_bytes() == original for path, original in originals.items())


def test_unselected_ambiguous_relation_does_not_block_current_characters(tmp_path):
    card, paths = fixture(tmp_path)
    named_persona(tmp_path, "visitor_one", "唐禾")
    named_persona(tmp_path, "visitor_two", "唐禾")
    for path in paths:
        data = yaml.safe_load(path.read_text())
        data["facts"].append(dict(entity="唐禾", kind="relation", attribute="relation:keeper", value="未辨明的旧同事", established_at="C0001"))
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    originals = {path: path.read_bytes() for path in paths}
    output = context.run(tmp_path, "C0002", 12000, 12).read_text(encoding="utf-8")
    assert "负责灯房" in output
    assert "未辨明的旧同事" not in output
    # Once one of these people is selected, the ambiguous relation must be resolved.
    data = yaml.safe_load(card.read_text())
    data["recap_inputs"]["characters"].append("visitor_one")
    card.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(context.DataError, match="多个 char_id"):
        context.run(tmp_path, "C0002", 12000, 12)
    assert all(path.read_bytes() == original for path, original in originals.items())
