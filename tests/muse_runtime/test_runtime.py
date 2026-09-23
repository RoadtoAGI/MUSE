from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import threading
import time
import urllib.error

import pytest

from muse_runtime import client, config, evaluation
from muse_runtime.cli import main, status


@pytest.fixture
def enabled(tmp_path):
    return config.set_mode(tmp_path, "jev")


def response(score=2.0, *, model=config.MODEL, usage=None):
    return {"model": model, "answers": {"fit": {"type": "score", "score": score,
            "probabilities": {"0": .1, "1": .1, "2": .5, "3": .3}}}, "usage": usage}


def one_item(name="candidate"):
    return {"id": name, "state": {"text": "private source"},
            "questions": evaluation.retrieval_questions()}


def fake_result(score=2.0, must=None):
    answers = response(score)["answers"]
    for index, value in enumerate(must or []):
        answers[f"must_{index}"] = {"type": "noul", "noul": value}
    return {"answers": answers, "model_requested": config.MODEL, "actual_model": config.MODEL,
            "usage": {"input_tokens": 10, "output_tokens": 2}, "elapsed_seconds": .01}


def test_unbound_never_uses_cwd_or_environment(tmp_path, monkeypatch):
    config.set_mode(tmp_path, "jev")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUSE_MODE", "jev")
    monkeypatch.setenv("MUSE_WORK_DIR", str(tmp_path))
    settings = config.resolve_settings()
    assert (settings.mode, settings.work_dir, settings.source) == ("standard", None, "unbound")
    assert not config.resolve_settings(output_dir=tmp_path / "references").enabled


