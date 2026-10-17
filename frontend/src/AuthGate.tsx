import {useEffect, useState} from 'react'
import type {ReactNode, FormEvent} from 'react'
import {getApp, getApps, initializeApp} from 'firebase/app'
import {browserLocalPersistence, browserPopupRedirectResolver, createUserWithEmailAndPassword, initializeAuth, GoogleAuthProvider, onAuthStateChanged, setPersistence, signInWithEmailAndPassword, signInWithPopup, signOut} from 'firebase/auth'
import type {Auth} from 'firebase/auth'
import {ArrowRight, FileText, GitBranch, Layers, ShieldCheck} from 'lucide-react'
import * as api from './api'
import type {Config} from './types'

export type Session = {uid:string;name:string;email:string|null;logout:()=>Promise<void>}

export default function AuthGate({children}:{children:(session:Session,config:Config)=>ReactNode}){
 const [config,setConfig]=useState<Config|null>(null)
 const [auth,setAuth]=useState<Auth|null>(null)
 const [session,setSession]=useState<Session|null>(null)
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState('')
 const [screen,setScreen]=useState<'landing'|'login'|'register'>('landing')
 const [email,setEmail]=useState('')
 const [password,setPassword]=useState('')
 const [busy,setBusy]=useState(false)
 const [attempt,setAttempt]=useState(0)

 useEffect(()=>{
  let active=true
  let revision=0
  let unsubscribe:undefined|(()=>void)
  setLoading(true);setError('')
  const setup=async()=>{
   const cfg=await api.getConfig()
   if(!active)return
   setConfig(cfg)
   if(cfg.auth_mode==='demo'){
    api.setTokenProvider(async()=>null)
    const profile=await api.getMe()
    if(active){setSession({...profile,logout:async()=>{throw new Error('Demo mode has no authenticated session. Configure Firebase for real login/logout.')}});setLoading(false)}
    return
   }
   if(!cfg.firebase||Object.values(cfg.firebase).some(v=>!v)){
    throw new Error('Firebase login is not configured. Set the public Firebase web configuration on the backend; see the foundation setup guide.')
   }
   const instance=initializeAuth(getApps().length?getApp():initializeApp(cfg.firebase),{persistence:browserLocalPersistence})
   await setPersistence(instance,browserLocalPersistence)
   if(!active)return
   setAuth(instance)
   api.setTokenProvider(async()=>{
    if(!instance.currentUser)throw new Error('Session ended; sign in again.')
    return instance.currentUser.getIdToken()
   })
   unsubscribe=onAuthStateChanged(instance,user=>{
    const current=++revision
    setSession(null);setError('')
    if(!user){setLoading(false);return}
    setLoading(true)
    void api.getMe().then(profile=>{
     if(active&&current===revision)setSession({...profile,logout:()=>signOut(instance)})
    }).catch(e=>{
     if(active&&current===revision)setError(e instanceof Error?e.message:String(e))
    }).finally(()=>{if(active&&current===revision)setLoading(false)})
   },e=>{if(active){setError(e.message);setLoading(false)}})
  }
  void setup().catch(e=>{if(active){setError(e instanceof Error?e.message:String(e));setLoading(false)}})
  return ()=>{active=false;revision++;unsubscribe?.();api.setTokenProvider(async()=>null)}
 },[attempt])

 const authenticate=async(action:'email'|'google',event?:FormEvent)=>{
  event?.preventDefault()
  if(!auth)return
  setError('');setBusy(true)
  try{
   if(action==='google')await signInWithPopup(auth,new GoogleAuthProvider(),browserPopupRedirectResolver)
   else if(screen==='register')await createUserWithEmailAndPassword(auth,email,password)
   else await signInWithEmailAndPassword(auth,email,password)
   setPassword('')
  }catch(e){setError(e instanceof Error?e.message:String(e))}
  finally{setBusy(false)}
 }
 if(loading)return <main className="auth-page"><div className="panel" role="status">Restoring your session...</div></main>
 if(session&&config)return children(session,config)
 return <main className="auth-page">
  <header className="auth-header"><strong>KATALYST</strong><nav><button className="btn" onClick={()=>setScreen('login')}>Login</button><button className="btn btn-primary" onClick={()=>setScreen('register')}>Register</button></nav></header>
  <section className="landing-layout">
   <div className="landing-copy"><div className="overline">AI-POWERED SOFTWARE DEVELOPMENT PLANNING</div><h1>From Idea to Implementation <span>— Powered by AI</span></h1><p>Turn business requirements into reviewable software plans, with human approval at every major stage.</p><div className="feature-grid">{[{icon:FileText,title:'Requirements & SRS',text:'Review traceable requirements and optionally generate, revise and approve an SRS with PDF export.'},{icon:ShieldCheck,title:'Human governed',text:'You decide when approved work moves forward.'},{icon:Layers,title:'Design & architecture',text:'Interactive prototypes are available. Stitch integration remains planned.'},{icon:GitBranch,title:'Development planning',text:'Architecture and Jira-ready planning are on the roadmap.'}].map(feature=><article className="note-card" key={feature.title}><feature.icon/><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div><h2>How it works</h2><p>Create a project → review requirements → approve artifacts → resume anytime. The existing prototype workflow and optional SRS review are available; the full SRS-to-Jira pipeline is not yet implemented.</p><button className="btn btn-primary" onClick={()=>setScreen('register')}>Start a Project <ArrowRight size={16}/></button></div>
   <section className="panel auth-panel" aria-label="Account access">
    <h2>{screen==='register'?'Create your account':screen==='login'?'Welcome back':'Your workspace, protected'}</h2>
    <p className="muted">Firebase Authentication · Your projects belong to your account.</p>
    {error&&<div className="message error" role="alert">{error}</div>}
    {screen==='landing'?<button className="btn btn-primary" onClick={()=>setScreen('login')}>Sign in to your workspace</button>:<form onSubmit={e=>void authenticate('email',e)}><label className="field">Email<input type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="field">Password<input type="password" autoComplete={screen==='register'?'new-password':'current-password'} required minLength={screen==='register'?6:undefined} value={password} onChange={e=>setPassword(e.target.value)}/></label><button className="btn btn-primary" disabled={busy||!auth}>{busy?'Please wait...':screen==='register'?'Register':'Login'}</button></form>}
    <button className="btn" disabled={busy||!auth} onClick={()=>void authenticate('google')}>Continue with Google</button>
    {error&&<button className="btn" onClick={()=>setAttempt(n=>n+1)}>Retry connection</button>}
    {auth?.currentUser&&!session&&<button className="btn" onClick={()=>{void signOut(auth).catch(e=>setError(String(e)))}}>Sign out of this account</button>}
   </section>
  </section>
 </main>
}
