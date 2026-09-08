import pathlib
import subprocess
import sys

import yaml

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"


def test_calibrate_baselines_outputs_language_family_percentiles(tmp_path):
    kb_root = tmp_path / "knowledge-base"
    scenes_a = kb_root / "novels" / "甲" / "scenes"
    scenes_b = kb_root / "novels" / "乙" / "scenes"
    scenes_a.mkdir(parents=True)
    scenes_b.mkdir(parents=True)
    sample = "他怔了怔。\n\n她没说话。\n\n炭火噼了一声。\n\n" * 8
    (scenes_a / "scene_S01.md").write_text(sample)
    (scenes_a / "scene_S02.md").write_text(sample * 2)
    # 观测型命中仍可进入描述统计；统计值自身不授予修订权限。
    (scenes_b / "scene_S03.md").write_text(
        "窗外雨声不断。祖父在檐下修伞。他探了一下手，碰到空的，收回来。他没抬头，只是修伞。" * 20
    )
    # _craft.md 旁注不是场景正文，不得进基线样本（含大量 markdown 标记会污染 marker_pollution）
    (scenes_a / "scene_S01_craft.md").write_text("# Craft Notes\n\n**Scene function:** test\n\n---\n" * 30)
    out = tmp_path / "calibration.yaml"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "calibrate_baselines.py"),
            "--kb-root",
            str(kb_root),
            "--out",
            str(out),
        ],
        check=True,
    )

    data = yaml.safe_load(out.read_text())
    assert "zh" in data
    assert "sentence_cv" in data["zh"]
    assert isinstance(data["zh"]["sentence_cv"]["p10"], float)
    assert isinstance(data["zh"]["sentence_cv"]["p50"], float)
    assert isinstance(data["zh"]["sentence_cv"]["p90"], float)
    assert data["zh"]["sentence_cv"]["samples"] == 3
    assert "micro_punchline_cadence" in data["zh"]
    assert isinstance(data["zh"]["micro_punchline_cadence"]["p80"], float)
    assert isinstance(data["zh"]["micro_punchline_cadence"]["p90"], float)
    # _craft.md 被排除：其英文 markdown 内容不得产生 en 段
    assert "en" not in data, "_craft.md 旁注混入了基线样本"
    assert "_split_results" not in data, "未声明 held-out 时应保持旧产物形态"
    assert data["zh"]["contrastive_negation_assertion"]["n_positive"] > 0


def test_calibration_includes_zero_scenes_dual_percentiles_and_provenance(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    import calibrate_baselines

    kb_root = tmp_path / "knowledge-base"
    train = kb_root / "novels" / "甲" / "scenes"
    held_out = kb_root / "novels" / "乙" / "scenes"
    train.mkdir(parents=True)
    held_out.mkdir(parents=True)
    (train / "scene_S01.md").write_text(("就在这时，他推门进来。" * 12), encoding="utf-8")
    (held_out / "scene_S02.md").write_text(
        "雨沿瓦沟落下，祖父把断裂的竹骨一根根换好。" * 12,
        encoding="utf-8",
    )

    data = calibrate_baselines.build_calibration(kb_root, held_out_works={"乙"})
    # 顶层校准值只由 train 作品产生，held-out 不得回流阈值。
    lexical = data["zh"]["lexical_cliche"]
    assert lexical["n_total"] == 1
    assert lexical["n_positive"] == 1
    assert lexical["prevalence"] == 1.0
    assert {"p80_all", "p90_all", "p80_positive", "p90_positive"} <= set(lexical)

    split_results = data["_split_results"]
    train_result = split_results["train"]
    held_out_result = split_results["held_out"]
    assert train_result["works"] == ["甲"]
    assert train_result["samples"] == ["novels/甲/scenes/scene_S01.md"]
    assert train_result["scene_count"] == 1
    assert len(train_result["corpus_sha256"]) == 64
    assert train_result["metrics"]["zh"]["lexical_cliche"]["n_total"] == 1
    assert train_result["metrics"]["zh"]["lexical_cliche"]["n_positive"] == 1

    assert held_out_result["works"] == ["乙"]
    assert held_out_result["samples"] == ["novels/乙/scenes/scene_S02.md"]
    assert held_out_result["scene_count"] == 1
    assert len(held_out_result["corpus_sha256"]) == 64
    held_out_lexical = held_out_result["metrics"]["zh"]["lexical_cliche"]
    assert held_out_lexical["n_total"] == 1
    assert held_out_lexical["n_positive"] == 0
    assert held_out_lexical["prevalence"] == 0.0

    provenance = data["_provenance"]
    assert len(provenance["corpus_sha256"]) == 64
    assert len(provenance["registry_sha256"]) == 64
    assert provenance["denominator_version"] == "chars-per-1k-v2"
    assert provenance["work_split"] == {"train": ["甲"], "held_out": ["乙"]}


def test_calibration_rejects_unknown_or_all_held_out_work(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    import calibrate_baselines

    kb_root = tmp_path / "knowledge-base"
    scenes = kb_root / "novels" / "甲" / "scenes"
    scenes.mkdir(parents=True)
    (scenes / "scene_S01.md").write_text("雨落在檐下。", encoding="utf-8")

    for held_out in ({"乙"}, {"甲"}):
        try:
            calibrate_baselines.build_calibration(kb_root, held_out_works=held_out)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid held-out split should fail: {held_out}")
