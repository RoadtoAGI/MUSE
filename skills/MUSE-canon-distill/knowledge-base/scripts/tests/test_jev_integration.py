"""Offline checks of the optional evaluator at the existing K tool boundary."""
from __future__ import annotations

from copy import deepcopy
import importlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import yaml

from muse_runtime import client, config

kq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_query")
iq = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.inspiration_query")


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    embeddings = kb / "embeddings"
    embeddings.mkdir(parents=True)
    names = ["书甲", "书乙", "书丙", "剧本丁"]
    entries = []
    for index, novel in enumerate(names):
        medium = "screenplay" if index == 3 else "novel"
        file = f"novels/{novel}/scenes/scene_S01.md"
        path = kb / file
        path.parent.mkdir(parents=True)
        path.write_text(f"{novel}原文标记。人物行动、信息关系与后果均在这段原文中。", encoding="utf-8")
        entry = {"novel": novel, "scene_id": "S01", "file": file, "description": f"场景描述{index}",
                 "source_medium": medium, "genre": "测试", "lang": "zh"}
        entries.append(entry)
        (path.parent.parent / "scene_index.json").write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")
    index_path = embeddings / "scene_index.json"
    index_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    vectors_path = embeddings / "scene_embeddings.npy"
    np.save(vectors_path, np.array([[1, 0], [.9, .1], [.2, .98], [.95, .05]], dtype=np.float32))
    for name, value in {"KB_ROOT": kb, "INDEX_PATH": index_path, "EMBEDDINGS_PATH": vectors_path,
                        "STYLE_EMBEDDINGS_PATH": embeddings / "style_embeddings.npy", "API_KEY": "embedding-test"}.items():
        monkeypatch.setattr(kq, name, value)
    monkeypatch.setattr(kq, "OpenAI", lambda **kwargs: object())
    monkeypatch.setattr(kq, "_embed_text_cached", lambda *args, **kwargs: [1, 0])
    kq._NOVEL_ANNOTATIONS_CACHE.clear()
    work = tmp_path / "work"
    work.mkdir()
    return kb, work, entries


def read_reference(results, work, *, suffix="reference", **kwargs):
    path = kq.save_reference_file(results, "查询", None, str(work / suffix), "S01", max_chars=0, **kwargs)
    return Path(path).read_text(encoding="utf-8")


def query_work(work, **kwargs):
    return kq.query("查询", work_dir=str(work), hybrid=False, pool=9, top_k=2, **kwargs)


def reverse_rank(settings, node, task, candidates, **kwargs):
    return [{"id": item["id"], "fit": 3.0, "rank_score": 3.0, "must_probabilities": [],
             "request_id": kwargs.get("request_id"), "original_position": position}
            for position, item in enumerate(reversed(candidates))]


def profile(work, materials):
    path = work / "phase0.yaml"
    path.write_text(yaml.safe_dump({"canon_reference_profile": {"user_reference_materials": materials}}, allow_unicode=True), encoding="utf-8")
    return str(path)


def test_scene_reordering_reaches_actual_reference_without_assessment_context(corpus, monkeypatch):
    _, work, _ = corpus
    standard = query_work(work)
    assert [result["novel"] for result in standard] == ["书甲", "书乙"]
    config.set_mode(work, "jev")
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.extend(deepcopy(candidates))
        assert kwargs["must"] == ["行动需要先获得信息"]
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(kq.runtime_assistance, "rank", rank)
    metadata = {}
    enhanced = query_work(work, must=["行动需要先获得信息"], run_metadata=metadata)
    text = read_reference(enhanced, work)
    assert [result["novel"] for result in enhanced] == ["书丙", "书乙"]
    assert "书丙原文标记" in text and "书甲原文标记" not in text
    assert text.index("书丙原文标记") < text.index("书乙原文标记")
    assert len(captured) == 3 and all("原文标记" in candidate["material"] for candidate in captured)
    assert all("reference_assessment" not in item and "must_probabilities" not in item for item in enhanced)
    assert all(marker not in text for marker in ("匹配辅助", "reference_assessment", "must_probabilities", "JEV"))
    assert metadata["strategy"] == "score"


