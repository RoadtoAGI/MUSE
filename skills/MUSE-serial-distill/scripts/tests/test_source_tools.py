"""Source conversion regressions: chapter identity and visibility precede model reading."""
import importlib.util
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


split = load("split_chapters")
extract = load("extract_scene")
query = load("select_references")


def test_chapter_titles_do_not_split_internal_headings():
    text = "# 序章\n前史\n# 第1章 夜\n甲\n## 一阵风\n乙\n# 第2章 雨\n丙\n"
    chapters, _ = split.split_into_chapters(text, split.compile_title_matcher(None))
    assert len(chapters) == 3
    assert "## 一阵风\n乙" in chapters[1]
    # Untitled chapter books remain supported through an explicit heading family.
    custom, _ = split.split_into_chapters("# 灯\n甲\n# 船\n乙", split.compile_title_matcher(r"^# "))
    assert len(custom) == 2


def test_directory_uses_natural_numeric_order(tmp_path):
    for n in [10, 2, 1]:
        (tmp_path / f"volume{n}.txt").write_text(f"{n}\n")
    assert split.read_input_text(tmp_path) == "1\n2\n10\n"


def test_extract_preserves_text_and_validates_entire_batch(tmp_path):
    source = tmp_path / "raw.md"
    source.write_text("首行\n甲  乙\n末行\n")
    output = tmp_path / "scenes"
    with pytest.raises(ValueError):
        extract.extract(source, output, [dict(scene_id="S1", start=1, end=2), dict(scene_id="S2", start=3, end=4)])
    assert not output.exists()
    paths = extract.extract(source, output, [dict(scene_id="S1", start=2, end=3)])
    assert paths[0].read_text().split("-->\n\n", 1)[1] == "甲  乙\n末行\n"


def test_visibility_uses_manifest_not_scene_rank_or_title_number(tmp_path):
    entries = []
    for seq, title in enumerate(["序章", "第1章", "第2章", "第3章"], 1):
        name = f"V01C{seq:04}.md"
        (tmp_path / name).write_text(f"# {title}\n正文\n")
        entries.append(dict(chapter_id=f"C{seq:04}", file=name, published_seq=seq))
    index = [
        dict(scene_id="past", source_chapters=["C0001"], published_seq=99, description="前史"),
        dict(scene_id="legacy", source_chapter="第2章", published_seq=1, description="未来秘密"),
        dict(scene_id="span", source_chapters=["C0001", "C0003"], description="跨章后文"),
        dict(scene_id="unknown", published_seq=1, description="来源不明"),
        dict(scene_id="bad-id", source_chapters=["C0999"], source_chapter="第1章", description="错误映射"),
    ]
    visible, skipped = query.select(index, {"entries": entries}, tmp_path, 2)
    assert [s["scene_id"] for s in visible] == ["past"]
    assert visible[0]["published_seq"] == 1
    assert skipped == 2
    visible, _ = query.select(index, {"entries": entries}, tmp_path, 3)
    assert [s["scene_id"] for s in visible] == ["past", "legacy", "span"]
    assert visible[1]["published_seq"] == 3


def test_ambiguous_legacy_title_is_not_disclosed(tmp_path):
    entries = []
    for seq in [1, 2]:
        name = f"C{seq:04}.md"
        (tmp_path / name).write_text("第1章\n各卷重编号\n")
        entries.append(dict(chapter_id=f"C{seq:04}", file=name, published_seq=seq))
    result, skipped = query.select([dict(source_chapter="第1章", description="秘密")], {"entries": entries}, tmp_path, 2)
    assert result == [] and skipped == 1


@pytest.mark.parametrize("cutoff", [-1, 3])
def test_cutoff_must_be_in_registered_range(tmp_path, cutoff):
    with pytest.raises(ValueError):
        query.select([], {"entries": [dict(chapter_id="C0001", file="x.md", published_seq=1)]}, tmp_path, cutoff)


def test_export_and_import_reject_volume_mismatch(tmp_path):
    import yaml
    exporter = load("export_gate")
    other = SCRIPTS.parents[1] / "MUSE-serial-writing/scripts/import_series.py"
    spec = importlib.util.spec_from_file_location("import_series", other)
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    (tmp_path / "published").mkdir()
    (tmp_path / "series/volumes").mkdir(parents=True)
    (tmp_path / "published/V02C0003.md").write_text("第2章\n仍属于第一卷\n")
    (tmp_path / "published/manifest.yaml").write_text(yaml.safe_dump(dict(entries=[dict(chapter_id="C0003", file="V02C0003.md")])))
    volume = tmp_path / "series/volumes/V01.yaml"
    volume.write_text(yaml.safe_dump(dict(volume_id="V01", chapters=[dict(chapter_id="C0003")])))
    assert exporter.check_manifest_match(tmp_path)
    with pytest.raises(importer.UsageError):
        importer.check_manifest_published_consistency(tmp_path)
    (tmp_path / "published/V02C0003.md").rename(tmp_path / "published/V01C0003.md")
    (tmp_path / "published/manifest.yaml").write_text(yaml.safe_dump(dict(entries=[dict(chapter_id="C0003", file="V01C0003.md")])))
    assert exporter.check_manifest_match(tmp_path) == []
    importer.check_manifest_published_consistency(tmp_path)


def test_actual_sequences_allow_gaps_and_nonordered_entries(tmp_path):
    (tmp_path / "V01C0009.md").write_text("编辑前言\n\n# 第1章\n已有事实\n")
    (tmp_path / "V02C0003.md").write_text("第2章\n后来的秘密\n")
    manifest = dict(entries=[dict(chapter_id="C0003", file="V02C0003.md", published_seq=30), dict(chapter_id="C0009", file="V01C0009.md", published_seq=10)])
    index = [dict(scene_id="future", source_chapters=["C0003"]), dict(scene_id="past", source_chapter="第1章")]
    result, skipped = query.select(index, manifest, tmp_path, 10)
    assert [(r["scene_id"], r["published_seq"]) for r in result] == [("past", 10)]
    assert skipped == 0
