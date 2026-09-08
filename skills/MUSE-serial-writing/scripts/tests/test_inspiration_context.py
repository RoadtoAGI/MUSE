"""Exercise chapter-bound inspiration at the actual scene-card consumer."""
from pathlib import Path
import subprocess
import sys

import yaml

SCRIPTS = Path(__file__).resolve().parents[1]


def _put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_shared_ledger_cannot_borrow_another_chapters_same_scene_id(tmp_path):
    _put(tmp_path, "chapter_card.yaml", {"chapter_id": "C0002"})
    scene = dict(scene_id="S01", arc_id="A01", title="渡口", pov="许禾", narration_style="limited",
                 participants=["xu-he"], location_time="渡口清晨", conflict="返航与雾封",
                 value_start="可离开", value_end="须留宿", scene_tasks=["雾封使末班船停航"],
                 handoff="共同等到天明", inspiration_refs=["INS-001"], prose_risk_contract={"used": False})
    _put(tmp_path, "pipeline/phase5_scenes.yaml", {"scenes": [scene]})
    encoding = dict(phase=5, chapter_id="C0001", scene_id="S01", adoption_kind="scene_carrier",
                    carrier="雾封导致停航，船主无权破例")
    ledger = {"inspirations": [dict(id="INS-001", type="pattern", status="accepted", project_encoding=[encoding])]}
    shared = _put(tmp_path, "series-ledger.yaml", ledger)
    (tmp_path / "pipeline/inspiration_ledger.yaml").symlink_to(shared)
    command = [sys.executable, str(SCRIPTS / "extract_scene_card.py"), "--work-dir", str(tmp_path), "--scene-id", "S01"]
    output = tmp_path / "pipeline/scene_S01/scene_card.md"
    bad = subprocess.run(command, capture_output=True, text=True)
    assert bad.returncode != 0 and not output.exists()
    assert "chapter_id=C0002" in bad.stderr
    encoding["chapter_id"] = "C0002"
    _put(tmp_path, "series-ledger.yaml", ledger)
    good = subprocess.run(command, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert "INS-001" in output.read_text()
    accepted = output.read_bytes()
    shared.unlink()
    missing = subprocess.run(command, capture_output=True, text=True)
    assert missing.returncode != 0 and output.read_bytes() == accepted
