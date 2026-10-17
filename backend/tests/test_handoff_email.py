import io
import json
import smtplib
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import ai, auth, handoff_email as mail, store
from app.main import app

DRAFT = {'recipients': ['registered@example.com'], 'subject': 'Approved handoff', 'body': 'Hello team,\nPlease review the attached ZIP.'}


@pytest.fixture
def configured(monkeypatch):
    for key, value in {'HOST': 'smtp.example.com', 'PORT': '465', 'USER': 'sender@example.com',
                       'PASSWORD': 'synthetic-password', 'FROM': 'sender@example.com', 'SECURITY': 'ssl'}.items():
        monkeypatch.setenv('KATALYST_SMTP_' + key, value)
    monkeypatch.setenv('KATALYST_EMAIL_ALLOWED_UIDS', 'demo-user')
    monkeypatch.setattr(ai, 'PROVIDER', 'demo')
    monkeypatch.setattr(mail, 'registered_recipient', lambda email: {'uid': email.lower(), 'email': email.lower()})
    with TestClient(app) as client:
        p = client.post('/api/projects', json={'title': 'Email trial', 'brief': 'Staff submit requests. Managers approve requests.'}).json()
        url = '/api/projects/' + p['id']
        p = client.post(url + '/requirements/analyze').json()
        p = client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'approved'}).json()
        p = client.post(url + '/stories/generate').json()
        p = client.post(url + '/approvals/g1', json={'artifact_version': p['stories_version'], 'decision': 'approved'}).json()
        p = client.post(url + '/prototype/generate').json()
        p = client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'approved'}).json()
        yield client, url, p


def preview(client, url, draft=None):
    result = client.post(url + '/email/preview', json=draft or DRAFT)
    assert result.status_code == 200, result.text
    return result.json()


def send(client, url, plan, draft=None):
    return client.post(url + '/email/send', json={**(draft or DRAFT), 'fingerprint': plan['fingerprint'], 'confirmed': True})


def test_exact_zip_preview_confirm_and_durable_duplicate_guard(configured, monkeypatch):
    client, url, p = configured
    transport = Mock()
    monkeypatch.setattr(mail, 'send_smtp', transport)
    plan = preview(client, url)
    assert plan['status'] == 'new'
    assert plan['from_email'] == 'sender@example.com'
    assert 'synthetic-password' not in json.dumps(plan)
    transport.assert_not_called()
    for confirmation in ({}, {'confirmed': False}):
        assert client.post(url + '/email/send', json={**DRAFT, 'fingerprint': plan['fingerprint'], **confirmation}).status_code == 422
    assert send(client, url, plan).json()['status'] == 'sent'
    archive = zipfile.ZipFile(io.BytesIO(transport.call_args.args[2]))
    downloaded = zipfile.ZipFile(io.BytesIO(client.get(url + '/export').content))
    assert {name: archive.read(name) for name in archive.namelist()} == {name: downloaded.read(name) for name in downloaded.namelist()}
    store.initialize()
    assert preview(client, url)['status'] == 'sent'
    assert send(client, url, plan).status_code == 200
    transport.assert_called_once()
    assert client.get(url).json() == p


def test_approved_srs_in_email_attachment(configured, monkeypatch):
    client, url, _ = configured
    p = client.post(url + '/srs/generate', json={'base_version': 0}).json()
    assert client.post(url + '/srs/approval', json={'artifact_version': p['srs_version'], 'decision': 'approved'}).status_code == 200
    transport = Mock()
    monkeypatch.setattr(mail, 'send_smtp', transport)
    plan = preview(client, url)
    assert 'srs.json' in plan['attachment_entries']
    assert send(client, url, plan).status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(transport.call_args.args[2]))
    assert json.loads(archive.read('srs.json'))['version'] == p['srs_version']
    assert json.loads(archive.read('srs-approval.json'))['artifact_version'] == p['srs_version']


@pytest.mark.parametrize('changes', [
    {'recipients': []}, {'recipients': ['a@example.com'] * 11},
    {'recipients': ['Name <a@example.com>']}, {'recipients': ['a@example.com\r\nBcc: other@example.com']},
    {'subject': 'Subject\nInjected'}, {'subject': ''}, {'subject': 'x' * 201},
    {'body': ''}, {'body': 'x' * 12001}, {'extra': True},
])
def test_invalid_drafts(configured, changes):
    client, url, _ = configured
    assert client.post(url + '/email/preview', json={**DRAFT, **changes}).status_code == 422


