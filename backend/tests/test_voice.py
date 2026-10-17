import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.genai.errors import APIError
from httpx import ConnectError

from app import ai, auth, store, voice
from app.main import app


@pytest.fixture
def pilot(monkeypatch):
    monkeypatch.setenv('KATALYST_LIVE_ENABLED', 'true')
    monkeypatch.setenv('KATALYST_LIVE_ALLOWED_UIDS', 'demo-user')
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    monkeypatch.setattr(ai, 'PROVIDER', 'demo')
    with TestClient(app) as client:
        p = client.post('/api/projects', json={'title': 'Voice trial', 'brief': 'Employees submit requests. Managers approve requests.'}).json()
        url = '/api/projects/' + p['id']
        p = client.post(url + '/requirements/analyze').json()
        p = client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'approved'}).json()
        p = client.post(url + '/stories/generate').json()
        monkeypatch.setattr(auth, 'mode', lambda: 'firebase')
        app.dependency_overrides[auth.current_user] = lambda: 'demo-user'
        try:
            yield client, url, p
        finally:
            app.dependency_overrides.clear()


def test_token_scope_snapshot_confirmation_cache_and_no_mutation(pilot, monkeypatch):
    client, url, p = pilot
    mint = Mock(return_value='auth_tokens/synthetic')
    monkeypatch.setattr(voice, 'mint_token', mint)
    assert client.post(url + '/voice/session', json={}).status_code == 422
    assert client.post(url + '/voice/session', json={'confirmed': False}).status_code == 422
    assert client.post(url + '/voice/session', json={'confirmed': True, 'model': 'arbitrary'}).status_code == 422
    response = client.post(url + '/voice/session', json={'confirmed': True})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()
    assert data['token'] == 'auth_tokens/synthetic'
    assert data['model'] == 'gemini-3.8-live'
    assert data['api_version'] == 'v1alpha'
    assert data['session_seconds'] == 180
    assert data['context']['counts']['requirements'] == len(p['requirements'])
    assert data['context']['counts']['user_stories'] == len(p['stories'])
    assert data['context']['approvals']['g0'] == {'decision': 'approved', 'current': True}
    assert data['context']['approvals']['g1']['decision'] == 'not_reviewed'
    assert 'synthetic-private-key' not in response.text
    assert 'owner' not in data['context']
    assert 'client_email' not in data['context']
    assert 'events' not in data['context']
    assert client.post(url + '/voice/session', json={'confirmed': True}).status_code == 429
    mint.assert_called_once()
    assert store.get(p['id']) == p


@pytest.mark.parametrize('setting,value,status', [
    ('KATALYST_LIVE_ENABLED', 'false', 409),
    ('KATALYST_LIVE_ALLOWED_UIDS', 'other-user', 403),
    ('KATALYST_LIVE_MODEL', ' ', 409),
    ('KATALYST_LIVE_MODEL', 'models/arbitrary', 409),
])
def test_pilot_gates(pilot, monkeypatch, setting, value, status):
    client, url, _ = pilot
    monkeypatch.setenv(setting, value)
    mint = Mock()
    monkeypatch.setattr(voice, 'mint_token', mint)
    assert client.post(url + '/voice/session', json={'confirmed': True}).status_code == status
    mint.assert_not_called()


def test_demo_and_missing_key_block_real_tokens(pilot, monkeypatch):
    client, url, _ = pilot
    monkeypatch.setattr(auth, 'mode', lambda: 'demo')
    assert client.post(url + '/voice/session', json={'confirmed': True}).status_code == 409
    monkeypatch.setattr(auth, 'mode', lambda: 'firebase')
    for name in ('KATALYST_LIVE_API_KEY', 'GOOGLE_API_KEY', 'GEMINI_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    assert client.post(url + '/voice/session', json={'confirmed': True}).status_code == 409


def test_context_oversize_explicit_omission_and_counts(pilot):
    _, _, p = pilot
    p['requirements'][0]['text'] = 'x' * 100_000
    context = voice.project_context(p)
    assert context['details_omitted']
    assert context['requirements'] == []
    assert context['counts']['requirements'] == len(p['requirements'])
    assert len(json.dumps(context).encode()) <= voice.MAX_CONTEXT_BYTES
    assert any('No engineering task backlog' in limitation for limitation in context['limitations'])


def test_cooldown_cross_worker_account_scope_and_restart(pilot):
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: store.claim_voice_slot('uid', 1000, 300), range(12)))
    assert sum(results) == 1
    store.initialize()
    assert not store.claim_voice_slot('uid', 1299, 300)
    assert store.claim_voice_slot('uid', 1300, 300)
    assert store.claim_voice_slot('another-uid', 1000, 300)


