import type {Dispatch, SetStateAction} from 'react'
import type {Project, PrototypeSpec, Requirement, Story, UIField} from './types'

type Setter<T> = Dispatch<SetStateAction<T>>

function nextId(prefix:string, ids:string[]){
 let number=1
 while(ids.includes(`${prefix}-${String(number).padStart(3,'0')}`))number++
 return `${prefix}-${String(number).padStart(3,'0')}`
}

export function RequirementsEditor({project,requirements,setRequirements,questions,setQuestions,busy,dirty,onSave,onDiscard,onApprove,approved}:{
 project:Project;requirements:Requirement[];setRequirements:Setter<Requirement[]>;questions:string[];setQuestions:Setter<string[]>;busy:boolean;dirty:boolean;onSave:()=>void;onDiscard:()=>void;onApprove:()=>void;approved:boolean
}){
 const update=(index:number,patch:Partial<Requirement>)=>setRequirements(items=>items.map((item,i)=>i===index?{...item,...patch}:item))
 return <div className="artifact-editor">
  <p className="muted">Create requirements manually or edit generated entries. Save changes before approval. Saving clears downstream stories, prototype, test requests and approvals.</p>
  <fieldset disabled={busy}>
   {requirements.length===0&&<p>No requirements. Add one manually or analyze your brief.</p>}
   {requirements.map((r,i)=><article className="requirement-row" key={r.id}>
    <div className="inline-between"><strong>{r.id}</strong><button className="btn" aria-label={`Delete ${r.id}`} onClick={()=>setRequirements(items=>items.filter((_,index)=>index!==i))}>Delete requirement</button></div>
    <label className="field">Requirement {r.id}<textarea rows={3} maxLength={2500} value={r.text} onChange={e=>update(i,{text:e.target.value})}/></label>
    <div className="form-grid"><label className="field">Type<select value={r.kind} onChange={e=>update(i,{kind:e.target.value})}>{['functional','non-functional','business-rule','assumption'].map(kind=><option key={kind}>{kind}</option>)}</select></label>
    <label className="field">Source<select value={r.source_id} onChange={e=>update(i,{source_id:e.target.value})}>{project.sources.map(source=><option key={source.id} value={source.id}>{source.id} - {source.name}</option>)}</select></label></div>
    <label className="field">Source reference<input value={r.source_reference} onChange={e=>update(i,{source_reference:e.target.value})}/></label>
   </article>)}
   <button className="btn" disabled={requirements.length>=30} onClick={()=>setRequirements(items=>[...items,{id:nextId('REQ',items.map(r=>r.id)),text:'',kind:'functional',source_id:'SRC-001',source_reference:'Manual addition - reviewer confirmation required'}])}>+ Add requirement</button>
   <h3>Open questions</h3>
   {questions.map((question,i)=><div className="editor-inline" key={i}><label className="field">Question {i+1}<input value={question} onChange={e=>setQuestions(items=>items.map((item,index)=>index===i?e.target.value:item))}/></label><button className="btn" aria-label={`Delete question ${i+1}`} onClick={()=>setQuestions(items=>items.filter((_,index)=>index!==i))}>Delete</button></div>)}
   <button className="btn" onClick={()=>setQuestions(items=>[...items,''])}>+ Add question</button>
   <div className="review-actions"><span role="status">{dirty?'Unsaved requirements changes':'Requirements saved'}</span><button className="btn" disabled={!dirty} onClick={onDiscard}>Discard changes</button><button className="btn" disabled={!dirty} onClick={onSave}>Save requirements</button><button className="btn btn-primary" disabled={dirty||requirements.length===0||approved} onClick={onApprove}>{approved?'G0 Approved':'Confirm G0'}</button></div>
  </fieldset>
 </div>
}

