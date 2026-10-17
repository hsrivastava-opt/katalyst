import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import pytest
from google.genai.errors import APIError
from httpx import ConnectError

spec = importlib.util.spec_from_file_location('check_live', Path(__file__).parents[1] / 'check_live.py')
check_live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_live)


def test_discovers_by_action_not_model_name():
    client = MagicMock()
    client.models.list.return_value = [
        SimpleNamespace(name='models/voice', supported_actions=['bidiGenerateContent']),
        SimpleNamespace(name='models/live-name-only', supported_actions=['generateContent']),
        SimpleNamespace(name='models/other', supported_actions=None),
    ]
    assert check_live.live_candidates(client) == ['models/voice']


def test_missing_key_sends_no_request(monkeypatch, capsys):
    from google import genai
    factory = MagicMock()
    monkeypatch.setattr(genai, 'Client', factory)
    for name in ('KATALYST_LIVE_API_KEY', 'GOOGLE_API_KEY', 'GEMINI_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    assert check_live.main([]) == 1
    factory.assert_not_called()
    assert 'No request was sent' in capsys.readouterr().err


def test_stdin_key_private_and_discovery_only(monkeypatch, capsys):
    from google import genai
    monkeypatch.setattr('sys.stdin', io.StringIO('synthetic-private-key\n'))
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.list.return_value = [
        SimpleNamespace(name='models/voice', supported_actions=['bidiGenerateContent'])]
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main(['--key-stdin']) == 0
    output = capsys.readouterr()
    assert 'synthetic-private-key' not in output.out + output.err
    assert 'models/voice' in output.out
    assert 'does not prove free-tier eligibility' in output.out
    client.models.generate_content.assert_not_called()
    client.auth_tokens.create.assert_not_called()
    assert factory.call_args.kwargs['vertexai'] is False
    assert factory.call_args.kwargs['http_options'].retry_options.attempts == 1


@pytest.mark.parametrize('error,expected', [
    (APIError(402, {'error': {'message': 'synthetic-private-key'}}), 'HTTP 402'),
    (APIError(429, {'error': {'message': 'synthetic-private-key'}}), 'HTTP 429'),
    (ConnectError('synthetic-private-key'), 'could not connect'),
])
def test_discovery_errors_are_explicit_and_redacted(monkeypatch, capsys, error, expected):
    from google import genai
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    factory.return_value.__enter__.return_value.models.list.side_effect = error
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main([]) == 1
    output = capsys.readouterr()
    assert expected in output.err
    assert 'synthetic-private-key' not in output.out + output.err


def test_no_live_models_is_not_success(monkeypatch, capsys):
    from google import genai
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    factory.return_value.__enter__.return_value.models.list.return_value = []
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main([]) == 1
    assert 'No models advertising' in capsys.readouterr().err


def test_opt_in_connection_sends_no_content(monkeypatch, capsys):
    from google import genai
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.list.return_value = [
        SimpleNamespace(name='models/gemini-3.8-live', supported_actions=['bidiGenerateContent'])]
    connection = client.aio.live.connect.return_value
    session = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=session)
    connection.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main(['--connect-test']) == 0
    connection.__aenter__.assert_awaited_once()
    connection.__aexit__.assert_awaited_once()
    session.assert_not_called()
    assert not session.method_calls
    assert 'Live connection accepted and closed' in capsys.readouterr().out


def test_connect_rejects_unlisted_model(monkeypatch, capsys):
    from google import genai
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    factory.return_value.__enter__.return_value.models.list.return_value = []
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main(['--connect-test']) == 1
    factory.return_value.__enter__.return_value.aio.live.connect.assert_not_called()
    assert 'does not advertise' in capsys.readouterr().err


def test_live_websocket_error_redacts_upstream_details(monkeypatch, capsys):
    from google import genai
    from websockets.exceptions import WebSocketException
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.models.list.return_value = [
        SimpleNamespace(name='models/gemini-3.8-live', supported_actions=['bidiGenerateContent'])]
    connection = client.aio.live.connect.return_value
    connection.__aenter__ = AsyncMock(side_effect=WebSocketException('synthetic-private-key'))
    connection.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(genai, 'Client', factory)
    assert check_live.main(['--connect-test']) == 1
    error = capsys.readouterr().err
    assert 'rejected or closed' in error
    assert 'synthetic-private-key' not in error


def test_ephemeral_mode_is_explicit_and_redacted(monkeypatch, capsys):
    from google import genai
    from unittest.mock import Mock
    monkeypatch.setenv('KATALYST_LIVE_API_KEY', 'synthetic-private-key')
    factory = MagicMock()
    factory.return_value.__enter__.return_value.models.list.return_value = [
        SimpleNamespace(name='models/gemini-3.8-live', supported_actions=['bidiGenerateContent'])]
    monkeypatch.setattr(genai, 'Client', factory)
    probe = Mock()
    monkeypatch.setattr(check_live, 'check_ephemeral', probe)
    assert check_live.main(['--ephemeral-test']) == 0
    probe.assert_called_once_with('synthetic-private-key', 'gemini-3.8-live')
    output = capsys.readouterr()
    assert 'Constrained ephemeral-token connection accepted' in output.out
    assert 'synthetic-private-key' not in output.out + output.err


def test_ephemeral_probe_uses_short_lived_token_and_no_real_project(monkeypatch):
    from google import genai
    from app import voice
    from unittest.mock import Mock
    factory = MagicMock()
    mint = Mock(return_value='auth_tokens/synthetic')
    connect = AsyncMock()
    monkeypatch.setattr(voice, 'mint_token', mint)
    monkeypatch.setattr(genai, 'Client', factory)
    monkeypatch.setattr(check_live, 'check_connection', connect)
    check_live.check_ephemeral('synthetic-private-key', 'gemini-3.8-live')
    assert factory.call_args.kwargs['api_key'] == 'auth_tokens/synthetic'
    assert factory.call_args.kwargs['http_options'].api_version == 'v1alpha'
    assert mint.call_args.args[2] == {'test': 'Synthetic read-only connection test; no real project data'}
    connect.assert_awaited_once_with(factory.return_value.__enter__.return_value, 'gemini-3.8-live')
