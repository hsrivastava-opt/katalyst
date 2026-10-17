import asyncio
from copy import deepcopy
import io
import json
import zipfile
import unicodedata
from unittest.mock import AsyncMock
from types import SimpleNamespace

import fitz
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app import ai, srs, store
from app.main import app
from app.models import SRSDocument

BRIEF = 'Staff submit repair requests. Facilities managers review repairs and technicians record completion.'
REQS = [
    {'id': 'REQ-001', 'text': 'Staff shall submit repair requests.', 'source_id': 'SRC-001'},
    {'id': 'REQ-002', 'text': 'Managers shall review repair requests.', 'source_id': 'SRC-001'},
]


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(ai, 'PROVIDER', 'demo')
    with TestClient(app) as client:
        p = client.post('/api/projects', json={'title': 'Facilities planning', 'brief': BRIEF}).json()
        url = '/api/projects/' + p['id']
        p = client.put(url + '/requirements', json={'requirements': REQS, 'open_questions': ['Who can review urgent repairs?']}).json()
        p = client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'approved'}).json()
        yield client, url, p


def generate(client, url, version=0):
    response = client.post(url + '/srs/generate', json={'base_version': version})
    assert response.status_code == 200, response.text
    return response.json()


def review(client, url, p, decision='approved'):
    response = client.post(url + '/srs/approval', json={
        'artifact_version': p['srs_version'], 'decision': decision, 'note': 'Reviewed all sections and open questions.',
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_srs_review_revisions_approval_and_pdf(ready, monkeypatch):
    client, url, before = ready
    p = generate(client, url)
    assert p['srs']['provider'] == 'demo'
    assert p['srs']['version'] == p['srs_version'] == 1
    assert p['srs']['requirements_version'] == before['requirements_version']
    assert [section['id'] for section in p['srs']['document']['sections']] == [key for key, _ in srs.SECTIONS]
    assert 'DETERMINISTIC DEMO' in p['srs']['document']['sections'][0]['content']
    assert p['srs_revisions'] == [p['srs']]
    for key in ('status', 'completion_percentage', 'resume_tab', 'approvals', 'stories', 'prototype'):
        assert p[key] == before[key]
    assert client.get(url + '/srs/pdf').status_code == 409
    p = review(client, url, p, 'rejected')
    assert client.get(url + '/srs/pdf').status_code == 409
    document = deepcopy(p['srs']['document'])
    document['sections'][0]['content'] += '\nReviewed by facilities lead.'
    monkeypatch.setattr(ai, 'srs', AsyncMock(side_effect=AssertionError('Manual edit called AI')))
    response = client.put(url + '/srs', json={'base_version': 1, 'document': document})
    assert response.status_code == 200, response.text
    p = response.json()
    assert p['srs_version'] == 2 and p['srs_approval'] is None
    assert p['srs']['provider'] == 'manual'
    assert len(p['srs_revisions']) == 2
    assert p['srs_revisions'][0]['document'] != document
    assert client.post(url + '/srs/approval', json={'artifact_version': 1, 'decision': 'approved'}).status_code == 409
    p = review(client, url, p)
    assert p['srs_approval']['reviewer'] == 'demo-user'
    response = client.get(url + '/srs/pdf')
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/pdf'
    assert 'SRS-v2.pdf' in response.headers['content-disposition']
    with fitz.open(stream=response.content, filetype='pdf') as pdf:
        text = ''.join(page.get_text() for page in pdf)
        assert 'Facilities planning - SRS' in text
        assert 'Reviewed by facilities lead.' in text
        assert 'REQ-001' in text and 'SRC-001' in text
        assert 'demo-user' in text
    assert client.get(url).json() == p
    assert [event['type'] for event in p['events']][-3:] == ['srs.rejected', 'srs.revision.saved', 'srs.approved']


@pytest.mark.parametrize('operation', ['save', 'analyze', 'upload'])
def test_upstream_changes_invalidate_srs_but_preserve_history(ready, operation):
    client, url, _ = ready
    p = review(client, url, generate(client, url))
    if operation == 'save':
        response = client.put(url + '/requirements', json={'requirements': REQS, 'open_questions': []})
    elif operation == 'analyze':
        response = client.post(url + '/requirements/analyze')
    else:
        response = client.post(url + '/sources', files={'file': ('policy.txt', b'Managers review urgent repairs.', 'text/plain')})
    assert response.status_code == 200, response.text
    current = client.get(url).json()
    assert current['srs'] is None and current['srs_approval'] is None
    assert current['srs_revisions'] == p['srs_revisions']
    assert current['srs_version'] == 1
    assert client.get(url + '/srs/pdf').status_code == 409
    assert client.post(url + '/srs/approval', json={'artifact_version': 1, 'decision': 'approved'}).status_code == 409
    if current['requirements']:
        client.post(url + '/approvals/g0', json={'artifact_version': current['requirements_version'], 'decision': 'approved'})
        updated = generate(client, url, 1)
        assert updated['srs_version'] == 2
        assert len(updated['srs_revisions']) == 2


def test_optional_srs_does_not_block_existing_journey_and_edits_do_not_clear_gates(ready):
    client, url, p = ready
    p = client.post(url + '/stories/generate').json()
    p = client.post(url + '/approvals/g1', json={'artifact_version': p['stories_version'], 'decision': 'approved'}).json()
    p = client.post(url + '/prototype/generate').json()
    p = client.post(url + '/approvals/g2', json={'artifact_version': p['prototype_version'], 'decision': 'approved'}).json()
    assert p['srs'] is None
    assert client.get(url + '/export').status_code == 200
    before = deepcopy(p)
    p = generate(client, url)
    p = review(client, url, p)
    with zipfile.ZipFile(io.BytesIO(client.get(url + '/export').content)) as package:
        assert json.loads(package.read('srs.json')) == p['srs']
        assert json.loads(package.read('srs-approval.json')) == p['srs_approval']
    document = deepcopy(p['srs']['document'])
    document['title'] = 'Updated SRS'
    p = client.put(url + '/srs', json={'base_version': 1, 'document': document}).json()
    for key in ('approvals', 'status', 'stories', 'prototype', 'completion_percentage', 'resume_tab'):
        assert p[key] == before[key]
    assert client.get(url + '/export').status_code == 200
    with zipfile.ZipFile(io.BytesIO(client.get(url + '/export').content)) as package:
        assert 'srs.json' not in package.namelist()
    client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'rejected'})
    assert client.get(url + '/srs/pdf').status_code == 409
    assert client.get(url).json()['srs_approval'] is None


