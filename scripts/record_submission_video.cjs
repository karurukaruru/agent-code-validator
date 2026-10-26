'use strict';
// Offline-only browser recording. The prepared page embeds an existing report;
// this server has no POST route, provider client, credentials, or paid API path.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
function arg(name,fallback){const i=args.indexOf(name);return i<0?fallback:args[i+1]}
const smoke=args.includes('--smoke');
const output=path.resolve(arg('--output','outputs/video-development/run-01'));
const bins=path.join(root,'.video-deps/imageio_ffmpeg/binaries');
const ffmpeg=arg('--ffmpeg',fs.existsSync(bins)?path.join(bins,fs.readdirSync(bins).find(x=>/^ffmpeg.*\.exe$/.test(x))||'missing'):null);
const fps=6,frames=path.join(output,smoke?'smoke-frames':'frames'),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let browser,socket,server,seq=0,frame=0,origin='';
const pending=new Map(),errors=[],captures=[],actions=[],network=[],httpRequests=[];
async function wait(fn,label){for(let i=0;i<100;i++){try{const result=await fn();if(result)return result}catch{}await sleep(200)}throw Error('Timed out: '+label)}
function cmd(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method))},10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const result=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error('Browser evaluation failed');return result.result.value}
async function click(selector){const box=await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('Missing target');const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);if(box.y<0||box.y>800)throw Error('Click target outside viewport');for(const type of ['mouseMoved','mousePressed','mouseReleased'])await cmd('Input.dispatchMouseEvent',{type,...box,...(type==='mouseMoved'?{}:{button:'left',clickCount:1})});actions.push({action:'click',selector,at:Date.now()})}
async function top(){await evaluate("document.getElementById('sdk-video-scene')?.remove();window.scrollTo({top:0,behavior:'instant'})");await sleep(200)}
async function tab(name){await evaluate("document.querySelector('.workspace').scrollIntoView({block:'start',behavior:'instant'});window.scrollBy(0,-50)");await sleep(200);await click('[data-pane="'+name+'"]');await sleep(200)}
async function sdk(){
 await evaluate("(()=>{const frame=document.createElement('iframe');frame.id='sdk-video-scene';frame.title='Recorded installed SDK comparison';frame.style='position:fixed;left:0;top:33px;width:100%;height:calc(100% - 33px);border:0;z-index:90;background:#f4f5ef';frame.src='/sdk/';document.body.append(frame)})()");
 await wait(()=>evaluate("(()=>{const doc=document.getElementById('sdk-video-scene')?.contentDocument;const summary=doc?.getElementById('upgrade-summary');return summary&&!summary.hidden&&doc.body.textContent.includes('NEEDS_REVIEW')})()"),'recorded installed SDK report');
 await evaluate("document.getElementById('sdk-video-scene').contentDocument.getElementById('upgrade-summary').scrollIntoView({block:'start',behavior:'instant'})");await sleep(200);
}
async function capture(seconds){const count=smoke?1:Math.round(seconds*fps),start=Date.now();for(let i=0;i<count;i++){await sleep(Math.max(0,start+i*1000/fps-Date.now()));const shot=await cmd('Page.captureScreenshot',{format:'jpeg',quality:90,captureBeyondViewport:false});const data=Buffer.from(shot.data,'base64'),name='frame-'+String(frame++).padStart(6,'0')+'.jpg';fs.writeFileSync(path.join(frames,name),data);captures.push({name,sha256:hash(data),at:Date.now()})}}
(async()=>{
 const prepared=JSON.parse(fs.readFileSync(path.join(output,'preparation.json'),'utf8'));
 if(prepared.capture_mode!=='recorded-replay'||prepared.new_inference_during_recording!==false)throw Error('Explicit offline replay preparation required');
 if(!ffmpeg||!fs.existsSync(ffmpeg))throw Error('Install imageio-ffmpeg in .video-deps or pass --ffmpeg');
 fs.mkdirSync(frames,{recursive:true});if(fs.readdirSync(frames).length)throw Error('Preserve previous captures; use a fresh output directory');
 const scenes=JSON.parse(fs.readFileSync(path.join(output,'narration.json'),'utf8'));
 let timeline=0;
 for(const scene of scenes){if(!/^[a-z][a-z0-9_-]*$/.test(scene.scene))throw Error('Unsafe narration scene name');scene.voice_sha256=hash(fs.readFileSync(path.join(output,scene.scene+'.wav')));const probe=spawnSync(ffmpeg,['-hide_banner','-i',path.join(output,scene.scene+'.wav'),'-f','null','-'],{encoding:'utf8',windowsHide:true});const match=probe.stderr.match(/Duration: (\d+):(\d+):(\d+\.\d+)/);if(probe.status!==0||!match)throw Error('Missing or invalid narration: '+scene.scene);scene.voice_seconds=Number(match[1])*3600+Number(match[2])*60+Number(match[3]);scene.seconds=Math.ceil(scene.voice_seconds+0.75);scene.start=timeline;timeline+=scene.seconds}
 if(!(timeline>0&&timeline<=165))throw Error('Narrated cut exceeds the 165-second production limit: '+timeline);
 server=http.createServer((req,res)=>{httpRequests.push({method:req.method,url:req.url});const allowed={'/':['index.html','text/html; charset=utf-8'],'/report.json':['report.json','application/json']};if(prepared.sdk_report_included)Object.assign(allowed,{'/sdk/':['sdk/index.html','text/html; charset=utf-8'],'/sdk/report.json':['sdk/report.json','application/json'],'/sdk/manifest.json':['sdk/manifest.json','application/json']});const item=req.method==='GET'&&allowed[req.url];if(!item){res.writeHead(req.method==='GET'?404:405);res.end();return}const framePolicy=req.url.startsWith('/sdk/')?"'self'":"'none'";const connectPolicy=req.url.startsWith('/sdk/')?"'self'":"'none'";res.writeHead(200,{'Content-Type':item[1],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src "+connectPolicy+"; base-uri 'none'; frame-ancestors "+framePolicy});res.end(fs.readFileSync(path.join(output,'website',item[0])))});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
 const executable=arg('--browser',['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync));if(!executable)throw Error('Chromium browser missing');
 const profile=path.join(output,'browser-profile');
 browser=spawn(executable,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--disable-component-update','--disable-sync','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 const port=await wait(()=>{const file=path.join(profile,'DevToolsActivePort');return fs.existsSync(file)&&Number(fs.readFileSync(file,'utf8').split('\n')[0])},'private Chrome debugging port');
 const target=await wait(async()=>{const reply=await fetch('http://127.0.0.1:'+port+'/json/list');return(await reply.json()).find(x=>x.type==='page')},'private recording page');
 socket=new WebSocket(target.webSocketDebuggerUrl);socket.addEventListener('message',event=>{const message=JSON.parse(event.data);if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails);if(message.method==='Network.requestWillBeSent')network.push({url:message.params.request.url,method:message.params.request.method});const entry=pending.get(message.id);if(entry){clearTimeout(entry.timer);pending.delete(message.id);message.error?entry.reject(Error(JSON.stringify(message.error))):entry.resolve(message.result)}});
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})});
 await cmd('Page.enable');await cmd('Runtime.enable');await cmd('Network.enable');await cmd('Network.setBlockedURLs',{urls:['https://*']});await cmd('Emulation.setDeviceMetricsOverride',{width:1600,height:800,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:origin});
 await wait(()=>evaluate("document.getElementById('state')?.textContent==='REPLAY / IDLE'"),'recorded replay ready');
 await evaluate("document.body.style.paddingBottom='260px'");
 if(!await evaluate("document.getElementById('runtime-label').textContent.includes('recorded replay')&&document.getElementById('recording-disclosure').textContent.includes('RECORDED REPLAY')"))throw Error('Replay disclosure is missing');
 for(const scene of scenes){
  if(scene.action==='top')await top();
  if(scene.action==='replay'){await top();await click('#run')}
  if(scene.action==='repair'){await wait(()=>evaluate("document.getElementById('state').textContent==='REPLAY / PASS'"),'successful saved playback');await tab('repair')}
  if(scene.action==='evidence')await tab('evidence');
  if(scene.action==='sdk'){if(!prepared.sdk_report_included)throw Error('No verified installed SDK evidence prepared');await sdk()}
  actions.push({action:'scene',scene:scene.scene,start:scene.start,seconds:scene.seconds,at:Date.now()});
  await capture(scene.seconds);console.log(JSON.stringify({scene:scene.scene,seconds:scene.seconds,frames:frame}));
 }
 if(errors.length||!await evaluate("document.getElementById('after-value').textContent==='21'&&document.getElementById('checks').textContent==='8/8'&&document.getElementById('mutation').textContent==='YES'"))throw Error('Recorded UI did not show the independently verified source result');
 if(network.some(x=>!x.url.startsWith(origin))||httpRequests.some(x=>x.method!=='GET'))throw Error('Unexpected nonlocal request or mutation during offline recording');
 const manifest={status:smoke?'SMOKE_VERIFIED':'CAPTURED',...prepared,capture_mode:smoke?'recorded-replay-smoke':'recorded-replay',capture_fps:fps,width:1600,height:800,duration_seconds:smoke?null:frame/fps,planned_duration_seconds:timeline,scenes,actions,captures,browser_errors:errors,network_requests:network,http_requests:httpRequests,new_model_requests:0,new_search_requests:0,voice:JSON.parse(fs.readFileSync(path.join(output,'voice.json'),'utf8').replace(/^\uFEFF/,'')),note:smoke?'One verification screenshot per scene, not an encoded or complete video capture. Cannot be encoded as a production video.':'Actual Chrome screenshots of an explicitly labelled saved-run replay. All source API calls happened before capture. Playback timing is editorial.'};
 fs.writeFileSync(path.join(output,smoke?'smoke.json':'capture.json'),JSON.stringify(manifest,null,2)+'\n');console.log(JSON.stringify({status:manifest.status,seconds:manifest.duration_seconds,planned_seconds:timeline,frames:frame,provider:prepared.provider,new_model_requests:0}));
})().catch(error=>{console.error(error.message);process.exitCode=1}).finally(()=>{for(const entry of pending.values())clearTimeout(entry.timer);if(socket)socket.close();if(browser)browser.kill();if(server)server.close()});
