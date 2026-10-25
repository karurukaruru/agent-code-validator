'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'dist/live-video'),frames=path.join(out,'frames');
const ffmpeg=path.join(root,'.video-deps/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe');
const scenes=JSON.parse(fs.readFileSync(path.join(__dirname,'live_video_narration.json'),'utf8'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const get=url=>new Promise((resolve,reject)=>{const req=http.get(url,res=>{let data='';res.on('data',x=>data+=x);res.on('end',()=>resolve({status:res.statusCode,data}));});req.setTimeout(2000,()=>req.destroy());req.on('error',reject)});
let browser,socket,seq=0,frame=0;const pending=new Map(),errors=[],captures=[],actions=[];
async function wait(fn,label){for(let i=0;i<80;i++){try{const r=await fn();if(r)return r}catch{}await sleep(250)}throw Error('Timed out: '+label)}
function cmd(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout'))},10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function scroll(y){await evaluate(`window.scrollTo({top:${y},behavior:'smooth'})`);actions.push({action:'scroll',y,at:Date.now()});await sleep(400)}
async function click(selector){const box=await evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);if(box.y<0||box.y>800)throw Error('Target out of view');await cmd('Input.dispatchMouseEvent',{type:'mouseMoved',...box});await cmd('Input.dispatchMouseEvent',{type:'mousePressed',...box,button:'left',clickCount:1});await cmd('Input.dispatchMouseEvent',{type:'mouseReleased',...box,button:'left',clickCount:1});actions.push({action:'click',selector,at:Date.now()})}
async function capture(seconds){const count=Math.ceil(seconds*8),start=Date.now();for(let i=0;i<count;i++){await sleep(Math.max(0,start+i*125-Date.now()));const shot=await cmd('Page.captureScreenshot',{format:'jpeg',quality:90,captureBeyondViewport:false});const data=Buffer.from(shot.data,'base64'),name=`frame-${String(frame++).padStart(5,'0')}.jpg`;fs.writeFileSync(path.join(frames,name),data);captures.push({name,sha256:hash(data),at:Date.now()})}}
(async()=>{
 fs.mkdirSync(frames,{recursive:true});if(fs.readdirSync(frames).length)throw Error('Preserve earlier recording; frames directory must be empty');
 if((await get('http://127.0.0.1:8780/state')).status!==200)throw Error('Start live demo server first');
 for(const scene of scenes){const probe=spawnSync(ffmpeg,['-hide_banner','-i',path.join(out,scene.scene+'.wav'),'-f','null','-'],{encoding:'utf8',windowsHide:true});const match=probe.stderr.match(/Duration: (\d+):(\d+):(\d+\.\d+)/);if(!match)throw Error('Missing narration');scene.voice_seconds=Number(match[1])*3600+Number(match[2])*60+Number(match[3]);scene.seconds=Math.ceil(scene.voice_seconds+1)}
 const exe=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);if(!exe)throw Error('Browser missing');
 browser=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--disable-sync','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9248','--user-data-dir='+path.join(out,'browser-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
 const target=await wait(async()=>JSON.parse((await get('http://127.0.0.1:9248/json/list')).data).find(x=>x.type==='page'),'browser');socket=new WebSocket(target.webSocketDebuggerUrl);socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}});await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true})});
 await cmd('Page.enable');await cmd('Runtime.enable');await cmd('Emulation.setDeviceMetricsOverride',{width:1600,height:800,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:'http://127.0.0.1:8780'});await wait(()=>evaluate("document.getElementById('state')?.textContent==='IDLE'"),'idle UI');
 let timeline=0;
 for(const scene of scenes){scene.start=timeline;
  if(scene.scene==='run')await click('#run');
  if(scene.scene==='repair'){const state=JSON.parse((await get('http://127.0.0.1:8780/state')).data);if(state.status!=='PASS')throw Error('Live workflow did not pass within narration interval: '+state.status);await scroll(450);await click('[data-pane="repair"]')}
  if(scene.scene==='task'){await scroll(0)}
  if(scene.scene==='evidence'){await scroll(450);await click('[data-pane="evidence"]')}
  if(scene.scene==='close'){await scroll(0)}
  await capture(scene.seconds);
  if(scene.scene==='run'){while(scene.seconds<60&&JSON.parse((await get('http://127.0.0.1:8780/state')).data).status==='RUNNING'){await capture(2);scene.seconds+=2}}
  timeline+=scene.seconds;console.log(JSON.stringify({scene:scene.scene,seconds:scene.seconds,frames:frame}));
 }
 const state=JSON.parse((await get('http://127.0.0.1:8780/state')).data);if(errors.length||state.status!=='PASS')throw Error('Recording QA failed');
 const manifest={status:'CAPTURED',live_inference:true,provider:'glm',model:'glm-5.3-flash',capture_fps:8,duration_seconds:frame/8,scenes,actions,captures,browser_errors:errors,report:state.report,voice:'Microsoft Zira Desktop (local synthesized narration)',note:'Actual browser screenshots during a live API workflow; pauses and narration are editorial; no fabricated UI or model results.'};fs.writeFileSync(path.join(out,'capture.json'),JSON.stringify(manifest,null,2));console.log(JSON.stringify({status:'CAPTURED',duration:frame/8,requests:state.report.requests.length,tokens:state.report.total_reported_tokens}));
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
