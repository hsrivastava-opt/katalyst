import {useEffect,useState} from 'react'
import {Activity, ArrowRight, BrainCircuit, Check, ChevronRight, CircleHelp, ClipboardCheck, Cloud, Download, FileText, GitBranch, Layers, LayoutDashboard, LoaderCircle, Lock, Menu, PackageOpen, Plus, ShieldCheck, Sparkles, UploadCloud, WandSparkles, X} from 'lucide-react'
import * as api from './api'
import type {Config,Project,ProjectInput,ProjectSummary,Requirement,Story,PrototypeSpec,SRSDocument} from './types'
import Prototype from './Prototype'
import AuthGate from './AuthGate'
import type {Session} from './AuthGate'
import ProjectDashboard from './ProjectDashboard'
import ProjectForm from './ProjectForm'
import {RequirementsEditor,StoriesEditor,PrototypeEditor} from './ArtifactEditors'
import SrsPanel from './SrsPanel'
import JiraPanel from './JiraPanel'
import EmailHandoffPanel from './EmailHandoffPanel'
import VoicePanel from './VoicePanel'

const phases=[{id:'capture',title:'Requirement Intake',number:'01',icon:FileText},{id:'stories',title:'Stories & Criteria',number:'02',icon:ClipboardCheck},{id:'prototype',title:'Live Prototype',number:'03',icon:Layers},{id:'handoff',title:'Engineering Handoff',number:'04',icon:PackageOpen}] as const
type Tab=typeof phases[number]['id']

function Status({done,label}:{done:boolean;label:string}){return <span className={'status-chip '+(done?'complete':'pending')}><span className="status-dot"/>{label}</span>}
function Stats({p}:{p:Project}){return <div className="metrics-grid">{[{label:'Requirements',v:p.requirements.length,icon:FileText},{label:'User Stories',v:p.stories.length,icon:GitBranch},{label:'Prototype Screens',v:p.prototype?.screens.length||0,icon:Layers},{label:'Approvals',v:['g0','g1','g2'].filter(g=>p.approvals[g]?.decision==='approved').length+'/3',icon:ShieldCheck}].map(x=><div key={x.label} className="metric"><div className="metric-icon"><x.icon size={18}/></div><strong>{x.v}</strong><span>{x.label}</span></div>)}</div>}

export default function App(){
 return <AuthGate>{(session,config)=><Workspace key={session.uid} session={session} config={config}/>}</AuthGate>
}

