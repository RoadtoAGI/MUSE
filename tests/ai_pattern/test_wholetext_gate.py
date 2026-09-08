import pathlib
import subprocess
import sys
import hashlib

import yaml

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "skills" / "MUSE-writing" / "scripts"


def _run_wholetext(tmp_path, text, lang):
    story = tmp_path / "story.md"
    story.write_text(text)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "wholetext_gate.py"),
            "--story",
            str(story),
            "--lang",
            lang,
            "--work-dir",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
    )
    report = yaml.safe_load((tmp_path / "pipeline/review/wholetext_gate.yaml").read_text())
    return result.returncode, report


def test_statistical_candidates_require_semantic_review(tmp_path):
    dirty = ("他怔了怔。\n\n她没说话。\n\n炭火噼了一声。\n\n不是恐惧，是认出来了。\n\n" * 30)

    rc, report = _run_wholetext(tmp_path, dirty, "zh")

    assert rc == 0
    assert report["verdict"] == "REVIEW"
    assert report["review_required"] is True
    assert not report["triggers"]
    observed = next(item for item in report["observations"] if item["type"] == "observe_hits")
    assert observed["hit_records"]
    assert all(hit.get("locator") or hit.get("location") for hit in observed["hit_records"])


def test_clean_text_passes(tmp_path):
    clean = (
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架，说这伞陪他走过的路比我认得的字还多。"
        * 20
    )

    rc, report = _run_wholetext(tmp_path, clean, "zh")

    assert rc == 0
    assert report["verdict"] == "PASS"


def test_density_contract_blocks_subseverity_hits_with_locators(tmp_path):
    """密度合同与 severity 解耦：短文本 2 处命中不到 severity high（count>=4），
    但密度已超名著基线 → density_contract trigger 必须阻断并逐 hit 给定位。
    守卫不变量：超基线命中必须以可定位形态到达 reviser（发牌端不可静默拆除）。"""
    clean = (
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架，说这伞陪他走过的路比我认得的字还多。"
        * 4
    )
    text = (
        "他把那东西收进柜底，沿着墙缝压住木门。"
        + clean
        + "她把这东西从布袋中取出，放在磨平的石桌上。"
    )

    rc, report = _run_wholetext(tmp_path, text, "zh")

    assert rc == 1
    assert report["verdict"] == "FAIL"
    trigger = next(
        t for t in report["triggers"]
        if t["type"] == "density_contract" and t["family"] == "dummy_pronoun"
    )
    # 不进 blocking_cluster（count 2 < high 门槛 4），密度合同是唯一拦截者
    assert not any(t["type"] == "blocking_cluster" for t in report["triggers"])
    assert trigger["count"] > trigger["max_count"]
    assert trigger["required_reduction"] == trigger["count"] - trigger["max_count"]
    assert trigger["baseline_per_1k"] == 1.42
    assert trigger["decision_ref"] == "pronoun-density-2026-07-17"
    assert all(record["locator"]["span"] for record in trigger["hit_records"])
    assert all(record["evidence_quote"] for record in trigger["hit_records"])


def test_density_contract_exact_budget_passes(tmp_path):
    """密度边界：count == max_count（密度严格 < 基线）→ 不触发合同。"""
    filler = "山道上无人，风把旗吹得笔直，远处的号角断断续续，驿卒把火盆拨旺。" * 46
    text = filler + "他把那东西塞回怀里。"
    assert len(text) > 1000 / 1.42  # 预算至少 1
    rc, report = _run_wholetext(tmp_path, text, "zh")

    assert rc == 0
    assert not any(t["type"] == "density_contract" for t in report["triggers"])
    assert report["verdict"] == "PASS"


def test_en_policy_is_report_only_including_dash_trigger(tmp_path):
    dirty = ("Not fear, but recognition — and then another aside. " * 40)

    rc, report = _run_wholetext(tmp_path, dirty, "en")

    assert rc == 0
    assert report["verdict"] == "REVIEW"
    assert report["whole_text"]["hits"] > 0 or report["whole_text"]["dash_per_1k"] > 5
    assert report["observations"], "en observe hits/dash should remain visible"
    assert report["input_story_sha256"] == hashlib.sha256(dirty.encode("utf-8")).hexdigest()


