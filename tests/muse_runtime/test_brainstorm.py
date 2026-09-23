from __future__ import annotations

from copy import deepcopy
import io
import json
import urllib.error

import pytest

from muse_runtime import brainstorm, client, config
from muse_runtime.cli import main, status


@pytest.fixture
def payload():
    return {"goal": "private author goal", "context": "private story facts",
            "constraints": ["private accepted constraint"], "feedback": ["private scoped feedback"],
            "candidates": [{"id": "private candidate b", "text": "private candidate text b"},
                           {"id": "private candidate a", "text": "private candidate text a"}],
            "questions": [{"id": "private question id", "question": "Does the action meet this private condition?"}]}


def successful_transport(monkeypatch, *, disposition="revise", recommendation="needs_author_preference"):
    calls = []
    def transport(request, timeout):
        request_body = json.loads(request.data)
        calls.append(request_body)
        answers = {}
        for key, question in request_body["questions"].items():
            if question["type"] == "noul":
                answers[key] = {"type": "noul", "noul": .65}
            else:
                choice = recommendation if key == "recommendation" else disposition
                answers[key] = {"type": "choice", "choice": choice,
                                "probabilities": {option: float(option == choice) for option in question["criteria"]}}
        return io.BytesIO(json.dumps({"model": config.MODEL, "answers": answers,
                                     "usage": {"input_tokens": 100, "output_tokens": 30}}).encode())
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    return calls


