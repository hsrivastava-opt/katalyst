import io, json, zipfile
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import ai

@pytest.fixture(autouse=True)
def demo_provider(monkeypatch):
    monkeypatch.setattr(ai,'PROVIDER','demo')
    monkeypatch.setenv('KATALYST_STORE','sqlite')

BRIEF='Build an employee onboarding portal where HR registers new employees, managers approve onboarding requests, and IT tracks laptop provisioning.'

def test_complete_hackathon_journey(tmp_path,monkeypatch):
    monkeypatch.setenv('KATALYST_DB',str(tmp_path/'test.sqlite'))
    monkeypatch.setenv('KATALYST_AI_PROVIDER','demo')
    with TestClient(app) as client:
        assert client.get('/api/health').json()['status']=='ok'
        p=client.post('/api/projects',json={'title':'Employee Onboarding','brief':BRIEF})
        assert p.status_code==201,p.text
        pid=p.json()['id']
        # Gate G0 must prevent bypassing approvals.
        assert client.post(f'/api/projects/{pid}/stories/generate').status_code==409
        r=client.post(f'/api/projects/{pid}/sources',files={'file':('hr-policy.txt',b'All users need an HR onboarding request.','text/plain')})
        assert r.status_code==200,r.text
        r=client.post(f'/api/projects/{pid}/requirements/analyze')
        assert r.status_code==200,r.text
        p=r.json()
        assert len(p['requirements'])>=3
        assert p['requirements'][0]['source_id']=='SRC-001'
        assert client.post(f'/api/projects/{pid}/approvals/g0',json={'artifact_version':999,'decision':'approved'}).status_code==409
        r=client.post(f'/api/projects/{pid}/approvals/g0',json={'artifact_version':p['requirements_version'],'decision':'approved'})
        assert r.status_code==200,r.text
        r=client.post(f'/api/projects/{pid}/stories/generate')
        assert r.status_code==200,r.text
        p=r.json()
        assert len(p['stories'])==len(p['requirements'])
        assert all(s['requirement_ids'] and 'Given' in s['acceptance_criteria'][0] for s in p['stories'])
        assert client.post(f'/api/projects/{pid}/prototype/generate').status_code==409
        p=client.post(f'/api/projects/{pid}/approvals/g1',json={'artifact_version':p['stories_version'],'decision':'approved'}).json()
        r=client.post(f'/api/projects/{pid}/prototype/generate')
        assert r.status_code==200,r.text
        p=r.json()
        assert len(p['prototype']['screens'])==3
        assert len(p['prototype']['concepts'])==2
        assert client.get(f'/api/projects/{pid}/export').status_code==409
        first={f['id']:'2026-11-07' if f['type']=='date' else ('hr@example.com' if f['type']=='email' else (f['options'][0] if f['type']=='select' else 'Sample Name')) for f in p['prototype']['screens'][0]['fields']}
        p=client.post(f'/api/projects/{pid}/demo/actions',json={'action':'submit','values':first}).json()
        request_id=p['demo_requests'][0]['id']
        assert p['demo_requests'][0]['status']=='pending'
        p=client.post(f'/api/projects/{pid}/demo/actions',json={'action':'approve','request_id':request_id}).json()
        assert p['demo_requests'][0]['status']=='approved'
        p=client.post(f'/api/projects/{pid}/demo/actions',json={'action':'toggle','request_id':request_id,'item':'Equipment assigned'}).json()
        assert p['demo_requests'][0]['checklist']['Equipment assigned'] is True
        p=client.post(f'/api/projects/{pid}/approvals/g2',json={'artifact_version':p['prototype_version'],'decision':'approved'}).json()
        assert p['status']=='prototype_approved'
        output=client.get(f'/api/projects/{pid}/export')
        assert output.status_code==200
        with zipfile.ZipFile(io.BytesIO(output.content)) as z:
            assert {'requirements.md','stories.md','acceptance.feature','prototype.json','traceability.json','approvals.json'}.issubset(set(z.namelist()))
            assert 'US-001' in z.read('stories.md').decode()
            assert 'GIVEN' in z.read('acceptance.feature').decode().upper()

def test_editing_invalidates_approvals(tmp_path,monkeypatch):
    monkeypatch.setenv('KATALYST_DB',str(tmp_path/'test2.sqlite'))
    with TestClient(app) as client:
        p=client.post('/api/projects',json={'title':'Test Employee Onboarding','brief':BRIEF}).json()
        pid=p['id']
        p=client.post(f'/api/projects/{pid}/requirements/analyze').json()
        p=client.post(f'/api/projects/{pid}/approvals/g0',json={'artifact_version':p['requirements_version'],'decision':'approved'}).json()
        edited=p['requirements'].copy()
        edited[0]={**edited[0],'text':'HR shall register an employee onboarding request with valid fields'}
        p=client.put(f'/api/projects/{pid}/requirements',json={'requirements':edited,'open_questions':p['open_questions']}).json()
        assert p['approvals']=={}
        assert client.post(f'/api/projects/{pid}/stories/generate').status_code==409

def test_upload_validation(tmp_path,monkeypatch):
    monkeypatch.setenv('KATALYST_DB',str(tmp_path/'test3.sqlite'))
    with TestClient(app) as client:
        p=client.post('/api/projects',json={'title':'Validation project','brief':BRIEF}).json()
        pid=p['id']
        assert client.post(f'/api/projects/{pid}/sources',files={'file':('malware.exe',b'MZ00','application/octet-stream')}).status_code==415
        assert client.post(f'/api/projects/{pid}/sources',files={'file':('big.txt',b'A'*6_000_001,'text/plain')}).status_code==413
