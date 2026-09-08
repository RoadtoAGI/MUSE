"""Check source-time isolation and inherited character inputs at the actual renderer."""
import importlib.util
from pathlib import Path
import sys
import yaml
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("serial_context", SCRIPTS / "assemble_serial_context.py")
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


def put(root, name, data):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True))
    return p


def persona(role, body, through="C0002", name="许禾"):
    role.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_dump(dict(name=name, through_chapter=through), allow_unicode=True)
    (role / "persona.md").write_text(f"---\n{meta}---\n{body}\n", encoding="utf-8")


def fixture(root):
    role = root / "series/ledgers/characters/keeper"
    persona(role, "为渡船提供照明的值班员")
    put(role, "snapshots/V01.yaml", dict(extends=None, through_chapter="C0002", state="看守灯房", capabilities=["维修灯罩"]))
    put(role, "snapshots/V02.yaml", dict(extends="V01", through_chapter="C0004", delta=dict(relationships=["与助手开始查账合作"])))
    put(role, "snapshots/V03.yaml", dict(extends="V02", through_chapter="C0007", state="未来任命"))
    put(role, "biography.yaml", dict(milestones=[dict(at="C0004", kind="关系", before="独自查账", after="合作", evidence="一起去"), dict(at="C0007", kind="职务", before="值班", after="未来任命", evidence="任命书")]))
    index = {f"C{i:04}": dict(volume_id=f"V{(i + 1)//2:02}", entry=dict(status="published")) for i in range(1, 8)}
    put(root, "published/manifest.yaml", dict(entries=[dict(chapter_id=cid, file=f"{info['volume_id']}{cid}.md", published_seq=i) for i, (cid, info) in enumerate(index.items(), 1)]))
    for cid, info in index.items():
        (root / "published" / f"{info['volume_id']}{cid}.md").write_text(f"# {cid}\n值班记录。\n", encoding="utf-8")
    for vid in {info["volume_id"] for info in index.values()}:
        put(root, f"series/volumes/{vid}.yaml", dict(volume_id=vid, chapters=[dict(chapter_id=cid, status="published", unit="U01") for cid, info in index.items() if info["volume_id"] == vid]))
    return role, index


def test_inheritance_and_persona_reach_consumer(tmp_path):
    _, index = fixture(tmp_path)
    text = context.render_section4(tmp_path, ["keeper"], index, "V03", {}, "C0005")
    for expected in ["为渡船提供照明", "维修灯罩", "看守灯房", "开始查账合作"]:
        assert expected in text
    assert "未来任命" not in text


def test_revisiting_current_volume_excludes_its_later_snapshot_and_milestone(tmp_path):
    _, index = fixture(tmp_path)
    text = context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0003")
    assert "维修灯罩" in text
    assert "开始查账合作" not in text
    assert "一起去" not in text


def test_persona_scope_is_independent_of_snapshot_availability(tmp_path):
    role, index = fixture(tmp_path)
    persona(role, "值班员先检查照明", through="C0001")
    early = context.render_section4(tmp_path, ["keeper"], index, "V01", {}, "C0002")
    assert "值班员先检查照明" in early
    assert "该角色尚无快照" in early
    # Later biographical understanding cannot enter an earlier chapter through persona.
    persona(role, "已经与助手共同查账", through="C0004")
    historical = context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0003")
    visible = context.render_section4(tmp_path, ["keeper"], index, "V03", {}, "C0005")
    assert "已经与助手共同查账" not in historical
    assert "已经与助手共同查账" in visible


def test_legacy_persona_is_latest_only(tmp_path):
    role, index = fixture(tmp_path)
    (role / "persona.md").write_text("# 许禾\n后来升任站长。\n", encoding="utf-8")
    historical = context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0003")
    latest = context.render_section4(tmp_path, ["keeper"], index, "V04", {})
    assert "后来升任站长" not in historical
    assert "看守灯房" in historical
    assert "后来升任站长" in latest