def test_family_by_scene_uniform_low_dose_is_audit_only(tmp_path):
    lint_dir = tmp_path / "pipeline" / "review" / "lint"
    scene_dir = tmp_path / "pipeline" / "scenes"
    lint_dir.mkdir(parents=True)
    scene_dir.mkdir(parents=True)
    for scene_id, char in (("S01", "甲"), ("S02", "乙")):
        text = char * 10_000
        (scene_dir / f"scene_{scene_id}.md").write_text(text, encoding="utf-8")
        (lint_dir / f"{scene_id}.ai_filler.yaml").write_text(
            yaml.safe_dump({
                "language": "zh",
                "input_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "hits": [{
                    "lint_id": f"{scene_id}-action-1",
                    "family": "action_log",
                    "rule": "micro_action_density",
                }],
                "cluster_alerts": [],
            }),
            encoding="utf-8",
        )

    story = (
        "窗外的雨下了整夜，把青石板路洗出一层暗光。祖父坐在檐下修旧伞，"
        "三根竹骨断在同一侧，他不肯换新的伞架。" * 20
    )
    rc, report = _run_wholetext(tmp_path, story, "zh")

    assert rc == 0
    assert report["verdict"] == "REVIEW"
    matrix = report["family_scene_matrix"]
    assert matrix["audit_only"] is True
    assert matrix["provenance_state"] == "fresh"
    assert matrix["families"]["action_log"]["uniform_low_dose"] is True
    signal = next(
        item for item in report["observations"]
        if item.get("kind") == "uniform_low_dose_distribution"
    )
    assert signal["blocking"] is False


def test_family_scene_matrix_uses_directive_bound_lint_revision(tmp_path):
    lint_dir = tmp_path / "pipeline/review/lint"
    review_dir = tmp_path / "pipeline/review"
    scene_dir = tmp_path / "pipeline/scenes"
    lint_dir.mkdir(parents=True)
    scene_dir.mkdir(parents=True)
    text = "甲" * 10_000
    (scene_dir / "scene_S01.md").write_text(text, encoding="utf-8")
    active = lint_dir / "S01.ai_filler.yaml"
    active.write_text(yaml.safe_dump({
        "language": "zh",
        "hits": [{"lint_id": "a1", "family": "action_log", "rule": "micro_action_density"}],
        "cluster_alerts": [],
    }), encoding="utf-8")
    (lint_dir / "S01.ai_filler.dist9.yaml").write_text(yaml.safe_dump({
        "language": "zh",
        "hits": [{"lint_id": "d1", "family": "dash_overuse", "rule": "dash_density"}],
        "cluster_alerts": [],
    }), encoding="utf-8")
    (review_dir / "S01.machine_directive.yaml").write_text(yaml.safe_dump({
        "scene_id": "S01",
        "lint_revision": {"artifact": "pipeline/review/lint/S01.ai_filler.yaml"},
        "entries": [],
    }), encoding="utf-8")

    story = "窗外的雨落在青石板上，祖父坐在檐下修旧伞。" * 50
    rc, report = _run_wholetext(tmp_path, story, "zh")

    assert rc == 0
    assert "action_log" in report["family_scene_matrix"]["families"]
    assert "dash_overuse" not in report["family_scene_matrix"]["families"]


def test_dialogue_dashes_exempt_from_density_matching_scene_layer(tmp_path):
    """对白内破折号不计入全文密度——与 scene 层 detect_dash_density 同语义。

    背景：dash_overuse 在 scene 层豁免引号内（对白打断/结巴是合法戏剧手法），
    wholetext 曾直接 text.count("——") 不豁免 → 同一 family 两套口径（跨消费者漂移）。
    实证：367 source 40 处里 12 处在对白内，把 5.38 虚推到 7.68；名著斯通纳 65%
    破折号在对白（全文口径 3.79 vs 叙述层 1.33）。
    """
    filler = "他把绢帛叠进护心镜后头的夹层，转身登上望楼。风把鬓边白发往北面吹。" * 6
    # 叙述层 0 处、对白内 6 处 —— 全部合法，密度应为 0
    dialogue_only = filler + "“我说——你听着，这事——不能这么办。”" * 3
    _, report = _run_wholetext(tmp_path, dialogue_only, "zh")
    assert report["whole_text"]["dash_per_1k"] == 0.0, "对白内破折号必须豁免"
    assert not [t for t in report["triggers"] if t["type"] == "dash_per_1k"]


