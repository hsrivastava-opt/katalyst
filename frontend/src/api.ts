import type {Project,ProjectInput,ProjectSummary,Config,Profile,Requirement,Story,PrototypeSpec,SRSDocument,JiraPreview,HandoffEmailDraft,HandoffEmailPreview} from './types'
let tokenProvider: (()=>Promise<string|null>) = async()=>null
export function setTokenProvider(provider:()=>Promise<string|null>){tokenProvider=provider}
async function authenticatedFetch(path:string,opts:RequestInit={}){
 const token=await tokenProvider()
 const headers=new Headers(opts.headers)
 if(token)headers.set('Authorization',`Bearer ${token}`)
 if(opts.body && !(opts.body instanceof FormData))headers.set('Content-Type','application/json')
 return fetch('/api'+path,{...opts,headers})
}
async function responseError(resp:Response){
 let msg='Request failed'
 try{const body=await resp.json();msg=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail||body)}catch{msg=resp.statusText||msg}
 return new Error(`${resp.status}: ${msg}`)
}
export async function request<T>(path:string,opts:RequestInit={}):Promise<T>{
 const resp=await authenticatedFetch(path,opts)
 if(!resp.ok)throw await responseError(resp)
 return resp.json() as Promise<T>
}
export const getProjects=()=>request<ProjectSummary[]>('/projects')
export const getProject=(id:string)=>request<Project>('/projects/'+id)
export const getConfig=async()=>{const response=await fetch('/api/config');if(!response.ok)throw await responseError(response);return response.json() as Promise<Config>}
export const getMe=()=>request<Profile>('/me')
export const createProject=(input:ProjectInput)=>request<Project>('/projects',{method:'POST',body:JSON.stringify(input)})
export const analyze=(id:string)=>request<Project>(`/projects/${id}/requirements/analyze`,{method:'POST'})
export const saveRequirements=(id:string,reqs:Requirement[],questions:string[])=>request<Project>(`/projects/${id}/requirements`,{method:'PUT',body:JSON.stringify({requirements:reqs,open_questions:questions})})
export const generateStories=(id:string)=>request<Project>(`/projects/${id}/stories/generate`,{method:'POST'})
export const saveStories=(id:string,stories:Story[])=>request<Project>(`/projects/${id}/stories`,{method:'PUT',body:JSON.stringify({stories})})
export const generatePrototype=(id:string)=>request<Project>(`/projects/${id}/prototype/generate`,{method:'POST'})
export const savePrototype=(id:string,prototype:PrototypeSpec)=>request<Project>(`/projects/${id}/prototype`,{method:'PUT',body:JSON.stringify({prototype})})
export const deletePrototype=(id:string)=>request<Project>(`/projects/${id}/prototype`,{method:'DELETE'})
export const previewJira=(id:string)=>request<JiraPreview>(`/projects/${id}/jira/preview`)
export const previewHandoffEmail=(id:string,draft:HandoffEmailDraft)=>request<HandoffEmailPreview>(`/projects/${id}/email/preview`,{method:'POST',body:JSON.stringify(draft)})
export const sendHandoffEmail=(id:string,draft:HandoffEmailDraft,fingerprint:string)=>request<HandoffEmailPreview>(`/projects/${id}/email/send`,{method:'POST',body:JSON.stringify({...draft,fingerprint,confirmed:true})})
export const createJira=(id:string,fingerprint:string)=>request<JiraPreview>(`/projects/${id}/jira/create`,{method:'POST',body:JSON.stringify({fingerprint,confirmed:true})})
export const generateSrs=(id:string,base_version:number)=>request<Project>(`/projects/${id}/srs/generate`,{method:'POST',body:JSON.stringify({base_version})})
export const saveSrs=(id:string,document:SRSDocument,base_version:number)=>request<Project>(`/projects/${id}/srs`,{method:'PUT',body:JSON.stringify({document,base_version})})
export const approveSrs=(id:string,artifact_version:number,decision:'approved'|'rejected',note:string)=>request<Project>(`/projects/${id}/srs/approval`,{method:'POST',body:JSON.stringify({artifact_version,decision,note})})
export const approve=(id:string,gate:string,version:number,decision='approved')=>request<Project>(`/projects/${id}/approvals/${gate}`,{method:'POST',body:JSON.stringify({artifact_version:version,decision})})
export const demoAction=(id:string,action:string,request_id?:string,values?:Record<string,string>,item?:string)=>request<Project>(`/projects/${id}/demo/actions`,{method:'POST',body:JSON.stringify({action,request_id,values,item})})
export const upload=async (id:string,file:File)=>{const form=new FormData();form.set('file',file);return request<{id:string;name:string;pages:number}>(`/projects/${id}/sources`,{method:'POST',body:form})}
export async function downloadExport(id:string){const r=await authenticatedFetch(`/projects/${id}/export`);if(!r.ok)throw await responseError(r); const b=await r.blob(), url=URL.createObjectURL(b), a=document.createElement('a');a.href=url;a.download=`KATALYST-${id}-handoff.zip`;a.click();URL.revokeObjectURL(url)}
export async function downloadSrsPdf(id:string,version:number){
 const response=await authenticatedFetch(`/projects/${id}/srs/pdf`)
 if(!response.ok)throw await responseError(response)
 const url=URL.createObjectURL(await response.blob()),anchor=document.createElement('a')
 anchor.href=url;anchor.download=`KATALYST-${id}-SRS-v${version}.pdf`;anchor.click();URL.revokeObjectURL(url)
}
