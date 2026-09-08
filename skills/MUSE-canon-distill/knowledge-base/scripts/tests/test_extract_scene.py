import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extract_scene import extract


def test_preserves_original_text_and_line_range(tmp_path):
    source = tmp_path / "full_text.md"
    source.write_text("第一行\n  原文缩进\n\n最后\n")
    paths = extract(source, tmp_path / "scenes", [{"scene_id": "A1S1", "start": 2, "end": 3}])
    assert paths[0].name == "scene_A1S1.md"
    assert paths[0].read_text().endswith("  原文缩进\n\n")
    assert "2-3" in paths[0].read_text()


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1), (1, 9)])
def test_invalid_batch_preserves_existing_outputs(tmp_path, start, end):
    source = tmp_path / "full_text.md"
    source.write_text("一\n二\n")
    out = tmp_path / "scenes"
    out.mkdir()
    old = out / "scene_S01.md"
    old.write_text("旧文件")
    with pytest.raises(ValueError):
        extract(source, out, [{"scene_id": "S01", "start": 1, "end": 1}, {"scene_id": "S02", "start": start, "end": end}])
    assert old.read_text() == "旧文件"
    assert not (out / "scene_S02.md").exists()


def test_cli_out_of_range_is_failure(tmp_path):
    source = tmp_path / "full_text.md"
    source.write_text("一\n")
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "extract_scene.py"), "--source", str(source), "--output-dir", str(tmp_path / "out"), "--scene-id", "S01", "--start", "1", "--end", "8"], capture_output=True, text=True)
    assert result.returncode == 1
    assert not (tmp_path / "out").exists()
