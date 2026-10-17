"""KATALYST API with Firebase ownership checks and an explicit local demo mode."""
from __future__ import annotations
import io, json, os, re, uuid, zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import fitz
from . import store, ai, auth, workflow, srs, jira, handoff_email
from .models import ProjectCreate, RequirementsUpdate, StoriesUpdate, ApprovalCreate, DemoAction, Requirement, Story, PrototypeSpec, PrototypeUpdate, validate_prototype
from .models import SRSGenerate, SRSUpdate, JiraCreate, HandoffEmailDraft, HandoffEmailSend

MAX_UPLOAD=6_000_000

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.initialize()
    store.initialize()
    yield

app=FastAPI(title='KATALYST Hackathon MVP',version='0.2.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in os.getenv('KATALYST_CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')],allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['*'])

@app.exception_handler(store.PersistenceError)
async def storage_unavailable(request, exc):
    return JSONResponse(status_code=503,content={'detail':str(exc)})

def read_project(pid, user_id):
    p=store.get(pid)
    if p is None or p.get('owner') != user_id: raise HTTPException(404,'Project not found')
    for key, value in (('srs', None), ('srs_version', 0), ('srs_revisions', []), ('srs_approval', None)):
        p.setdefault(key, value)
    p.update(workflow.summary(p))
    return p

def commit(p):
    p['updated_at']=now(); p.update(workflow.summary(p)); store.save(p)
    return p

def audit(p,event,actor='demo-user',detail=None):
    p['events'].append({'id':uuid.uuid4().hex[:10],'type':event,'actor':actor,'detail':detail or {},'at':now()})

def require(p,gate):
    if not p['approvals'].get(gate,{}).get('decision')=='approved':
        raise HTTPException(409,f'Approval {gate.upper()} is required first')

def validate_requirements(reqs):
    ids=[r['id'] for r in reqs]
    if any(not id.strip() for id in ids):raise HTTPException(422,'Requirement IDs must not be empty')
    if len(ids)!=len(set(ids)): raise HTTPException(422,'Requirement IDs must be unique')

def validate_stories(stories,reqs):
    ids={r['id'] for r in reqs}
    seen=set()
    for s in stories:
        if not s['id'].strip():raise HTTPException(422,'Story IDs must not be empty')
        if s['id'] in seen: raise HTTPException(422,'Story IDs must be unique')
        seen.add(s['id'])
        if not set(s['requirement_ids']).issubset(ids):raise HTTPException(422,f"Story {s['id']} references nonexistent requirements")
        for c in s['acceptance_criteria']:
            if not all(re.search(r'\b'+key+r'\b',c,re.I) for key in ['Given','When','Then']):
                raise HTTPException(422,f"Story {s['id']} needs Given/When/Then criteria")

@app.get('/api/health')
def health():return {'status':'ok','service':'KATALYST','time':now()}

@app.get('/api/config')
def config():return {**ai.provider_info(),'demo_auth_only':auth.mode()=='demo',
                     'auth_mode':auth.mode(),'firebase':auth.public_config() if auth.mode()=='firebase' else None,
                     'scope':'foundation + prototype workflow + optional SRS review/PDF + confirmed Jira REST and SMTP handoff; Gmail OAuth/architecture/sprint automation pending'}

@app.get('/api/me')
def me(user=Depends(auth.authenticated_user)):
    profile={**user,'last_seen_at':now()}
    store.save_user(profile)
    return profile

@app.get('/api/projects')
def projects(user_id:str=Depends(auth.current_user)):
    return [workflow.project_summary(p) for p in store.all_projects(user_id)]

@app.post('/api/projects',status_code=201)
def create(body: ProjectCreate,user_id: str = Depends(auth.current_user)):
    pid='PRJ-'+uuid.uuid4().hex[:8].upper()
    timestamp=now()
    p={'id':pid,**body.model_dump(),'owner':user_id, 'status':'draft','created_at':timestamp,'updated_at':timestamp,'sources':[{'id':'SRC-001','name':'Original business brief','text':body.brief,'page_map':[{'page':1,'text':body.brief[:1600]}],'type':'brief'}],'requirements':[],'requirements_version':0,'open_questions':[],'potential_conflicts':[],'stories':[],'stories_version':0,'assumptions':[],'prototype':None,'prototype_version':0,'prototype_provider':'','approvals':{},'events':[],'demo_requests':[],'metrics':{}}
    p.update(srs=None, srs_version=0, srs_revisions=[], srs_approval=None)
    audit(p,'project.created',user_id,{'source':'user brief'})
    return commit(p)

@app.get('/api/projects/{pid}')
def get_project(pid:str,user_id:str=Depends(auth.current_user)):return read_project(pid,user_id)

@app.post('/api/projects/{pid}/sources')
async def upload_source(pid:str, file:UploadFile=File(...),user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id)
    raw=await file.read(MAX_UPLOAD+1)
    if len(raw)>MAX_UPLOAD:raise HTTPException(413,'File too large (maximum 6 MB)')
    name=Path(file.filename or 'document').name[:160]
    ext=Path(name).suffix.lower()
    pages=[]
    if ext=='.pdf':
        try:
            doc=fitz.open(stream=raw,filetype='pdf')
            if len(doc)>50:raise HTTPException(413,'PDF exceeds 50-page demo limit')
            pages=[{'page':i+1,'text':page.get_text('text')[:1500]} for i,page in enumerate(doc)]
            doc.close()
        except HTTPException:raise
        except Exception as exc:raise HTTPException(422,'Could not extract text from PDF') from exc
    elif ext in ('.txt','.md'):
        try: pages=[{'page':1,'text':raw.decode('utf-8-sig')[:20000]}]
        except UnicodeDecodeError as exc:raise HTTPException(422,'Text must be UTF-8') from exc
    else:raise HTTPException(415,'Supported formats: PDF, TXT, MD')
    sid=f'SRC-{len(p["sources"])+1:03d}'
    source={'id':sid,'name':name,'type':ext.lstrip('.'),'text':'\n'.join(x['text'] for x in pages)[:20000],'page_map':pages}
    if os.getenv('KATALYST_UPLOAD_BUCKET'):
        try:
            from google.cloud import storage as cloudstorage
            bucket=cloudstorage.Client().bucket(os.environ['KATALYST_UPLOAD_BUCKET'])
            key=f"demo-projects/{pid}/{sid}/{name}"
            bucket.blob(key).upload_from_string(raw,content_type=file.content_type or 'application/octet-stream')
            source['storage_uri']=f"gs://{bucket.name}/{key}"
        except Exception as exc:
            raise HTTPException(502,'Google Cloud Storage upload failed. Check bucket configuration and service-account permissions.') from exc
    p['sources'].append(source)
    # Changing evidence invalidates downstream approvals.
    p['approvals']={};p['requirements']=[];p['stories']=[];p['prototype']=None;p['status']='draft'
    srs.invalidate(p)
    p['demo_requests']=[];p['prototype_provider']=''
    audit(p,'source.uploaded',user_id,{'sourceId':sid,'name':name})
    commit(p)
    return {'id':sid,'name':name,'pages':len(pages),'characters':len(source['text'])}

@app.post('/api/projects/{pid}/requirements/analyze')
async def analyze_requirements(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id)
    try: result=await ai.analyze(p['brief'],p['sources'][1:])
    except ai.AIQuotaError as exc:raise HTTPException(429,str(exc)) from exc
    except (RuntimeError,ValueError,ValidationError) as exc:raise HTTPException(502,str(exc)) from exc
    validate_requirements([r.model_dump() for r in result.requirements])
    p['requirements']=[r.model_dump() for r in result.requirements]
    p['requirements_version']+=1;p['open_questions']=result.open_questions;p['potential_conflicts']=result.potential_conflicts
    srs.invalidate(p)
    p['stories']=[];p['prototype']=None;p['approvals']={};p['status']='requirements_review'
    p['demo_requests']=[];p['prototype_provider']=''
    audit(p,'requirements.generated',user_id,{'version':p['requirements_version'],'provider':ai.PROVIDER})
    return commit(p)

@app.put('/api/projects/{pid}/requirements')
def update_requirements(pid:str,body:RequirementsUpdate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id)
    reqs=[r.model_dump() for r in body.requirements]
    validate_requirements(reqs)
    valid_sources={source['id'] for source in p['sources']}
    if any(r['source_id'] not in valid_sources for r in reqs):
        raise HTTPException(422,'Requirements must reference an existing source')
    p['requirements']=reqs;p['open_questions']=body.open_questions;p['requirements_version']+=1
    srs.invalidate(p)
    p['stories']=[];p['prototype']=None;p['approvals']={};p['status']='requirements_review'
    p['demo_requests']=[];p['prototype_provider']=''
    audit(p,'requirements.edited',user_id,{'version':p['requirements_version']})
    return commit(p)

def require_current_srs(p):
    require(p,'g0')
    if not p['srs'] or p['srs']['requirements_version'] != p['requirements_version']:
        raise HTTPException(409,'Generate an SRS from the current approved requirements first')

def check_srs_version(p, version):
    if p['srs_version'] != version:
        raise HTTPException(409,f'SRS version mismatch. Current version: {p["srs_version"]}. Reload the project before retrying.')

def save_srs_revision(p, document, provider, user_id):
    try:srs.validate(document,p)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    try:srs.append_revision(p,document,provider,user_id,now())
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    audit(p,'srs.revision.saved',user_id,{'version':p['srs_version'],'provider':provider,'requirements_version':p['requirements_version']})
    return commit(p)

@app.post('/api/projects/{pid}/srs/generate')
async def generate_srs(pid:str,body:SRSGenerate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g0');check_srs_version(p,body.base_version)
    try:srs.check_capacity(p)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    try:document=await ai.srs(p)
    except ai.AIQuotaError as exc:raise HTTPException(429,str(exc)) from exc
    except (RuntimeError,ValueError,ValidationError) as exc:raise HTTPException(502,str(exc)) from exc
    current=read_project(pid,user_id);require(current,'g0');check_srs_version(current,body.base_version)
    if any(current[key] != p[key] for key in ('requirements_version','requirements','sources','open_questions','potential_conflicts')):
        raise HTTPException(409,'Requirements or evidence changed during SRS generation. Reload and generate again.')
    return save_srs_revision(current,document,ai.PROVIDER,user_id)

@app.put('/api/projects/{pid}/srs')
def update_srs(pid:str,body:SRSUpdate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require_current_srs(p);check_srs_version(p,body.base_version)
    return save_srs_revision(p,body.document,'manual',user_id)

@app.post('/api/projects/{pid}/srs/approval')
def approve_srs(pid:str,body:ApprovalCreate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require_current_srs(p);check_srs_version(p,body.artifact_version)
    p['srs_approval']={'decision':body.decision,'artifact_version':p['srs_version'],'reviewer':user_id,'at':now(),'note':body.note[:1000]}
    audit(p,'srs.'+body.decision,user_id,{'version':p['srs_version'],'note':body.note[:200]})
    return commit(p)

@app.get('/api/projects/{pid}/srs/pdf')
def download_srs_pdf(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require_current_srs(p)
    approval=p['srs_approval']
    if not approval or approval['decision']!='approved' or approval['artifact_version']!=p['srs_version']:
        raise HTTPException(409,'Approve the current SRS revision before downloading its PDF')
    try:content=srs.pdf(p)
    except (RuntimeError,ValueError) as exc:raise HTTPException(500,'SRS PDF rendering failed; the saved document has not changed') from exc
    return StreamingResponse(io.BytesIO(content),media_type='application/pdf',
                             headers={'Content-Disposition':f'attachment; filename="KATALYST-{pid}-SRS-v{p["srs_version"]}.pdf"'})

@app.post('/api/projects/{pid}/stories/generate')
async def generate_stories(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g0')
    try: result=await ai.stories(p['requirements'])
    except ai.AIQuotaError as exc:raise HTTPException(429,str(exc)) from exc
    except (RuntimeError,ValueError,ValidationError) as exc:raise HTTPException(502,str(exc)) from exc
    s=[x.model_dump() for x in result.stories]
    validate_stories(s,p['requirements'])
    p['stories']=s;p['assumptions']=result.assumptions;p['stories_version']+=1;p['prototype']=None
    p['approvals'].pop('g1',None);p['approvals'].pop('g2',None);p['status']='stories_review'
    p['demo_requests']=[];p['prototype_provider']=''
    audit(p,'stories.generated',user_id,{'version':p['stories_version'],'provider':ai.PROVIDER})
    return commit(p)

@app.put('/api/projects/{pid}/stories')
def update_stories(pid:str,body:StoriesUpdate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g0')
    stories=[x.model_dump() for x in body.stories]
    validate_stories(stories,p['requirements'])
    p['stories']=stories;p['stories_version']+=1;p['prototype']=None;p['approvals'].pop('g1',None);p['approvals'].pop('g2',None);p['status']='stories_review'
    p['demo_requests']=[];p['prototype_provider']=''
    audit(p,'stories.edited',user_id,{'version':p['stories_version']})
    return commit(p)

@app.post('/api/projects/{pid}/prototype/generate')
async def generate_prototype(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g1')
    try: generated=await ai.prototype(p['brief'],p['stories'])
    except ai.AIQuotaError as exc:raise HTTPException(429,str(exc)) from exc
    except (RuntimeError,ValueError,ValidationError) as exc:raise HTTPException(502,str(exc)) from exc
    try: validate_prototype(generated)
    except ValueError as exc: raise HTTPException(502,str(exc)) from exc
    p['prototype']=generated.model_dump();p['prototype_version']+=1
    p['prototype_provider']=ai.PROVIDER
    p['approvals'].pop('g2',None);p['status']='prototype_review';p['demo_requests']=[]
    audit(p,'prototype.generated',user_id,{'version':p['prototype_version'],'provider':p['prototype_provider']})
    return commit(p)

@app.put('/api/projects/{pid}/prototype')
def update_prototype(pid:str,body:PrototypeUpdate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g1')
    try: validate_prototype(body.prototype)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    p['prototype']=body.prototype.model_dump();p['prototype_version']+=1
    p['prototype_provider']='manual';p['demo_requests']=[]
    p['approvals'].pop('g2',None);p['status']='prototype_review'
    audit(p,'prototype.edited',user_id,{'version':p['prototype_version'],'provider':'manual'})
    return commit(p)

@app.delete('/api/projects/{pid}/prototype')
def delete_prototype(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g1')
    if not p['prototype']:raise HTTPException(409,'No prototype to delete')
    p['prototype']=None;p['prototype_version']+=1;p['prototype_provider']='';p['demo_requests']=[]
    p['approvals'].pop('g2',None);p['status']='stories_approved'
    audit(p,'prototype.deleted',user_id,{'version':p['prototype_version']})
    return commit(p)

@app.post('/api/projects/{pid}/approvals/{gate}')
def approve(pid:str,gate:str,body:ApprovalCreate,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id)
    version_key={'g0':'requirements_version','g1':'stories_version','g2':'prototype_version'}
    if gate not in version_key:raise HTTPException(404,'Unknown approval gate')
    expected=p[version_key[gate]]
    if expected==0 or expected!=body.artifact_version:
        raise HTTPException(409,f'Artifact version mismatch. Current version: {expected}')
    if gate=='g1':require(p,'g0')
    if gate=='g2':require(p,'g1')
    if gate=='g0' and not p['requirements']:raise HTTPException(409,'No requirements to approve')
    if gate=='g1' and not p['stories']:raise HTTPException(409,'No stories to approve')
    if gate=='g2' and not p['prototype']:raise HTTPException(409,'No prototype to approve')
    p['approvals'][gate]={'decision':body.decision,'artifact_version':expected,'reviewer':user_id,'note':body.note[:1000],'at':now()}
    if body.decision=='approved':p['status']={'g0':'requirements_approved','g1':'stories_approved','g2':'prototype_approved'}[gate]
    else:
        p['status']=gate+'_rejected'
        if gate=='g0':p['srs_approval']=None
        if gate=='g0':p['approvals'].pop('g1',None);p['approvals'].pop('g2',None)
        if gate=='g1':p['approvals'].pop('g2',None)
    audit(p,f'{gate}.{body.decision}',user_id,{'version':expected,'note':body.note[:200]})
    return commit(p)

@app.post('/api/projects/{pid}/demo/actions')
def demo_action(pid:str,body:DemoAction,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id)
    if not p['prototype']:raise HTTPException(409,'Generate a prototype first')
    requests=p['demo_requests']
    if body.action=='submit':
        fields=p['prototype']['screens'][0]['fields']
        cleaned={}
        for f in fields:
            val=str(body.values.get(f['id'],'')).strip()[:250]
            if f.get('required') and not val:raise HTTPException(422,f"{f['label']} is required")
            if f['type']=='select' and val and val not in f.get('options',[]):raise HTTPException(422,f"Invalid {f['label']}")
            if f['type']=='email' and val and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',val):raise HTTPException(422,f"Invalid {f['label']}")
            cleaned[f['id']]=val
        request={'id':'REQ-'+uuid.uuid4().hex[:6].upper(),'values':cleaned,'status':'pending','checklist':{'Equipment assigned':False,'Application access granted':False,'Welcome checklist completed':False},'created_at':now()}
        requests.append(request)
    else:
        item=next((x for x in requests if x['id']==body.request_id),None)
        if item is None: raise HTTPException(404,'Demo request not found')
        if body.action in ('approve','request_changes'):
            if item['status']!='pending':raise HTTPException(409,'Only pending requests may be reviewed')
            item['status']='approved' if body.action=='approve' else 'changes_requested'
        elif body.action=='toggle':
            if item['status']!='approved':raise HTTPException(409,'Approve request before provisioning')
            if body.item not in item['checklist']:raise HTTPException(422,'Unknown checklist item')
            item['checklist'][body.item]=not item['checklist'][body.item]
    audit(p,'prototype.demo.'+body.action,user_id,{'requestId':body.request_id})
    return commit(p)

def _markdown_package(p):
    req='\n'.join(f"- **{r['id']}** [{r['kind']}]: {r['text']} (source: {r['source_id']})" for r in p['requirements'])
    story_lines=[];feature_lines=[]
    for s in p['stories']:
        story_lines.append(f"## {s['id']}\nAs a **{s['role']}**, I want **{s['goal']}** so that **{s['benefit']}**.\n\nSources: {', '.join(s['requirement_ids'])}\n"+'\n'.join(f'- {a}' for a in s['acceptance_criteria']))
        for i,c in enumerate(s['acceptance_criteria'],1):
            feature_lines.append(f"# {s['id']} criterion {i}\nScenario: {s['id']} - {i}\n"+'\n'.join('  '+line for line in c.splitlines()))
    return {'README.md':f"# {p['title']}\n\nKATALYST engineering handoff (hackathon demonstrator).\n\nSource project: {p['id']}\nStatus: {p['status']}\n\nThis package contains approved artifacts and a schema-driven demo, not production source code.\n",'requirements.md':f"# Requirements\n\n## Original brief\n\n{p['brief']}\n\n## Atomic requirements\n\n{req}\n\n## Open questions\n\n"+'\n'.join('- '+x for x in p['open_questions']), 'stories.md':'# User stories\n\n'+'\n\n'.join(story_lines),'acceptance.feature':'Feature: Approved enterprise workflow\n\n'+'\n\n'.join(feature_lines),'prototype.json':json.dumps(p['prototype'],indent=2),'traceability.json':json.dumps({'mappings':[{'story_id':s['id'],'requirement_ids':s['requirement_ids']} for s in p['stories']]},indent=2),'approvals.json':json.dumps(p['approvals'],indent=2),'audit.json':json.dumps(p['events'],indent=2)}

def handoff_files(p):
    files = _markdown_package(p)
    if p['srs'] and p['srs_approval'] and p['srs_approval']['decision']=='approved' and p['srs_approval']['artifact_version']==p['srs_version']:
        files['srs.json'] = json.dumps(p['srs'],indent=2)
        files['srs-approval.json'] = json.dumps(p['srs_approval'],indent=2)
    return files

def handoff_archive(files):
    content=io.BytesIO()
    with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as z:
        for name,text in files.items():z.writestr(name,text)
    return content.getvalue()

@app.get('/api/projects/{pid}/export')
def export(pid:str,user_id:str=Depends(auth.current_user)):
    p=read_project(pid,user_id);require(p,'g2')
    content=io.BytesIO(handoff_archive(handoff_files(p)))
    return StreamingResponse(content,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="KATALYST-{pid}-handoff.zip"'})

def approved_handoff_project(pid, user_id):
    p=read_project(pid,user_id)
    for gate,key,artifact in (('g0','requirements_version','requirements'),('g1','stories_version','stories'),('g2','prototype_version','prototype')):
        require(p,gate)
        if not p[artifact] or p['approvals'][gate]['artifact_version']!=p[key]:
            raise HTTPException(409,'Current artifacts must be approved through G2 before external handoff')
    return p

def jira_project(pid, user_id):
    return approved_handoff_project(pid, user_id)

@app.post('/api/projects/{pid}/email/preview')
def email_preview(pid:str,body:HandoffEmailDraft,user_id:str=Depends(auth.current_user)):
    p=approved_handoff_project(pid,user_id)
    config=handoff_email.configuration(user_id)
    return handoff_email.preview(p,body,handoff_files(p),config)

@app.post('/api/projects/{pid}/email/send')
def email_send(pid:str,body:HandoffEmailSend,user_id:str=Depends(auth.current_user)):
    p=approved_handoff_project(pid,user_id)
    config=handoff_email.configuration(user_id)
    files=handoff_files(p)
    plan=handoff_email.preview(p,body,files,config)
    if plan['fingerprint']!=body.fingerprint:
        raise HTTPException(409,'Email preview is out of date. Preview and confirm the current handoff again.')
    def check_current():
        if handoff_files(approved_handoff_project(pid,user_id))!=files:
            raise HTTPException(409,'The handoff changed before sending. Delivery was blocked; review with an administrator.')
    return handoff_email.deliver(p,config,plan,handoff_archive(files),user_id,check_current)

@app.get('/api/projects/{pid}/jira/preview')
def jira_preview(pid:str,user_id:str=Depends(auth.current_user)):
    p=jira_project(pid,user_id)
    try:config=jira.configuration(user_id)
    except jira.JiraError as exc:raise HTTPException(409,str(exc)) from exc
    return jira.plan(p,config)

@app.post('/api/projects/{pid}/jira/create')
def jira_create(pid:str,body:JiraCreate,user_id:str=Depends(auth.current_user)):
    p=jira_project(pid,user_id)
    try:
        config=jira.configuration(user_id);preview=jira.plan(p,config)
        if preview['fingerprint']!=body.fingerprint:
            raise HTTPException(409,'Jira preview is out of date. Preview and confirm the current ticket contents again.')
        return jira.deliver(p,config,preview,user_id,lambda:jira_project(pid,user_id))
    except jira.JiraError as exc:raise HTTPException(409,str(exc)) from exc

# Single-container deployment: serve Vite build from the same origin as the API.
frontend_dist=Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if frontend_dist.exists():
    app.mount('/',StaticFiles(directory=str(frontend_dist),html=True),name='frontend')
else:
    offline=Path(__file__).resolve().parents[2] / 'frontend' / 'offline'
    if offline.exists() and auth.mode()=='demo':
        app.mount('/',StaticFiles(directory=str(offline),html=True),name='offline_fallback')
    else:
        @app.get('/', include_in_schema=False)
        def frontend_not_built():
            raise HTTPException(503,'Build the React frontend with npm run build in frontend, then restart the backend')