function Workspace({session,config}:{session:Session;config:Config}){
 const [projects,setProjects]=useState<ProjectSummary[]>([])
 const [project,setProject]=useState<Project|null>(null)
 const [tab,setTabState]=useState<Tab>('capture')
 const [busy,setBusy]=useState('')
 const [error,setError]=useState('')
 const [toast,setToast]=useState('')
 const [creating,setCreating]=useState(false)
 const [dashboard,setDashboard]=useState(true)
 const [loadingProjects,setLoadingProjects]=useState(true)
 const [reqs,setReqs]=useState<Requirement[]>([])
 const [questions,setQuestions]=useState<string[]>([])
 const [stories,setStories]=useState<Story[]>([])
 const [prototypeDraft,setPrototypeDraft]=useState<PrototypeSpec|null>(null)
 const [srsDraft,setSrsDraft]=useState<SRSDocument|null>(null)
 const [mobileMenu,setMobileMenu]=useState(false)
 const [emailDirty,setEmailDirty]=useState(false)

 const resetDrafts=(p:Project)=>{setReqs(structuredClone(p.requirements));setQuestions([...p.open_questions]);setStories(structuredClone(p.stories));setPrototypeDraft(structuredClone(p.prototype));setSrsDraft(structuredClone(p.srs?.document??null))}
 const sync=(p:Project)=>{setProject(p);resetDrafts(p);void api.getProjects().then(setProjects).catch(e=>setError(String(e)))}
 const run=async(label:string,fn:()=>Promise<Project>)=>{setBusy(label);setError('');try{const p=await fn();sync(p);setToast(label+' — done');setTimeout(()=>setToast(''),3800)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy('')}}
 useEffect(()=>{let active=true;api.getProjects().then(list=>{if(active)setProjects(list)}).catch(e=>{if(active)setError(String(e))}).finally(()=>{if(active)setLoadingProjects(false)});return()=>{active=false}},[])
 const refreshProjects=async()=>{setLoadingProjects(true);setError('');try{setProjects(await api.getProjects())}catch(e){setError(String(e))}finally{setLoadingProjects(false)}}
 const selectProject=async(id:string)=>{if(!canLeave())return;setError('');setMobileMenu(false);setBusy('Resuming project');try{const p=await api.getProject(id);sync(p);setTabState(p.resume_tab);setCreating(false);setDashboard(false)}catch(e){setError(String(e))}finally{setBusy('')}}
 const startProject=()=>{if(!canLeave())return;setCreating(true);setDashboard(false);setProject(null);setMobileMenu(false);setError('')}
 const showDashboard=()=>{if(!canLeave())return;setCreating(false);setDashboard(true);setMobileMenu(false);void refreshProjects()}
 const create=(input:ProjectInput)=>run('Project created',async()=>{const p=await api.createProject(input);setCreating(false);setDashboard(false);setTabState('capture');return p})
 const doApprove=(gate:'g0'|'g1'|'g2',version:number)=>{if(dirty){setError('Save or discard your edits before approval.');return}void run(`${gate.toUpperCase()} approved`,()=>api.approve(project!.id,gate,version))}
 const loaded=project
 const g0=project?.approvals.g0?.decision==='approved'
 const g1=project?.approvals.g1?.decision==='approved'
 const g2=project?.approvals.g2?.decision==='approved'
 const reqDirty=JSON.stringify(reqs)!==JSON.stringify(project?.requirements)||JSON.stringify(questions)!==JSON.stringify(project?.open_questions)
 const storyDirty=JSON.stringify(stories)!==JSON.stringify(project?.stories)
 const prototypeDirty=JSON.stringify(prototypeDraft)!==JSON.stringify(project?.prototype)
 const srsDirty=JSON.stringify(srsDraft)!==JSON.stringify(project?.srs?.document??null)
 const dirty=!!project&&(reqDirty||storyDirty||prototypeDirty||srsDirty)
 const hasUnsaved=dirty||emailDirty
 const canLeave=()=>{if(busy)return false;if(hasUnsaved&&!window.confirm('Discard unsaved artifact or email changes and leave this view?'))return false;if(project)resetDrafts(project);return true}
 const setTab=(next:Tab)=>{if(next!==tab&&canLeave())setTabState(next)}
 const confirmChange=(message:string,action:()=>void)=>{if(window.confirm(message))action()}
 useEffect(()=>{if(!hasUnsaved)return;const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[hasUnsaved])
 const stepDone=[Boolean(g0),Boolean(g1),Boolean(g2),Boolean(g2)]

 return <div className="shell">
   <aside className={'sidebar '+(mobileMenu?'mobile-open':'')}>
     <div className="brand"><div className="brand-symbol">K<span>↗</span></div><div><div className="brand-title">KATALYST</div><div className="brand-desc">INTELLIGENCE INTO ACTION</div></div></div>
     <div className="sidebar-group"><div className="nav-label">WORKSPACE</div><button className={'sidebar-link '+(dashboard?'active':'')} disabled={!!busy} onClick={showDashboard}><LayoutDashboard size={18}/> My Projects</button><button className="sidebar-link" disabled={!!busy} onClick={startProject}><Plus size={18}/> New project</button></div>
     <div className="sidebar-group projects-group"><div className="nav-label">YOUR PROJECTS <span>{projects.length}</span></div>{projects.length===0&&<p className="sidebar-hint">Create your first project to begin.</p>}{projects.map(p=><button className={'project-nav '+(project?.id===p.id?'selected':'')} disabled={!!busy} key={p.id} onClick={()=>selectProject(p.id)}><div className="project-avatar">{p.title.charAt(0)}</div><div className="project-nav-text"><strong>{p.title}</strong><small>{p.id}</small></div><ChevronRight size={14}/></button>)}</div>
     <div className="sidebar-bottom"><div className="google-badge"><Cloud size={17}/><div><strong>Google AI Builder Cup</strong><span>Hackathon MVP · v0.2</span></div></div><div className="sidebar-fineprint">Prototype environment</div></div>
   </aside>
   {mobileMenu&&<button className="mobile-backdrop" onClick={()=>setMobileMenu(false)} aria-label="Close menu"/>}
   <main className="main">
     <header className="topbar"><button className="hamburger" onClick={()=>setMobileMenu(!mobileMenu)} aria-label="Toggle menu"><Menu/></button><div className="breadcrumb">Workspace <ChevronRight size={15}/> <strong>{dashboard?'My Projects':creating?'New project':project?.title||'Welcome'}</strong></div><div className="top-actions"><span className="cloud-connected"><span className="live-dot"/>{config.is_live_ai?'Google AI configured':'Offline AI demo'}</span><span className="profile-label" title={session.email||session.name}>{session.email||session.name}</span>{config.auth_mode==='firebase'&&<button className="btn" disabled={!!busy} onClick={()=>{if(canLeave())void session.logout().catch(e=>setError(String(e)))}}>Logout</button>}</div></header>
     <div className="content">
     {(error||toast)&&<div className={'message '+(error?'error':'success')}><span>{error||toast}</span><button onClick={()=>{setError('');setToast('')}}><X size={17}/></button></div>}
     {config.auth_mode==='demo'&&<div className="demo-disclosure" role="status"><ShieldCheck size={18}/><span><strong>Local demo identity only.</strong> No real authentication or private user accounts. Do not expose this server publicly. Configure Firebase for login and per-user access.</span></div>}
     {dashboard?<ProjectDashboard projects={projects} loading={loadingProjects||!!busy} onCreate={startProject} onResume={id=>{void selectProject(id)}} onRefresh={()=>{void refreshProjects()}}/>:!loaded||creating?<ProjectForm busy={!!busy} onCreate={create} onCancel={showDashboard}/>:
       <>
       <div className="page-heading"><div><div className="overline"><span className="square-dot"/> LIVE PROJECT WORKSPACE</div><h1>{project.title}</h1><p>From unstructured business intent to a reviewable and executable experience.</p></div><div className="project-meta"><span className="id-pill">{project.id}</span><Status done={Boolean(g2)} label={g2?'Ready for handoff':'Work in progress'}/></div></div>
       {config?.provider==='demo'&&<div className="demo-disclosure"><CircleHelp size={18}/><span><strong>Offline demonstration mode.</strong> Artifacts are produced by deterministic templates, not live Gemini inference. Set <code>KATALYST_AI_PROVIDER=gemini</code> or <code>adk</code> to test actual Google models.</span></div>}
       <Stats p={project}/>
       <VoicePanel key={project.id} projectId={project.id} enabled={!!config.live_voice_enabled} disabled={!!busy||hasUnsaved} onBusy={working=>setBusy(working?'Voice conversation active':'')}/>
       <div className="wizard-tabs">{phases.map((s,i)=><button key={s.id} className={'wizard-tab '+(tab===s.id?'current':'')} onClick={()=>setTab(s.id)}><span className={'tab-number '+(stepDone[i]?'done':'')}>{stepDone[i]?<Check size={14}/>:s.number}</span><span>{s.title}</span>{i<3&&<ChevronRight className="tab-chevron" size={16}/>}</button>)}</div>
       {tab==='capture'&&<div className="two-col">
        <section className="panel wide">
         <div className="section-heading"><div><div className="eyebrow">STEP 01 - UNDERSTAND</div><h2>Requirement intelligence</h2><p>Capture, add, delete and edit requirements before approval.</p></div><FileText/></div>
         <div className="source-brief"><div className="subsection-title">Original business brief <Status done label="Source of truth"/></div><p>{project.brief}</p></div>
         <div className="source-upload"><label className="upload-label"><UploadCloud size={18}/> Add supporting policy/document
          <input type="file" accept=".pdf,.txt,.md" disabled={!!busy||dirty} onChange={async e=>{
           const file=e.target.files?.[0];if(!file)return
           if(!window.confirm('Adding evidence clears requirements, stories, prototype, approvals and test requests, and invalidates the current SRS (history retained). Continue?')){e.target.value='';return}
           setBusy('Uploading source');setError('')
           try{await api.upload(project.id,file);sync(await api.getProject(project.id));setToast('Source uploaded. Regenerate requirements to incorporate it.')}catch(err){setError(String(err))}finally{setBusy('');e.target.value=''}
          }}/></label><small>PDF, TXT or Markdown - max 6MB</small></div>
         <div className="sources-inline">{project.sources.map(source=><span className="source-tag" key={source.id}>{source.name} <small>{source.id}</small></span>)}</div>
         <div className="inline-between"><h3>Requirements</h3><button className="btn btn-primary" disabled={!!busy||dirty} onClick={()=>confirmChange('Analyze requirements? This replaces existing requirements, clears downstream artifacts and approvals, and invalidates the current SRS (history retained).',()=>{void run('Requirements analyzed',()=>api.analyze(project.id))})}><BrainCircuit size={16}/>{project.requirements.length?'Re-analyze':'Analyze requirements'}</button></div>
         {srsDirty&&<p role="status">Save or discard SRS edits before changing requirements.</p>}
         <RequirementsEditor project={project} requirements={reqs} setRequirements={setReqs} questions={questions} setQuestions={setQuestions} busy={!!busy||srsDirty} dirty={reqDirty} approved={!!g0}
          onDiscard={()=>resetDrafts(project)} onSave={()=>confirmChange('Save requirements? This clears stories, prototype, approvals and test requests, and invalidates the current SRS (history retained).',()=>{void run('Requirements saved',()=>api.saveRequirements(project.id,reqs,questions))})} onApprove={()=>doApprove('g0',project.requirements_version)}/>
         {project.potential_conflicts.length>0&&<div className="conflict-box"><strong>Potential policy conflict</strong>{project.potential_conflicts.map((text,i)=><p key={i}>{text}</p>)}</div>}
         <SrsPanel key={`${project.id}-${project.srs_version}`} project={project} draft={srsDraft} setDraft={setSrsDraft} busy={!!busy} requirementsDirty={reqDirty} dirty={srsDirty} run={run}
          onDownload={()=>{setBusy('Downloading SRS PDF');setError('');void api.downloadSrsPdf(project.id,project.srs_version).then(()=>setToast('SRS PDF downloaded')).catch(e=>setError(String(e))).finally(()=>setBusy(''))}}/>
        </section>
        <aside className="aside-notes"><div className="note-card minimal"><h3>Requirement confirmation</h3><p>Save edits and approve G0 to unlock stories. An empty draft cannot be approved.</p><Status done={!!g0} label={g0?'Approved':'Waiting for review'}/></div><button className="btn btn-next" disabled={!g0||!!busy||dirty} onClick={()=>setTab('stories')}>Continue to user stories <ArrowRight size={16}/></button></aside>
       </div>}
       {tab==='stories'&&<div className="two-col">
        <section className="panel wide">
         <div className="section-heading"><div><div className="eyebrow">STEP 02 - STRUCTURE</div><h2>User stories & acceptance criteria</h2><p>Maintain traceable, testable stories manually or with AI.</p></div><GitBranch/></div>
         {!g0?<div className="empty-box"><Lock/><strong>G0 approval required</strong><button className="btn" onClick={()=>setTab('capture')}>Go to requirements</button></div>:<>
          <div className="inline-between"><span>{project.requirements.length} approved requirements</span><button className="btn btn-primary" disabled={!!busy||dirty} onClick={()=>confirmChange('Generate stories? This replaces existing stories and clears the prototype, G1/G2 approvals and test requests.',()=>{void run('Stories generated',()=>api.generateStories(project.id))})}><Sparkles size={16}/>{stories.length?'Regenerate stories':'Generate user stories'}</button></div>
          <StoriesEditor requirements={project.requirements} stories={stories} setStories={setStories} busy={!!busy} dirty={storyDirty} approved={!!g1}
           onDiscard={()=>resetDrafts(project)} onSave={()=>confirmChange('Save stories? This clears the prototype, G1/G2 approvals and test requests.',()=>{void run('Stories saved',()=>api.saveStories(project.id,stories))})} onApprove={()=>doApprove('g1',project.stories_version)}/>
         </>}
        </section>
        <aside className="aside-notes"><div className="note-card minimal"><h3>Story review</h3><p>Each story needs a role, goal, benefit, linked requirements and at least one Given/When/Then criterion.</p><Status done={!!g1} label={g1?'Approved':'Waiting for review'}/></div><button className="btn btn-next" disabled={!g1||!!busy||dirty} onClick={()=>setTab('prototype')}>Continue to prototyping <ArrowRight size={16}/></button></aside>
       </div>}
       {tab==='prototype'&&<section className="panel">
        <div className="section-heading"><div><div className="eyebrow">STEP 03 - DESIGN & VALIDATE</div><h2>Interactive prototype studio</h2><p>Create, modify or delete a safe three-screen prototype.</p></div><Layers/></div>
        {!g1?<div className="empty-box"><Lock/><strong>G1 approval required</strong><button className="btn" onClick={()=>setTab('stories')}>Go to user stories</button></div>:<>
         <div className="inline-between design-toolbar"><span>3 screens - 2 design concepts - editable intake fields</span><button className="btn btn-primary" disabled={!!busy||dirty} onClick={()=>confirmChange('Generate a prototype? This replaces the current prototype and clears G2 approval and test requests.',()=>{void run('Prototype generated',()=>api.generatePrototype(project.id))})}><WandSparkles size={16}/>{project.prototype?'Regenerate prototype':'Generate prototype'}</button></div>
         <details className="prototype-editor" open={!project.prototype||undefined}><summary>Edit prototype structure and design</summary>
          <PrototypeEditor draft={prototypeDraft} setDraft={setPrototypeDraft} busy={!!busy} dirty={prototypeDirty} exists={!!project.prototype}
           onDiscard={()=>resetDrafts(project)} onSave={()=>{if(prototypeDraft)confirmChange('Save prototype? This clears G2 approval and test requests.',()=>{void run('Prototype saved',()=>api.savePrototype(project.id,prototypeDraft))})}}
           onDelete={()=>confirmChange('Delete the entire saved prototype, its G2 approval and test requests? Unsaved prototype edits will also be discarded.',()=>{void run('Prototype deleted',()=>api.deletePrototype(project.id))})}/>
         </details>
         {prototypeDirty?<div className="empty-box" role="status">Save or discard prototype edits to use the live preview or approve G2.</div>:project.prototype&&<>
          <div className="prototype-intro"><span>Author: {project.prototype_provider}</span><span>Version {project.prototype_version}</span></div>
          <fieldset className="preview-controls" disabled={!!busy}><Prototype project={project} refresh={sync} run={run}/></fieldset>
          <div className="review-actions"><span>Review and test this saved version before approval.</span><button className="btn btn-primary" disabled={!!busy||dirty||!!g2} onClick={()=>doApprove('g2',project.prototype_version)}>{g2?'G2 Approved':'Approve prototype G2'}</button></div>
         </>}
        </>}
       </section>}
       {tab==='handoff'&&<div className="two-col"><section className="panel wide"><div className="section-heading"><div><div className="eyebrow">STEP 04 · SHIP</div><h2>Engineering handoff</h2><p>Export approved specifications, test scenarios, traceability and the prototype schema.</p></div><div className="section-icon"><PackageOpen/></div></div><div className="handoff-grid">{[{title:'Original requirements',desc:'Traceable requirements and open questions',icon:FileText},{title:'User stories',desc:'Reviewed business and engineering stories',icon:GitBranch},{title:'Acceptance tests',desc:'Gherkin scenarios ready for QA',icon:ClipboardCheck},{title:'Prototype schema',desc:'Validated UI definition',icon:Layers},{title:'Traceability map',desc:'Relationships across generated artifacts',icon:Activity},{title:'Approval audit',desc:'Versioned governance and run history',icon:ShieldCheck}].map(x=><div className="handoff-item" key={x.title}><div className="handoff-icon"><x.icon/></div><strong>{x.title}</strong><small>{x.desc}</small></div>)}</div><div className="handoff-callout"><div><strong>{g2?'Engineering package is ready':'Complete approval gate G2 to export'}</strong><p>The generated ZIP contains actual project artifacts. It is not production-ready generated application source.</p></div><button className="btn btn-primary" disabled={!g2||!!busy} onClick={async()=>{try{await api.downloadExport(project.id);setToast('Handoff package downloaded')}catch(e){setError(String(e))}}}><Download size={16}/> Download handoff</button></div></section><aside className="aside-notes"><div className="note-card minimal"><div className="eyebrow">QUALITY CHECKPOINTS</div><h3>Approvals</h3><div className="gate-line"><Status done={!!g0} label="G0 — Requirements"/></div><div className="gate-line"><Status done={!!g1} label="G1 — User stories"/></div><div className="gate-line"><Status done={!!g2} label="G2 — Prototype"/></div></div><div className="note-card minimal"><div className="eyebrow">AUDIT TRACE</div><h3>{project.events.length} recorded events</h3><div className="audit-list">{project.events.slice(-5).reverse().map(x=><div key={x.id}><b>{x.type}</b><small>{new Date(x.at).toLocaleString()}</small></div>)}</div></div></aside></div>}
       {tab==='handoff'&&<section className="panel"><JiraPanel key={`${project.id}-${project.requirements_version}-${project.stories_version}-${project.prototype_version}-${!!g2}`} projectId={project.id} approved={!!g0&&!!g1&&!!g2} disabled={!!busy||dirty} onBusy={working=>setBusy(working?'Working with Jira':'')}/></section>}
       {tab==='handoff'&&<section className="panel"><EmailHandoffPanel key={`${project.id}-${project.requirements_version}-${project.stories_version}-${project.prototype_version}-${project.srs_version}-${!!g2}`} project={project} approved={!!g0&&!!g1&&!!g2} disabled={!!busy||dirty} onBusy={working=>setBusy(working?'Working with email':'')} onDirty={setEmailDirty}/></section>}
       </>}
     </div>
     <footer className="footer"><span>© KATALYST · AI Builder Cup Demonstrator</span><span>Human expertise. AI-powered execution.</span></footer>
   </main>
   {busy&&<div className="busy-floating"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
 </div>
}
