from __future__ import annotations

import io
import json
import urllib.error

import pytest

from muse_runtime import client, config, brainstorm

QUESTIONS = {'check': {'type': 'noul', 'instructions': 'Is this a greeting?'}}


def response(model=config.MODEL, *, nested=False):
    body = {'model': model, 'answers': {'check': {'type': 'noul', 'noul': .9}},
            'usage': {'input_tokens': 10, 'output_tokens': 2}}
    return io.BytesIO(json.dumps({'data': body} if nested else body).encode())


@pytest.fixture
def ready(tmp_path, monkeypatch):
    monkeypatch.setenv('MUSE_JEV_API_KEY', 'official-test-secret')
    monkeypatch.setenv('MUSE_JEV_TUZI_API_KEY', 'tuzi-test-secret')
    return config.set_mode(tmp_path, 'jev')


def failure(code, body=None):
    return urllib.error.HTTPError(client.ENDPOINT, code, 'private server message', {},
                                  io.BytesIO(json.dumps(body or {}).encode()))


def test_official_success_never_reads_or_calls_backup(ready, monkeypatch):
    calls = []
    def transport(request, timeout):
        calls.append(request.full_url)
        assert request.get_header('Authorization') == 'Bearer official-test-secret'
        return response()
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    monkeypatch.setattr(client, 'resolve_tuzi_key', lambda *_: pytest.fail('read backup on success'))
    result = client.JevClient(ready).evaluate({'text': 'hello'}, QUESTIONS)
    assert calls == [client.ENDPOINT]
    assert result['provider'] == 'typesafe'
    assert result['fallback_reason'] is None


@pytest.mark.parametrize('code,body,reason', [
    (402, None, 'quota_exhausted'), (429, None, 'rate_limited'),
    (403, {'error': {'code': 'insufficient_credits'}}, 'quota_exhausted'),
    (400, {'error': {'type': 'insufficient_quota'}}, 'quota_exhausted'),
    (403, {'detail': 'Insufficient credits. Please top up.'}, 'quota_exhausted'),
])
@pytest.mark.parametrize('nested', [False, True])
def test_fallback_preserves_request_maps_model_and_reuses_backup(ready, monkeypatch, code, body, reason, nested):
    calls = []
    state = {'text': 'private candidate'}
    def transport(request, timeout):
        payload = json.loads(request.data)
        calls.append((request.full_url, payload, timeout))
        if request.full_url == client.ENDPOINT:
            raise failure(code, body)
        assert request.get_header('Authorization') == 'Bearer tuzi-test-secret'
        return response('typesafe/jev-1.13-20260917', nested=nested)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    instance = client.JevClient(ready)
    result = instance.evaluate(state, QUESTIONS, timeout=3)
    again = instance.evaluate(state, QUESTIONS)
    assert [c[0] for c in calls] == [client.ENDPOINT, client.TUZI_ENDPOINT, client.TUZI_ENDPOINT]
    assert calls[0][1]['model'] == config.MODEL and calls[1][1]['model'] == client.TUZI_MODEL
    assert all(c[1]['state'] == state and c[1]['questions'] == QUESTIONS for c in calls)
    assert calls[1][2] <= 3
    assert result['provider'] == 'tuzi' and result['fallback_reason'] == reason
    assert result['model_requested'] == client.TUZI_MODEL
    assert [a['status'] for a in result['attempts']] == ['error', 'evaluated']
    assert again['attempts'][0]['provider'] == 'tuzi'
    log = (ready.work_dir / '.muse/jev-events.jsonl').read_text()
    assert 'private' not in log and 'secret' not in log
    # A new batch/command retries the higher-priority provider, allowing recovery.
    monkeypatch.setattr(client.urllib.request, 'urlopen', lambda *a, **k: response())
    assert client.JevClient(ready).evaluate(state, QUESTIONS)['provider'] == 'typesafe'


@pytest.mark.parametrize('code', [401, 403, 422, 500, 529])
def test_non_capacity_errors_do_not_switch(ready, monkeypatch, code):
    calls = []
    def transport(request, timeout):
        calls.append(request.full_url)
        raise failure(code)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match=f'http_{code}'):
        client.JevClient(ready).evaluate({}, QUESTIONS)
    assert calls == [client.ENDPOINT]


