import json
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth as firebase_auth
from google.auth.exceptions import DefaultCredentialsError

from app import ai, auth, store, workflow
from app.main import app

PROJECT = {
    'title': 'Purchase Planning',
    'description': 'Coordinate office supplies.',
    'brief': 'Employees submit supply requests, managers approve and operations tracks delivery.',
    'business_domain': 'Operations',
    'client_name': 'Synthetic Client',
    'client_email': 'synthetic@example.com',
    'expected_timeline': '8 weeks',
    'additional_notes': 'Synthetic test project only.',
}


@pytest.fixture
def firebase_client(monkeypatch):
    monkeypatch.setenv('KATALYST_AUTH_MODE', 'firebase')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'synthetic-project')
    monkeypatch.delenv('FIREBASE_AUTH_EMULATOR_HOST', raising=False)
    monkeypatch.setattr(auth, 'firebase_app', lambda: object())
    monkeypatch.setattr(ai, 'PROVIDER', 'demo')

    def verify(token):
        if token not in ('alice-token', 'bob-token'):
            raise firebase_auth.InvalidIdTokenError('Invalid token')
        uid = token.removesuffix('-token')
        return {'uid': uid, 'email': uid + '@example.com', 'name': uid.title()}

    monkeypatch.setattr(auth, 'verify_token', verify)
    with TestClient(app) as client:
        yield client


def headers(user='alice'):
    return {'Authorization': 'Bearer ' + user + '-token'}


def test_profile_owner_metadata_and_dashboard(firebase_client):
    client = firebase_client
    assert client.get('/api/projects').status_code == 401
    assert client.get('/api/me', headers=headers()).json()['uid'] == 'alice'
    p = client.post('/api/projects', json=PROJECT,
                    headers={**headers(), 'X-Demo-User': 'bob'}).json()
    assert p['owner'] == 'alice'
    assert p['client_email'] == PROJECT['client_email']
    assert p['events'][0]['actor'] == 'alice'
    assert p['current_stage'] == 'Requirements intake'
    assert p['completion_percentage'] == 0
    assert p['resume_tab'] == 'capture'
    listing = client.get('/api/projects', headers=headers()).json()
    assert len(listing) == 1
    assert listing[0]['description'] == PROJECT['description']
    assert listing[0]['business_domain'] == 'Operations'
    assert listing[0]['created_at'] == p['created_at']
    assert client.get('/api/projects', headers=headers('bob')).json() == []
    with sqlite3.connect(store._path()) as db:
        profile = json.loads(db.execute('SELECT body FROM users WHERE uid=?', ('alice',)).fetchone()[0])
    assert profile['email'] == 'alice@example.com'


@pytest.mark.parametrize('method,path,body', [
    ('GET', '', None),
    ('POST', '/sources', None),
    ('POST', '/requirements/analyze', None),
    ('PUT', '/requirements', {'requirements': [{'id': 'REQ-001', 'text': 'Valid requirement'}]}),
    ('POST', '/stories/generate', None),
    ('PUT', '/stories', {'stories': [{'id': 'US-001', 'requirement_ids': ['REQ-001'],
                                     'role': 'user', 'goal': 'request', 'benefit': 'track',
                                     'acceptance_criteria': ['Given a request When approved Then track it']}]}),
    ('POST', '/prototype/generate', None),
    ('PUT', '/prototype', {'prototype': ai._default_prototype(PROJECT['brief'], []).model_dump()}),
    ('DELETE', '/prototype', None),
    ('POST', '/srs/generate', {'base_version': 0}),
    ('PUT', '/srs', {'base_version': 0, 'document': {
        'title': 'SRS', 'sections': [
            {'id': key, 'title': key, 'content': 'Clarification required'}
            for key in ['purpose','scope','functional','non_functional','interfaces','data','assumptions','acceptance']
        ]}}),
    ('POST', '/srs/approval', {'artifact_version': 1, 'decision': 'approved'}),
    ('GET', '/srs/pdf', None),
    ('GET', '/jira/preview', None),
    ('POST', '/jira/create', {'fingerprint': 'a'*64, 'confirmed': True}),
    ('POST', '/email/preview', {'recipients': ['alice@example.com'], 'subject': 'Handoff', 'body': 'Review attached'}),
    ('POST', '/voice/session', {'confirmed': True}),
    ('POST', '/email/send', {'recipients': ['alice@example.com'], 'subject': 'Handoff', 'body': 'Review attached', 'fingerprint': 'a'*64, 'confirmed': True}),
    ('POST', '/approvals/g0', {'artifact_version': 1, 'decision': 'approved'}),
    ('POST', '/approvals/g1', {'artifact_version': 1, 'decision': 'approved'}),
    ('POST', '/approvals/g2', {'artifact_version': 1, 'decision': 'approved'}),
    ('POST', '/demo/actions', {'action': 'submit', 'values': {}}),
    ('GET', '/export', None),
])
def test_every_project_surface_rejects_other_users(firebase_client, method, path, body):
    client = firebase_client
    p = client.post('/api/projects', json=PROJECT, headers=headers()).json()
    url = '/api/projects/' + p['id'] + path
    kwargs = {'files': {'file': ('evidence.txt', b'Synthetic evidence.', 'text/plain')}} if path == '/sources' else {}
    if body is not None:
        kwargs['json'] = body
    assert client.request(method, url, headers=headers('bob'), **kwargs).status_code == 404
    assert client.request(method, url, headers={'X-Demo-User': 'alice'}, **kwargs).status_code == 401
    assert client.get('/api/projects/' + p['id'], headers=headers()).json() == p