def test_standard_never_constructs_jev_client_and_switch_off_restores_output(corpus, monkeypatch):
    _, work, _ = corpus
    def forbidden(*args, **kwargs):
        pytest.fail("standard path read a JEV key or constructed its client")
    monkeypatch.setattr(client, "resolve_key", forbidden)
    monkeypatch.setattr(client, "JevClient", forbidden)
    baseline = query_work(work, must=["已有条件"])
    config.set_mode(work, "jev")
    monkeypatch.setattr(kq.runtime_assistance, "rank", reverse_rank)
    assert query_work(work) != baseline
    config.set_mode(work, "standard")
    restored = query_work(work, must=["已有条件"])
    assert restored == baseline
    assert read_reference(restored, work, suffix="after") == read_reference(baseline, work, suffix="before")


@pytest.mark.parametrize("with_avoid", [False, True])
def test_failed_pool_materializes_exact_baseline(corpus, monkeypatch, with_avoid):
    _, work, _ = corpus
    profile_path = profile(work, [{"work": "书甲", "stance": "avoid"}]) if with_avoid else None
    args = {"canon_reference_profile": profile_path}
    baseline = query_work(work, **args)
    baseline_text = read_reference(baseline, work, suffix="before", **args)
    config.set_mode(work, "jev")
    monkeypatch.setattr(kq.runtime_assistance, "rank", lambda *args, **kwargs: None)
    metadata = {}
    result = query_work(work, run_metadata=metadata, **args)
    assert read_reference(result, work, suffix="after", **args) == baseline_text
    assert metadata["strategy"] == "fallback"


def test_mmr_evaluation_preserves_original_selection_and_order(corpus, monkeypatch):
    _, work, _ = corpus
    baseline = query_work(work, mmr_lambda=.3)
    config.set_mode(work, "jev")
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.extend(candidates)
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(kq.runtime_assistance, "rank", rank)
    metadata = {}
    result = query_work(work, mmr_lambda=.3, run_metadata=metadata)
    assert result == baseline
    assert [candidate["id"] for candidate in captured] == [candidate["file"] for candidate in baseline]
    assert metadata["strategy"] == "evaluation_only_mmr"


def test_source_medium_avoid_and_disjoint_scope_are_filtered_before_evaluation(corpus, monkeypatch):
    _, work, _ = corpus
    config.set_mode(work, "jev")
    path = profile(work, [
        {"work": "书甲", "stance": "avoid"},
        {"work": "书乙", "intended_domains": ["prose_style_imitation"], "reuse_mode": "style_only"},
    ])
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.extend(candidates)
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(kq.runtime_assistance, "rank", rank)
    result = query_work(work, canon_reference_profile=path, intended_domains=["world_rule"])
    assert [candidate["novel"] for candidate in captured] == ["书丙"]
    assert captured[0]["intended_domains"] == ["world_rule"]
    assert [candidate["novel"] for candidate in result] == ["书丙"]


def test_style_only_remains_the_evaluation_and_materialization_scope(corpus, monkeypatch):
    _, work, _ = corpus
    config.set_mode(work, "jev")
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.extend(candidates)
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(kq.runtime_assistance, "rank", rank)
    args = {"reuse_mode": "style_only", "intended_domains": ["prose_style_imitation"]}
    results = query_work(work, **args)
    assert captured and all(candidate["style_only"] for candidate in captured)
    assert all(candidate["intended_domains"] == ["prose_style_imitation"] for candidate in captured)
    text = read_reference(results, work, **args)
    assert "reuse_tier: style" in text and "reuse_mandate: false" in text
    assert 'tier="full"' not in text