def test_stale_template_recipient_snapshot_and_gates(configured, monkeypatch):
    client, url, p = configured
    transport = Mock()
    monkeypatch.setattr(mail, 'send_smtp', transport)
    plan = preview(client, url)
    assert send(client, url, plan, {**DRAFT, 'body': 'Changed'}).status_code == 409
    assert send(client, url, plan, {**DRAFT, 'recipients': ['another@example.com']}).status_code == 409
    monkeypatch.setenv('KATALYST_SMTP_FROM', 'new@example.com')
    assert send(client, url, plan).status_code == 409
    monkeypatch.setenv('KATALYST_SMTP_FROM', 'sender@example.com')
    p['open_questions'].append('New context')
    store.save(p)
    assert send(client, url, plan).status_code == 409
    client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'rejected'})
    assert client.post(url + '/email/preview', json=DRAFT).status_code == 409
    assert send(client, url, plan).status_code == 409
    transport.assert_not_called()


def test_configuration_allowlist_and_unregistered_user(configured, monkeypatch):
    client, url, _ = configured
    monkeypatch.setenv('KATALYST_EMAIL_ALLOWED_UIDS', 'someone-else')
    assert client.post(url + '/email/preview', json=DRAFT).status_code == 403
    monkeypatch.setenv('KATALYST_EMAIL_ALLOWED_UIDS', 'demo-user')
    monkeypatch.delenv('KATALYST_SMTP_PASSWORD')
    assert client.post(url + '/email/preview', json=DRAFT).status_code == 409
    monkeypatch.setenv('KATALYST_SMTP_PASSWORD', 'synthetic-password')
    monkeypatch.setattr(mail, 'registered_recipient', Mock(side_effect=HTTPException(422, 'Recipient not registered')))
    assert client.post(url + '/email/preview', json=DRAFT).status_code == 422


def test_uncertain_and_storage_failure_never_blindly_retry(configured, monkeypatch):
    client, url, _ = configured
    transport = Mock(side_effect=HTTPException(502, 'Uncertain SMTP outcome'))
    monkeypatch.setattr(mail, 'send_smtp', transport)
    plan = preview(client, url)
    assert send(client, url, plan).status_code == 502
    assert preview(client, url)['status'] == 'blocked'
    assert send(client, url, plan).status_code == 409
    transport.assert_called_once()
    other = {**DRAFT, 'subject': 'Separate test delivery'}
    transport.reset_mock(side_effect=True)
    monkeypatch.setattr(store, 'finish_delivery', Mock(side_effect=store.PersistenceError('Storage unavailable')))
    plan = preview(client, url, other)
    assert send(client, url, plan, other).status_code == 503
    assert preview(client, url, other)['status'] == 'pending'
    assert send(client, url, plan, other).status_code == 409
    transport.assert_called_once()


def test_gate_revoked_after_claim_blocks_smtp(configured, monkeypatch):
    client, url, p = configured
    original = store.claim_delivery
    def revoke(kind, key, entry):
        claimed = original(kind, key, entry)
        p['approvals']['g2']['decision'] = 'rejected'
        store.save(p)
        return claimed
    monkeypatch.setattr(store, 'claim_delivery', revoke)
    transport = Mock()
    monkeypatch.setattr(mail, 'send_smtp', transport)
    assert send(client, url, preview(client, url)).status_code == 409
    transport.assert_not_called()


def test_concurrent_email_claims(configured):
    _, _, p = configured
    entry = {'project_id': p['id'], 'status': 'pending'}
    with ThreadPoolExecutor(max_workers=6) as workers:
        results = list(workers.map(lambda _: store.claim_delivery('email', 'synthetic-key', entry), range(12)))
    assert sum(results) == 1


def test_firestore_email_delivery_claim_and_persistence(monkeypatch):
    from google.api_core.exceptions import AlreadyExists
    monkeypatch.setenv('KATALYST_STORE', 'firestore')
    collection, reference = Mock(), Mock()
    collection.document.return_value.collection.return_value.document.return_value = reference
    monkeypatch.setattr(store, '_collection', lambda: collection)
    entry = {'project_id': 'synthetic', 'status': 'pending'}
    reference.create.side_effect = [None, AlreadyExists('claimed')]
    assert store.claim_delivery('email', 'key', entry)
    assert not store.claim_delivery('email', 'key', entry)
    store.finish_delivery('email', 'key', entry)
    reference.get.return_value.exists = True
    reference.get.return_value.to_dict.return_value = entry
    assert store.delivery('email', 'key') == entry
    reference.set.assert_called_once_with(entry)
    collection.document.assert_called_with('_email_deliveries')


def test_recipient_deduplication_and_revalidation(configured, monkeypatch):
    client, url, _ = configured
    plan = preview(client, url, {**DRAFT, 'recipients': ['registered@example.com', 'REGISTERED@example.com']})
    assert plan['recipients'] == ['registered@example.com']
    plan = preview(client, url)
    monkeypatch.setattr(mail, 'registered_recipient', Mock(side_effect=HTTPException(422, 'Recipient disabled')))
    transport = Mock()
    monkeypatch.setattr(mail, 'send_smtp', transport)
    assert send(client, url, plan).status_code == 422
    transport.assert_not_called()