@pytest.mark.parametrize('failure,status', [
    (RuntimeError('Model unavailable'), 502),
    (ai.AIQuotaError('Quota exhausted'), 429),
    (ValueError('Invalid SRS content'), 502),
])
def test_srs_generation_failure_preserves_artifacts(ready, monkeypatch, failure, status):
    client, url, _ = ready
    before = review(client, url, generate(client, url))
    monkeypatch.setattr(ai, 'srs', AsyncMock(side_effect=failure))
    response = client.post(url + '/srs/generate', json={'base_version': 1})
    assert response.status_code == status
    assert client.get(url).json() == before


@pytest.mark.parametrize('mutation', [
    lambda d: d['sections'].reverse(),
    lambda d: d['sections'].pop(),
    lambda d: d['sections'][0].update(content=' '),
    lambda d: d['sections'][0].update(requirement_ids=['REQ-999']),
    lambda d: d['sections'][0].update(source_ids=['SRC-999']),
    lambda d: d['sections'][2].update(requirement_ids=[]),
    lambda d: d['sections'][0].update(id='scope'),
    lambda d: [section.update(content='a'*4000) for section in d['sections']],
])
def test_invalid_srs_edits_leave_approval_and_history_intact(ready, mutation):
    client, url, _ = ready
    before = review(client, url, generate(client, url))
    document = deepcopy(before['srs']['document'])
    mutation(document)
    response = client.put(url + '/srs', json={'base_version': 1, 'document': document})
    assert response.status_code == 422, response.text
    assert client.get(url).json() == before


def test_versions_limits_legacy_projects_and_pdf_failure(ready, monkeypatch):
    client, url, p = ready
    # Old persisted projects receive additive defaults without a destructive migration.
    legacy = store.get(p['id'])
    for key in ('srs', 'srs_version', 'srs_revisions', 'srs_approval'):
        legacy.pop(key)
    store.save(legacy)
    assert client.get(url).json()['srs_revisions'] == []
    p = generate(client, url)
    assert client.post(url + '/srs/generate', json={'base_version': 0}).status_code == 409
    assert client.put(url + '/srs', json={'base_version': 0, 'document': p['srs']['document']}).status_code == 409
    for version in range(1, 10):
        response = client.put(url + '/srs', json={'base_version': version, 'document': p['srs']['document']})
        assert response.status_code == 200, response.text
    before = client.get(url).json()
    assert before['srs_version'] == 10
    generator = AsyncMock(side_effect=AssertionError('Limit should be checked before calling AI'))
    monkeypatch.setattr(ai, 'srs', generator)
    assert client.post(url + '/srs/generate', json={'base_version': 10}).status_code == 409
    assert client.put(url + '/srs', json={'base_version': 10, 'document': p['srs']['document']}).status_code == 409
    generator.assert_not_awaited()
    assert client.get(url).json() == before
    before = review(client, url, before)
    monkeypatch.setattr(srs, 'pdf', lambda _: (_ for _ in ()).throw(RuntimeError('render failure')))
    assert client.get(url + '/srs/pdf').status_code == 500
    assert client.get(url).json() == before


def test_history_byte_limit_preserves_current_approval(ready, monkeypatch):
    client, url, _ = ready
    before = review(client, url, generate(client, url))
    monkeypatch.setattr(srs, 'MAX_HISTORY_BYTES', 100)
    response = client.put(url + '/srs', json={'base_version': 1, 'document': before['srs']['document']})
    assert response.status_code == 409
    assert 'storage limit' in response.json()['detail']
    assert client.get(url).json() == before