def test_firestore_voice_cooldown_is_transactional(monkeypatch):
    from google.cloud import firestore
    monkeypatch.setenv('KATALYST_STORE', 'firestore')
    client = Mock()
    reference = client.collection.return_value.document.return_value.collection.return_value.document.return_value
    transaction = client.transaction.return_value
    reference.get.return_value.exists = False
    monkeypatch.setattr(store, 'firestore_client', lambda: client)
    decorator = Mock(side_effect=lambda function: function)
    monkeypatch.setattr(firestore, 'transactional', decorator)
    assert store.claim_voice_slot('uid', 1000, 300)
    transaction.set.assert_called_once_with(reference, {'last_started': 1000})
    reference.get.assert_called_with(transaction=transaction)
    reference.get.return_value.exists = True
    reference.get.return_value.to_dict.return_value = {'last_started': 1000}
    transaction.reset_mock()
    assert not store.claim_voice_slot('uid', 1200, 300)
    transaction.set.assert_not_called()
    assert store.claim_voice_slot('uid', 1300, 300)
    assert decorator.call_count == 3


def test_constrained_single_use_token_expiry_and_grounded_context(pilot, monkeypatch):
    from google import genai
    _, _, p = pilot
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.auth_tokens.create.return_value = SimpleNamespace(name='auth_tokens/synthetic')
    monkeypatch.setattr(genai, 'Client', factory)
    timestamp = datetime.now(timezone.utc)
    assert voice.mint_token('synthetic-private-key', 'gemini-3.8-live', voice.project_context(p), timestamp) == 'auth_tokens/synthetic'
    config = client.auth_tokens.create.call_args.kwargs['config']
    assert config.uses == 1
    assert (config.expire_time - timestamp).total_seconds() == 180
    assert (config.new_session_expire_time - timestamp).total_seconds() == 45
    assert config.lock_additional_fields is None
    constraints = config.live_connect_constraints
    assert constraints.model == 'gemini-3.8-live'
    assert constraints.config.tools == []
    assert constraints.config.max_output_tokens == 1024
    assert p['requirements'][0]['text'] in constraints.config.system_instruction
    assert 'untrusted data' in constraints.config.system_instruction
    assert 'cannot perform any changes' in constraints.config.system_instruction
    assert factory.call_args.kwargs['vertexai'] is False
    assert factory.call_args.kwargs['http_options'].retry_options.attempts == 1


@pytest.mark.parametrize('error,status', [
    (APIError(402, {'error': {'message': 'synthetic-private-key'}}), 502),
    (APIError(403, {'error': {'message': 'synthetic-private-key'}}), 502),
    (APIError(429, {'error': {'message': 'synthetic-private-key'}}), 429),
    (ConnectError('synthetic-private-key'), 502),
])
def test_token_failure_safe_error_and_consumed_cooldown(pilot, monkeypatch, error, status):
    from google import genai
    client, url, _ = pilot
    factory = MagicMock()
    factory.return_value.__enter__.return_value.auth_tokens.create.side_effect = error
    monkeypatch.setattr(genai, 'Client', factory)
    response = client.post(url + '/voice/session', json={'confirmed': True})
    assert response.status_code == status
    assert 'synthetic-private-key' not in response.text
    assert client.post(url + '/voice/session', json={'confirmed': True}).status_code == 429


def test_invalid_ephemeral_token_is_explicit(pilot, monkeypatch):
    from google import genai
    _, _, p = pilot
    factory = MagicMock()
    factory.return_value.__enter__.return_value.auth_tokens.create.return_value = SimpleNamespace(name=None)
    monkeypatch.setattr(genai, 'Client', factory)
    with pytest.raises(HTTPException) as error:
        voice.mint_token('synthetic', 'gemini-3.8-live', voice.project_context(p), datetime.now(timezone.utc))
    assert error.value.status_code == 502


def test_token_request_serializes_with_installed_sdk(pilot, monkeypatch):
    from google import genai
    _, _, p = pilot
    with genai.Client(api_key='synthetic-private-key', vertexai=False) as client:
        request = Mock(return_value=SimpleNamespace(body='{"name":"auth_tokens/synthetic"}'))
        monkeypatch.setattr(client._api_client, 'request', request)
        monkeypatch.setattr(genai, 'Client', lambda **kwargs: client)
        assert voice.mint_token('synthetic-private-key', 'gemini-3.8-live',
                                voice.project_context(p), datetime.now(timezone.utc)) == 'auth_tokens/synthetic'
        assert request.call_args.args[:2] == ('post', 'auth_tokens')
        wire = request.call_args.args[2]
        assert wire['uses'] == 1
        assert 'bidiGenerateContentSetup' in wire
        assert 'synthetic-private-key' not in json.dumps(wire)
