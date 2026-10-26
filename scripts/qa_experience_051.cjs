'use strict';
// Synthetic localhost transport tests in real Chrome. No provider client or key.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const assert = require('node:assert/strict'), {spawn} = require('node:child_process'),crypto=require('node:crypto');
const root = path.resolve(__dirname, '..');
const outputIndex=process.argv.indexOf('--output');
const output = path.resolve(root,outputIndex<0?'evidence/experience-051':process.argv[outputIndex+1]);
if (fs.existsSync(output)) throw Error('Preserve previous evidence; choose a new output path');
fs.mkdirSync(output, {recursive:true});
const live = fs.readFileSync(path.join(root,'patchcourt/web/live.html'),'utf8');
const inspector = fs.readFileSync(path.join(root,'patchcourt/web/index.html'),'utf8');
const report = JSON.parse(fs.readFileSync(path.join(root,'evidence/development-050/deepseek-live-01/report.json'),'utf8'));
const sdk = fs.readFileSync(path.join(root,'evidence/upgrade-run-050/real-sdk/upgrade/report.json'));
const replay = live.replace('<script>', '<script id="recorded-data" type="application/json">'+JSON.stringify(report).replace(/</g,'\\u003c')+'</script><script>');
const fixtureBanner = '<div style="padding:8px 5%;background:#e6ebfc;font:12px Arial">UI TRANSPORT TEST · Saved-state fixture · No model inference</div>';
const requests=[],checks=[],errors=[],pending=new Map();
let browser,socket,seq=0,session='synthetic-session-1',sessionDelay=1000,mode='deny',failState=false;
let runs=0,state='IDLE',held=null,holdNext=false;
function snapshot() {return {provider:'deepseek',model:'deepseek-flash',status:state,runs,events:state==='PASS'?report.events:[],report:state==='PASS'?report:null};}
function send(res,status,value,type='application/json') {res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store'});res.end(type.startsWith('application/json')?JSON.stringify(value):value);}
const server=http.createServer((req,res)=>{
 requests.push({method:req.method,url:req.url});
 if(req.method==='GET'&&req.url==='/')return send(res,200,live.replace('<body>','<body>'+fixtureBanner),'text/html; charset=utf-8');
 if(req.method==='GET'&&req.url==='/replay')return send(res,200,replay,'text/html; charset=utf-8');
 if(req.method==='GET'&&req.url==='/sdk')return send(res,200,inspector,'text/html; charset=utf-8');
 if(req.method==='GET'&&req.url==='/report.json')return send(res,200,sdk,'text/plain');
 if(req.method==='GET'&&req.url==='/session')return setTimeout(()=>send(res,200,{session,provider:'deepseek',model:'deepseek-flash'}),sessionDelay);
 if(req.method==='GET'&&req.url==='/state'){
  if(failState)return send(res,503,{error:'Synthetic transport outage'});
  if(holdNext){holdNext=false;held={res,value:snapshot()};return;}
  return send(res,200,snapshot());
 }
 if(req.method==='POST'&&req.url==='/run'){
  if(mode==='deny')return send(res,403,{error:'Local session required'});
  runs++;state='RUNNING';
  if(mode==='lost')return res.destroy();
  return send(res,202,{status:'RUNNING'});
 }
 send(res,404,{error:'Not found'});
});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(fn,label){for(let i=0;i<100;i++){try{if(await fn())return;}catch{}await sleep(100);}throw Error('Timed out: '+label);}
function command(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP timeout: '+method)),10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
function ok(value,name){assert.ok(value,name);checks.push(name);}
function posts(){return requests.filter(row=>row.method==='POST').length;}
async function shot(name){const r=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(output,name+'.png'),Buffer.from(r.data,'base64'));}
async function key(value){await command('Input.dispatchKeyEvent',{type:'keyDown',key:value});await command('Input.dispatchKeyEvent',{type:'keyUp',key:value});}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
 const exe=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 if(!exe)throw Error('Installed Chrome or Edge required');
 const profile=path.join(root,'outputs','experience-051-profiles',path.basename(output)+'-'+process.pid);fs.mkdirSync(profile,{recursive:true});
 browser=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let port;await wait(()=>{const name=path.join(profile,'DevToolsActivePort');if(fs.existsSync(name))port=Number(fs.readFileSync(name,'utf8').split('\n')[0]);return port;},'private Chrome port');
 let target;await wait(async()=>{target=(await(await fetch('http://127.0.0.1:'+port+'/json/list')).json()).find(item=>item.type==='page');return target;},'Chrome page');
 socket=new WebSocket(target.webSocketDebuggerUrl);
 socket.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}});
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 await command('Page.enable');await command('Runtime.enable');await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await command('Page.navigate',{url:base});await wait(()=>evaluate("!!document.getElementById('run')"),'initial DOM');
 ok(await evaluate("document.getElementById('run').disabled"),'Run disabled before session and state handshake');
 await wait(()=>evaluate("!document.getElementById('run').disabled"),'local handshake');sessionDelay=0;
 ok(await evaluate("document.getElementById('connection').hidden"),'Successful handshake clears connecting notice');
 await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='DISCONNECTED'"),'expired session notice');
 await sleep(700);
 ok(await evaluate("document.getElementById('connection-message').textContent.includes('expired')"),'HTTP 403 explanation survives polling');
 ok(await evaluate("document.getElementById('run').disabled"),'Expired session cannot submit another inference request');
 const denied=posts();await evaluate("document.getElementById('run').click()");await sleep(400);ok(posts()===denied,'Disabled Run does not repeat a denied POST');
 session='synthetic-session-2';const beforeReconnect=posts();await evaluate("document.getElementById('reconnect').click()");await wait(()=>evaluate("!document.getElementById('run').disabled"),'read-only reconnect');
 ok(posts()===beforeReconnect,'Reconnect uses GET only and does not execute a workflow');
 mode='lost';await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='DISCONNECTED'"),'unconfirmed POST');
 ok(await evaluate("document.getElementById('connection-message').textContent.includes('may already be active')"),'Lost POST response explains uncertain execution');
 const lost=posts();await sleep(600);ok(posts()===lost,'Unconfirmed POST is never automatically retried');
 ok(await evaluate("document.getElementById('run').disabled"),'Run stays disabled until uncertain execution is checked');
 state='PASS';await evaluate("document.getElementById('reconnect').click()");await wait(()=>evaluate("document.getElementById('after-value').textContent==='21'"),'completed saved result');
 ok(posts()===lost,'Reconnect recovers completed task without a second POST');
 ok(await evaluate("document.getElementById('checks').textContent==='8/8'"),'Recovered result keeps original verification evidence');
 mode='deny';await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='DISCONNECTED'"),'failed restart');
 ok(await evaluate("document.getElementById('after-value').textContent==='21'&&document.getElementById('checks').textContent==='8/8'"),'Declined new run preserves the previous completed result');
 await evaluate("document.getElementById('reconnect').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='PASS'"),'completed result after declined restart');
 failState=true;await wait(()=>evaluate("document.getElementById('state').textContent==='DISCONNECTED'"),'poll disconnection');
 ok(await evaluate("document.getElementById('after-value').textContent==='21'&&document.getElementById('connection-message').textContent.includes('last received')"),'Disconnect retains completed value with explicit stale-evidence notice');
 await shot('connection-desktop');
 await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(200);
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Connection recovery fits mobile width');await shot('connection-mobile');
 failState=false;await evaluate("document.getElementById('reconnect').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='PASS'"),'completed reconnect');
 mode='accept';holdNext=true;await wait(()=>held,'held stale poll');await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='RUNNING'"),'accepted new run');
 send(held.res,200,held.value);held=null;await sleep(100);
 ok(await evaluate("document.getElementById('after-value').textContent==='—'&&document.getElementById('run').disabled"),'Late previous-state response cannot restore prior success or enable duplicate execution');
 state='PASS';await wait(()=>evaluate("document.getElementById('state').textContent==='PASS'"),'new saved result');
 await evaluate("document.getElementById('tab-timeline').focus()");await key('ArrowRight');
 ok(await evaluate("document.activeElement.id==='tab-repair'&&document.getElementById('tab-repair').getAttribute('aria-selected')==='true'&&!document.getElementById('repair').hidden&&document.getElementById('timeline').hidden"),'Arrow key selects and focuses associated repair panel');
 await key('End');ok(await evaluate("document.activeElement.id==='tab-evidence'"),'End selects final live tab');await key('Home');ok(await evaluate("document.activeElement.id==='tab-timeline'"),'Home selects first live tab');
 await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await command('Page.navigate',{url:base+'/sdk'});
 await wait(()=>evaluate("document.getElementById('run-id').textContent.includes('8170')||document.getElementById('case-title').textContent.includes('NVIDIA')"),'SDK report');
 await evaluate("document.getElementById('tab-protocol').focus()");await key('End');
 ok(await evaluate("document.activeElement.id==='tab-provenance'&&document.getElementById('tab-provenance').getAttribute('aria-selected')==='true'&&!document.getElementById('pane-provenance').hidden"),'SDK keyboard tabs expose linked provenance panel');await shot('sdk-keyboard');
 await command('Page.navigate',{url:base+'/replay'});await wait(()=>evaluate("document.getElementById('state').textContent==='REPLAY / IDLE'"),'recorded replay');
 const endpointsBefore=requests.filter(row=>['/session','/state','/run'].includes(row.url)).length;
 await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});const start=Date.now();await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='REPLAY / PASS'"),'reduced motion replay');
 ok(Date.now()-start<1500,'Reduced-motion replay reveals saved evidence without staged animation');
 ok(await evaluate("document.getElementById('connection').hidden&&document.getElementById('after-value').textContent==='21'"),'Recorded mode stays offline and preserves real saved value');await sleep(400);
 ok(requests.filter(row=>['/session','/state','/run'].includes(row.url)).length===endpointsBefore,'Replay makes no session, state or run request');
 ok(await evaluate("getComputedStyle(document.getElementById('state')).animationName==='none'"),'Reduced-motion mode disables pulse animation');
 ok(errors.length===0,'No unhandled browser JavaScript exceptions');
 fs.writeFileSync(path.join(output,'qa-results.json'),JSON.stringify({status:'PASS',scope:'Real Chrome UI/transport tests using synthetic localhost states, including a saved development-report fixture. No provider HTTP, credentials or model execution.',checks,errors,requests,source_sha256:{'patchcourt/web/live.html':crypto.createHash('sha256').update(live).digest('hex'),'patchcourt/web/index.html':crypto.createHash('sha256').update(inspector).digest('hex')},new_model_requests:0,new_search_requests:0},null,2)+'\n');
 console.log(JSON.stringify({status:'PASS',checks:checks.length,output,new_model_requests:0}));
})().catch(error=>{fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:error.message,checks,errors,requests},null,2));console.error(error.message);process.exitCode=1;}).finally(()=>{if(held)held.res.destroy();for(const item of pending.values())clearTimeout(item.timer);if(socket)socket.close();if(browser)browser.kill();server.close();});
