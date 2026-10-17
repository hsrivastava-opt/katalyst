from copy import deepcopy
import io
import json
import zipfile
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app

REQUIREMENT = {'id': 'REQ-001', 'text': 'Staff shall submit maintenance requests.'}
STORY = {
    'id': 'US-001', 'requirement_ids': ['REQ-001'], 'role': 'staff',
    'goal': 'submit a request', 'benefit': 'track maintenance',
    'acceptance_criteria': ['Given a logged in member When they submit a request Then it is pending'],
}
PROTOTYPE = {
    'title': 'Maintenance', 'subtitle': 'Manual workflow', 'primary_color': '#2563eb',
    'concepts': [
        {'id': 'c1', 'name': 'Clear', 'description': 'First style', 'primaryColor': '#2563eb'},
        {'id': 'c2', 'name': 'Bold', 'description': 'Second style', 'primaryColor': '#7c3aed'},
    ],
    'screens': [
        {'id': 'intake', 'kind': 'intake', 'title': 'Request', 'fields': [
            {'id': 'summary', 'label': 'Summary', 'type': 'text', 'required': True},
        ]},
        {'id': 'approval', 'kind': 'approval', 'title': 'Review'},
        {'id': 'checklist', 'kind': 'checklist', 'title': 'Complete'},
    ],
}

def test_reordered_artifacts_persist_and_export_in_saved_order(manual_project):
    client, url, _ = manual_project
    requirements = [{**REQUIREMENT, 'id': 'REQ-002'}, REQUIREMENT]
    project = client.put(url + '/requirements', json={
        'requirements': requirements, 'open_questions': ['Second question', 'First question'],
    }).json()
    assert [r['id'] for r in client.get(url).json()['requirements']] == ['REQ-002', 'REQ-001']
    assert project['open_questions'] == ['Second question', 'First question']
    project = approve(client, url, project, 'g0', 'requirements_version')
    criteria = ['Given a request When approved Then notify staff', *STORY['acceptance_criteria']]
    stories = [{**STORY, 'id': 'US-002', 'acceptance_criteria': criteria}, STORY]
    project = client.put(url + '/stories', json={'stories': stories}).json()
    assert [s['id'] for s in client.get(url).json()['stories']] == ['US-002', 'US-001']
    assert project['stories'][0]['requirement_ids'] == ['REQ-001']
    project = approve(client, url, project, 'g1', 'stories_version')
    spec = deepcopy(PROTOTYPE)
    spec['concepts'].reverse()
    spec['screens'][0]['fields'].insert(0, {
        'id': 'priority', 'label': 'Priority', 'type': 'select', 'options': ['Urgent', 'Normal'],
    })
    project = client.put(url + '/prototype', json={'prototype': spec}).json()
    assert client.get(url).json()['prototype'] == project['prototype']
    project = approve(client, url, project, 'g2', 'prototype_version')
    with zipfile.ZipFile(io.BytesIO(client.get(url + '/export').content)) as package:
        requirements_md = package.read('requirements.md').decode()
        stories_md = package.read('stories.md').decode()
        feature = package.read('acceptance.feature').decode()
        assert requirements_md.index('REQ-002') < requirements_md.index('REQ-001')
        assert stories_md.index('US-002') < stories_md.index('US-001')
        assert feature.index(criteria[0]) < feature.index(criteria[1])
        prototype = json.loads(package.read('prototype.json'))
        assert prototype['concepts'][0]['id'] == 'c2'
        assert [f['id'] for f in prototype['screens'][0]['fields']] == ['priority', 'summary']
        assert prototype['screens'][0]['fields'][0]['options'] == ['Urgent', 'Normal']


