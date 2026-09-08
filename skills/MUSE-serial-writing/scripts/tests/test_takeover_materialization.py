"""A published-only takeover can prepare its next chapter without fabricated history workspaces."""
import importlib.util
from pathlib import Path
import sys
import yaml
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("materialize_chapter", SCRIPTS / "materialize_chapter.py")
materializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(materializer)


def put(root, rel, data):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def fixture(root):
    put(root, "series/story_bible.yaml", dict(frozen=dict(premise="渡船值守")))
    put(root, "series/volumes/V01.yaml", dict(volume_id="V01", chapters=[
        dict(chapter_id="C0001", status="published", unit="U01", logline="已停船等待气象记录", opened=[], closed=[]),
        dict(chapter_id="C0002", status="outline", unit="U01", logline="装配测试", opened=[], closed=[], hook_type="信息投放")]))
    put(root, "published/manifest.yaml", dict(entries=[dict(chapter_id="C0001", published_seq=1, file="V01C0001.md")]))
    (root / "published/V01C0001.md").write_text("# 第1章\n他们把船停在岸边，留下红旗。\n")


def test_published_only_previous_chapter_supplies_tail_and_summary(tmp_path):
    fixture(tmp_path)
    chapter = materializer.run(tmp_path, "V01", "C0002", SCRIPTS)
    assert "留下红旗" in (chapter / "pipeline/prev_chapter_tail.md").read_text()
    context = (chapter / "pipeline/serial_context.md").read_text()
    assert "接管卷纲摘要" in context and "已停船等待气象记录" in context
    assert not (tmp_path / "chapters/V01/C0001").exists()


def test_existing_incomplete_runtime_chapter_still_requires_recap(tmp_path):
    fixture(tmp_path)
    (tmp_path / "chapters/V01/C0001").mkdir(parents=True)
    with pytest.raises(materializer.BlockingError):
        materializer.run(tmp_path, "V01", "C0002", SCRIPTS)
    assert not (tmp_path / "chapters/V01/C0002").exists()
