from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import yaml


ev = importlib.import_module("skills.MUSE-canon-distill.knowledge-base.scripts.kb_retrieval_eval")


def test_metrics_pure_functions():
    relevant = {("书A", "S01"): 2, ("书A", "S03"): 1}
    results = [{"novel": "书A", "scene_id": "S02"}, {"novel": "书A", "scene_id": "S01"}]

    assert ev.recall_at_k(results, relevant, 2) == pytest.approx(0.5)
    assert ev.mrr(results, relevant) == pytest.approx(0.5)
    assert ev.ndcg_at_k([2, 0, 1], ideal=[2, 1, 0], k=2) == pytest.approx(0.8262, abs=1e-3)


def test_eval_missing_set_exit2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        ev.main(["--eval-set", str(tmp_path / "missing.yaml")])

    assert exc.value.code == 2


def test_eval_runs_matrix_with_injected_retriever(tmp_path):
    eval_set = tmp_path / "queries.yaml"
    eval_set.write_text(
        yaml.safe_dump(
            [
                {
                    "query_id": "q001",
                    "query": "测试",
                    "genre": "武侠",
                    "style_hint": "贴身",
                    "relevant": [{"novel": "书A", "scene_id": "S01", "grade": 2}],
                }
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "metrics.json"

    def fake_retriever(query, config):
        assert config["name"] in {"baseline", "+hybrid", "+stylevec", "+mmr", "full", "+function"}
        return [{"novel": "书A", "scene_id": "S01", "style_match": 0.5}]

    metrics = ev.run_eval(eval_set, out_path=out, retriever=fake_retriever)

    assert set(metrics["configs"]) == {"baseline", "+hybrid", "+stylevec", "+mmr", "full", "+function"}
    assert metrics["query_count"] == 1
    assert json.loads(out.read_text(encoding="utf-8"))["query_count"] == 1