def test_narration_dashes_still_counted_and_carry_locators(tmp_path):
    """叙述层统计带真实定位，供既有语义审阅判断作用。"""
    unit = "他数到第九十六面的时候停了手——不必再数下去。风向记进心里那本账。"
    story = unit * 12
    _, report = _run_wholetext(tmp_path, story, "zh")

    dash_trigger = next(t for t in report["observations"] if t["type"] == "dash_per_1k_observe")
    assert dash_trigger["value"] > dash_trigger["threshold"]
    assert len(dash_trigger["locators"]) == 12, "每处叙述层破折号都要可定位"
    first = dash_trigger["locators"][0]
    assert {"start", "end", "context"} <= set(first)
    assert story[first["start"]:first["end"]] == "——", "locator 偏移必须指向原文"
    assert first["context"], "context 供 reviser 判断手艺功能"


def test_observed_cluster_keeps_original_locators():
    from wholetext_gate import build_report

    unit = "他站住，没动，风停了。太阳挺好，风也不大，天很静。"
    report = build_report(unit * 10, "zh")
    assert report["verdict"] == "REVIEW"
    assert not report["triggers"]
    alert = report["observed_alerts"][0]
    assert alert["hit_records"]
    rec = alert["hit_records"][0]
    assert {"start", "end", "span"} <= set(rec["locator"])


def test_directive_uses_current_density_budget_instead_of_cluster_severity(tmp_path):
    import ai_filler_lint
    from family_gate import evaluate_regression
    from machine_directive import build_directive

    scene = tmp_path / "pipeline/scenes/scene_S01.md"
    lint_path = tmp_path / "pipeline/review/lint/S01.ai_filler.yaml"
    scene.parent.mkdir(parents=True)
    lint_path.parent.mkdir(parents=True)
    text = "他把那东西收进柜底。" * 4 + "山道上无人，驿卒把火盆拨旺。" * 300
    scene.write_text(text)
    lint = ai_filler_lint.analyze(text, scene_id="S01", lang="zh")
    measured = [hit for hit in lint["hits"] if hit.get("family") == "dummy_pronoun"]
    assert len(measured) == 4
    # A retained legacy severity label cannot strengthen the current contract.
    lint["cluster_alerts"] = [{"family": "dummy_pronoun", "severity": "high",
        "alert_id": "S01-dummy-legacy", "hit_ids": [hit["lint_id"] for hit in measured], "hits": 4}]
    lint_path.write_text(yaml.safe_dump(lint, allow_unicode=True))
    directive, ledger = build_directive(tmp_path, "S01")
    assert directive["entries"] == []
    assert any(entry["family"] == "dummy_pronoun" and entry["status"] == "observed"
               for entry in ledger["entries"])
    unchanged = evaluate_regression(lint, lint, {"dummy_pronoun"}, lang="zh")
    assert unchanged["verdict"] == "PASS"
    assert unchanged["families"]["dummy_pronoun"]["decision"] == "target_contract_satisfied"

    # A short over-budget text must arrive as a current, locatable repair even
    # when its count has not reached the old severity-high threshold.
    text = "他把那东西收进柜底。" * 2
    scene.write_text(text)
    lint = ai_filler_lint.analyze(text, scene_id="S01", lang="zh")
    lint_path.write_text(yaml.safe_dump(lint, allow_unicode=True))
    directive, _ = build_directive(tmp_path, "S01")
    entry = next(entry for entry in directive["entries"] if entry["family"] == "dummy_pronoun")
    assert len(entry["all_hit_ids"]) == 2
    assert entry["status"] == "pending"
    assert all(record.get("locator") and record.get("evidence_quote") for record in entry["hit_records"])
