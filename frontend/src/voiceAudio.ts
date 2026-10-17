export function pcm16Base64(samples:Float32Array):string {
 const bytes=new Uint8Array(samples.length*2),view=new DataView(bytes.buffer)
 samples.forEach((sample,index)=>{
  const clipped=Math.max(-1,Math.min(1,sample))
  view.setInt16(index*2,Math.round(clipped*(clipped<0?32768:32767)),true)
 })
 let binary=''
 bytes.forEach(byte=>{binary+=String.fromCharCode(byte)})
 return btoa(binary)
}

export function decodePcm16(data:string):Float32Array {
 const binary=atob(data)
 if(!binary.length||binary.length%2)throw new Error('Received invalid PCM audio')
 const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0)),view=new DataView(bytes.buffer)
 return Float32Array.from({length:binary.length/2},(_,index)=>view.getInt16(index*2,true)/32768)
}

export class VoiceAudio {
 private context:AudioContext
 private stream:MediaStream|null=null
 private source:MediaStreamAudioSourceNode|null=null
 private capture:AudioWorkletNode|null=null
 private silent:GainNode|null=null
 private playing=new Set<AudioBufferSourceNode>()
 private nextTime=0
 private closed=false
 constructor(){
  this.context=new AudioContext({sampleRate:16000})
 }
 async prepare(onAudio:(data:string)=>void,onError:(message:string)=>void){
  await this.context.resume()
  if(this.closed)return
  if(this.context.sampleRate!==16000)throw new Error('This browser cannot capture voice at the required 16 kHz. Try a recent Edge or Chrome.')
  const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}})
  if(this.closed){stream.getTracks().forEach(track=>track.stop());return}
  this.stream=stream
  stream.getAudioTracks().forEach(track=>{track.onended=()=>onError('Microphone access ended. Start a new session when it is available.')})
  await this.context.audioWorklet.addModule('/voice-capture.js')
  if(this.closed)return
  this.source=this.context.createMediaStreamSource(stream)
  this.capture=new AudioWorkletNode(this.context,'katalyst-voice-capture')
  this.capture.port.onmessage=(event:MessageEvent<Float32Array>)=>{
   if(this.closed)return
   try{onAudio(pcm16Base64(event.data))}
   catch{onError('Microphone audio could not be sent. The voice session has ended.')}
  }
  this.capture.onprocessorerror=()=>onError('Microphone processing failed. The voice session has ended.')
  this.silent=this.context.createGain()
  this.silent.gain.value=0
  this.source.connect(this.capture)
  this.capture.connect(this.silent)
  this.silent.connect(this.context.destination)
 }
 play(data:string,mimeType:string){
  if(this.closed)return
  if(!/^audio\/pcm(?:;|$)/.test(mimeType))throw new Error('The Live model returned an unsupported audio format.')
  const match=mimeType.match(/rate=(\d+)/),rate=match?Number(match[1]):24000
  if(![16000,24000,48000].includes(rate)||data.length>1_000_000)throw new Error('The Live model returned invalid audio.')
  if(this.nextTime-this.context.currentTime>8)throw new Error('Audio playback fell behind. End the session and try again.')
  const samples=decodePcm16(data),buffer=this.context.createBuffer(1,samples.length,rate)
  buffer.copyToChannel(samples,0)
  const source=this.context.createBufferSource()
  source.buffer=buffer
  source.connect(this.context.destination)
  this.playing.add(source)
  source.onended=()=>{source.disconnect();this.playing.delete(source)}
  const start=Math.max(this.context.currentTime,this.nextTime)
  source.start(start)
  this.nextTime=start+buffer.duration
 }
 interrupt(){
  this.playing.forEach(source=>{source.stop();source.disconnect()})
  this.playing.clear();this.nextTime=0
 }
 async close(){
  if(this.closed)return
  this.closed=true
  this.stream?.getTracks().forEach(track=>{track.onended=null;track.stop()})
  this.capture?.port.close()
  this.capture?.disconnect();this.source?.disconnect();this.silent?.disconnect()
  this.interrupt()
  if(this.context.state!=='closed')await this.context.close()
 }
}
