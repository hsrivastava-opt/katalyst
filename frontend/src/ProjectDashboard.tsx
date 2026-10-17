import {ArrowRight, Plus} from 'lucide-react'
import type {ProjectSummary} from './types'

export default function ProjectDashboard({projects,loading,onCreate,onResume,onRefresh}:{projects:ProjectSummary[];loading:boolean;onCreate:()=>void;onResume:(id:string)=>void;onRefresh:()=>void}){
 const latest=projects[0]
 return <section>
  <div className="page-heading"><div><div className="overline">YOUR PERSISTENT WORKSPACE</div><h1>My Projects</h1><p>Start a project or resume from its current saved workflow stage.</p></div><button className="btn" onClick={onRefresh} disabled={loading}>Refresh</button></div>
  <div className="dashboard-actions"><button className="btn btn-primary" onClick={onCreate}><Plus size={17}/> Start New Project</button><button className="btn" disabled={!latest||loading} onClick={()=>latest&&onResume(latest.id)}>Resume Existing Project <ArrowRight size={16}/></button></div>
  <div className="demo-disclosure"><span><strong>Foundation milestone.</strong> The progress below measures the existing requirements-to-prototype workflow, not the future SRS-to-Jira planning pipeline.</span></div>
  {loading?<p role="status">Loading your projects...</p>:projects.length===0?<div className="empty-box"><h2>No projects yet</h2><p>Create your first project to begin. Your saved work will appear here when you return.</p></div>:<div className="project-grid">{projects.map(p=><article className="panel project-card" key={p.id}><span className="eyebrow">{p.business_domain||'Business project'}</span><h2>{p.title}</h2><p>{p.description||p.brief}</p><dl><dt>Created</dt><dd>{new Date(p.created_at).toLocaleString()}</dd><dt>Updated</dt><dd>{new Date(p.updated_at).toLocaleString()}</dd><dt>Current stage</dt><dd>{p.current_stage}</dd><dt>Status</dt><dd>{p.status.replace(/_/g,' ')}</dd></dl><label>Prototype workflow: {p.completion_percentage}%<progress value={p.completion_percentage} max={100}/></label><button className="btn btn-primary" onClick={()=>onResume(p.id)}>Resume <ArrowRight size={16}/></button></article>)}</div>}
 </section>
}