export function StoriesEditor({requirements,stories,setStories,busy,dirty,onSave,onDiscard,onApprove,approved}:{
 requirements:Requirement[];stories:Story[];setStories:Setter<Story[]>;busy:boolean;dirty:boolean;onSave:()=>void;onDiscard:()=>void;onApprove:()=>void;approved:boolean
}){
 const update=(index:number,patch:Partial<Story>)=>setStories(items=>items.map((item,i)=>i===index?{...item,...patch}:item))
 return <div className="artifact-editor">
  <p className="muted">Add, delete or modify stories and acceptance criteria. Link every story to approved requirements. Saving clears the prototype, its test requests and G1/G2 approvals.</p>
  <fieldset disabled={busy}>
   {stories.length===0&&<p>No stories. Add one manually or generate from approved requirements.</p>}
   {stories.map((story,i)=><article className="story-card" key={story.id}>
    <div className="inline-between"><strong>{story.id}</strong><button className="btn" aria-label={`Delete ${story.id}`} onClick={()=>setStories(items=>items.filter((_,index)=>index!==i))}>Delete user story</button></div>
    <label className="field">Role {story.id}<input value={story.role} onChange={e=>update(i,{role:e.target.value})}/></label>
    <label className="field">Goal {story.id}<input value={story.goal} onChange={e=>update(i,{goal:e.target.value})}/></label>
    <label className="field">Benefit {story.id}<input value={story.benefit} onChange={e=>update(i,{benefit:e.target.value})}/></label>
    <fieldset className="requirement-links"><legend>Linked requirements for {story.id}</legend>{requirements.map(requirement=><label key={requirement.id}><input type="checkbox" checked={story.requirement_ids.includes(requirement.id)} onChange={e=>update(i,{requirement_ids:e.target.checked?[...story.requirement_ids,requirement.id]:story.requirement_ids.filter(id=>id!==requirement.id)})}/>{requirement.id}: {requirement.text}</label>)}</fieldset>
    {story.acceptance_criteria.map((criterion,index)=><div key={index}><label className="field">Acceptance criterion {index+1} for {story.id}<textarea className="gherkin" rows={4} value={criterion} onChange={e=>update(i,{acceptance_criteria:story.acceptance_criteria.map((item,j)=>j===index?e.target.value:item)})}/></label><button className="btn" aria-label={`Delete criterion ${index+1} for ${story.id}`} onClick={()=>update(i,{acceptance_criteria:story.acceptance_criteria.filter((_,j)=>j!==index)})}>Delete criterion</button></div>)}
    <button className="btn" onClick={()=>update(i,{acceptance_criteria:[...story.acceptance_criteria,'Given \nWhen \nThen ']})}>+ Add criterion</button>
   </article>)}
   <button className="btn" disabled={stories.length>=30} onClick={()=>setStories(items=>[...items,{id:nextId('US',items.map(s=>s.id)),requirement_ids:[],role:'',goal:'',benefit:'',acceptance_criteria:['Given \nWhen \nThen ']}])}>+ Add user story</button>
   <div className="review-actions"><span role="status">{dirty?'Unsaved story changes':'Stories saved'}</span><button className="btn" disabled={!dirty} onClick={onDiscard}>Discard changes</button><button className="btn" disabled={!dirty} onClick={onSave}>Save stories</button><button className="btn btn-primary" disabled={dirty||stories.length===0||approved} onClick={onApprove}>{approved?'G1 Approved':'Approve G1'}</button></div>
  </fieldset>
 </div>
}

export function newPrototype():PrototypeSpec{
 return {title:'New workflow prototype',subtitle:'Manually authored prototype',primary_color:'#2563eb',concepts:[
  {id:'concept-1',name:'Clarity',description:'Professional workspace',primaryColor:'#2563eb'},
  {id:'concept-2',name:'Momentum',description:'Alternative visual concept',primaryColor:'#7c3aed'},
 ],screens:[
  {id:'intake',kind:'intake',title:'Submit request',description:'Enter request details',fields:[{id:'requestName',label:'Request name',type:'text',required:true,options:[]}]},
  {id:'approval',kind:'approval',title:'Review requests',description:'Approve or request changes',fields:[]},
  {id:'checklist',kind:'checklist',title:'Track completion',description:'Fixed demonstration checklist',fields:[]},
 ]}
}

