from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest
import yaml


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
rc = importlib.import_module("rhetoric_cards")


def _make_kb(tmp_path: Path, text: str, *, container: str = "novels", work: str = "测试作品") -> Path:
    kb = tmp_path / "knowledge-base"
    work_dir = kb / container / work
    work_dir.mkdir(parents=True)
    (work_dir / "full_text.md").write_text(text, encoding="utf-8")
    return kb


def _prepare(
    kb: Path,
    *,
    container: str = "novels",
    work: str = "测试作品",
    body_start: int = 1,
    body_end: int | None = None,
    figure_scope: list[str] | None = None,
    chunk_lines: int = 2,
    chunk_chars: int = 8000,
    scope_file: Path | None = None,
) -> dict:
    source = kb / container / work / "full_text.md"
    line_count = len(source.read_text(encoding="utf-8").splitlines())
    return rc.prepare_package(
        kb,
        container=container,
        work=work,
        source="full_text.md",
        body_start=body_start,
        body_end=body_end or line_count,
        figure_scope=figure_scope or ["comparison"],
        chunk_lines=chunk_lines,
        chunk_chars=chunk_chars,
        edition_id="test-edition",
        scope_file=scope_file,
    )


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_scope_manifest(
    tmp_path: Path,
    kb: Path,
    *,
    container: str = "novels",
    work: str = "测试作品",
    source: str = "full_text.md",
    body_start: int,
    body_end: int,
) -> Path:
    source_path = kb / container / work / source
    path = kb / "rhetoric" / "rhetoric-corpus-scope.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "status": "frozen",
                "corpus": [
                    {
                        "container": container,
                        "work": work,
                        "source_file": source,
                        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                        "start_line": body_start,
                        "end_line": body_end,
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _write_scope_entries(kb: Path, entries: list[dict], *, name: str = "scope.yaml") -> Path:
    path = kb / "rhetoric" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"version": 1, "status": "frozen", "corpus": entries},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _scope_entry(kb: Path, work: str, *, start_line: int, end_line: int) -> dict:
    source = kb / "novels" / work / "full_text.md"
    return {
        "container": "novels",
        "work": work,
        "source_file": "full_text.md",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "start_line": start_line,
        "end_line": end_line,
    }


def _candidate(task: dict, *, figure_type: str = "simile", quote: str | None = None) -> dict:
    value = {
        "source_locator": task["source_locator"],
        "chapter": task["chapter"],
        "figure_type": figure_type,
        "quote": quote or task["text"].strip(),
        "sensory_mapping": "把抽象压迫转成可见的坠落和摊平",
        "context_fact": "对象正在失去厚度并铺展到平面",
        "image_mechanism": "借熟悉物态变化呈现陌生空间变化",
        "property_alignment": "两者都由立体形态变为扁平铺展",
        "context_alignment": "物理过程与现场观察顺序一致",
        "narrative_function": "让尺度变化获得瞬时可视性",
        "transfer_rule": "写陌生过程时选取变化路径同构的日常物",
        "failure_boundary": "只共享颜色或气氛、变化路径不同时失效",
        "quality_assessment": "exemplary",
        "confidence": 0.96,
        "review_status": "source_checked",
    }
    if figure_type in rc.COMPARISON_FIGURES:
        value.update(
            {
                "tenor": "失去厚度的物体",
                "vehicle": "玻璃板上融化的冰淇淋",
                "ground": "由立体坍成贴面扩散形态",
            }
        )
    else:
        value["device_elements"] = {"semantic_shift": "把物体写成有意志的行动者"}
    return value


def _output_for(package: dict, task_path: Path, *, include_first: bool = False) -> dict:
    explicit_results = []
    for index, task in enumerate(package["explicit_tasks"]):
        if index == 0 and include_first:
            explicit_results.append(
                {
                    "task_id": task["task_id"],
                    "disposition": "include",
                    "occurrences": [_candidate(task)],
                }
            )
        else:
            explicit_results.append(
                {
                    "task_id": task["task_id"],
                    "disposition": "exclude",
                    "reason": "语法比较或与 scope 无关",
                    "occurrences": [],
                }
            )
    return {
        "schema_version": "rhetoric-agent-output/v1",
        "task_package_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
        "explicit_results": explicit_results,
        "semantic_results": [
            {"task_id": task["task_id"], "reviewed": True, "discoveries": []}
            for task in package["semantic_tasks"]
        ],
    }


def _ingest_complete(tmp_path: Path) -> tuple[Path, dict, Path]:
    kb = _make_kb(
        tmp_path,
        "前言\n第一部\n探测艇跌落时，像玻璃板上融化的冰淇淋。\n余波散去。\n",
    )
    scope_file = _write_scope_manifest(tmp_path, kb, body_start=2, body_end=4)
    package = _prepare(kb, body_start=2, body_end=4, scope_file=scope_file)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    _write_json(output_path, _output_for(package, task_path, include_first=True))
    coverage = rc.ingest_files(task_path, output_path, kb_root=kb)
    return kb, coverage, kb / "novels" / "测试作品"


def test_prepare_chunks_cover_body_without_gap_or_overlap_and_ids_are_stable(tmp_path):
    kb = _make_kb(
        tmp_path,
        "前言\n第一部\n甲。\n乙。\n第二部\n丙。\n丁。\n",
    )

    first = _prepare(kb, body_start=2, body_end=7, chunk_lines=2)
    second = _prepare(kb, body_start=2, body_end=7, chunk_lines=2)

    ranges = [(item["start_line"], item["end_line"]) for item in first["semantic_tasks"]]
    assert ranges == [(2, 3), (4, 4), (5, 6), (7, 7)]
    assert [line for start, end in ranges for line in range(start, end + 1)] == list(range(2, 8))
    assert [item["chapter"] for item in first["semantic_tasks"]] == [
        "第一部",
        "第一部",
        "第二部",
        "第二部",
    ]
    assert [item["task_id"] for item in first["semantic_tasks"]] == [
        item["task_id"] for item in second["semantic_tasks"]
    ]


def test_prepare_semantic_chunks_honor_line_and_character_budgets(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n甲乙丙\n丁戊己\n庚辛壬\n")

    package = _prepare(kb, body_end=4, chunk_lines=50, chunk_chars=7)

    ranges = [
        (task["start_line"], task["end_line"])
        for task in package["semantic_tasks"]
    ]
    assert [line for start, end in ranges for line in range(start, end + 1)] == [1, 2, 3, 4]
    assert all(len(task["text"]) <= 7 for task in package["semantic_tasks"])
    assert package["chunk_chars"] == 7


def test_slice_task_package_respects_character_and_task_budgets(tmp_path):
    kb = _make_kb(
        tmp_path,
        "第一部\n云像船。\n灯仿佛醒了。\n山如同墙。\n水犹如镜。\n星宛如针。\n",
    )
    package = _prepare(kb, body_end=6, chunk_lines=1)
    task_path = tmp_path / "parent-tasks.json"
    shard_dir = tmp_path / "task-shards"
    _write_json(task_path, package)
    all_tasks = package["explicit_tasks"] + package["semantic_tasks"]
    largest_task = max(
        len(json.dumps(task, ensure_ascii=False, separators=(",", ":")))
        for task in all_tasks
    )

    manifest = rc.slice_task_package(
        task_path,
        shard_dir,
        kb_root=kb,
        max_chars=largest_task + 10,
        max_tasks=2,
    )

    parent_digest = hashlib.sha256(task_path.read_bytes()).hexdigest()
    assert manifest["parent_task_package_sha256"] == parent_digest
    assert len(manifest["shards"]) > 1
    seen: list[str] = []
    for shard_meta in manifest["shards"]:
        shard = json.loads((shard_dir / shard_meta["file"]).read_text(encoding="utf-8"))
        tasks = shard["explicit_tasks"] + shard["semantic_tasks"]
        assert shard["schema_version"] == "rhetoric-task-shard/v1"
        assert shard["parent_task_package_sha256"] == parent_digest
        assert shard["output_contract"]["task_package_sha256"] == parent_digest
        assert shard["task_count"] <= 2
        assert shard["task_payload_chars"] <= largest_task + 10
        seen.extend(task["task_id"] for task in tasks)
    expected = [task["task_id"] for task in all_tasks]
    assert sorted(seen) == sorted(expected)
    assert len(seen) == len(set(seen))


def test_prepare_explicit_cue_scan_recalls_all_supported_comparison_forms(tmp_path):
    lines = [
        "第一部",
        "云像船。",
        "灯仿佛醒了。",
        "山如同墙。",
        "水犹如镜。",
        "星宛如针。",
        "风好似刀。",
        "火似蛇般游走。",
        "人群潮水一般涌来。",
        "两份结果完全一样。",
        "远山似被漫长雨季反复冲刷又被暮色层层压低还被尘埃覆盖并在仓库角落遗忘多年的旧纸屏风般伏着。",
    ]
    kb = _make_kb(tmp_path, "\n".join(lines) + "\n")

    package = _prepare(kb, body_end=len(lines), chunk_lines=50)

    assert [task["cue_line"] for task in package["explicit_tasks"]] == list(range(2, 12))
    assert all(task["cue_terms"] for task in package["explicit_tasks"])


def test_all_scope_covers_supported_noncomparison_figures():
    scope = set(rc.expand_figure_scope(["all"]))

    assert {
        "rhetorical_question",
        "apostrophe",
        "allusion",
        "euphemism",
        "paradox",
        "oxymoron",
        "gradation",
        "synecdoche",
    }.issubset(scope)
    assert scope == set(rc.FIGURE_TYPES)


def test_three_body_scope_is_the_exact_frozen_trilogy_subset():
    rhetoric_dir = Path(rc.__file__).resolve().parents[1] / "rhetoric"
    inventory = yaml.safe_load(
        (rhetoric_dir / "corpus_scope.yaml").read_text(encoding="utf-8")
    )
    trilogy = yaml.safe_load(
        (rhetoric_dir / "three_body_scope.yaml").read_text(encoding="utf-8")
    )

    assert trilogy["status"] == "frozen"
    assert trilogy["corpus"] == inventory["corpus"][:3]
    assert [entry["work"] for entry in trilogy["corpus"]] == [
        "三体Ⅰ-地球往事",
        "三体Ⅱ-黑暗森林",
        "三体Ⅲ-死神永生",
    ]


def test_scope_manifest_binds_complete_status_and_verify_detects_manifest_change(tmp_path):
    kb = _make_kb(tmp_path, "前言\n第一部\n云像船。\n")
    scope_file = _write_scope_manifest(tmp_path, kb, body_start=2, body_end=3)
    package = _prepare(kb, body_start=2, body_end=3, scope_file=scope_file)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    _write_json(output_path, _output_for(package, task_path))

    coverage = rc.ingest_files(task_path, output_path, kb_root=kb)

    assert coverage["status"] == "complete"
    assert coverage["scope_file"] == "rhetoric/rhetoric-corpus-scope.yaml"
    assert coverage["scope_file_sha256"] == hashlib.sha256(scope_file.read_bytes()).hexdigest()
    assert coverage["scope_entry"]["start_line"] == 2
    assert rc.verify_work(kb, "novels", "测试作品") == []

    scope = yaml.safe_load(scope_file.read_text(encoding="utf-8"))
    scope["corpus"][0]["scope_note"] = "manifest changed after ingest"
    scope_file.write_text(
        yaml.safe_dump(scope, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    errors = rc.verify_work(kb, "novels", "测试作品")

    assert any("scope manifest checksum mismatch" in error for error in errors)


def test_prepare_rejects_scope_manifest_boundary_mismatch(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    scope_file = _write_scope_manifest(tmp_path, kb, body_start=1, body_end=1)

    with pytest.raises(rc.RhetoricError, match="scope manifest.*boundary"):
        _prepare(kb, body_start=1, body_end=2, scope_file=scope_file)


def test_global_verify_rejects_empty_enrollment(tmp_path):
    kb = tmp_path / "knowledge-base"
    (kb / "novels").mkdir(parents=True)

    errors = rc.verify_all(kb)

    assert any("requires --scope-file" in error for error in errors)


def test_scoped_verify_and_index_are_driven_by_every_manifest_entry(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n", work="作品甲")
    second_dir = kb / "novels" / "作品乙"
    second_dir.mkdir(parents=True)
    (second_dir / "full_text.md").write_text("第一部\n灯仿佛醒了。\n", encoding="utf-8")
    scope_file = _write_scope_entries(
        kb,
        [
            _scope_entry(kb, "作品甲", start_line=1, end_line=2),
            _scope_entry(kb, "作品乙", start_line=1, end_line=2),
        ],
        name="two-work-scope.yaml",
    )

    first_package = _prepare(
        kb,
        work="作品甲",
        body_end=2,
        scope_file=scope_file,
    )
    first_tasks = tmp_path / "first-tasks.json"
    first_output = tmp_path / "first-output.json"
    _write_json(first_tasks, first_package)
    _write_json(first_output, _output_for(first_package, first_tasks))
    rc.ingest_files(first_tasks, first_output, kb_root=kb)

    errors = rc.verify_all(kb, scope_file=scope_file)
    assert any("作品乙" in error and "missing coverage.yaml" in error for error in errors)
    with pytest.raises(rc.RhetoricError, match="作品乙.*missing coverage.yaml"):
        rc.rebuild_global_index(kb, scope_file=scope_file)

    second_package = _prepare(
        kb,
        work="作品乙",
        body_end=2,
        scope_file=scope_file,
    )
    second_tasks = tmp_path / "second-tasks.json"
    second_output = tmp_path / "second-output.json"
    _write_json(second_tasks, second_package)
    _write_json(second_output, _output_for(second_package, second_tasks))
    rc.ingest_files(second_tasks, second_output, kb_root=kb)

    assert rc.verify_all(kb, scope_file=scope_file) == []
    index = rc.rebuild_global_index(kb, scope_file=scope_file)
    assert index["scope_status"] == "complete"
    assert index["scope_file"] == "rhetoric/two-work-scope.yaml"
    assert index["scope_file_sha256"] == hashlib.sha256(scope_file.read_bytes()).hexdigest()
    assert index["enrolled_work_ids"] == ["novel:作品甲", "novel:作品乙"]


def test_scoped_verify_rejects_coverage_bound_to_another_manifest(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    first_scope = _write_scope_entries(
        kb,
        [_scope_entry(kb, "测试作品", start_line=1, end_line=2)],
        name="first-scope.yaml",
    )
    second_scope = _write_scope_entries(
        kb,
        [_scope_entry(kb, "测试作品", start_line=1, end_line=2)],
        name="second-scope.yaml",
    )
    package = _prepare(kb, body_end=2, scope_file=first_scope)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    _write_json(output_path, _output_for(package, task_path))
    rc.ingest_files(task_path, output_path, kb_root=kb)

    errors = rc.verify_all(kb, scope_file=second_scope)

    assert any("scope manifest locator mismatch" in error for error in errors)


def test_explicit_false_positive_can_be_excluded_without_losing_completeness(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n两份结果完全一样。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    _write_json(output_path, _output_for(package, task_path))

    coverage = rc.ingest_files(task_path, output_path, kb_root=kb)

    assert coverage["status"] == "range_complete"
    assert coverage["counts"]["excluded_explicit"] == 1
    assert coverage["counts"]["occurrences"] == 0
    assert rc.verify_work(kb, "novels", "测试作品") == []


@pytest.mark.parametrize("missing_lane", ["explicit", "semantic"])
def test_ingest_blocks_unhandled_explicit_or_unreviewed_semantic_task(tmp_path, missing_lane):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path)
    if missing_lane == "explicit":
        output["explicit_results"] = []
    else:
        output["semantic_results"][0]["reviewed"] = False
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match="unhandled explicit|not reviewed"):
        rc.ingest_files(task_path, output_path, kb_root=kb)


def test_ingest_blocks_task_digest_or_source_hash_mismatch(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path)
    output["task_package_sha256"] = "0" * 64
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match="task package checksum"):
        rc.ingest_files(task_path, output_path, kb_root=kb)

    output["task_package_sha256"] = hashlib.sha256(task_path.read_bytes()).hexdigest()
    _write_json(output_path, output)
    (kb / "novels" / "测试作品" / "full_text.md").write_text(
        "第一部\n云已经散了。\n", encoding="utf-8"
    )
    with pytest.raises(rc.RhetoricError, match="source checksum"):
        rc.ingest_files(task_path, output_path, kb_root=kb)


@pytest.mark.parametrize(
    ("locator", "quote", "error"),
    [
        ("full_text.md:L99", "云像船。", "invalid locator"),
        ("full_text.md:L2", "原文中没有这句话", "quote not found"),
    ],
)
def test_ingest_blocks_invalid_locator_or_unbacked_quote(tmp_path, locator, quote, error):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path, include_first=True)
    candidate = output["explicit_results"][0]["occurrences"][0]
    candidate["source_locator"] = locator
    candidate["quote"] = quote
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match=error):
        rc.ingest_files(task_path, output_path, kb_root=kb)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda item: item.update(figure_type="zeugma"), "invalid figure_type"),
        (lambda item: item.pop("ground"), "comparison fields"),
        (lambda item: item.update(quality_assessment="excellent"), "quality_assessment"),
    ],
)
def test_ingest_rejects_illegal_figure_missing_comparison_field_or_quality(tmp_path, mutate, error):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2, figure_scope=["all"])
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path, include_first=True)
    mutate(output["explicit_results"][0]["occurrences"][0])
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match=error):
        rc.ingest_files(task_path, output_path, kb_root=kb)


