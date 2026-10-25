'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'evidence/live-browser');fs.mkdirSync(out,{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let browser,socket,seq=0;const pending=new Map(),errors=[],checks=[];
async function wait(fn){for(let i=0;i<80;i++){try{let r=await fn();if(r)return r}catch{}await sleep(250)}throw Error('Timed out')}
function cmd(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP timeout')),10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
function ok(value,name){assert.ok(value,name);checks.push(name)}
(async()=>{
 const state=await (await fetch('http://127.0.0.1:8780/state')).json();ok(state.status==='PASS','Actual recorded workflow completed');
 const denied=await fetch('http://127.0.0.1:8780/run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});ok(denied.status===403,'Unauthenticated POST cannot trigger model calls');
 const session=await (await fetch('http://127.0.0.1:8780/session')).json();
 const badOrigin=await fetch('http://127.0.0.1:8780/run',{method:'POST',headers:{'Content-Type':'application/json','Origin':'https://evil.invalid','X-PatchCourt-Session':session.session},body:'{}'});ok(badOrigin.status===403,'Cross-origin POST rejected');
 const body=await fetch('http://127.0.0.1:8780/run',{method:'POST',headers:{'Content-Type':'application/json','Origin':'http://127.0.0.1:8780','X-PatchCourt-Session':session.session},body:'{"code":"bad"}'});ok(body.status===400,'Arbitrary payload rejected');
 ok((await fetch('http://127.0.0.1:8780/.env')).status===404,'Credential file path unavailable');
 const exe=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 browser=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9249','--user-data-dir='+path.join(root,'outputs/live-qa-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
 const target=await wait(async()=>(await (await fetch('http://127.0.0.1:9249/json/list')).json()).find(x=>x.type==='page'));
 socket=new WebSocket(target.webSocketDebuggerUrl);socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}});await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true})});await cmd('Page.enable');await cmd('Runtime.enable');
 await cmd('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:'http://127.0.0.1:8780'});await wait(()=>evaluate("document.getElementById('state')?.textContent==='PASS'"));
 ok(await evaluate("document.getElementById('after-value').textContent==='21'"),'Recovered task displayed');ok(await evaluate("document.getElementById('checks').textContent==='8/8'"),'Independent checks displayed');ok(await evaluate("document.getElementById('mutation').textContent==='YES'"),'Negative control displayed');
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Desktop has no horizontal overflow');
 let image=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'desktop.png'),Buffer.from(image.data,'base64'));
 await evaluate("document.querySelector('[data-pane=repair]').click()");ok(await evaluate("document.getElementById('repair').classList.contains('active')&&document.getElementById('check-list').children.length===8"),'Repair tab shows actual mapping and controls');
 await cmd('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(300);ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile has no horizontal overflow');
 image=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'mobile.png'),Buffer.from(image.data,'base64'));ok(errors.length===0,'No browser runtime exceptions');
 const after=await (await fetch('http://127.0.0.1:8780/state')).json();ok(after.runs===state.runs,'Read-only QA and rejected requests caused no inference');
 fs.writeFileSync(path.join(out,'qa-results.json'),JSON.stringify({status:'PASS',checks,errors,source_report_created_at:state.report.created_at},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length}));
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