@pytest.mark.parametrize('key,value', [('SECURITY', 'none'), ('PORT', '0'), ('PORT', 'abc'),
                                     ('FROM', 'Sender <sender@example.com>'), ('HOST', 'https://smtp.example.com')])
def test_invalid_smtp_configuration(configured, monkeypatch, key, value):
    client, url, _ = configured
    monkeypatch.setenv('KATALYST_SMTP_' + key, value)
    assert client.post(url + '/email/preview', json=DRAFT).status_code == 409


def test_message_size_limit_precedes_network(configured, monkeypatch):
    client, url, _ = configured
    factory = Mock()
    monkeypatch.setattr(smtplib, 'SMTP_SSL', factory)
    with pytest.raises(HTTPException) as error:
        mail.send_smtp(mail.configuration('demo-user'), preview(client, url), b'x' * 15_000_000)
    assert error.value.status_code == 413
    factory.assert_not_called()


@pytest.mark.parametrize('security', ['ssl', 'starttls'])
def test_smtp_tls_bcc_mime_attachment_and_errors(configured, monkeypatch, security):
    client, url, _ = configured
    monkeypatch.setenv('KATALYST_SMTP_SECURITY', security)
    smtp = Mock()
    smtp.send_message.return_value = {}
    factory = MagicMock()
    factory.return_value.__enter__.return_value = smtp
    monkeypatch.setattr(smtplib, 'SMTP_SSL' if security == 'ssl' else 'SMTP', factory)
    plan = preview(client, url)
    config = mail.configuration('demo-user')
    mail.send_smtp(config, plan, b'synthetic-zip')
    if security == 'starttls':
        smtp.starttls.assert_called_once()
        assert [call[0] for call in smtp.method_calls] == ['ehlo', 'starttls', 'ehlo', 'login', 'send_message']
    message = smtp.send_message.call_args.args[0]
    assert message['To'] == 'undisclosed-recipients:;'
    assert message['Bcc'] is None
    assert smtp.send_message.call_args.kwargs['to_addrs'] == DRAFT['recipients']
    assert list(message.iter_attachments())[0].get_payload(decode=True) == b'synthetic-zip'
    smtp.send_message.return_value = {'registered@example.com': (550, b'private diagnostic')}
    with pytest.raises(HTTPException):
        mail.send_smtp(config, plan, b'synthetic-zip')
    smtp.send_message.side_effect = smtplib.SMTPAuthenticationError(535, b'synthetic-password')
    with pytest.raises(HTTPException) as error:
        mail.send_smtp(config, plan, b'synthetic-zip')
    assert error.value.status_code == 502
    assert 'synthetic-password' not in str(error.value.detail)


@pytest.mark.parametrize('disabled,email', [(False, 'registered@example.com'), (True, 'registered@example.com'), (False, None)])
def test_firebase_registered_recipient_contract(monkeypatch, disabled, email):
    from firebase_admin import auth as firebase_auth
    monkeypatch.setattr(auth, 'mode', lambda: 'firebase')
    sentinel = object()
    monkeypatch.setattr(auth, 'firebase_app', lambda: sentinel)
    lookup = Mock(return_value=SimpleNamespace(uid='registered', email=email, disabled=disabled))
    monkeypatch.setattr(firebase_auth, 'get_user_by_email', lookup)
    if disabled or not email:
        with pytest.raises(HTTPException) as error:
            mail.registered_recipient('registered@example.com')
        assert error.value.status_code == 422
    else:
        assert mail.registered_recipient(email) == {'uid': 'registered', 'email': email}
        lookup.assert_called_once_with(email, app=sentinel)


def test_firebase_missing_service_failure_and_demo_rejection(monkeypatch):
    from firebase_admin import auth as firebase_auth
    from firebase_admin.exceptions import FirebaseError
    monkeypatch.setattr(auth, 'mode', lambda: 'firebase')
    monkeypatch.setattr(auth, 'firebase_app', lambda: None)
    for failure, expected in [(firebase_auth.UserNotFoundError('missing'), 422), (FirebaseError('internal', 'private diagnostic'), 503)]:
        monkeypatch.setattr(firebase_auth, 'get_user_by_email', Mock(side_effect=failure))
        with pytest.raises(HTTPException) as error:
            mail.registered_recipient('registered@example.com')
        assert error.value.status_code == expected
        assert 'private diagnostic' not in error.value.detail
    monkeypatch.setattr(auth, 'mode', lambda: 'demo')
    with pytest.raises(HTTPException) as error:
        mail.registered_recipient('registered@example.com')
    assert error.value.status_code == 409