def test_noncomparison_requires_device_elements_but_not_tenor_vehicle_ground(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n铁门吞下了最后一道光。\n")
    package = _prepare(kb, body_end=2, figure_scope=["personification"])
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    semantic_task = package["semantic_tasks"][0]
    candidate = _candidate(
        {**semantic_task, "source_locator": "full_text.md:L2", "text": "铁门吞下了最后一道光。"},
        figure_type="personification",
    )
    output = _output_for(package, task_path)
    output["semantic_results"][0]["discoveries"] = [candidate]
    candidate.pop("device_elements")
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match="device_elements"):
        rc.ingest_files(task_path, output_path, kb_root=kb)

    candidate["device_elements"] = {"agentive_verb": "吞下"}
    candidate.pop("tenor", None)
    candidate.pop("vehicle", None)
    candidate.pop("ground", None)
    _write_json(output_path, output)
    coverage = rc.ingest_files(task_path, output_path, kb_root=kb)

    occurrence_path = next(
        (kb / "novels" / "测试作品" / "rhetoric" / "occurrences").glob("*.yaml")
    )
    occurrence = yaml.safe_load(occurrence_path.read_text(encoding="utf-8"))
    assert coverage["status"] == "range_complete"
    assert occurrence["figure_type"] == "personification"
    assert occurrence["device_elements"] == {"agentive_verb": "吞下"}
    assert "tenor" not in occurrence


