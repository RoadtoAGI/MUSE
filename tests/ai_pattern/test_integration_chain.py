import pathlib
import subprocess
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"))

from ai_filler_lint import analyze


SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"


def test_referential_contract_detector_to_directive_chain(tmp_path):
    scene_id = "S03"
    dirty = "它伏在门边。它随风晃动。他把那东西收了起来。\n\n" * 16
    lint = {"scene_id": scene_id, **analyze(dirty, scene_id=scene_id, lang="zh")}
    lint_dir = tmp_path / "pipeline" / "review" / "lint"
    lint_dir.mkdir(parents=True)
    scenes_dir = tmp_path / "pipeline" / "scenes"
    scenes_dir.mkdir(parents=True)
    (scenes_dir / f"scene_{scene_id}.md").write_text(dirty, encoding="utf-8")
    before_path = lint_dir / f"{scene_id}.ai_filler.yaml"
    before_path.write_text(yaml.safe_dump(lint, allow_unicode=True, sort_keys=False))

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(tmp_path),
            "--scene-id",
            scene_id,
        ],
        check=True,
    )
    directive_path = tmp_path / "pipeline" / "review" / f"{scene_id}.machine_directive.yaml"
    directive = yaml.safe_load(directive_path.read_text())
    assert directive["entries"]
    assert all(entry["id"].startswith(f"{scene_id}-") for entry in directive["entries"])

    scene_dir = tmp_path / "pipeline" / f"scene_{scene_id}"
    scene_dir.mkdir(parents=True)
    (scene_dir / "revision_summary.md").write_text(
        "status: complete\n\n"
        "1. **[patch 1 · issue_id A-7 · applied]** L12\n"
        "   - preserve: 克制对白\n"
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "machine_directive.py"),
            "--work-dir",
            str(tmp_path),
            "--scene-id",
            scene_id,
            "--refresh",
            "--lint-artifact",
            str(before_path),
        ],
        check=True,
    )
    refreshed = yaml.safe_load(directive_path.read_text())
    assert refreshed["dispatch_ready"] is True

    after_path = lint_dir / f"{scene_id}.ai_filler.v2.yaml"
    clean = "祖父修好了断裂的竹骨，把旧伞放在门边。"
    after_path.write_text(yaml.safe_dump(analyze(clean, scene_id=scene_id, lang="zh"), allow_unicode=True))
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "family_gate.py"),
            "--before",
            str(before_path),
            "--after",
            str(after_path),
        ],
        check=True,
    )

    clean_story = tmp_path / "story.md"
    clean_story.write_text(
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架，说这伞陪他走过的路比我认得的字还多。"
        * 20
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "wholetext_gate.py"),
            "--story",
            str(clean_story),
            "--lang",
            "zh",
            "--work-dir",
            str(tmp_path),
        ],
        check=True,
    )