def approve(client, url, project, gate, key):
    response = client.post(url + '/approvals/' + gate, json={
        'artifact_version': project[key], 'decision': 'approved',
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def manual_project(monkeypatch):
    # Manual creation must never consume Gemini quota, regardless of configured provider.
    for name in ('analyze', 'stories', 'prototype'):
        monkeypatch.setattr(ai, name, AsyncMock(side_effect=AssertionError('Unexpected AI call')))
    with TestClient(app) as client:
        project = client.post('/api/projects', json={
            'title': 'Manual maintenance', 'brief': 'Staff request repairs and facilities managers review requests.',
        }).json()
        url = '/api/projects/' + project['id']
        project = client.put(url + '/requirements', json={'requirements': [REQUIREMENT]}).json()
        project = approve(client, url, project, 'g0', 'requirements_version')
        project = client.put(url + '/stories', json={'stories': [STORY]}).json()
        project = approve(client, url, project, 'g1', 'stories_version')
        yield client, url, project


def test_manual_prototype_create_edit_delete_recreate_and_export(manual_project):
    client, url, project = manual_project
    response = client.put(url + '/prototype', json={'prototype': PROTOTYPE})
    assert response.status_code == 200, response.text
    project = response.json()
    assert project['prototype_provider'] == 'manual'
    assert project['prototype_version'] == 1
    assert project['events'][-1]['type'] == 'prototype.edited'
    assert client.get(url).json()['prototype'] == project['prototype']
    project = client.post(url + '/demo/actions', json={'action': 'submit', 'values': {'summary': 'Leaking tap'}}).json()
    assert len(project['demo_requests']) == 1
    project = approve(client, url, project, 'g2', 'prototype_version')
    assert client.get(url + '/export').status_code == 200

    edited = deepcopy(project['prototype'])
    edited['title'] = 'Facilities service'
    edited['screens'][0]['fields'].append({
        'id': 'priority', 'label': 'Priority', 'type': 'select', 'required': True,
        'options': ['Normal', 'Urgent'],
    })
    project = client.put(url + '/prototype', json={'prototype': edited}).json()
    assert project['prototype_version'] == 2
    assert project['demo_requests'] == []
    assert 'g2' not in project['approvals']
    assert {'g0', 'g1'} == set(project['approvals'])
    assert client.get(url + '/export').status_code == 409
    assert client.post(url + '/approvals/g2', json={'artifact_version': 1, 'decision': 'approved'}).status_code == 409
    assert client.post(url + '/demo/actions', json={'action': 'submit', 'values': {'summary': 'Broken chair'}}).status_code == 422
    project = approve(client, url, project, 'g2', 'prototype_version')
    edited['screens'][0]['fields'].pop()
    edited['screens'][0]['fields'][0]['label'] = 'Repair description'
    project = client.put(url + '/prototype', json={'prototype': edited}).json()
    assert len(project['prototype']['screens'][0]['fields']) == 1
    assert project['prototype_version'] == 3
    project = approve(client, url, project, 'g2', 'prototype_version')

    project = client.delete(url + '/prototype').json()
    assert project['prototype'] is None
    assert project['prototype_version'] == 4
    assert project['prototype_provider'] == ''
    assert project['events'][-1]['type'] == 'prototype.deleted'
    assert project['demo_requests'] == []
    assert 'g2' not in project['approvals']
    assert project['completion_percentage'] == 67
    assert client.get(url + '/export').status_code == 409
    assert client.post(url + '/approvals/g2', json={'artifact_version': 4, 'decision': 'approved'}).status_code == 409
    assert client.post(url + '/demo/actions', json={'action': 'submit'}).status_code == 409
    assert client.delete(url + '/prototype').status_code == 409
    project = client.put(url + '/prototype', json={'prototype': PROTOTYPE}).json()
    assert project['prototype_version'] == 5


@pytest.mark.parametrize('mutation', [
    lambda p: p['screens'].reverse(),
    lambda p: p['screens'].pop(),
    lambda p: p['concepts'].pop(),
    lambda p: p['screens'][0]['fields'].clear(),
    lambda p: p['screens'][0]['fields'].append(deepcopy(p['screens'][0]['fields'][0])),
    lambda p: p['screens'][0]['fields'][0].update(type='select', options=[]),
    lambda p: p['screens'][0]['fields'][0].update(type='select', options=['']),
    lambda p: p['screens'][0]['fields'][0].update(type='html'),
    lambda p: p['screens'][0]['fields'][0].update(unexpected='javascript'),
    lambda p: p['screens'][0]['fields'][0].update(label=' '),
    lambda p: p['screens'][1].update(fields=p['screens'][0]['fields']),
    lambda p: p['screens'][1].update(id='intake'),
    lambda p: p['concepts'][1].update(id='c1'),
    lambda p: p['concepts'][0].update(name=' '),
    lambda p: p.update(primary_color='invalid'),
    lambda p: p.update(title=' '),
])
def test_invalid_prototype_does_not_overwrite_saved_artifact(manual_project, mutation):
    client, url, _ = manual_project
    before = client.put(url + '/prototype', json={'prototype': PROTOTYPE}).json()
    changed = deepcopy(PROTOTYPE)
    mutation(changed)
    response = client.put(url + '/prototype', json={'prototype': changed})
    assert response.status_code == 422, response.text
    assert client.get(url).json() == before


def test_requirements_add_modify_delete_all_and_gate_invalidation(manual_project):
    client, url, _ = manual_project
    project = client.put(url + '/prototype', json={'prototype': PROTOTYPE}).json()
    project = approve(client, url, project, 'g2', 'prototype_version')
    client.post(url + '/demo/actions', json={'action': 'submit', 'values': {'summary': 'Test request'}})
    requirements = [{**REQUIREMENT, 'text': 'Staff shall submit repairs with location.'},
                    {**REQUIREMENT, 'id': 'REQ-002', 'text': 'Facilities shall review urgent repairs.'}]
    response = client.put(url + '/requirements', json={'requirements': requirements, 'open_questions': ['Who reviews?']})
    assert response.status_code == 200, response.text
    project = response.json()
    assert project['requirements_version'] == 2
    assert len(project['requirements']) == 2
    assert project['open_questions'] == ['Who reviews?']
    assert not project['stories'] and project['prototype'] is None
    assert project['approvals'] == {} and project['demo_requests'] == []
    assert project['prototype_provider'] == ''
    assert client.put(url + '/prototype', json={'prototype': PROTOTYPE}).status_code == 409
    assert client.delete(url + '/prototype').status_code == 409
    assert client.post(url + '/stories/generate').status_code == 409
    project = client.put(url + '/requirements', json={'requirements': []}).json()
    assert project['requirements'] == []
    assert client.get(url).json()['requirements'] == []
    assert client.post(url + '/approvals/g0', json={'artifact_version': 3, 'decision': 'approved'}).status_code == 409
    project = client.put(url + '/requirements', json={'requirements': [REQUIREMENT]}).json()
    assert project['requirements_version'] == 4
    approve(client, url, project, 'g0', 'requirements_version')


def test_stories_add_modify_delete_all_and_gate_invalidation(manual_project):
    client, url, _ = manual_project
    project = client.put(url + '/prototype', json={'prototype': PROTOTYPE}).json()
    project = approve(client, url, project, 'g2', 'prototype_version')
    client.post(url + '/demo/actions', json={'action': 'submit', 'values': {'summary': 'Test request'}})
    stories = [{**STORY, 'goal': 'submit a request with location', 'acceptance_criteria': [
        *STORY['acceptance_criteria'], 'Given no location When submitting Then show a validation error',
    ]}, {**STORY, 'id': 'US-002'}]
    response = client.put(url + '/stories', json={'stories': stories})
    assert response.status_code == 200, response.text
    project = response.json()
    assert project['stories_version'] == 2
    assert len(project['stories']) == 2
    assert len(project['stories'][0]['acceptance_criteria']) == 2
    assert set(project['approvals']) == {'g0'}
    assert project['prototype'] is None and project['demo_requests'] == []
    assert project['prototype_provider'] == ''
    assert client.post(url + '/prototype/generate').status_code == 409
    project = client.put(url + '/stories', json={'stories': []}).json()
    assert project['stories'] == []
    assert client.get(url).json()['stories'] == []
    assert client.post(url + '/approvals/g1', json={'artifact_version': 3, 'decision': 'approved'}).status_code == 409
    project = client.put(url + '/stories', json={'stories': [STORY]}).json()
    assert project['stories_version'] == 4
    approve(client, url, project, 'g1', 'stories_version')


@pytest.mark.parametrize('endpoint,body', [
    ('requirements', {'requirements': [REQUIREMENT, REQUIREMENT]}),
    ('requirements', {'requirements': [{**REQUIREMENT, 'source_id': 'SRC-999'}]}),
    ('requirements', {'requirements': [{**REQUIREMENT, 'text': '    '}]}),
    ('stories', {'stories': [STORY, STORY]}),
    ('stories', {'stories': [{**STORY, 'requirement_ids': ['REQ-999']}]}),
    ('stories', {'stories': [{**STORY, 'requirement_ids': []}]}),
    ('stories', {'stories': [{**STORY, 'acceptance_criteria': []}]}),
    ('stories', {'stories': [{**STORY, 'acceptance_criteria': ['Not a scenario']}]}),
    ('stories', {'stories': [{**STORY, 'role': ' '}]}),
])
def test_invalid_manual_edits_leave_saved_state_unchanged(manual_project, endpoint, body):
    client, url, before = manual_project
    assert client.put(url + '/' + endpoint, json=body).status_code == 422
    assert client.get(url).json() == before


def test_new_prototype_routes_require_g1_and_allow_cors(manual_project):
    client, url, project = manual_project
    client.put(url + '/stories', json={'stories': [STORY]})
    assert client.put(url + '/prototype', json={'prototype': PROTOTYPE}).status_code == 409
    assert client.delete(url + '/prototype').status_code == 409
    response = client.options(url + '/prototype', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'DELETE',
    })
    assert response.status_code == 200
    assert 'DELETE' in response.headers['access-control-allow-methods']