def test_manual_selection_skips_mode_resolution_and_jev(corpus, monkeypatch):
    _, work, _ = corpus
    config.set_mode(work, "jev")
    def forbidden(*args, **kwargs):
        pytest.fail("manual selection invoked mode/evaluation")
    monkeypatch.setattr(kq.runtime_assistance, "settings_for", forbidden)
    monkeypatch.setattr(kq.runtime_assistance, "rank", forbidden)
    monkeypatch.setattr(sys, "argv", ["kb_query.py", "--select", "书乙:S01", "--work-dir", str(work),
                                    "--output-dir", str(work / "pipeline/references"), "--scene-id", "manual"])
    kq.main()
    text = (work / "pipeline/references/manual_ref.md").read_text(encoding="utf-8")
    assert "书乙原文标记" in text and "书甲原文标记" not in text


def test_missing_source_is_infrastructure_error_before_evaluation(corpus, monkeypatch):
    kb, work, entries = corpus
    config.set_mode(work, "jev")
    (kb / entries[1]["file"]).unlink()
    monkeypatch.setattr(kq.runtime_assistance, "rank", lambda *args, **kwargs: pytest.fail("called evaluator with missing source"))
    with pytest.raises(kq.KBInfraError, match="候选原文缺失"):
        query_work(work)


