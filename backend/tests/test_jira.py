import io
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from app import ai, jira, store
from app.main import app


@pytest.fixture
def configured(monkeypatch):
    for name, value in {
        'KATALYST_JIRA_SITE': 'https://synthetic-team.atlassian.net',
        'KATALYST_JIRA_PROJECT_KEY': 'KAT', 'KATALYST_JIRA_EMAIL': 'service@example.com',
        'KATALYST_JIRA_API_TOKEN': 'synthetic-secret', 'KATALYST_JIRA_ISSUE_TYPE_ID': '10001',
        'KATALYST_JIRA_ALLOWED_UIDS': 'demo-user',
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(ai, 'PROVIDER', 'demo')
    with TestClient(app) as client:
        p = client.post('/api/projects', json={'title': 'Jira trial', 'brief': 'Staff submit requests. Managers approve requests.'}).json()
        url = '/api/projects/' + p['id']
        p = client.post(url + '/requirements/analyze').json()
        p = client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'approved'}).json()
        p = client.post(url + '/stories/generate').json()
        p = client.post(url + '/approvals/g1', json={'artifact_version': p['stories_version'], 'decision': 'approved'}).json()
        p = client.post(url + '/prototype/generate').json()
        p = client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'approved'}).json()
        yield client, url, p


def preview(client, url):
    response = client.get(url + '/jira/preview')
    assert response.status_code == 200, response.text
    return response.json()


def create(client, url, plan):
    return client.post(url + '/jira/create', json={'fingerprint': plan['fingerprint'], 'confirmed': True})


def test_preview_confirmation_creation_and_duplicate_prevention(configured, monkeypatch):
    client, url, project = configured
    send = Mock(side_effect=['KAT-1', 'KAT-2'])
    monkeypatch.setattr(jira, 'create_issue', send)
    plan = preview(client, url)
    assert len(plan['tickets']) == len(project['stories']) == 2
    assert plan['destination']['project_key'] == 'KAT'
    assert 'Given' in plan['tickets'][0]['description']
    assert 'REQ-001' in plan['tickets'][0]['description']
    assert 'synthetic-secret' not in json.dumps(plan)
    send.assert_not_called()
    assert client.post(url + '/jira/create', json={'fingerprint': plan['fingerprint'], 'confirmed': False}).status_code == 422
    assert client.post(url + '/jira/create', json={'fingerprint': plan['fingerprint']}).status_code == 422
    response = create(client, url, plan)
    assert response.status_code == 200, response.text
    assert [item['issue_key'] for item in response.json()['tickets']] == ['KAT-1', 'KAT-2']
    assert all(item['status'] == 'created' for item in preview(client, url)['tickets'])
    assert create(client, url, plan).status_code == 200
    assert send.call_count == 2
    assert client.get(url).json() == project


def test_missing_configuration_and_shared_account_authorization(configured, monkeypatch):
    client, url, _ = configured
    monkeypatch.delenv('KATALYST_JIRA_API_TOKEN')
    assert 'not configured' in client.get(url + '/jira/preview').json()['detail']
    monkeypatch.setenv('KATALYST_JIRA_API_TOKEN', 'synthetic-secret')
    monkeypatch.setenv('KATALYST_JIRA_ALLOWED_UIDS', 'someone-else')
    assert 'not authorized' in client.get(url + '/jira/preview').json()['detail']


@pytest.mark.parametrize('site', ['http://example.atlassian.net', 'https://localhost', 'https://example.atlassian.net/other',
                                 'https://example.atlassian.net:443', 'https://example.atlassian.net@evil.example'])
def test_untrusted_destinations_rejected(configured, monkeypatch, site):
    client, url, _ = configured
    monkeypatch.setenv('KATALYST_JIRA_SITE', site)
    assert client.get(url + '/jira/preview').status_code == 409


def test_stale_preview_and_gates(configured, monkeypatch):
    client, url, p = configured
    send = Mock()
    monkeypatch.setattr(jira, 'create_issue', send)
    plan = preview(client, url)
    monkeypatch.setenv('KATALYST_JIRA_PROJECT_KEY', 'OTHER')
    assert create(client, url, plan).status_code == 409
    monkeypatch.setenv('KATALYST_JIRA_PROJECT_KEY', 'KAT')
    client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'rejected'})
    assert client.get(url + '/jira/preview').status_code == 409
    assert create(client, url, plan).status_code == 409
    send.assert_not_called()


def test_partial_delivery_blocks_retry_and_preserves_created_keys(configured, monkeypatch):
    client, url, _ = configured
    send = Mock(side_effect=['KAT-1', jira.JiraError('Uncertain outcome; check Jira')])
    monkeypatch.setattr(jira, 'create_issue', send)
    plan = preview(client, url)
    assert create(client, url, plan).status_code == 409
    after = preview(client, url)
    assert after['tickets'][0]['issue_key'] == 'KAT-1'
    assert after['tickets'][1]['status'] == 'blocked'
    assert create(client, url, after).status_code == 409
    assert send.call_count == 2


def test_created_ticket_then_storage_failure_remains_pending(configured, monkeypatch):
    client, url, _ = configured
    send = Mock(return_value='KAT-1')
    monkeypatch.setattr(jira, 'create_issue', send)
    monkeypatch.setattr(store, 'finish_jira_delivery', Mock(side_effect=store.PersistenceError('Storage unavailable')))
    plan = preview(client, url)
    assert create(client, url, plan).status_code == 503
    assert preview(client, url)['tickets'][0]['status'] == 'pending'
    assert create(client, url, plan).status_code == 409
    send.assert_called_once()


