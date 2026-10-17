import {useState} from 'react'
import type {JiraPreview} from './types'
import * as api from './api'

export default function JiraPanel({projectId,approved,disabled,onBusy}:{projectId:string;approved:boolean;disabled:boolean;onBusy:(busy:boolean)=>void}){
 const [preview,setPreview]=useState<JiraPreview|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [message,setMessage]=useState('')
 const [confirmed,setConfirmed]=useState(false)
 const newCount=preview?.tickets.filter(ticket=>ticket.status==='new').length||0
 const blocked=preview?.tickets.some(ticket=>ticket.status==='blocked'||ticket.status==='pending')
 const load=async()=>{
  setBusy(true);onBusy(true);setError('');setMessage('');setConfirmed(false)
  try{setPreview(await api.previewJira(projectId))}catch(e){setPreview(null);setError(e instanceof Error?e.message:String(e))}finally{setBusy(false);onBusy(false)}
 }
 const create=async()=>{
  if(!preview||!confirmed)return
  setBusy(true);onBusy(true);setError('');setMessage('')
  try{
   const result=await api.createJira(projectId,preview.fingerprint)
   setPreview(result);setConfirmed(false)
   setMessage('Jira delivery completed. Confirmed ticket links are shown below.')
  }catch(e){
   setError(e instanceof Error?e.message:String(e));setConfirmed(false)
   try{setPreview(await api.previewJira(projectId))}
   catch(refreshError){setPreview(null);setError(previous=>previous+' Status refresh also failed: '+String(refreshError))}
  }finally{setBusy(false);onBusy(false)}
 }
 return <section className="jira-panel" aria-label="Jira handoff">
  <div className="section-divider"/><h3>Create Jira tickets</h3>
  <p>Send one ticket per approved user story to the administrator-configured shared Jira project. Ticket contents include acceptance criteria and requirement IDs. This shares those contents with Atlassian using the shared account.</p>
  {!approved&&<p role="status">Complete approval through G2 before creating Jira tickets.</p>}
  <fieldset className="srs-controls" disabled={disabled||busy||!approved}>
   <button className="btn btn-primary" onClick={()=>{void load()}}>{busy?'Working with Jira...':preview?'Refresh Jira preview':'Create Jira tickets'}</button>
   <small>Preview only; no tickets are created until you explicitly approve below.</small>
   {error&&<p className="jira-error" role="alert">{error}</p>}
   {message&&<p role="status">{message}</p>}
   {preview&&<>
    <p><strong>Destination:</strong> {preview.destination.site} / {preview.destination.project_key} - issue type ID {preview.destination.issue_type_id}</p>
    <p>Approved versions: requirements {preview.versions.requirements_version}, stories {preview.versions.stories_version}, prototype {preview.versions.prototype_version}.</p>
    {preview.tickets.map(ticket=><article className="story-card" key={ticket.delivery_id}>
     <h4>{ticket.summary}</h4><p>Status: {ticket.status}</p>
     {ticket.url&&<a href={ticket.url} target="_blank" rel="noreferrer">{ticket.issue_key} - Open in Jira</a>}
     {ticket.changed&&<p role="status">This story differs from its original delivery. The existing ticket will NOT be duplicated or updated automatically. Review changes manually in Jira.</p>}
     {ticket.error&&<p role="alert">{ticket.error}</p>}
     <details><summary>Review ticket contents</summary><p className="srs-content">{ticket.description}</p><small>Recovery label: katalyst-{ticket.delivery_id}</small></details>
    </article>)}
    {blocked&&<p role="alert">A delivery is pending or blocked. No more tickets can be sent until an administrator checks Jira and reconciles the saved delivery record. Refreshing does not resend tickets.</p>}
    <p>{newCount} new ticket(s). Confirmed tickets are skipped on repeat clicks. Tickets are not automatically assigned to a sprint.</p>
    <label className="jira-confirm"><input type="checkbox" checked={confirmed} disabled={newCount===0||!!blocked} onChange={e=>setConfirmed(e.target.checked)}/> I reviewed this destination and ticket contents and approve sharing them with Jira.</label>
    <button className="btn btn-primary" disabled={!confirmed||newCount===0||!!blocked} onClick={()=>{void create()}}>Approve & create {newCount} Jira ticket(s)</button>
   </>}
  </fieldset>
 </section>
}
