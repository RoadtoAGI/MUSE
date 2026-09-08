import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"))

from ai_filler_lint import analyze


NAKED = "她推门进去。\n\n炭火噼了一声。\n\n她只知道，南边有路。\n\n" * 10


def test_unknown_device_warns_not_fails(capsys):
    result = analyze(NAKED, devices=("no_such_device",))
    captured = capsys.readouterr()

    assert result["device_budget_applied"] is False
    assert "no_such_device" in captured.err