def test_pdf_paginates_and_escapes_user_content(ready):
    client, url, _ = ready
    p = generate(client, url)
    document = deepcopy(p['srs']['document'])
    document['title'] = 'R\u00e9vision - Facilities <b>plain text</b>'
    document['sections'][0]['content'] = '<script>alert("not executable")</script>\n' + ('Reviewed repair evidence and open questions. ' * 100)
    document['sections'][1]['content'] = 'Scope boundary reviewed. ' * 200
    p = client.put(url + '/srs', json={'base_version': 1, 'document': document}).json()
    review(client, url, p)
    response = client.get(url + '/srs/pdf')
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype='pdf') as pdf:
        assert len(pdf) > 1
        text = unicodedata.normalize('NFKC', ''.join(page.get_text() for page in pdf))
        assert '<b>plain text</b>' in text
        assert '<script>' in text and '</script>' in text
        assert 'R\u00e9vision' in text
        assert 'Acceptance and verification' in text
        assert f'Page {len(pdf)}/{len(pdf)}' in text


def test_srs_prompt_contains_grounding_and_typed_schema(ready, monkeypatch):
    client, url, p = ready
    output = asyncio.run(ai.srs(p))
    structured = AsyncMock(return_value=output)
    monkeypatch.setattr(ai, 'PROVIDER', 'gemini')
    monkeypatch.setattr(ai, '_structured', structured)
    result = generate(client, url)
    assert result['srs']['provider'] == 'gemini'
    prompt, schema = structured.call_args.args
    assert schema is SRSDocument
    assert 'REQ-001' in prompt and 'SRC-001' in prompt
    assert 'Who can review urgent repairs?' in prompt
    assert 'Do not invent' in prompt
    from google import genai
    from google.genai import _transformers
    with genai.Client(api_key='synthetic-test-key', vertexai=False) as sdk:
        wire = _transformers.t_schema(sdk._api_client, SRSDocument).model_dump(mode='json', exclude_none=True, by_alias=True)
    assert 'additional_properties' not in json.dumps(wire)
    assert 'additionalProperties' not in json.dumps(wire)
    for keyword in ('minLength', 'maxLength', 'minItems', 'maxItems'):
        assert keyword not in json.dumps(wire)
    fields = wire['properties']['sections']['items']['properties']
    assert fields['id']['enum'] == [key for key, _ in srs.SECTIONS]
    assert fields['content']['type'] == 'STRING'


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(title='x' * 161),
    lambda d: d['sections'].pop(),
    lambda d: d['sections'].append(deepcopy(d['sections'][0])),
    lambda d: d['sections'][0].update(title='x' * 121),
    lambda d: d['sections'][0].update(content='x' * 6001),
    lambda d: d['sections'][0].update(content=' '),
    lambda d: d['sections'][0].update(requirement_ids=['REQ-001'] * 31),
    lambda d: d['sections'][0].update(source_ids=['SRC-001'] * 51),
])
def test_simplified_srs_generation_schema_keeps_runtime_limits(ready, mutation):
    _, _, project = ready
    document = asyncio.run(ai.srs(project)).model_dump()
    mutation(document)
    with pytest.raises(ValidationError):
        SRSDocument.model_validate(document)

def test_adk_srs_uses_typed_output_without_live_credentials(ready, monkeypatch):
    _, _, project = ready
    output = asyncio.run(ai.srs(project))
    from google.adk.models import google_llm
    from google.genai import types
    response = types.GenerateContentResponse(candidates=[
        types.Candidate(content=types.Content(
            role='model', parts=[types.Part(text=output.model_dump_json())]), finish_reason='STOP'),
    ])
    generate_content = AsyncMock(return_value=response)
    client = SimpleNamespace(vertexai=False, aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(google_llm, 'Client', lambda **_: client)
    monkeypatch.setattr(ai, 'PROVIDER', 'adk')
    result = asyncio.run(ai.srs(project))
    assert result == output
    assert generate_content.call_args.kwargs['config'].response_schema is SRSDocument


def test_generation_detects_upstream_change_while_waiting(ready, monkeypatch):
    client, url, p = ready
    output = asyncio.run(ai.srs(p))
    async def generate_and_change(_):
        changed = store.get(p['id'])
        changed['requirements_version'] += 1
        store.save(changed)
        return output
    monkeypatch.setattr(ai, 'srs', generate_and_change)
    response = client.post(url + '/srs/generate', json={'base_version': 0})
    assert response.status_code == 409
    assert client.get(url).json()['srs_version'] == 0


def test_srs_g0_required_even_with_valid_document(ready):
    client, url, p = ready
    document = asyncio.run(ai.srs(p)).model_dump()
    client.post(url + '/approvals/g0', json={'artifact_version': p['requirements_version'], 'decision': 'rejected'})
    assert client.post(url + '/srs/generate', json={'base_version': 0}).status_code == 409
    assert client.put(url + '/srs', json={'base_version': 0, 'document': document}).status_code == 409
    assert client.post(url + '/srs/approval', json={'artifact_version': 1, 'decision': 'approved'}).status_code == 409
    assert client.get(url + '/srs/pdf').status_code == 409