def test_standard_has_no_credential_or_transport_access(tmp_path, payload, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("standard mode accessed Jev")
    monkeypatch.setattr(config.os, "getenv", forbidden)
    monkeypatch.setattr(brainstorm, "JevClient", forbidden)
    assert brainstorm.evaluate(config.resolve_settings(tmp_path), payload) == {
        "status": "skipped", "reason": "standard_mode", "mode": "standard",
        "candidates": [], "recommendation": None}
    assert not (tmp_path / ".muse/jev-events.jsonl").exists()


def test_complete_pool_uses_real_client_without_forcing_ranking_or_logging_text(tmp_path, payload, monkeypatch):
    calls = successful_transport(monkeypatch)
    result = brainstorm.evaluate(config.set_mode(tmp_path, "jev"), payload)
    assert len(calls) == 1
    assert calls[0]["state"] == payload
    assert calls[0]["model"] == config.MODEL
    questions = calls[0]["questions"]
    assert set(questions) == {"c0_disposition", "c0_q0", "c1_disposition", "c1_q0", "recommendation"}
    assert "state.candidates[1]" in questions["c1_q0"]["instructions"]
    assert "state.questions[0]" in questions["c1_q0"]["instructions"]
    assert set(questions["recommendation"]["criteria"]) == {
        "private candidate b", "private candidate a", "none_of_the_above", "needs_author_preference"}
    assert result["status"] == "evaluated"
    assert [candidate["id"] for candidate in result["candidates"]] == ["private candidate b", "private candidate a"]
    assert result["candidates"][0]["checks"] == [{"id": "private question id", "type": "noul", "noul": .65}]
    assert result["recommendation"]["choice"] == "needs_author_preference"
    assert "reason" not in result and "selected" not in result
    raw = (tmp_path / ".muse/jev-events.jsonl").read_text()
    assert "private" not in raw and "unit-test-secret" not in raw
    event = json.loads(raw)
    assert event["candidate_count"] == 2 and event["question_count"] == 5
    assert event["status"] == "evaluated" and event["request_id"] == result["request_id"]
    assert event["usage"] == result["usage"]
    assert "results" not in event and "answers" not in event


def test_all_candidates_can_need_rebuilding(tmp_path, payload, monkeypatch):
    successful_transport(monkeypatch, disposition="rebuild", recommendation="none_of_the_above")
    result = brainstorm.evaluate(config.set_mode(tmp_path, "jev"), payload)
    assert result["recommendation"]["choice"] == "none_of_the_above"
    assert all(candidate["disposition"]["choice"] == "rebuild" for candidate in result["candidates"])
    assert len(result["candidates"]) == len(payload["candidates"])


def test_candidate_recommendation_preserves_other_directions(tmp_path, payload, monkeypatch):
    successful_transport(monkeypatch, recommendation="private candidate a")
    result = brainstorm.evaluate(config.set_mode(tmp_path, "jev"), payload)
    assert result["recommendation"]["choice"] == "private candidate a"
    assert [candidate["id"] for candidate in result["candidates"]] == ["private candidate b", "private candidate a"]


def test_missing_key_is_visible_and_does_not_change_mode(tmp_path, payload, monkeypatch, capsys):
    monkeypatch.delenv("MUSE_JEV_API_KEY", raising=False)
    settings = config.set_mode(tmp_path, "jev")
    result = brainstorm.evaluate(settings, payload)
    assert result["status"] == "error" and result["error"] == "configuration_error"
    assert result["candidates"] == [] and result["recommendation"] is None
    assert "MUSE_JEV_API_KEY" in capsys.readouterr().err
    assert config.resolve_settings(tmp_path).enabled
    assert json.loads((tmp_path / ".muse/jev-events.jsonl").read_text())["status"] == "config_error"


@pytest.mark.parametrize("failure, expected", [
    (urllib.error.HTTPError("https://private.example", 429, "unit-test-secret", {}, None), "http_429"),
    (urllib.error.URLError("private candidate text unit-test-secret"), "transport_error"),
])
def test_failures_are_explicit_without_partial_advice_or_sensitive_details(tmp_path, payload, monkeypatch, failure, expected):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    def transport(*args, **kwargs):
        raise failure
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    result = brainstorm.evaluate(config.set_mode(tmp_path, "jev"), payload)
    assert result["status"] == "error" and result["error"] == expected
    assert result["candidates"] == [] and result["recommendation"] is None
    raw = (tmp_path / ".muse/jev-events.jsonl").read_text()
    assert "private" not in raw and "unit-test-secret" not in raw


@pytest.mark.parametrize("invalid_choice", ["unknown", [], {}, None])
def test_invalid_choice_response_cannot_produce_recommendation(tmp_path, payload, monkeypatch, invalid_choice):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    def transport(*args, **kwargs):
        return io.BytesIO(json.dumps({"model": config.MODEL, "answers": {
            "c0_disposition": {"type": "choice", "choice": invalid_choice,
                               "probabilities": {key: .25 for key in brainstorm.DISPOSITIONS}}}}).encode())
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    result = brainstorm.evaluate(config.set_mode(tmp_path, "jev"), payload)
    assert result["status"] == "error" and result["error"] == "invalid_choice"
    assert result["candidates"] == []


@pytest.mark.parametrize("patch", [
    {"goal": " "}, {"context": []}, {"constraints": [False]}, {"feedback": "text"},
    {"unknown": "private"}, {"candidates": []},
    {"candidates": [{"id": "none_of_the_above", "text": "text"}]},
    {"candidates": [{"id": "needs_author_preference", "text": "text"}]},
    {"candidates": [{"id": "a", "text": "first"}, {"id": "a", "text": "second"}]},
    {"candidates": [{"id": "a", "text": "text", "unshared_metadata": "private"}]},
    {"questions": [{"id": "check", "question": "?"}, {"id": "check", "question": "?"}]},
])
def test_input_boundary_rejects_invalid_or_ambiguous_fields(tmp_path, payload, monkeypatch, patch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid input reached client")
    monkeypatch.setattr(brainstorm, "JevClient", forbidden)
    with pytest.raises(config.RuntimeConfigError):
        brainstorm.evaluate(config.set_mode(tmp_path, "jev"), {**payload, **patch})


def test_optional_context_and_checks_default_without_changing_input():
    payload = {"goal": "goal", "candidates": [{"id": "a", "text": "text"}]}
    original = deepcopy(payload)
    state = brainstorm.validate_input(payload)
    assert state["context"] == "" and state["questions"] == []
    assert state["constraints"] == [] and state["feedback"] == []
    assert payload == original
    assert set(brainstorm.build_questions(state)) == {"c0_disposition", "recommendation"}


def test_cli_evaluate_reports_status_and_failure_exit(tmp_path, payload, monkeypatch, capsys):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(payload))
    argv = ["brainstorm", "evaluate", "--work-dir", str(tmp_path), "--input", str(input_file)]
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"
    config.set_mode(tmp_path, "jev")
    monkeypatch.delenv("MUSE_JEV_API_KEY", raising=False)
    assert main(argv) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    successful_transport(monkeypatch)
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "evaluated"
    assert status(tmp_path)["recent"]["brainstorm"]["status"] == "evaluated"


def test_cli_guide_reads_packaged_resource_without_configuration(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("guide accessed configuration or credential")
    monkeypatch.setattr(config.os, "getenv", forbidden)
    assert main(["brainstorm", "guide"]) == 0
    output = capsys.readouterr().out
    assert "brainstorm evaluate" in output


def test_cli_invalid_input_and_missing_work_are_visible(tmp_path, capsys):
    input_file = tmp_path / "input.json"
    input_file.write_bytes(b"\xff")
    argv = ["brainstorm", "evaluate", "--work-dir", str(tmp_path), "--input", str(input_file)]
    assert main(argv) == 1
    assert "CONFIG_ERROR" in capsys.readouterr().err
    assert main(["brainstorm", "evaluate", "--work-dir", str(tmp_path / "missing"), "--input", str(input_file)]) == 1
    assert "work-dir" in capsys.readouterr().err


def test_unexpected_exception_propagates_in_library_and_is_sanitized_at_cli(tmp_path, payload, monkeypatch, capsys):
    monkeypatch.setenv("MUSE_JEV_API_KEY", "unit-test-secret")
    def transport(*args, **kwargs):
        raise RuntimeError("private request unit-test-secret")
    monkeypatch.setattr(client.urllib.request, "urlopen", transport)
    settings = config.set_mode(tmp_path, "jev")
    with pytest.raises(RuntimeError):
        brainstorm.evaluate(settings, payload)
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(payload))
    assert main(["brainstorm", "evaluate", "--work-dir", str(tmp_path), "--input", str(input_file)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "[muse RUNTIME_ERROR] RuntimeError"
