"""Reject an import destination inside its source before creating any workspace."""
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("layout", ["nested", "same", "symlink"])
def test_recursive_import_is_rejected_without_creating_destination(tmp_path, layout):
    source = tmp_path / "export"
    source.mkdir()
    marker = source / "source.txt"
    marker.write_text("existing source")
    if layout == "same":
        destination = source
    elif layout == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(source, target_is_directory=True)
        destination = alias / "works"
    else:
        destination = source / "works"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "import_series.py"),
         "--from", str(source), "--works-root", str(destination)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "递归复制自身" in result.stderr
    assert list(source.iterdir()) == [marker]
    assert marker.read_text() == "existing source"