def test_missing_backup_preserves_official_failure(ready, monkeypatch):
    monkeypatch.delenv('MUSE_JEV_TUZI_API_KEY')
    def transport(*a, **k):
        raise failure(402)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match='http_402') as caught:
        client.JevClient(ready).evaluate({}, QUESTIONS)
    assert len(caught.value.attempts) == 1


def test_both_fail_once_without_loop_or_sensitive_output(ready, monkeypatch):
    calls = []
    def transport(request, timeout):
        calls.append(request.full_url)
        raise failure(402 if request.full_url == client.ENDPOINT else 429)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match='http_429') as caught:
        client.JevClient(ready).evaluate({}, QUESTIONS)
    assert calls == [client.ENDPOINT, client.TUZI_ENDPOINT]
    assert [a['provider'] for a in caught.value.attempts] == ['typesafe', 'tuzi']
    assert 'secret' not in str(caught.value) and 'private' not in str(caught.value)


def test_switch_shares_time_budget(ready, monkeypatch):
    ticks = iter([0., 2.])
    monkeypatch.setattr(client.time, 'monotonic', lambda: next(ticks))
    def transport(*a, **k):
        raise failure(402)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match='request_timeout'):
        client.JevClient(ready).evaluate({}, QUESTIONS, timeout=1)


def test_backup_does_not_truncate_large_payload(ready, monkeypatch):
    calls = []
    def transport(request, timeout):
        calls.append(request.full_url)
        raise failure(402)
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match='tuzi_payload_too_large'):
        client.JevClient(ready).evaluate({'text': '中' * 12000}, QUESTIONS)
    assert calls == [client.ENDPOINT]


def test_unexpected_backup_model_is_rejected(ready, monkeypatch):
    def transport(request, timeout):
        if request.full_url == client.ENDPOINT:
            raise failure(402)
        return response('unrelated-model')
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    with pytest.raises(client.JevError, match='unexpected_model'):
        client.JevClient(ready).evaluate({}, QUESTIONS)


def test_brainstorm_records_actual_backup_model_and_keeps_author_state(ready, monkeypatch):
    payload = {'goal': 'compare', 'candidates': [{'id': 'a', 'text': 'private draft'}]}
    def transport(request, timeout):
        if request.full_url == client.ENDPOINT:
            raise failure(402)
        questions = json.loads(request.data)['questions']
        answers = {}
        for name, question in questions.items():
            chosen = next(iter(question['criteria']))
            answers[name] = {'type': 'choice', 'choice': chosen,
                             'probabilities': {k: float(k == chosen) for k in question['criteria']}}
        return io.BytesIO(json.dumps({'model': 'typesafe/jev-1.13-20260917', 'answers': answers}).encode())
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    result = brainstorm.evaluate(ready, payload)
    assert result['provider'] == 'tuzi' and result['model_requested'] == client.TUZI_MODEL
    assert result['candidates'][0]['id'] == 'a'
    events = [json.loads(line) for line in (ready.work_dir / '.muse/jev-events.jsonl').read_text().splitlines()]
    assert events[-1]['node'] == 'brainstorm'
    assert events[-1]['model_requested'] == client.TUZI_MODEL
    assert events[-1]['provider'] == 'tuzi' and len(events[-1]['attempts']) == 2
    assert not (ready.work_dir / 'pipeline').exists()


def test_retrieval_consumes_fallback_and_records_provider(ready, monkeypatch):
    from muse_runtime import evaluation
    def transport(request, timeout):
        if request.full_url == client.ENDPOINT:
            raise failure(429)
        return io.BytesIO(json.dumps({'model': client.TUZI_MODEL, 'answers': {
            'fit': {'type': 'score', 'score': 2., 'probabilities': {'0': 0., '1': 0., '2': 1., '3': 0.}}}}).encode())
    monkeypatch.setattr(client.urllib.request, 'urlopen', transport)
    result = evaluation.rerank(ready, 'scene_retrieval', {'query': 'query'}, [{'id': 'a', 'material': 'text'}])
    assert result[0]['id'] == 'a' and result[0]['rank_score'] == 2.
    events = [json.loads(line) for line in (ready.work_dir / '.muse/jev-events.jsonl').read_text().splitlines()]
    assert events[-1]['providers'] == ['tuzi']
    assert events[-1]['actual_models'] == [client.TUZI_MODEL]
