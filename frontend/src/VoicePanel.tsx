import {useEffect,useRef,useState} from 'react'
import type {Session} from '@google/genai'
import * as api from './api'
import {VoiceAudio} from './voiceAudio'

type Line={speaker:'You'|'KATALYST';text:string}
type Runtime={session:Session|null;audio:VoiceAudio|null;timer:ReturnType<typeof setTimeout>|null;setup:boolean;ended:boolean}

export default function VoicePanel({projectId,enabled,disabled,onBusy}:{projectId:string;enabled:boolean;disabled:boolean;onBusy:(busy:boolean)=>void}){
 const [active,setActive]=useState(false)
 const [ready,setReady]=useState(false)
 const [consent,setConsent]=useState(false)
 const [error,setError]=useState('')
 const [message,setMessage]=useState('')
 const [snapshot,setSnapshot]=useState('')
 const [lines,setLines]=useState<Line[]>([])
 const runtime=useRef<Runtime|null>(null)
 const mounted=useRef(true)
 const busyCallback=useRef(onBusy)
 busyCallback.current=onBusy
 const end=(reason:string)=>{
  const current=runtime.current
  runtime.current=null
  if(current){
   current.ended=true
   if(current.timer)clearTimeout(current.timer)
   try{current.session?.close()}
   catch{if(mounted.current)setError('Live connection cleanup failed. Close this browser tab to fully disconnect.')}
   void current.audio?.close().catch(()=>{
    if(mounted.current)setError('Audio cleanup failed. Close this browser tab to release audio resources.')
   })
  }
  if(mounted.current){setActive(false);setReady(false);setMessage(reason)}
  busyCallback.current(false)
 }
 useEffect(()=>{
  mounted.current=true
  const pagehide=()=>end('')
  window.addEventListener('pagehide',pagehide)
  return()=>{mounted.current=false;window.removeEventListener('pagehide',pagehide);end('')}
 },[])
 useEffect(()=>{
  if(!active)return
  const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''}
  window.addEventListener('beforeunload',warn)
  return()=>window.removeEventListener('beforeunload',warn)
 },[active])
 const fail=(current:Runtime,text:string)=>{
  if(runtime.current!==current)return
  setError(text);end('Voice session stopped.')
 }
 const append=(speaker:Line['speaker'],text:string)=>{
  if(!text)return
  setLines(previous=>{
   const last=previous[previous.length-1]
   const next=last?.speaker===speaker
    ?[...previous.slice(0,-1),{speaker,text:(last.text+text).slice(-6000)}]
    :[...previous,{speaker,text:text.slice(-6000)}]
   return next.slice(-40)
  })
 }
 const start=async()=>{
  if(runtime.current||!consent)return
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){
   setError('Microphone streaming requires HTTPS (or localhost) and a supported browser.');return
  }
  const current:Runtime={session:null,audio:null,timer:null,setup:false,ended:false}
  runtime.current=current
  setError('');setMessage('Allow microphone access, then wait for the Live connection.');setLines([]);setSnapshot('')
  setActive(true);busyCallback.current(true)
  current.timer=setTimeout(()=>fail(current,'Voice startup timed out. Check microphone permission and connectivity.'),40000)
  let phase:'microphone'|'credentials'|'live'='microphone'
  try{
   current.audio=new VoiceAudio()
   await current.audio.prepare(data=>{
    if(current.setup&&current.session&&!current.ended)current.session.sendRealtimeInput({audio:{data,mimeType:'audio/pcm;rate=16000'}})
   },text=>fail(current,text))
   if(current.ended)return
   phase='credentials'
   const info=await api.startVoiceSession(projectId)
   if(current.ended)return
   setSnapshot(info.snapshot_at)
   const remaining=Date.parse(info.expires_at)-Date.now()
   if(remaining<=0)throw new Error('Voice credentials expired before connection. Wait five minutes and start again.')
   const {GoogleGenAI,Modality}=await import('@google/genai')
   if(current.ended)return
   phase='live'
   const ai=new GoogleGenAI({apiKey:info.token,httpOptions:{apiVersion:info.api_version}})
   let connectionTimeout:ReturnType<typeof setTimeout>|null=null
   const connection=ai.live.connect({
    model:info.model,
    config:{responseModalities:[Modality.AUDIO],inputAudioTranscription:{},outputAudioTranscription:{}},
    callbacks:{
     onmessage:response=>{
      if(current.ended)return
      if(response.setupComplete){
       current.setup=true;setReady(true);setMessage('Microphone on. Ask about this project.')
       if(current.timer)clearTimeout(current.timer)
       current.timer=setTimeout(()=>end('Three-minute voice session ended. Microphone is off.'),Math.max(0,Date.parse(info.expires_at)-Date.now()))
      }
      const content=response.serverContent
      if(content?.interrupted)current.audio?.interrupt()
      if(content?.inputTranscription?.text)append('You',content.inputTranscription.text)
      if(content?.outputTranscription?.text)append('KATALYST',content.outputTranscription.text)
      for(const part of content?.modelTurn?.parts||[]){
       const audio=part.inlineData
       if(audio?.data){
        try{current.audio?.play(audio.data,audio.mimeType||'')}
        catch{fail(current,'Live audio could not be played. Check your browser audio output and restart later.');return}
       }
      }
     },
     onerror:()=>fail(current,'Live connection failed. Check model access, free-tier quota, billing and connectivity. No automatic retry was made.'),
     onclose:()=>{if(!current.ended)end('Live connection closed. Microphone is off. Wait for the cooldown before restarting.')},
    },
   })
   // Release connections that finish after End or a startup timeout.
   void connection.then(session=>{if(current.ended)session.close()},()=>{/* Main await reports connection errors. */})
   try{
    current.session=await Promise.race([connection,new Promise<never>((_,reject)=>{
     connectionTimeout=setTimeout(()=>reject(new Error('Live connection timed out. No automatic retry was made.')),20000)
    })])
   }finally{if(connectionTimeout)clearTimeout(connectionTimeout)}
   if(current.ended){current.session.close();return}
  }catch(e){
   const text=phase==='live'?'Live connection failed or timed out. Check model access, quota and connectivity. No automatic retry was made.'
    :phase==='microphone'?'Microphone setup failed. Check browser permission and AudioWorklet support, then try again.'
    :e instanceof Error?e.message:'Voice credentials could not be requested.'
   fail(current,text)
  }
 }
 return <section className="panel voice-panel" aria-label="Ask KATALYST voice assistant">
  <h3>Ask KATALYST <span className="status-chip">Voice pilot - read only</span></h3>
  <p>Ask “What is the project status?”, “How many user stories are there?” or “What is left before handoff?” Answers use a saved snapshot at session start, not live Jira task status. Requirement capture is not enabled yet.</p>
  {!enabled&&<p role="status">Voice is disabled on this deployment. An administrator must enable the pilot and allowlist your Firebase UID.</p>}
  <p>Starting shares this project's saved requirements, stories, open questions and status with Google Gemini, plus microphone audio while connected. Free-tier data may be used to improve Google products. KATALYST does not persist raw audio or transcripts; Google processing follows its API terms. Transcripts may be inaccurate.</p>
  <label className="jira-confirm"><input type="checkbox" checked={consent} disabled={active||disabled||!enabled} onChange={e=>setConsent(e.target.checked)}/> I agree to share this project snapshot and my microphone audio with Gemini.</label>
  <div className="voice-actions">
   <button className="btn btn-primary" disabled={!enabled||disabled||active||!consent} onClick={()=>{void start()}}>Start voice conversation</button>
   <button className="btn btn-secondary" disabled={!active} onClick={()=>end('Conversation ended. Microphone is off.')}>End conversation</button>
  </div>
  <p role="status">{active?(ready?'Microphone ON - listening':'Starting voice - microphone may be active'):'Microphone off'}. Sessions last at most 3 minutes; one start attempt per account every 5 minutes.</p>
  {snapshot&&<p>Saved snapshot: {new Date(snapshot).toLocaleString()}. End and restart for fresh project data.</p>}
  {message&&<p role="status">{message}</p>}
  {error&&<p className="jira-error" role="alert">{error}</p>}
  <h4>Session transcript</h4>
  <small>Only the latest 40 transcript blocks (up to 6,000 characters each) are shown. Cleared when starting a new conversation or leaving the project.</small>
  <div className="voice-transcript" role="log" aria-label="Voice transcript">{lines.map((line,index)=><p key={index}><strong>{line.speaker}:</strong> {line.text}</p>)}</div>
 </section>
}