@pytest.mark.parametrize('error,status', [
    (firebase_auth.InvalidIdTokenError('bad'), 401),
    (firebase_auth.ExpiredIdTokenError('expired', cause=None), 401),
    (firebase_auth.RevokedIdTokenError('revoked'), 401),
    (firebase_auth.UserDisabledError('disabled'), 401),
    (firebase_auth.UserNotFoundError('deleted'), 401),
    (firebase_auth.CertificateFetchError('certificates unavailable', cause=None), 503),
    (DefaultCredentialsError('server credentials missing'), 503),
])
def test_invalid_sessions_fail_closed(firebase_client, monkeypatch, error, status):
    monkeypatch.setattr(auth, 'verify_token', Mock(side_effect=error))
    response = firebase_client.get('/api/projects', headers=headers())
    assert response.status_code == status
    assert 'server credentials missing' not in response.text


def test_id_tokens_are_checked_for_revocation(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(auth, 'firebase_app', lambda: sentinel)
    verifier = Mock(return_value={'uid': 'alice'})
    monkeypatch.setattr(firebase_auth, 'verify_id_token', verifier)
    assert auth.verify_token('synthetic-token') == {'uid': 'alice'}
    verifier.assert_called_once_with('synthetic-token', app=sentinel, check_revoked=True)


def test_project_resume_after_session_and_server_restart(firebase_client):
    client = firebase_client
    p = client.post('/api/projects', json=PROJECT, headers=headers()).json()
    base = '/api/projects/' + p['id']
    p = client.post(base + '/requirements/analyze', headers=headers()).json()
    p = client.post(base + '/approvals/g0', headers=headers(),
                    json={'artifact_version': p['requirements_version'], 'decision': 'approved'}).json()
    assert p['resume_tab'] == 'stories'
    assert p['completion_percentage'] == 33
    assert p['approvals']['g0']['reviewer'] == 'alice'
    assert client.get(base).status_code == 401
    with TestClient(app) as restarted:
        p = restarted.get(base, headers=headers()).json()
        assert p['resume_tab'] == 'stories'
        assert p['approvals']['g0']['decision'] == 'approved'
        p = restarted.post(base + '/stories/generate', headers=headers()).json()
        p = restarted.post(base + '/approvals/g1', headers=headers(),
                           json={'artifact_version': p['stories_version'], 'decision': 'approved'}).json()
        assert p['resume_tab'] == 'prototype'
        assert p['completion_percentage'] == 67
        p = restarted.put(base + '/requirements', headers=headers(),
                          json={'requirements': p['requirements'], 'open_questions': []}).json()
        assert p['resume_tab'] == 'capture'
        assert p['completion_percentage'] == 0
        assert p['approvals'] == {}


@pytest.mark.parametrize('invalid', [
    {'client_email': 'invalid'}, {'title': '   '}, {'brief': ' ' * 30},
    {'owner': 'bob'}, {'additional_notes': 'x' * 4001},
])
def test_project_metadata_validation(firebase_client, invalid):
    assert firebase_client.post('/api/projects', json=PROJECT | invalid,
                                headers=headers()).status_code == 422


def test_demo_mode_has_one_fixed_identity():
    with TestClient(app) as client:
        config = client.get('/api/config').json()
        assert config['demo_auth_only'] is True
        assert config['firebase'] is None
        p = client.post('/api/projects', json=PROJECT, headers={'X-Demo-User': 'spoofed'}).json()
        assert p['owner'] == 'demo-user'


def test_missing_or_unknown_auth_configuration_is_rejected(monkeypatch):
    monkeypatch.delenv('KATALYST_AUTH_MODE')
    assert auth.mode() == 'firebase'
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    with pytest.raises(RuntimeError, match='emulator'):
        auth.initialize()
    monkeypatch.setenv('KATALYST_AUTH_MODE', 'typo')
    with pytest.raises(RuntimeError, match='must be firebase or demo'):
        auth.initialize()


def test_legacy_sqlite_owner_index_migration(monkeypatch, tmp_path):
    path = tmp_path / 'legacy.sqlite'
    monkeypatch.setenv('KATALYST_DB', str(path))
    legacy = dict(PROJECT, id='legacy', owner='alice', updated_at='2026-01-01')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE projects(id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, body TEXT NOT NULL)')
        db.execute('INSERT INTO projects VALUES(?,?,?)', ('legacy', legacy['updated_at'], json.dumps(legacy)))
    store.initialize()
    assert store.all_projects('alice') == [legacy]
    assert store.all_projects('bob') == []


def test_firestore_adapter_uses_owner_filter_and_persists_projects(monkeypatch):
    monkeypatch.setenv('KATALYST_STORE', 'firestore')
    documents = {}
    collection = Mock()
    database = Mock()
    database.collection.return_value = collection

    def document(pid):
        reference = Mock()
        reference.set.side_effect = lambda data, **kwargs: documents.update({pid: dict(data)})
        reference.get.side_effect = lambda: Mock(exists=pid in documents, to_dict=lambda: documents.get(pid))
        return reference

    collection.document.side_effect = document

    def where(*, filter):
        assert filter.field_path == 'owner'
        assert filter.op_string == '=='
        query = Mock()
        query.stream.return_value = [Mock(to_dict=lambda p=p: dict(p))
                                     for p in documents.values() if p['owner'] == filter.value]
        return query

    collection.where.side_effect = where
    monkeypatch.setattr(store, 'firestore_client', lambda: database)
    store.save(dict(PROJECT, id='PRJ-A', owner='alice', updated_at='2026-01-01'))
    store.save(dict(PROJECT, id='PRJ-B', owner='bob', updated_at='2026-01-02'))
    assert store.get('PRJ-A')['owner'] == 'alice'
    assert [p['id'] for p in store.all_projects('alice')] == ['PRJ-A']
    store.save_user({'uid': 'uid/with/slash', 'email': None})
    collection.document.assert_called_with('uid%2Fwith%2Fslash')
    database.collection.assert_called_with('users')


@pytest.mark.parametrize('path', ['/api/me', '/api/projects'])
def test_firestore_failure_is_explicit_and_does_not_fall_back_to_sqlite(
        firebase_client, monkeypatch, path):
    monkeypatch.setenv('KATALYST_STORE', 'firestore')
    monkeypatch.setattr(store, 'firestore_client',
                        Mock(side_effect=DefaultCredentialsError('SENSITIVE CREDENTIAL DETAIL')))
    response = firebase_client.get(path, headers=headers())
    assert response.status_code == 503
    assert 'storage unavailable' in response.json()['detail']
    assert 'SENSITIVE' not in response.text


def test_default_storage_matches_auth_mode_and_unknown_storage_fails(monkeypatch):
    monkeypatch.delenv('KATALYST_STORE')
    assert store._is_firestore() is False
    monkeypatch.setenv('KATALYST_AUTH_MODE', 'firebase')
    assert store._is_firestore() is True
    monkeypatch.setenv('KATALYST_STORE', 'typo')
    with pytest.raises(RuntimeError, match='must be firestore or sqlite'):
        store.initialize()


def test_workflow_summary_requires_an_unbroken_approval_chain():
    project = {'requirements': [], 'stories': [], 'prototype': None,
               'approvals': {'g1': {'decision': 'approved'}, 'g2': {'decision': 'approved'}}}
    progress = workflow.summary(project)
    assert progress['completion_percentage'] == 0
    assert progress['resume_tab'] == 'capture'
    project['approvals'] = {g: {'decision': 'approved'} for g in ('g0', 'g1', 'g2')}
    assert workflow.summary(project)['completion_percentage'] == 100
    project['approvals']['g0']['decision'] = 'rejected'
    assert workflow.summary(project)['completion_percentage'] == 0