def test_http_evaluation_to_cli_reference_keeps_delivery_identity(corpus, monkeypatch):
    _, work, entries = corpus
    config.set_mode(work, "jev")
    monkeypatch.setenv("MUSE_JEV_API_KEY", "integration-test-secret")
    requests = []
    def transport(request, timeout):
        payload = json.loads(request.data)
        requests.append(payload)
        text = payload["state"]["candidate"]["material"]
        score = 3 if "书丙" in text else 2 if "书乙" in text else 0
        probabilities = {str(level): float(level == score) for level in range(4)}
        answers = {"fit": {"type": "score", "score": score, "probabilities": probabilities},
                   "must_0": {"type": "noul", "noul": .8}}
        body = {"model": config.MODEL, "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 10}}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    monkeypatch.setattr(sys, "argv", ["kb_query.py", "--query", "查询", "--work-dir", str(work),
                                    "--output-dir", str(work / "pipeline/references"), "--scene-id", "live",
                                    "--top_k", "2", "--must", "明确条件"])
    kq.main()
    text = (work / "pipeline/references/live_ref.md").read_text(encoding="utf-8")
    assert text.index("书丙原文标记") < text.index("书乙原文标记")
    assert "书甲原文标记" not in text
    assert len(requests) == 3
    assert all(payload["state"]["task"]["must"] == ["明确条件"] for payload in requests)
    events_text = (work / ".muse/jev-events.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in events_text.splitlines()]
    evaluated = next(event for event in events if event["status"] == "evaluated")
    delivered = next(event for event in events if event["status"] == "delivered")
    assert evaluated["request_id"] == delivered["request_id"]
    assert delivered["selected_ids"] == [entries[2]["file"], entries[1]["file"]]
    assert evaluated["usage"] == {"input_tokens": 300, "output_tokens": 30}
    assert all(term not in events_text for term in ("integration-test-secret", "原文标记", "明确条件"))


def test_cli_delivery_records_only_sources_actually_written_after_fallback(corpus, monkeypatch):
    _, work, _ = corpus
    path = profile(work, [{"work": "书甲", "stance": "avoid"},
                          {"work": "书乙", "intended_domains": ["world_rule"]}])
    config.set_mode(work, "jev")
    monkeypatch.setattr(kq.runtime_assistance, "rank", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["kb_query.py", "--query", "查询", "--work-dir", str(work),
                                    "--output-dir", str(work / "pipeline/references"), "--scene-id", "fallback",
                                    "--top_k", "2", "--canon-reference-profile", path,
                                    "--intended-domains", "prose_style_imitation"])
    kq.main()
    text = (work / "pipeline/references/fallback_ref.md").read_text(encoding="utf-8")
    assert "原文标记" not in text
    events = [json.loads(line) for line in (work / ".muse/jev-events.jsonl").read_text().splitlines()]
    delivered = next(event for event in events if event["status"] == "delivered")
    assert delivered["selected_ids"] == []


@pytest.mark.parametrize("output_kind, flags", [("json", ["--json"]), ("candidate_table", ["--list"]), ("stdout", ["--include-text"])])
def test_cli_all_output_forms_exclude_disjoint_fallback_candidates(corpus, monkeypatch, capsys, output_kind, flags):
    _, work, entries = corpus
    path = profile(work, [{"work": "书甲", "intended_domains": ["world_rule"]}])
    config.set_mode(work, "jev")
    monkeypatch.setattr(kq.runtime_assistance, "rank", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["kb_query.py", "--query", "查询", "--work-dir", str(work),
                                    "--top_k", "2", "--canon-reference-profile", path,
                                    "--intended-domains", "prose_style_imitation", *flags])
    kq.main()
    output = capsys.readouterr().out
    assert "书甲" not in output
    assert "书乙" in output
    if output_kind == "json":
        assert [result["novel"] for result in json.loads(output)] == ["书乙"]
    events = [json.loads(line) for line in (work / ".muse/jev-events.jsonl").read_text().splitlines()]
    delivered = next(event for event in events if event["status"] == "delivered")
    assert delivered["selected_ids"] == [entries[1]["file"]]
    assert delivered["output"] == output_kind and delivered["strategy"] == "fallback"


@pytest.fixture
def cards(tmp_path, monkeypatch):
    kb = tmp_path / "cards-kb"
    folder = kb / "inspiration"
    folder.mkdir(parents=True)
    for name, novel, phases in [("a", "书甲", [3]), ("b", "书乙", [3]), ("c", "书丙", [5])]:
        card = {"card_id": name, "pattern_name": f"秘密传递{name}", "dramatic_function": "秘密传递让伙伴行动",
                "applicability": "监听情境", "phase_affinity": phases,
                "source_scenes": [{"novel": novel, "scene_id": "S01", "note": "秘密传递方式"}]}
        (folder / f"{name}.yaml").write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(iq, "KB_ROOT", kb)
    work = tmp_path / "card-work"
    work.mkdir()
    return kb, work


def run_cards(work, *, signals='{"motif":"秘密传递"}', preferred_works=None, phase=3):
    result = iq.run(phase, signals, str(work / "pipeline/references"), top_k=2,
                    preferred_works=preferred_works, work_dir=str(work))
    assert result == 0
    return (work / f"pipeline/references/inspiration/phase{phase}_cards.md").read_text(encoding="utf-8")


def test_inspiration_reorder_clean_output_and_unchanged_preferred_selection(cards, monkeypatch):
    _, work = cards
    baseline = run_cards(work)
    preferred_baseline = run_cards(work, preferred_works=["书甲"])
    config.set_mode(work, "jev")
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.append((deepcopy(task), deepcopy(candidates)))
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(iq.runtime_assistance, "rank", rank)
    enhanced = run_cards(work)
    assert enhanced != baseline
    assert "匹配辅助" not in enhanced and "reference_assessment" not in enhanced
    preferred = run_cards(work, preferred_works=["书甲"])
    assert preferred == preferred_baseline
    assert captured[0][0]["phase"] == 3
    assert all(not any(name.startswith("_") for name in candidate["material"]) for candidate in captured[0][1])


def test_inspiration_phase_only_skips_evaluation(cards, monkeypatch):
    _, work = cards
    baseline = run_cards(work, signals="{}", phase=5)
    config.set_mode(work, "jev")
    monkeypatch.setattr(iq.runtime_assistance, "rank", lambda *args, **kwargs: pytest.fail("phase-only called JEV"))
    assert run_cards(work, signals="{}", phase=5) == baseline


def test_inspiration_profile_filters_cross_source_cards_before_external_evaluation(cards, monkeypatch):
    kb, work = cards
    multi = yaml.safe_load((kb / "inspiration/a.yaml").read_text())
    multi["card_id"] = "multi"
    multi["source_scenes"].append({"novel": "书丙", "scene_id": "S01", "note": "秘密传递"})
    (kb / "inspiration/multi.yaml").write_text(yaml.safe_dump(multi, allow_unicode=True), encoding="utf-8")
    path = profile(work, [
        {"work": "书甲", "reuse_mode": "style_only", "intended_domains": ["prose_style_imitation"]},
        {"work": "书乙", "stance": "avoid"},
        {"work": "书丙", "intended_domains": ["world_rule"]},
    ])
    config.set_mode(work, "jev")
    captured = []
    def rank(settings, node, task, candidates, **kwargs):
        captured.extend(candidates)
        return reverse_rank(settings, node, task, candidates, **kwargs)
    monkeypatch.setattr(iq.runtime_assistance, "rank", rank)
    assert iq.run(3, '{"motif":"秘密传递"}', str(work / "pipeline/references"), work_dir=str(work),
                  canon_reference_profile=path) == 0
    assert {candidate["id"] for candidate in captured} == {"a", "c"}
    by_id = {candidate["id"]: candidate for candidate in captured}
    assert by_id["a"]["style_only"]
    assert by_id["a"]["intended_domains"] == ["prose_style_imitation"]
    assert by_id["c"]["intended_domains"] == ["world_rule"]
    text = (work / "pipeline/references/inspiration/phase3_cards.md").read_text(encoding="utf-8")
    assert "书乙" not in text and "multi" not in text
    assert "reuse_mode: style_only" in text and "intended_domains: prose_style_imitation" in text


def test_inspiration_multi_source_intersects_all_source_permissions(cards):
    kb, work = cards
    multi = yaml.safe_load((kb / "inspiration/a.yaml").read_text())
    multi["source_scenes"].append({"novel": "书丙", "scene_id": "S01"})
    path = profile(work, [
        {"work": "书甲", "reuse_mode": "style_only", "intended_domains": ["prose_style_imitation"]},
        {"work": "书丙", "intended_domains": ["scene_carrier", "prose_style_imitation"]},
    ])
    allowed = iq.scoped_cards([multi], path)
    assert len(allowed) == 1 and allowed[0]["_style_only"]
    assert allowed[0]["_intended_domains"] == ["prose_style_imitation"]
    avoid_path = profile(work, [{"work": "书丙", "stance": "avoid"}])
    assert iq.scoped_cards([multi], avoid_path) == []


def test_inspiration_permissions_cover_sources_declared_only_in_analysis(cards):
    kb, work = cards
    card = yaml.safe_load((kb / "inspiration/a.yaml").read_text())
    card["source_analyses"] = [{"novel": "书乙", "creative_move": "只在分析中声明的来源"}]
    path = profile(work, [{"work": "书乙", "stance": "avoid"}])
    assert iq.scoped_cards([card], path) == []
    assert iq._source_works(card) == {"书甲"}


def test_copied_k_script_standard_works_without_runtime_and_jev_reports_install_error(cards, tmp_path):
    kb, work = cards
    standalone = tmp_path / "standalone-K"
    scripts = Path(iq.__file__).parent
    shutil.copytree(scripts, standalone / "knowledge-base/scripts", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    shutil.copytree(kb / "inspiration", standalone / "knowledge-base/inspiration")
    source = """
import importlib.abc, sys
class MissingRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'muse_runtime' or fullname.startswith('muse_runtime.'):
            raise ModuleNotFoundError('runtime unavailable', name='muse_runtime')
sys.meta_path.insert(0, MissingRuntime())
sys.path.insert(0, sys.argv[1])
import inspiration_query
raise SystemExit(inspiration_query.run(3, '{"motif":"秘密传递"}', sys.argv[2], work_dir=sys.argv[3]))
"""
    command = [sys.executable, "-I", "-c", source, str(standalone / "knowledge-base/scripts"),
               str(work / "pipeline/references"), str(work)]
    standard = subprocess.run(command, cwd=standalone, capture_output=True, text=True)
    assert standard.returncode == 0, standard.stderr
    config.set_mode(work, "jev")
    enhanced = subprocess.run(command, cwd=standalone, capture_output=True, text=True)
    assert enhanced.returncode == 2
    assert "安装 muse-runtime" in enhanced.stderr
    assert "Traceback" not in enhanced.stderr
