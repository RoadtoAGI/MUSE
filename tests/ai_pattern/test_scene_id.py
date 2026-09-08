import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"))

from ai_filler_lint import analyze


FIXTURE = "他怔了怔。\n\n她没说话。\n\n炭火噼了一声。\n\n" * 8


def test_scene_id_propagates_to_ids():
    result = analyze(FIXTURE, scene_id="S02")

    assert all(hit["lint_id"].startswith("S02-") for hit in result["hits"])
    assert all(alert["alert_id"].startswith("S02-") for alert in result["cluster_alerts"])


def test_default_scene_id_backcompat():
    result = analyze(FIXTURE)

    assert all(hit["lint_id"].startswith("S01-") for hit in result["hits"])