def test_changed_story_keeps_existing_mapping(configured, monkeypatch):
    client, url, p = configured
    send = Mock(side_effect=['KAT-1', 'KAT-2'])
    monkeypatch.setattr(jira, 'create_issue', send)
    plan = preview(client, url)
    assert create(client, url, plan).status_code == 200
    modified = deepcopy(p['stories'])
    modified[0]['goal'] = 'submit a request with a location'
    p = client.put(url + '/stories', json={'stories': modified}).json()
    client.post(url + '/approvals/g1', json={'artifact_version': p['stories_version'], 'decision': 'approved'})
    p = client.post(url + '/prototype/generate').json()
    client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'approved'})
    current = preview(client, url)
    assert current['tickets'][0]['changed'] is True
    assert current['tickets'][0]['issue_key'] == 'KAT-1'
    assert create(client, url, current).status_code == 200
    assert send.call_count == 2
    assert create(client, url, plan).status_code == 409


def test_atomic_claim_across_connections(configured):
    _, _, p = configured
    entry = {'project_id': p['id'], 'status': 'pending'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: store.claim_jira_delivery('one-key', entry), range(4)))
    assert outcomes.count(True) == 1
    assert store.jira_delivery('one-key') == entry


def test_revoked_approval_stops_remaining_deliveries(configured, monkeypatch):
    client, url, p = configured
    plan = preview(client, url)
    def revoke_after_first(config, ticket):
        changed = store.get(p['id'])
        changed['approvals']['g2']['decision'] = 'rejected'
        store.save(changed)
        return 'KAT-1'
    send = Mock(side_effect=revoke_after_first)
    monkeypatch.setattr(jira, 'create_issue', send)
    assert create(client, url, plan).status_code == 409
    send.assert_called_once()
    assert store.jira_delivery(plan['tickets'][0]['delivery_id'])['issue_key'] == 'KAT-1'
    assert store.jira_delivery(plan['tickets'][1]['delivery_id']) is None


def test_delivery_links_survive_storage_reinitialization(configured, monkeypatch):
    client, url, _ = configured
    send = Mock(side_effect=['KAT-1', 'KAT-2'])
    monkeypatch.setattr(jira, 'create_issue', send)
    plan = preview(client, url)
    assert create(client, url, plan).status_code == 200
    store.initialize()
    assert [ticket['issue_key'] for ticket in preview(client, url)['tickets']] == ['KAT-1', 'KAT-2']
    assert create(client, url, plan).status_code == 200
    assert send.call_count == 2


def test_firestore_claim_uses_create_and_handles_conflict(configured, monkeypatch):
    from google.api_core.exceptions import AlreadyExists
    monkeypatch.setenv('KATALYST_STORE', 'firestore')
    reference = Mock()
    collection = Mock()
    collection.document.return_value.collection.return_value.document.return_value = reference
    monkeypatch.setattr(store, '_collection', lambda: collection)
    reference.create.side_effect = [None, AlreadyExists('claimed')]
    entry = {'project_id': 'test'}
    assert store.claim_jira_delivery('key', entry) is True
    assert store.claim_jira_delivery('key', entry) is False
    store.finish_jira_delivery('key', entry)
    reference.set.assert_called_once_with(entry)
    reference.get.return_value.exists = True
    reference.get.return_value.to_dict.return_value = entry
    assert store.jira_delivery('key') == entry


def test_rest_transport_adf_auth_and_safe_response(configured, monkeypatch):
    _, _, p = configured
    config = jira.configuration('demo-user')
    ticket = jira.plan(p, config)['tickets'][0]
    response = io.BytesIO(b'{"key":"KAT-123","self":"https://do-not-trust.example"}')
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(jira, 'build_opener', lambda *_: opener)
    assert jira.create_issue(config, ticket) == 'KAT-123'
    request = opener.open.call_args.args[0]
    assert request.full_url == 'https://synthetic-team.atlassian.net/rest/api/3/issue'
    assert request.get_header('Authorization').startswith('Basic ')
    payload = json.loads(request.data)
    assert payload['fields']['description']['type'] == 'doc'
    assert payload['fields']['issuetype'] == {'id': '10001'}
    assert 'katalyst-' + ticket['delivery_id'] in payload['fields']['labels']
    assert jira.NoRedirect().redirect_request(None, None, None, None, None, None) is None


@pytest.mark.parametrize('error', [
    HTTPError('https://example', 400, 'synthetic-secret', {}, None),
    URLError('synthetic-secret'), TimeoutError('synthetic-secret'),
])
def test_transport_errors_are_explicit_without_leaking_credentials(configured, monkeypatch, error):
    _, _, p = configured
    config = jira.configuration('demo-user')
    opener = Mock()
    opener.open.side_effect = error
    monkeypatch.setattr(jira, 'build_opener', lambda *_: opener)
    with pytest.raises(jira.JiraError) as failure:
        jira.create_issue(config, jira.plan(p, config)['tickets'][0])
    assert 'synthetic-secret' not in str(failure.value)


@pytest.mark.parametrize('body', [b'not json', b'{}', b'{"key":"OTHER-1"}', b'[]'])
def test_invalid_jira_success_response_is_not_claimed_as_success(configured, monkeypatch, body):
    _, _, p = configured
    config = jira.configuration('demo-user')
    opener = Mock()
    opener.open.return_value = io.BytesIO(body)
    monkeypatch.setattr(jira, 'build_opener', lambda *_: opener)
    with pytest.raises(jira.JiraError):
        jira.create_issue(config, jira.plan(p, config)['tickets'][0])
