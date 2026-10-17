import {useEffect,useState} from 'react'
import {ArrowLeft,ArrowRight,CheckCircle2,ClipboardList,Monitor,PlusCircle, ShieldCheck, Wrench} from 'lucide-react'
import type { Project, UIField } from './types'
import {demoAction} from './api'

type Props={project:Project; refresh:(p:Project)=>void; run:(label:string,fn:()=>Promise<Project>)=>void}
export default function Prototype({project,refresh,run}:Props){
 const spec=project.prototype!
 const [tab,setTab]=useState(0)
 const [concept,setConcept]=useState(0)
 const [values,setValues]=useState<Record<string,string>>({})
 const accent=spec.concepts[concept]?.primaryColor||spec.primary_color
 useEffect(()=>{setTab(0);setConcept(0);setValues({})},[project.id,project.prototype_version])
 const screens=spec.screens
 const pending=project.demo_requests.filter(r=>r.status==='pending')
 const approved=project.demo_requests.filter(r=>r.status==='approved')
 const act=(action:string,id?:string, item?:string, data?:Record<string,string>)=>run('Running demo action',async()=>{const p=await demoAction(project.id,action,id,data,item);refresh(p);if(action==='submit'){setValues({});setTab(1)}if(action==='approve')setTab(2);return p})
 const input=(f:UIField)=>{
   const common={id:f.id,required:f.required,value:values[f.id]||'',onChange:(e:React.ChangeEvent<HTMLInputElement|HTMLSelectElement>)=>setValues(v=>({...v,[f.id]:e.target.value}))}
   return <label className="field" key={f.id}><span>{f.label} {f.required&&<b className="asterisk">*</b>}</span>{f.type==='select'?<select {...common}><option value="">Select {f.label.toLowerCase()}</option>{f.options.map(o=><option key={o}>{o}</option>)}</select>:<input {...common} type={f.type==='date'?'date':f.type==='email'?'email':'text'} placeholder={'Enter '+f.label.toLowerCase()}/>}</label>
 }
 return <section className={'preview-frame '+(concept===1?'momentum':'clarity')} style={{'--preview-accent':accent} as React.CSSProperties}>
   <div className="preview-topbar"><div className="preview-brand"><span className="mini-brand">K</span><strong>{spec.title}</strong></div><span className="demo-pill">LIVE INTERACTIVE PREVIEW</span></div>
   <div className="preview-menus">{screens.map((s,i)=><button key={s.id} className={'preview-menu '+(tab===i?'active':'')} onClick={()=>setTab(i)}>{i===0?<PlusCircle size={15}/>:i===1?<ShieldCheck size={15}/>:<Wrench size={15}/>} {s.title}</button>)}</div>
   <div className="preview-body">
    <p>{spec.subtitle}</p>
    <div className="preview-page-head"><div><div className="eyebrow">STEP {tab+1} OF {screens.length} · {screens[tab].kind.toUpperCase()}</div><h2>{screens[tab].title}</h2><p>{screens[tab].description}</p></div><div className="preview-icon"><Monitor size={22}/></div></div>
    {tab===0&&<form className="demo-form" onSubmit={e=>{e.preventDefault();act('submit',undefined,undefined,values)}}><div className="form-grid">{screens[0].fields.map(input)}</div><div className="prototype-action"><span>Actions are saved to the demo project state.</span><button className="btn btn-strong" type="submit">Submit request <ArrowRight size={16}/></button></div></form>}
    {tab===1&&<div><p className="table-helper">{pending.length} request(s) awaiting reviewer action</p>{!pending.length?<div className="empty-result"><ClipboardList/><h3>No pending requests</h3><p>Submit a request on the first screen to populate this queue.</p><button className="btn" onClick={()=>setTab(0)}>Go to registration</button></div>:<div className="demo-table">{pending.map(req=><div className="demo-list-row" key={req.id}><div><div className="row-title">{Object.values(req.values).find(Boolean)||req.id}</div><small>{req.id} · {Object.values(req.values).slice(1,3).join(' · ')}</small></div><div className="row-actions"><button className="btn btn-soft" onClick={()=>act('request_changes',req.id)}>Request changes</button><button className="btn btn-strong" onClick={()=>act('approve',req.id)}>Approve <CheckCircle2 size={15}/></button></div></div>)}</div>}</div>}
    {tab===2&&<div><p className="table-helper">Track real state changes inside your generated prototype.</p>{!approved.length?<div className="empty-result"><Wrench/><h3>Nothing ready for provisioning</h3><p>Approve a request on the previous screen to start the checklist.</p><button className="btn" onClick={()=>setTab(1)}>Go to approvals</button></div>:<div className="provisioning-grid">{approved.map(r=>{const count=Object.values(r.checklist).filter(Boolean).length,all=Object.keys(r.checklist).length;return <div className="provision-card" key={r.id}><div className="row-title">{Object.values(r.values).find(Boolean)||r.id}</div><small>{r.id} · {count}/{all} complete</small><div className="progress small"><div style={{width:`${count/all*100}%`,background:accent}}/></div>{Object.entries(r.checklist).map(([k,v])=><label className="checkrow" key={k}><input type="checkbox" checked={v} onChange={()=>act('toggle',r.id,k)}/><span>{k}</span></label>)}</div>})}</div>}</div>}
    <div className="prototype-footer"><button className="plain-link" disabled={tab===0} onClick={()=>setTab(v=>v-1)}><ArrowLeft size={15}/> Back</button><div className="dots">{screens.map((_,i)=><button key={i} onClick={()=>setTab(i)} className={i===tab?'selected':''} aria-label={`Go to screen ${i+1}`}/>)}</div><button className="plain-link" disabled={tab===2} onClick={()=>setTab(v=>v+1)}>Next <ArrowRight size={15}/></button></div>
   </div>
   <div className="preview-concepts">{spec.concepts.map((c,i)=><button key={c.id} className={'concept-selector '+(i===concept?'selected':'')} onClick={()=>setConcept(i)}><span style={{background:c.primaryColor}} className="concept-dot"/><span>{c.name}</span></button>)}<small>{spec.concepts[concept]?.description} - Prototype actions are controlled by a fixed renderer.</small></div>
 </section>
}