def test_work_modes_and_output_binding_are_isolated(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    config.set_mode(first, "jev")
    config.set_mode(second, "standard")
    assert config.resolve_settings(output_dir=first / "pipeline/ref/scene").enabled
    assert not config.resolve_settings(second, output_dir=first / "pipeline/ref").enabled
    config.set_mode(first, "standard")
    assert not config.resolve_settings(first).enabled
    assert (first / config.CONFIG_FILE).read_text() == "mode: standard\n"


def test_serial_chapter_does_not_inherit(tmp_path):
    (tmp_path / "series").mkdir()
    chapter = tmp_path / "chapters/volume/chapter"
    chapter.mkdir(parents=True)
    config.set_mode(tmp_path, "jev")
    assert not config.resolve_settings(chapter).enabled


def test_standard_delivery_metadata_does_not_claim_a_model_request(tmp_path):
    config.record_event(config.resolve_settings(tmp_path), "retrieval", "delivered", selected_ids=["a"])
    event = json.loads((tmp_path / ".muse/jev-events.jsonl").read_text())
    assert event["mode"] == "standard" and event["model_requested"] is None


@pytest.mark.parametrize("contents", ["- jev\n", "mode: invalid\n", "mode: jev\njev: {}\n", "mode: [jev]\n"])
def test_bad_config_is_visible(tmp_path, contents):
    path = tmp_path / config.CONFIG_FILE
    path.parent.mkdir()
    path.write_text(contents)
    with pytest.raises(config.RuntimeConfigError):
        config.resolve_settings(tmp_path)


def test_standard_and_status_do_not_read_key_or_construct_client(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("standard/settings/status touched the credential or client")
    monkeypatch.setattr(config.os, "getenv", forbidden)
    monkeypatch.setattr(evaluation, "JevClient", forbidden)
    standard = config.resolve_settings(tmp_path)
    assert evaluation.evaluate_many(standard, "test", [one_item()]) is None
    assert evaluation.rerank(standard, "test", {}, [{"id": "a", "material": "text"}]) is None
    assert main(["mode", "set", "jev", "--work-dir", str(tmp_path)]) == 0
    assert status(tmp_path)["mode"] == "jev"
    assert "TypeSafe" in capsys.readouterr().out
    with pytest.raises(config.RuntimeConfigError, match="standard"):
        config.resolve_key(standard)


def test_missing_key_is_configuration_failure(enabled, monkeypatch):
    monkeypatch.delenv("MUSE_JEV_API_KEY", raising=False)
    with pytest.raises(config.RuntimeConfigError, match="MUSE_JEV_API_KEY"):
        evaluation.evaluate_many(enabled, "retrieval", [one_item()])
    event = json.loads((enabled.work_dir / ".muse/jev-events.jsonl").read_text())
    assert event["status"] == "config_error"


@pytest.mark.parametrize("patch", [
    {"answers": None},
    {"answers": {"fit": {"type": "noul", "noul": .5}}},
    {"answers": {"fit": {"type": "score", "score": True, "probabilities": {}}}},
    {"answers": {"fit": {"type": "score", "score": float("nan"), "probabilities": {}}}},
    {"answers": {"fit": {"type": "score", "score": 4, "probabilities": {}}}},
    {"answers": {"fit": {"type": "score", "score": 2, "probabilities": {"0": 1}}}},
    {"answers": {"fit": {"type": "score", "score": 2, "probabilities": {"0": .5, "1": .5, "2": .5, "3": .5}}}},
])
def test_invalid_answer_cannot_rank(patch):
    body = response()
    body.update(patch)
    with pytest.raises(client.JevError):
        client.validated_answers(body, evaluation.retrieval_questions())


@pytest.mark.parametrize("value", [-.1, 1.1, True, "0.5", None, float("inf")])
def test_noul_bounds(value):
    with pytest.raises(client.JevError):
        client.validated_answers({"answers": {"must_0": {"type": "noul", "noul": value}}},
                                 {"must_0": {"type": "noul"}})


@pytest.mark.parametrize("model, usage, expected", [
    (None, None, None),
    (config.MODEL, {"input_tokens": 1, "output_tokens": 0}, None),
    ("jev-other", {}, "unexpected_model"),
    ({}, {}, "unexpected_model"),
    (config.MODEL, [], "invalid_usage"),
    (config.MODEL, {"input_tokens": -1}, "invalid_usage"),
    (config.MODEL, {"input_tokens": True}, "invalid_usage"),
])
def test_response_metadata_is_checked(enabled, monkeypatch, model, usage, expected):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-credential")
    body = response(model=model, usage=usage)
    seen = []
    def transport(request, timeout):
        seen.append((json.loads(request.data), timeout))
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    instance = client.JevClient(enabled)
    if expected:
        with pytest.raises(client.JevError, match=expected):
            instance.evaluate({}, evaluation.retrieval_questions(), timeout=2)
    else:
        result = instance.evaluate({}, evaluation.retrieval_questions(), timeout=2)
        assert result["actual_model"] == model
        assert result["usage"] == (usage or {})
    assert seen[0][0]["model"] == config.MODEL
    assert seen[0][1] == 2


def test_http_error_does_not_echo_server_or_credentials(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    def transport(*args, **kwargs):
        raise urllib.error.HTTPError("https://secret.example", 429, "unit-test-secret", {}, None)
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    with pytest.raises(client.JevError) as error:
        client.JevClient(enabled).evaluate({}, evaluation.retrieval_questions())
    assert str(error.value) == "http_429"


def test_log_failure_preserves_results(enabled, monkeypatch, capsys):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    monkeypatch.setattr(client.JevClient, "evaluate", lambda *a, **k: fake_result())
    def unavailable(*args, **kwargs):
        raise PermissionError("private path")
    monkeypatch.setattr(config.os, "open", unavailable)
    assert evaluation.evaluate_many(enabled, "retrieval", [one_item()]) is not None
    error = capsys.readouterr().err
    assert "LOG_WARNING" in error
    assert "private path" not in error


def test_complete_batch_order_logs_evaluation_without_source(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    monkeypatch.setattr(client.JevClient, "evaluate", lambda *a, **k: fake_result())
    items = [one_item("b"), one_item("a")]
    results = evaluation.evaluate_many(enabled, "retrieval", items, request_id="request-fixture")
    assert [r["id"] for r in results] == ["b", "a"]
    raw = (enabled.work_dir / ".muse/jev-events.jsonl").read_text()
    event = json.loads(raw)
    assert event["status"] == "evaluated"
    assert event["usage"] == {"input_tokens": 20, "output_tokens": 4}
    assert event["usage_complete"]
    assert event["request_id"] == "request-fixture"
    assert event["mode"] == "jev"
    assert "unit-test-secret" not in raw and "private source" not in raw


def test_one_failed_candidate_falls_back_entire_pool(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    def evaluate(self, state, questions, **kwargs):
        if state["text"] == "bad":
            raise client.JevError("invalid_response")
        return fake_result()
    monkeypatch.setattr(client.JevClient, "evaluate", evaluate)
    bad = one_item("bad")
    bad["state"]["text"] = "bad"
    assert evaluation.evaluate_many(enabled, "retrieval", [one_item(), bad]) is None
    event = json.loads((enabled.work_dir / ".muse/jev-events.jsonl").read_text())
    assert event["status"] == "fallback"
    assert not event["usage_complete"]


def test_deadline_returns_without_waiting_for_running_http_and_stops_queued_calls(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    release, lock = threading.Event(), threading.Lock()
    started = []
    def evaluate(self, state, questions, *, timeout):
        with lock:
            started.append(timeout)
        release.wait(2)
        return fake_result()
    monkeypatch.setattr(client.JevClient, "evaluate", evaluate)
    before = time.monotonic()
    try:
        result = evaluation.evaluate_many(enabled, "retrieval", [one_item(str(i)) for i in range(8)], deadline_seconds=.08)
        assert result is None
        assert time.monotonic() - before < .5
        assert 1 <= len(started) <= 3
        assert all(0 < timeout <= .08 for timeout in started)
    finally:
        release.set()
    event = json.loads((enabled.work_dir / ".muse/jev-events.jsonl").read_text())
    assert event["error"] == "batch_timeout"


def test_score_only_ties_and_explicit_must_combination(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    seen = []
    def evaluate(self, state, questions, **kwargs):
        seen.append((deepcopy(state), deepcopy(questions)))
        return fake_result(score=2.0, must=[state["candidate"]["material"]["probability"]])
    monkeypatch.setattr(client.JevClient, "evaluate", evaluate)
    candidates = [{"id": "low", "material": {"probability": .1}, "old_rank": 99, "intended_domains": ["world_rule"]},
                  {"id": "high", "material": {"probability": .9}}]
    baseline = evaluation.rerank(enabled, "retrieval", {"query": "query"}, candidates, must=["one relationship"])
    combined = evaluation.rerank(enabled, "retrieval", {"query": "query"}, candidates,
                                 must=["one relationship"], combine_must=True)
    assert [r["id"] for r in baseline] == ["low", "high"]
    assert [r["id"] for r in combined] == ["high", "low"]
    assert combined[0]["rank_score"] == pytest.approx(1.8)
    assert all("old_rank" not in state["candidate"] for state, _ in seen)
    assert all(state["task"]["must"] == ["one relationship"] for state, _ in seen)
    assert all(questions["must_0"]["type"] == "noul" for _, questions in seen)
    assert "intended_domains" in seen[0][1]["fit"]["instructions"]


def test_rubric_language_changes_questions_only(enabled, monkeypatch):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    seen = []
    def evaluate(self, state, questions, **kwargs):
        seen.append((deepcopy(state), deepcopy(questions)))
        return fake_result()
    monkeypatch.setattr(client.JevClient, "evaluate", evaluate)
    candidates = [{"id": "a", "material": "中文原文", "style_only": True}]
    for language in ("zh", "en"):
        evaluation.rerank(enabled, "retrieval", {"query": "中文要求"}, candidates, rubric_language=language)
    assert seen[0][0] == seen[1][0]
    assert seen[0][1] != seen[1][1]
    assert set(seen[0][1]) == {"fit"}


def test_cli_has_no_hook_or_key_reference_entry(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["hook"])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        main(["mode", "set", "jev", "--work-dir", str(tmp_path), "--key-ref", "env:SECRET"])
    assert error.value.code == 2