def test_occurrence_locator_can_cross_explicit_context_and_semantic_chunk_boundary(tmp_path):
    kb = _make_kb(
        tmp_path,
        "第一部\n暗处的星群收拢。\n像一张缓慢张开的网。\n网线越过天际。\n远端仍在发亮。\n",
    )
    package = _prepare(kb, body_end=5, chunk_lines=2)
    task_path = tmp_path / "comparison-tasks.json"
    output_path = tmp_path / "comparison-output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path, include_first=True)
    candidate = output["explicit_results"][0]["occurrences"][0]
    candidate["source_locator"] = "full_text.md:L1-L5"
    candidate["quote"] = "像一张缓慢张开的网。"
    _write_json(output_path, output)

    coverage = rc.ingest_files(task_path, output_path, kb_root=kb)

    assert coverage["counts"]["occurrences"] == 1

    other_kb = _make_kb(
        tmp_path / "semantic",
        "第一部\n铁门吞下最后一道光。\n黑暗沿门缝漫进来。\n走廊失声。\n",
    )
    semantic_package = _prepare(
        other_kb,
        body_end=4,
        chunk_lines=2,
        figure_scope=["personification"],
    )
    semantic_task_path = tmp_path / "semantic-tasks.json"
    semantic_output_path = tmp_path / "semantic-output.json"
    _write_json(semantic_task_path, semantic_package)
    semantic_output = _output_for(semantic_package, semantic_task_path)
    first_task = semantic_package["semantic_tasks"][0]
    cross_chunk = _candidate(
        {**first_task, "source_locator": "full_text.md:L2-L4", "text": "铁门吞下最后一道光。"},
        figure_type="personification",
        quote="铁门吞下最后一道光。",
    )
    semantic_output["semantic_results"][0]["discoveries"] = [cross_chunk]
    _write_json(semantic_output_path, semantic_output)

    semantic_coverage = rc.ingest_files(
        semantic_task_path,
        semantic_output_path,
        kb_root=other_kb,
    )

    assert semantic_coverage["counts"]["occurrences"] == 1


