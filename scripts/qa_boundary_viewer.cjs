'use strict';
// Native Chrome DevTools protocol, no npm dependencies or API access.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),evidence=path.resolve(process.argv[2]||path.join(root,'evidence/boundary-run')),out=path.join(evidence,'browser');
fs.mkdirSync(out,{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let browser,socket,seq=0;const pending=new Map(),errors=[],checks=[];
async function wait(fn){for(let i=0;i<80;i++){try{if(await fn())return}catch{}await sleep(150)}throw Error('Timed out')}
function cmd(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP timeout')),10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
function ok(value,name){assert.ok(value,name);checks.push(name)}
async function load(name){
 const file=path.join(evidence,name,'report.json'),run=JSON.parse(fs.readFileSync(file,'utf8'));
 const doc=await cmd('DOM.getDocument'),input=await cmd('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#file'});
 await cmd('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[file]});
 await wait(()=>evaluate("document.getElementById('run-id').textContent==="+JSON.stringify(run.run_id)));
}
(async()=>{
 const exe=process.env.CHROME_PATH||['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','/usr/bin/google-chrome','/usr/bin/chromium'].find(fs.existsSync);
 if(!exe)throw Error('Set CHROME_PATH to a local Chrome/Chromium executable');
 const profile=fs.mkdtempSync(path.join(root,'outputs/boundary-qa-'));
 browser=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9253','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 await wait(async()=>Boolean((await (await fetch('http://127.0.0.1:9253/json/list')).json()).find(x=>x.type==='page')));
 const target=(await (await fetch('http://127.0.0.1:9253/json/list')).json()).find(x=>x.type==='page');
 socket=new WebSocket(target.webSocketDebuggerUrl);socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}});
 await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true})});await cmd('Page.enable');await cmd('Runtime.enable');
 await cmd('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await cmd('Page.navigate',{url:pathToFileURL(path.join(evidence,'source-regression/index.html')).href});
 await wait(()=>evaluate("Boolean(document.getElementById('file'))"));await load('source-regression');
 ok(await evaluate("document.getElementById('case-status').textContent==='FAIL'"),'Regression verdict displayed');
 ok(await evaluate("[...document.querySelectorAll('#boundary-contracts .badge')].map(x=>x.textContent).join(',')==='PASS,FAIL,FAIL'"),'All three contract checks displayed');
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Desktop has no horizontal overflow');
 let screenshot=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'desktop.png'),Buffer.from(screenshot.data,'base64'));
 await load('source-recovery');
 ok(await evaluate("document.getElementById('case-status').textContent==='NEEDS REVIEW'&&document.getElementById('pane-protocol').textContent.includes('candidate restores')"),'Recovery preserves unhealthy-baseline warning');
 await evaluate("document.querySelector('[data-pane=repair]').click()");
 ok(await evaluate("document.getElementById('pane-repair').textContent.includes('21')&&document.getElementById('pane-repair').textContent.includes('deterministic task simulation')"),'Recovered value and deterministic scope displayed');
 await evaluate("document.querySelector('[data-pane=provenance]').click()");
 ok(await evaluate("document.getElementById('pane-provenance').textContent.includes('framework_input')&&document.getElementById('pane-provenance').textContent.includes('source_sha256')"),'Captured boundaries and source hashes accessible');
 await load('source-both-broken');await evaluate("document.querySelector('[data-pane=protocol]').click()");
 ok(await evaluate("document.getElementById('case-status').textContent==='NEEDS REVIEW'&&document.getElementById('pane-protocol').textContent.includes('No structural differences')"),'Identical broken outputs do not show PASS');
 await cmd('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(200);
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile has no horizontal overflow');
 screenshot=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'mobile.png'),Buffer.from(screenshot.data,'base64'));
 await load('source-healthy');ok(await evaluate("document.getElementById('case-status').textContent==='PASS'"),'Healthy pair displays PASS');
 ok(errors.length===0,'No browser runtime exceptions');
 fs.writeFileSync(path.join(out,'qa-results.json'),JSON.stringify({status:'PASS',checks,errors,provider_requests:0},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length}));
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