def test_null_persona_scope_requires_initial_design_snapshot(tmp_path):
    role, index = fixture(tmp_path)
    persona(role, "开工前确定的照明职责", through=None)
    with pytest.raises(context.DataError, match="V00"):
        context.render_section4(tmp_path, ["keeper"], index, "V01", {}, "C0001")
    put(role, "snapshots/V00.yaml", dict(extends=None, state="开工设定"))
    text = context.render_section4(tmp_path, ["keeper"], index, "V01", {}, "C0001")
    assert "开工前确定的照明职责" in text
    assert "开工设定" in text


def test_consumed_biography_missing_fields_raise_instead_of_rendering_none(tmp_path):
    role, index = fixture(tmp_path)
    put(role, "biography.yaml", dict(milestones=[dict(at="C0004", description="独自查账变为合作", evidence="一起去")]))
    # A next chapter in the same volume consumes this already-published milestone.
    index["C0008"] = dict(volume_id="V02")
    put(tmp_path, "chapters/V02/C0008/chapter_card.yaml", dict(chapter_id="C0008", prev_chapter="C0004"))
    with pytest.raises(context.DataError, match="kind, before, after"):
        context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0008")


def test_buffer_character_change_missing_before_is_rejected(tmp_path):
    _, index = fixture(tmp_path)
    delta = dict(at="C0004", kind="关系变化", after="一起查账", evidence="一起去")
    with pytest.raises(context.DataError, match="buffer character_deltas.*before"):
        context.render_section4(tmp_path, ["keeper"], index, "V03", {"keeper": [("C0004", delta)]}, "C0005")


def test_legacy_snapshot_uses_published_chapter_boundary(tmp_path):
    role, index = fixture(tmp_path)
    put(role, "snapshots/V02.yaml", dict(extends="V01", relationships=["已成立伙伴关系"]))
    before = context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0003")
    after = context.render_section4(tmp_path, ["keeper"], index, "V03", {}, "C0005")
    assert "已成立伙伴关系" not in before
    assert "已成立伙伴关系" in after


@pytest.mark.parametrize("parent", ["V02", "V00"])
def test_broken_inheritance_is_reported(tmp_path, parent):
    role, index = fixture(tmp_path)
    put(role, "snapshots/V02.yaml", dict(extends=parent, through_chapter="C0004", state="changed"))
    with pytest.raises(context.DataError):
        context.render_section4(tmp_path, ["keeper"], index, "V03", {}, "C0005")


def test_snapshot_producer_records_actual_published_boundary(tmp_path):
    role, _ = fixture(tmp_path)
    (role / "snapshots/V02.yaml").unlink()
    put(tmp_path, "series/volumes/V02.yaml", dict(chapters=[dict(chapter_id="C0003"), dict(chapter_id="C0004"), dict(chapter_id="C0005")]))
    put(tmp_path, "published/manifest.yaml", dict(entries=[dict(chapter_id="C0003", published_seq=3), dict(chapter_id="C0004", published_seq=4)]))
    spec = importlib.util.spec_from_file_location("snapshot_character", SCRIPTS / "snapshot_character.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    path, _ = producer.run(tmp_path, "V02", "keeper")
    data = yaml.safe_load(path.read_text())
    assert data["through_chapter"] == "C0004"
    assert data["extends"] == "V01"


def test_character_time_uses_published_sequence_not_numeric_id(tmp_path):
    role = tmp_path / "series/ledgers/characters/keeper"
    put(role, "snapshots/V01.yaml", dict(extends=None, through_chapter="C0009", state="过去的身份"))
    put(tmp_path, "published/manifest.yaml", dict(entries=[dict(chapter_id="C0009", published_seq=10), dict(chapter_id="C0003", published_seq=30)]))
    index = dict(C0009=dict(volume_id="V01"), C0003=dict(volume_id="V02"))
    text = context.render_section4(tmp_path, ["keeper"], index, "V02", {}, "C0003")
    assert "过去的身份" in text
