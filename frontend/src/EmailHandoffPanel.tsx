import {useEffect,useState} from 'react'
import type {Project,HandoffEmailPreview} from './types'
import * as api from './api'

export default function EmailHandoffPanel({project,approved,disabled,onBusy,onDirty}:{project:Project;approved:boolean;disabled:boolean;onBusy:(busy:boolean)=>void;onDirty:(dirty:boolean)=>void}){
 const initialSubject=`Engineering handoff: ${project.title}`.slice(0,200)
 const initialBody=`Hello team,\n\nThe approved engineering handoff for ${project.title} (${project.id}) is attached.\n\nPlease review the requirements, user stories, acceptance scenarios, prototype definition and traceability records. An approved SRS is included when available; the SRS PDF is downloaded separately.\n\nThis is a specification package, not production application source code. Please flag questions before implementation.\n\nThank you,\nKATALYST project team`
 const [recipients,setRecipients]=useState('')
 const [subject,setSubject]=useState(initialSubject)
 const [body,setBody]=useState(initialBody)
 const [preview,setPreview]=useState<HandoffEmailPreview|null>(null)
 const [confirmed,setConfirmed]=useState(false)
 const [busy,setBusy]=useState(false)
 const [edited,setEdited]=useState(false)
 const [error,setError]=useState('')
 useEffect(()=>{onDirty(edited);return()=>onDirty(false)},[edited,onDirty])
 const invalidate=()=>{setPreview(null);setConfirmed(false);setError('');setEdited(true)}
 const draft=()=>({recipients:recipients.split(/[,;\n]+/).map(email=>email.trim()).filter(Boolean),subject,body})
 const load=async()=>{
  setBusy(true);onBusy(true);setError('');setConfirmed(false)
  try{const plan=await api.previewHandoffEmail(project.id,draft());setPreview(plan);if(plan.status==='sent')setEdited(false)}
  catch(e){setPreview(null);setError(e instanceof Error?e.message:String(e))}
  finally{setBusy(false);onBusy(false)}
 }
 const send=async()=>{
  if(!preview||!confirmed)return
  setBusy(true);onBusy(true);setError('')
  try{setPreview(await api.sendHandoffEmail(project.id,draft(),preview.fingerprint));setEdited(false)}
  catch(e){
   setError(e instanceof Error?e.message:String(e))
   try{setPreview(await api.previewHandoffEmail(project.id,draft()))}
   catch(refreshError){setPreview(null);setError(previous=>previous+' Status refresh failed: '+String(refreshError))}
  }finally{setConfirmed(false);setBusy(false);onBusy(false)}
 }
 return <section className="email-handoff" aria-label="Email handoff">
  <h3>Email handoff</h3>
  <p>Use the editable template below to send the current approved ZIP from the shared SMTP account. Only active registered KATALYST accounts can receive it. Recipients are hidden from one another (Bcc delivery).</p>
  {!approved&&<p role="status">Complete current approvals through G2 before emailing the handoff.</p>}
  <fieldset className="srs-controls" disabled={disabled||busy||!approved}>
   <label>Registered recipient emails (maximum 10)<textarea rows={2} value={recipients} maxLength={2600} placeholder="Separate addresses with commas or new lines" onChange={e=>{invalidate();setRecipients(e.target.value)}}/></label>
   <label>Email subject<input value={subject} maxLength={200} onChange={e=>{invalidate();setSubject(e.target.value)}}/></label>
   <label>Email template<textarea rows={12} value={body} maxLength={12000} onChange={e=>{invalidate();setBody(e.target.value)}}/></label>
   <button className="btn btn-secondary" onClick={()=>{invalidate();setSubject(initialSubject);setBody(initialBody)}}>Reset template</button>
   <small>Drafts are not saved. Sending shares all ZIP contents, including the brief, audit records and any approved SRS, with these recipients and the mail provider.</small>
   <button className="btn btn-primary" disabled={!recipients.trim()||!subject.trim()||!body.trim()} onClick={()=>{void load()}}>{busy?'Working with email...':'Preview email & attachment'}</button>
   {error&&<p className="jira-error" role="alert">{error}</p>}
   {preview&&<article className="story-card">
    <h4>Email preview</h4>
    <p><strong>From:</strong> {preview.from_email}</p>
    <p><strong>Bcc:</strong> {preview.recipients.join(', ')}</p>
    <p><strong>Subject:</strong> {preview.subject}</p>
    <p className="srs-content">{preview.body}</p>
    <p><strong>Attachment:</strong> {preview.attachment}</p>
    <details><summary>Included ZIP entries</summary><ul>{preview.attachment_entries.map(name=><li key={name}>{name}</li>)}</ul></details>
    <p role="status">Delivery: {preview.status}{preview.at?' - '+new Date(preview.at).toLocaleString():''}</p>
    {preview.status==='sent'&&<p role="status">The SMTP server accepted the email. This does not confirm inbox delivery. An identical email will not be sent again.</p>}
    {(preview.status==='pending'||preview.status==='blocked')&&<p role="alert">{preview.error||'Delivery outcome is pending or uncertain.'} Ask an administrator to reconcile the SMTP record before any resend. Do not edit the template to bypass this block.</p>}
    {preview.status==='new'&&<>
     <label className="jira-confirm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> I reviewed the recipients, message and attachment contents and authorize sending this handoff.</label>
     <button className="btn btn-primary" disabled={!confirmed} onClick={()=>{void send()}}>Confirm & send handoff</button>
    </>}
   </article>}
  </fieldset>
 </section>
}
