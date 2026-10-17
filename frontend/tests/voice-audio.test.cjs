const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const path=require('node:path')
const vm=require('node:vm')
const ts=require('typescript')
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'..','src','voiceAudio.ts'),'utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
}).outputText
const exportsObject={}
vm.runInNewContext(code,{exports:exportsObject,btoa,atob,Uint8Array,Float32Array,DataView,Set,Math,Error})

test('PCM encode is 16-bit little-endian, clipped and round-trips',()=>{
 const encoded=exportsObject.pcm16Base64(new Float32Array([-2,-1,-0.5,0,0.5,1,2]))
 const bytes=Buffer.from(encoded,'base64')
 assert.deepEqual(Array.from({length:7},(_,i)=>bytes.readInt16LE(i*2)),[-32768,-32768,-16384,0,16384,32767,32767])
 const decoded=exportsObject.decodePcm16(encoded)
 assert.equal(decoded[0],-1)
 assert.equal(decoded[3],0)
 assert.ok(Math.abs(decoded[5]-1)<0.0001)
})
test('invalid PCM is rejected explicitly',()=>{
 assert.throws(()=>exportsObject.decodePcm16(''),/invalid PCM/)
 assert.throws(()=>exportsObject.decodePcm16(btoa('x')),/invalid PCM/)
})

function audioHarness(getUserMedia){
 const counts={tracks:0,close:0,stop:0,disconnect:0,ports:0}
 const node=()=>({connect(){},disconnect(){counts.disconnect++}})
 class Context{
  sampleRate=16000;currentTime=0;state='running';destination={}
  audioWorklet={addModule:async()=>{}}
  async resume(){}
  createMediaStreamSource(){return node()}
  createGain(){return {...node(),gain:{value:1}}}
  createBuffer(_channels,length,rate){return {duration:length/rate,copyToChannel(){}}}
  createBufferSource(){return {...node(),start(){},stop(){counts.stop++}}}
  async close(){counts.close++;this.state='closed'}
 }
 class Worklet{
  port={close(){counts.ports++}}
  connect(){}
  disconnect(){counts.disconnect++}
 }
 const track={onended:null,stop(){counts.tracks++}}
 const stream={getTracks:()=>[track],getAudioTracks:()=>[track]}
 const exports={}
 vm.runInNewContext(code,{exports,btoa,atob,Uint8Array,Float32Array,DataView,Set,Math,Error,
  AudioContext:Context,AudioWorkletNode:Worklet,
  navigator:{mediaDevices:{getUserMedia:getUserMedia||(async()=>stream)}}})
 return {audio:new exports.VoiceAudio(),counts,stream}
}
test('End releases microphone, worklet, playback and context exactly once',async()=>{
 const {audio,counts}=audioHarness()
 await audio.prepare(()=>{},()=>assert.fail('unexpected audio error'))
 audio.play(exportsObject.pcm16Base64(new Float32Array(240)),'audio/pcm;rate=24000')
 audio.interrupt()
 assert.equal(counts.stop,1)
 await audio.close()
 await audio.close()
 assert.equal(counts.tracks,1)
 assert.equal(counts.close,1)
 assert.equal(counts.ports,1)
 assert.ok(counts.disconnect>=4)
})
test('late microphone grant after cancellation is immediately released',async()=>{
 let resolve,notify
 const waiting=new Promise(done=>{resolve=done})
 const requested=new Promise(done=>{notify=done})
 const {audio,counts,stream}=audioHarness(()=>{notify();return waiting})
 const prepare=audio.prepare(()=>{},()=>assert.fail('unexpected audio error'))
 await requested
 await audio.close()
 resolve(stream)
 await prepare
 assert.equal(counts.tracks,1)
 assert.equal(counts.close,1)
 assert.equal(counts.ports,0)
})
test('playback rejects unsupported formats and excessive queued audio',async()=>{
 const {audio}=audioHarness()
 assert.throws(()=>audio.play('AA==','audio/wav'),/unsupported audio/)
 const data=exportsObject.pcm16Base64(new Float32Array(24000))
 for(let i=0;i<9;i++)audio.play(data,'audio/pcm;rate=24000')
 assert.throws(()=>audio.play(data,'audio/pcm;rate=24000'),/fell behind/)
 await audio.close()
})
test('worklet batches microphone samples without changing sample order',()=>{
 let Processor
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'..','public','voice-capture.js'),'utf8'),{
  AudioWorkletProcessor:class{port={postMessage:samples=>output.push(Array.from(samples))}},
  Float32Array,registerProcessor:(_name,implementation)=>{Processor=implementation},
 })
 const output=[],processor=new Processor()
 for(let i=0;i<16;i++)processor.process([[new Float32Array(128).fill(i)]])
 assert.equal(output.length,1)
 assert.equal(output[0].length,2048)
 assert.equal(output[0][0],0)
 assert.equal(output[0][2047],15)
})
