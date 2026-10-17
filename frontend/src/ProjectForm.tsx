import {useState} from 'react'
import {ArrowRight} from 'lucide-react'
import type {ProjectInput} from './types'

const initial:ProjectInput={title:'',description:'',brief:'',business_domain:'',client_name:'',client_email:'',expected_timeline:'',additional_notes:''}
const example:ProjectInput={...initial,title:'Employee Onboarding Portal',description:'Coordinate HR, manager review and IT provisioning.',business_domain:'Human Resources',brief:'Build an employee onboarding portal. HR registers new joiners with name, email, start date and department. Managers approve or request changes. IT tracks equipment and application access provisioning after approval.'}

export default function ProjectForm({busy,onCreate,onCancel}:{busy:boolean;onCreate:(input:ProjectInput)=>void;onCancel:()=>void}){
 const [input,setInput]=useState<ProjectInput>(initial)
 const [step,setStep]=useState(1)
 const change=(key:keyof ProjectInput,value:string)=>setInput(previous=>({...previous,[key]:value}))
 return <section className="panel project-form"><div className="inline-between"><div><div className="eyebrow">START NEW PROJECT · STEP {step} OF 2</div><h1>{step===1?'Project details':'Business requirements'}</h1></div><button className="btn" disabled={busy} onClick={onCancel}>Cancel</button></div><form onSubmit={e=>{e.preventDefault();if(step===1)setStep(2);else onCreate(input)}}>
  {step===1?<><div className="form-grid">
   <label className="field">Project name<input required minLength={3} maxLength={120} value={input.title} onChange={e=>change('title',e.target.value)}/></label>
   <label className="field">Business domain<input required maxLength={120} value={input.business_domain} onChange={e=>change('business_domain',e.target.value)} placeholder="e.g. Retail, Finance, HR"/></label>
   <label className="field">Client name (optional)<input maxLength={160} value={input.client_name} onChange={e=>change('client_name',e.target.value)}/></label>
   <label className="field">Client email (optional)<input type="email" maxLength={254} value={input.client_email} onChange={e=>change('client_email',e.target.value)}/></label>
   <label className="field">Expected timeline (optional)<input maxLength={200} value={input.expected_timeline} onChange={e=>change('expected_timeline',e.target.value)} placeholder="e.g. 8 weeks"/></label>
  </div><label className="field">Project description<textarea required maxLength={2000} rows={3} value={input.description} onChange={e=>change('description',e.target.value)}/></label>
  <button type="button" className="btn" onClick={()=>setInput(example)}>Use onboarding example</button>
  </>:<><label className="field">Business requirements<textarea required minLength={25} maxLength={20000} rows={8} value={input.brief} onChange={e=>change('brief',e.target.value)} placeholder="Describe the actors, data, actions and expected outcomes..."/></label><label className="field">Additional notes (optional)<textarea maxLength={4000} rows={3} value={input.additional_notes} onChange={e=>change('additional_notes',e.target.value)}/></label>  <p className="muted">After creation you can attach PDF, TXT or Markdown evidence in the requirements workspace. Optional SRS generation unlocks after G0 approval. DOCX extraction is not yet supported.</p><button type="button" className="btn" disabled={busy} onClick={()=>setStep(1)}>Back</button></>}
  <button type="submit" className="btn btn-primary" disabled={busy}>{busy?'Saving project...':step===1?'Continue':'Create project'} <ArrowRight size={16}/></button>
 </form></section>
}
