"""共享参考检查只覆盖约定的维护副本，不扩大为运行时跨包依赖。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import package_lint


def write_pair(root, writing_text="shared", serial_text="shared"):
    for package, text in (("MUSE-writing", writing_text), ("MUSE-serial-writing", serial_text)):
        path = root / "skills" / package / "skills" / "craft/reference.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_shared_reference_divergence_and_missing_peer(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(package_lint, "SHARED_REFERENCE_PAIRS", (("craft/reference.md", "craft/reference.md"),))
    write_pair(tmp_path)
    assert package_lint.scan_shared_references(tmp_path) == 0
    write_pair(tmp_path, serial_text="different decision")
    assert package_lint.scan_shared_references(tmp_path) == 1
    assert "共享参考分歧" in capsys.readouterr().err
    (tmp_path / "skills/MUSE-serial-writing/skills/craft/reference.md").unlink()
    assert package_lint.scan_shared_references(tmp_path) == 1
    assert "共享参考缺件" in capsys.readouterr().err


def test_single_package_does_not_require_peer(tmp_path):
    (tmp_path / "skills/MUSE-writing/skills").mkdir(parents=True)
    assert package_lint.scan_shared_references(tmp_path) == 0


def test_observed_case_source_is_not_a_development_instruction():
    source = "来源：Query 183 / query_183 / writing-bench 183 的实际作品观察。"
    assert not any(pattern.search(source) for pattern, _ in package_lint.PROTOCOL_NOTE_PATTERNS)
    task = "待验证用例：Query 183"
    assert any(pattern.search(task) for pattern, _ in package_lint.PROTOCOL_NOTE_PATTERNS)