export function PrototypeEditor({draft,setDraft,busy,dirty,exists,onSave,onDiscard,onDelete}:{
 draft:PrototypeSpec|null;setDraft:Setter<PrototypeSpec|null>;busy:boolean;dirty:boolean;exists:boolean;onSave:()=>void;onDiscard:()=>void;onDelete:()=>void
}){
 const update=(patch:Partial<PrototypeSpec>)=>setDraft(value=>value?{...value,...patch}:value)
 const fieldUpdate=(index:number,patch:Partial<UIField>)=>setDraft(value=>value?{...value,screens:value.screens.map((screen,i)=>i===0?{...screen,fields:screen.fields.map((field,j)=>index===j?{...field,...patch}:field)}:screen)}:value)
 return <div className="artifact-editor">
  <p className="muted">Keep the three workflow screens and two concepts. Edit their text and add/delete intake fields. Saving or deleting clears G2 and existing test requests. No AI calls are needed.</p>
  <fieldset disabled={busy}>
   {!draft?<button className="btn" onClick={()=>setDraft(newPrototype())}>+ Create prototype manually</button>:<>
    <label className="field">Prototype title<input value={draft.title} onChange={e=>update({title:e.target.value})}/></label>
    <label className="field">Prototype subtitle<input value={draft.subtitle} onChange={e=>update({subtitle:e.target.value})}/></label>
    {draft.concepts.map((concept,i)=><article className="story-card" key={concept.id}><h3>Concept {i+1}</h3>
     <label className="field">Concept {i+1} name<input value={concept.name} onChange={e=>update({concepts:draft.concepts.map((item,j)=>i===j?{...item,name:e.target.value}:item)})}/></label>
     <label className="field">Concept {i+1} description<input value={concept.description} onChange={e=>update({concepts:draft.concepts.map((item,j)=>i===j?{...item,description:e.target.value}:item)})}/></label>
     <label className="field">Concept {i+1} color<input type="color" value={concept.primaryColor} onChange={e=>update({concepts:draft.concepts.map((item,j)=>i===j?{...item,primaryColor:e.target.value}:item)})}/></label>
    </article>)}
    {draft.screens.map((screen,i)=><article className="story-card" key={screen.id}><h3>{screen.kind} screen</h3>
     <label className="field">{screen.kind} title<input value={screen.title} onChange={e=>update({screens:draft.screens.map((item,j)=>i===j?{...item,title:e.target.value}:item)})}/></label>
     <label className="field">{screen.kind} description<textarea value={screen.description} onChange={e=>update({screens:draft.screens.map((item,j)=>i===j?{...item,description:e.target.value}:item)})}/></label>
    </article>)}
    <h3>Intake fields</h3>
    {draft.screens[0].fields.map((field,i)=><article className="story-card" key={field.id}><div className="inline-between"><strong>{field.id}</strong><button className="btn" aria-label={`Delete field ${field.id}`} onClick={()=>update({screens:draft.screens.map((screen,index)=>index===0?{...screen,fields:screen.fields.filter((_,j)=>j!==i)}:screen)})}>Delete field</button></div>
     <label className="field">Field {i+1} label<input value={field.label} onChange={e=>fieldUpdate(i,{label:e.target.value})}/></label>
     <label className="field">Field {i+1} type<select value={field.type} onChange={e=>{const value=e.target.value;if(value==='text'||value==='date'||value==='select'||value==='email')fieldUpdate(i,{type:value})}}>{['text','date','select','email'].map(type=><option key={type}>{type}</option>)}</select></label>
     <label><input type="checkbox" checked={field.required} onChange={e=>fieldUpdate(i,{required:e.target.checked})}/> Required</label>
     {field.type==='select'&&<><h4>Options</h4>{field.options.map((option,index)=><div className="editor-inline" key={index}><label className="field">Field {i+1} option {index+1}<input value={option} onChange={e=>fieldUpdate(i,{options:field.options.map((item,j)=>j===index?e.target.value:item)})}/></label><button className="btn" onClick={()=>fieldUpdate(i,{options:field.options.filter((_,j)=>j!==index)})}>Delete option</button></div>)}<button className="btn" onClick={()=>fieldUpdate(i,{options:[...field.options,'']})}>+ Add option</button></>}
    </article>)}
    <button className="btn" onClick={()=>update({screens:draft.screens.map((screen,i)=>i===0?{...screen,fields:[...screen.fields,{id:nextId('field',screen.fields.map(field=>field.id)),label:'New field',type:'text',required:false,options:[]}]}:screen)})}>+ Add intake field</button>
   </>}
   <div className="review-actions"><span role="status">{dirty?'Unsaved prototype changes':'Prototype saved'}</span><button className="btn" disabled={!dirty} onClick={onDiscard}>Discard changes</button><button className="btn" disabled={!dirty||!draft} onClick={onSave}>Save prototype</button><button className="btn" disabled={!exists} onClick={onDelete}>Delete prototype</button></div>
  </fieldset>
 </div>
}
