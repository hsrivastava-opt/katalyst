import {useState} from 'react'
import type {Dispatch, SetStateAction} from 'react'
import * as api from './api'
import type {Project, SRSDocument, SRSSection} from './types'

type Props = {
 project:Project;draft:SRSDocument|null;setDraft:Dispatch<SetStateAction<SRSDocument|null>>
 busy:boolean;requirementsDirty:boolean;dirty:boolean
 run:(label:string,action:()=>Promise<Project>)=>void
 onDownload:()=>void
}

export default function SrsPanel({project,draft,setDraft,busy,requirementsDirty,dirty,run,onDownload}:Props){
 const [historyVersion,setHistoryVersion]=useState('')
 const [note,setNote]=useState('')
 const approvedRequirements=project.approvals.g0?.decision==='approved'
 const current=project.srs
 const approved=project.srs_approval?.decision==='approved'&&project.srs_approval.artifact_version===project.srs_version
 const historical=project.srs_revisions.find(revision=>String(revision.version)===historyVersion)
 const updateSection=(id:string,patch:Partial<SRSSection>)=>setDraft(document=>document?{
  ...document,sections:document.sections.map(section=>section.id===id?{...section,...patch}:section),
 }:document)
 const generate=()=>{
  if(current&&!window.confirm('Generate a new SRS revision? The current revision is preserved in history, but its SRS approval will be reset. Stories and prototype are unchanged.'))return
  run('SRS generated',()=>api.generateSrs(project.id,project.srs_version))
 }
 return <section className="srs-panel">
  <div className="section-divider"/>
  <div className="eyebrow">OPTIONAL - SOFTWARE REQUIREMENTS SPECIFICATION</div>
  <h2>SRS generation & review</h2>
  <p>This optional document uses your approved requirements and source excerpts. It does not block stories or change G1/G2. Review every section; unknown business rules must remain questions, not invented facts.</p>
  {!approvedRequirements&&<p role="status">Confirm G0 to generate, edit, approve or download an SRS.</p>}
  {requirementsDirty&&<p role="status">Save or discard requirement edits before working on the SRS.</p>}
  {!current&&project.srs_revisions.length>0&&<p role="status">The previous SRS is out of date after requirement/evidence changes. History is retained. Generate a new revision after confirming G0.</p>}
  <fieldset className="srs-controls" disabled={busy||requirementsDirty||!approvedRequirements}>
   <button className="btn btn-primary" disabled={dirty||project.srs_revisions.length>=10} onClick={generate}>{current?'Regenerate SRS':'Generate SRS'}</button>
   <p className="muted">Generation makes one model request in Gemini/ADK mode; editing, approval and PDF export make none. Demo mode produces a labeled template. Up to 10 revisions / 400 KB of SRS history are supported per project.</p>
   {current&&draft&&<>
    <p>Revision {current.version} - requirements version {current.requirements_version} - authoring provider: {current.provider}</p>
    <p role="status">{dirty?'Unsaved SRS changes':approved?'Current SRS approved':project.srs_approval?.decision==='rejected'?'Changes requested - edit and save a new revision':'SRS awaiting human review'}</p>
    <label className="field">SRS title<input maxLength={160} value={draft.title} onChange={e=>setDraft(document=>document?{...document,title:e.target.value}:document)}/></label>
    {draft.sections.map(section=><details className="srs-section" key={section.id}>
     <summary>{section.title}</summary>
     <label className="field">Section title for {section.id}<input maxLength={120} value={section.title} onChange={e=>updateSection(section.id,{title:e.target.value})}/></label>
     <label className="field">Content for {section.id}<textarea rows={8} maxLength={6000} value={section.content} onChange={e=>updateSection(section.id,{content:e.target.value})}/></label>
     <div className="form-grid">
      <label className="field">Requirements for {section.id}<select multiple value={section.requirement_ids} onChange={e=>updateSection(section.id,{requirement_ids:Array.from(e.target.selectedOptions,option=>option.value)})}>{project.requirements.map(requirement=><option key={requirement.id} value={requirement.id}>{requirement.id}: {requirement.text}</option>)}</select></label>
      <label className="field">Sources for {section.id}<select multiple value={section.source_ids} onChange={e=>updateSection(section.id,{source_ids:Array.from(e.target.selectedOptions,option=>option.value)})}>{project.sources.map(source=><option key={source.id} value={source.id}>{source.id}: {source.name}</option>)}</select></label>
     </div>
     <small>Use Ctrl (Windows) or Command (Mac) to select multiple references. Every approved requirement must be linked in at least one section.</small>
    </details>)}
    <div className="review-actions">
     <button className="btn" disabled={!dirty} onClick={()=>setDraft(structuredClone(current.document))}>Discard SRS changes</button>
     <button className="btn" disabled={!dirty||project.srs_revisions.length>=10} onClick={()=>run('SRS revision saved',()=>api.saveSrs(project.id,draft,project.srs_version))}>Save SRS revision</button>
    </div>
    <p>Saving or regenerating creates a revision and clears SRS approval only. Changing requirements or uploading evidence invalidates the current SRS; earlier revisions stay in history.</p>
    <label className="field">SRS review note<input maxLength={1000} value={note} onChange={e=>setNote(e.target.value)}/></label>
    <div className="review-actions">
     <button className="btn" disabled={dirty||project.srs_approval?.decision==='rejected'} onClick={()=>run('SRS changes requested',()=>api.approveSrs(project.id,project.srs_version,'rejected',note))}>Request SRS changes</button>
     <button className="btn btn-primary" disabled={dirty||approved} onClick={()=>{
      if(window.confirm(`Approve SRS revision ${project.srs_version}? Confirm that you have reviewed all eight sections and outstanding questions.`))run('SRS approved',()=>api.approveSrs(project.id,project.srs_version,'approved',note))
     }}>Approve SRS revision</button>
     <button className="btn" disabled={dirty||!approved} onClick={onDownload}>Download SRS PDF</button>
    </div>
    {project.srs_approval&&<p>Review: {project.srs_approval.decision} by {project.srs_approval.reviewer} at {new Date(project.srs_approval.at).toLocaleString()}. {project.srs_approval.note}</p>}
   </>}
  </fieldset>
  {project.srs_revisions.length>0&&<details className="srs-history"><summary>Saved SRS revisions ({project.srs_revisions.length}/10)</summary>
   <label className="field">View SRS revision<select disabled={busy} value={historyVersion} onChange={e=>setHistoryVersion(e.target.value)}><option value="">Select a saved revision</option>{project.srs_revisions.map(revision=><option key={revision.version} value={revision.version}>Revision {revision.version} - requirements v{revision.requirements_version} - {revision.provider}</option>)}</select></label>
   {historical&&<article><h3>{historical.document.title}</h3><p>Read-only historical revision {historical.version}. Saved by {historical.actor} at {new Date(historical.at).toLocaleString()}. Not a statement of current approval.</p>
    {historical.document.sections.map(section=><section key={section.id}><h4>{section.title}</h4><p className="srs-content">{section.content}</p><small>Requirements: {section.requirement_ids.join(', ')||'None'}; sources: {section.source_ids.join(', ')||'None'}</small></section>)}
   </article>}
  </details>}
 </section>
}