def test_ingest_rejects_same_occurrence_discovered_twice(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output.json"
    _write_json(task_path, package)
    output = _output_for(package, task_path, include_first=True)
    output["semantic_results"][0]["discoveries"] = [
        dict(output["explicit_results"][0]["occurrences"][0])
    ]
    _write_json(output_path, output)

    with pytest.raises(rc.RhetoricError, match="duplicate occurrence_id"):
        rc.ingest_files(task_path, output_path, kb_root=kb)


def test_ingest_merges_partial_outputs_and_rejects_duplicate_task_results(tmp_path):
    kb = _make_kb(
        tmp_path,
        "第一部\n云像船。\n灯仿佛醒了。\n余波散去。\n",
    )
    package = _prepare(kb, body_end=4, chunk_lines=2)
    task_path = tmp_path / "tasks.json"
    first_path = tmp_path / "output-1.json"
    second_path = tmp_path / "output-2.json"
    _write_json(task_path, package)
    complete = _output_for(package, task_path)
    first = {
        **complete,
        "explicit_results": complete["explicit_results"][:1],
        "semantic_results": complete["semantic_results"][:1],
    }
    second = {
        **complete,
        "explicit_results": complete["explicit_results"][1:],
        "semantic_results": complete["semantic_results"][1:],
    }
    _write_json(first_path, first)
    _write_json(second_path, second)

    coverage = rc.ingest_files(task_path, [first_path, second_path], kb_root=kb)

    assert coverage["status"] == "range_complete"
    assert coverage["counts"]["explicit_tasks"] == len(package["explicit_tasks"])
    assert coverage["counts"]["semantic_chunks"] == len(package["semantic_tasks"])

    second["explicit_results"].append(complete["explicit_results"][0])
    _write_json(second_path, second)
    with pytest.raises(rc.RhetoricError, match="duplicate explicit task result"):
        rc.ingest_files(task_path, [first_path, second_path], kb_root=kb)


def test_rerun_include_to_exclude_requires_replace_and_removes_stale_card(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    include_path = tmp_path / "include.json"
    exclude_path = tmp_path / "exclude.json"
    _write_json(task_path, package)
    _write_json(include_path, _output_for(package, task_path, include_first=True))
    _write_json(exclude_path, _output_for(package, task_path, include_first=False))
    rc.ingest_files(task_path, include_path, kb_root=kb)
    occurrences_dir = kb / "novels" / "测试作品" / "rhetoric" / "occurrences"
    assert len(list(occurrences_dir.glob("*.yaml"))) == 1

    with pytest.raises(rc.RhetoricError, match="stale occurrence cards.*--replace"):
        rc.ingest_files(task_path, exclude_path, kb_root=kb)

    coverage = rc.ingest_files(task_path, exclude_path, kb_root=kb, replace=True)

    assert coverage["occurrence_ids"] == []
    assert coverage["counts"]["occurrences"] == 0
    assert list(occurrences_dir.glob("*.yaml")) == []
    assert rc.verify_work(kb, "novels", "测试作品") == []


def test_ingest_replace_rolls_back_whole_rhetoric_tree_when_swap_fails(
    tmp_path,
    monkeypatch,
):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    include_path = tmp_path / "include.json"
    exclude_path = tmp_path / "exclude.json"
    _write_json(task_path, package)
    _write_json(include_path, _output_for(package, task_path, include_first=True))
    _write_json(exclude_path, _output_for(package, task_path, include_first=False))
    rc.ingest_files(task_path, include_path, kb_root=kb)
    work_dir = kb / "novels" / "测试作品"
    rhetoric_dir = work_dir / "rhetoric"
    before = _tree_snapshot(rhetoric_dir)
    original_rename = Path.rename

    def fail_stage_promotion(self: Path, target: Path) -> Path:
        target_path = Path(target)
        if self.name.startswith(".rhetoric-stage-") and target_path.name == "rhetoric":
            raise OSError("injected stage promotion failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_stage_promotion)

    with pytest.raises(OSError, match="injected stage promotion failure"):
        rc.ingest_files(task_path, exclude_path, kb_root=kb, replace=True)

    assert _tree_snapshot(rhetoric_dir) == before
    assert not list(work_dir.glob(".rhetoric-stage-*"))
    assert not list(work_dir.glob(".rhetoric-backup-*"))


def test_ingest_staged_validation_failure_leaves_old_tree_unchanged(tmp_path, monkeypatch):
    kb = _make_kb(tmp_path, "第一部\n云像船。\n")
    package = _prepare(kb, body_end=2)
    task_path = tmp_path / "tasks.json"
    include_path = tmp_path / "include.json"
    exclude_path = tmp_path / "exclude.json"
    _write_json(task_path, package)
    _write_json(include_path, _output_for(package, task_path, include_first=True))
    _write_json(exclude_path, _output_for(package, task_path, include_first=False))
    rc.ingest_files(task_path, include_path, kb_root=kb)
    work_dir = kb / "novels" / "测试作品"
    rhetoric_dir = work_dir / "rhetoric"
    before = _tree_snapshot(rhetoric_dir)

    def reject_stage(*_args, **_kwargs) -> None:
        raise rc.RhetoricError("injected staged validation failure")

    monkeypatch.setattr(rc, "_validate_staged_snapshot", reject_stage)

    with pytest.raises(rc.RhetoricError, match="injected staged validation failure"):
        rc.ingest_files(task_path, exclude_path, kb_root=kb, replace=True)

    assert _tree_snapshot(rhetoric_dir) == before
    assert not list(work_dir.glob(".rhetoric-stage-*"))
    assert not list(work_dir.glob(".rhetoric-backup-*"))


def test_complete_fixture_verifies_and_builds_per_work_and_global_indexes(tmp_path):
    kb, coverage, work_dir = _ingest_complete(tmp_path)

    errors = rc.verify_work(kb, "novels", "测试作品")
    global_index = rc.rebuild_global_index(kb, scope_file=kb / coverage["scope_file"])

    assert coverage["status"] == "complete"
    assert errors == []
    occurrence_files = list((work_dir / "rhetoric" / "occurrences").glob("*.yaml"))
    assert len(occurrence_files) == 1
    occurrence = yaml.safe_load(occurrence_files[0].read_text(encoding="utf-8"))
    assert occurrence["schema_version"] == "rhetoric-occurrence/v1"
    assert occurrence["occurrence_id"].startswith("rh-")
    assert occurrence["quality_assessment"] == "exemplary"
    assert "玻璃板上融化的冰淇淋" in (work_dir / "rhetoric" / "index.md").read_text(
        encoding="utf-8"
    )
    assert "full_text.md:L2" in (work_dir / "rhetoric" / "index.md").read_text(
        encoding="utf-8"
    )
    assert global_index["count"] == 1
    assert global_index["scope_status"] == "complete"
    assert global_index["occurrences"][0]["occurrence_id"] == occurrence["occurrence_id"]
    stored = json.loads((kb / "rhetoric" / "occurrence_index.json").read_text(encoding="utf-8"))
    assert stored == global_index
    assert "测试作品" in (kb / "rhetoric" / "index.md").read_text(encoding="utf-8")


def test_locator_sort_key_orders_line_numbers_numerically():
    locators = ["full_text.md:L100", "full_text.md:L9", "full_text.md:L20-L21"]

    assert sorted(locators, key=rc._locator_sort_key) == [
        "full_text.md:L9",
        "full_text.md:L20-L21",
        "full_text.md:L100",
    ]


def test_verify_rejects_semantic_chunk_gap_or_overlap(tmp_path):
    kb, _, work_dir = _ingest_complete(tmp_path)
    coverage_path = work_dir / "rhetoric" / "coverage.yaml"
    coverage = yaml.safe_load(coverage_path.read_text(encoding="utf-8"))
    coverage["semantic_chunks"][0]["start_line"] += 1
    coverage_path.write_text(
        yaml.safe_dump(coverage, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    errors = rc.verify_work(kb, "novels", "测试作品")

    assert any("gap or overlap" in error for error in errors)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda item: item.update(source_sha256="0" * 64), "source checksum"),
        (lambda item: item.update(occurrence_id="rh-" + "0" * 24), "occurrence_id hash mismatch"),
        (lambda item: item.update(source_locator="full_text.md:L99"), "invalid locator"),
        (lambda item: item.update(quote="不存在的引文"), "quote not found"),
    ],
)
def test_verify_rejects_tampered_hash_locator_or_quote(tmp_path, mutation, error):
    kb, _, work_dir = _ingest_complete(tmp_path)
    occurrence_path = next((work_dir / "rhetoric" / "occurrences").glob("*.yaml"))
    occurrence = yaml.safe_load(occurrence_path.read_text(encoding="utf-8"))
    mutation(occurrence)
    occurrence_path.write_text(
        yaml.safe_dump(occurrence, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    errors = rc.verify_work(kb, "novels", "测试作品")

    assert any(error in message for message in errors)


def test_verify_rejects_duplicate_occurrence_id(tmp_path):
    kb, _, work_dir = _ingest_complete(tmp_path)
    occurrence_path = next((work_dir / "rhetoric" / "occurrences").glob("*.yaml"))
    duplicate = occurrence_path.with_name("duplicate.yaml")
    duplicate.write_text(occurrence_path.read_text(encoding="utf-8"), encoding="utf-8")

    errors = rc.verify_work(kb, "novels", "测试作品")

    assert any("duplicate occurrence_id" in error for error in errors)


def test_verify_rejects_stored_occurrence_not_referenced_by_any_task(tmp_path):
    kb, _, work_dir = _ingest_complete(tmp_path)
    coverage_path = work_dir / "rhetoric" / "coverage.yaml"
    coverage = yaml.safe_load(coverage_path.read_text(encoding="utf-8"))
    coverage["explicit_tasks"][0]["disposition"] = "exclude"
    coverage["explicit_tasks"][0]["occurrence_ids"] = []
    coverage_path.write_text(
        yaml.safe_dump(coverage, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = rc.verify_work(kb, "novels", "测试作品")

    assert any("task occurrence references do not match stored cards" in error for error in errors)


def test_cli_prepare_ingest_verify_and_index_round_trip(tmp_path):
    kb = _make_kb(tmp_path, "第一部\n两份结果完全一样。\n")
    task_path = tmp_path / "cli-tasks.json"
    output_path = tmp_path / "cli-output-explicit.json"
    second_output_path = tmp_path / "cli-output-semantic.json"
    shard_dir = tmp_path / "cli-shards"
    scope_file = _write_scope_manifest(tmp_path, kb, body_start=1, body_end=2)

    assert rc.main(
        [
            "--kb-root",
            str(kb),
            "prepare",
            "--container",
            "novels",
            "--work",
            "测试作品",
            "--source",
            "full_text.md",
            "--body-start",
            "1",
            "--body-end",
            "2",
            "--figure-scope",
            "comparison",
            "--chunk-lines",
            "2",
            "--edition-id",
            "test-edition",
            "--scope-file",
            str(scope_file),
            "--out",
            str(task_path),
        ]
    ) == 0
    package = json.loads(task_path.read_text(encoding="utf-8"))
    assert rc.main(
        [
            "--kb-root",
            str(kb),
            "slice",
            "--tasks",
            str(task_path),
            "--out-dir",
            str(shard_dir),
            "--max-chars",
            "10000",
            "--max-tasks",
            "1",
        ]
    ) == 0
    assert len(list(shard_dir.glob("shard-*.json"))) == 2
    complete = _output_for(package, task_path)
    _write_json(output_path, {**complete, "semantic_results": []})
    _write_json(second_output_path, {**complete, "explicit_results": []})

    assert rc.main(
        [
            "--kb-root",
            str(kb),
            "ingest",
            "--tasks",
            str(task_path),
            "--output",
            str(output_path),
            "--output",
            str(second_output_path),
            "--replace",
        ]
    ) == 0
    assert rc.main(
        [
            "--kb-root",
            str(kb),
            "verify",
            "--scope-file",
            str(scope_file),
        ]
    ) == 0
    assert rc.main(
        [
            "--kb-root",
            str(kb),
            "index",
            "--scope-file",
            str(scope_file),
        ]
    ) == 0
