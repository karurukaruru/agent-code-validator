'use strict';
// Exercise the exported judge package without starting an inference service.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
function option(name,fallback){const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1]}
const folder=path.resolve(option('--package',path.join(root,'outputs/judge-demo-development-v2')));
const out=path.resolve(option('--output',path.join(root,'evidence/judge-browser-development')));
if(fs.existsSync(out))throw Error('Refusing to overwrite browser evidence');
fs.mkdirSync(out,{recursive:true});
const types={'.html':'text/html; charset=utf-8','.json':'application/json','.whl':'application/octet-stream'};
let browser,socket,seq=0;const checks=[],errors=[],requests=[],pending=new Map();
const server=http.createServer((req,res)=>{
 requests.push({method:req.method,url:req.url});
 const decoded=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 const file=path.resolve(folder,'.'+(decoded==='/'?'/index.html':decoded));
 if(req.method!=='GET'||!file.startsWith(folder+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return}
 res.writeHead(200,{'Content-Type':types[path.extname(file)]||'text/plain'});fs.createReadStream(file).pipe(res);
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let i=0;i<100;i++){try{const v=await fn();if(v)return v}catch{}await sleep(200)}throw Error('Timed out')}
function cmd(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP timeout')),10000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
function ok(value,name){assert.ok(value,name);checks.push(name)}
async function shot(name){const r=await cmd('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))}
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const exe=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);ok(exe,'Installed browser available');
 browser=spawn(exe,['--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9253','--user-data-dir='+path.join(root,'outputs/judge-qa-profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
 const target=await wait(async()=>(await(await fetch('http://127.0.0.1:9253/json/list')).json()).find(x=>x.type==='page'));
 socket=new WebSocket(target.webSocketDebuggerUrl);socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}});
 await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true})});await cmd('Page.enable');await cmd('Runtime.enable');
 await cmd('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:base});
 await wait(()=>evaluate("document.title.includes('inspect the repair')"));ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Landing desktop has no horizontal overflow');
 ok(await evaluate("document.body.textContent.includes('no API key needed')"),'Landing discloses recorded evidence');await shot('landing-desktop');
 const links=await evaluate("[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).filter(x=>x&&!x.startsWith('https:'))");
 for(const link of new Set(links))ok((await fetch(new URL(link,base))).status===200,'Exported link works: '+link);
 await cmd('Page.navigate',{url:base+'/repair.html'});await wait(()=>evaluate("document.getElementById('state')?.textContent==='REPLAY / IDLE'"));
 ok(await evaluate("document.getElementById('runtime-label').textContent.includes('recorded replay')"),'Replay identifies recording and provider');
 ok(await evaluate("document.getElementById('after-value').textContent==='—'"),'No recovered value before playback');
 await evaluate("document.getElementById('run').click()");await wait(()=>evaluate("document.getElementById('state').textContent==='REPLAY / PASS'"));
 ok(await evaluate("document.getElementById('after-value').textContent==='21'"),'Recovered task value comes from saved execution');
 ok(await evaluate("document.getElementById('checks').textContent==='8/8'"),'Independent controls displayed');
 ok(await evaluate("document.getElementById('mutation').textContent==='YES'"),'Corrupted repair rejection displayed');
 ok(await evaluate("document.documentElement.scrollWidth<=innerWidth"),'Replay desktop has no overflow');await shot('repair-desktop');
 await evaluate("document.querySelector('[data-pane=repair]').click()");ok(await evaluate("document.getElementById('check-list').children.length===8"),'Repair pane contains eight actual controls');await shot('repair-checks');
 await evaluate("document.querySelector('[data-pane=evidence]').click()");ok(await evaluate("document.getElementById('summary').textContent.includes('returned_models')"),'Requested and returned model identity visible');await shot('repair-evidence');
 await evaluate("document.getElementById('run').click()");ok(await evaluate("document.getElementById('after-value').textContent==='—'&&document.getElementById('checks').textContent==='—'&&document.getElementById('mutation').textContent==='—'"),'Second replay clears all prior success indicators');
 await wait(()=>evaluate("document.getElementById('state').textContent==='REPLAY / PASS'"));
 await cmd('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await evaluate("document.querySelector('[data-pane=timeline]').click()");await sleep(300);
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Replay mobile has no horizontal overflow');await shot('repair-mobile');
 await cmd('Page.navigate',{url:base});await wait(()=>evaluate("document.title.includes('inspect the repair')"));ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Landing mobile has no horizontal overflow');await shot('landing-mobile');
 await cmd('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:base+'/sdk-upgrade.html'});await wait(()=>evaluate("document.body.textContent.includes('UNHEALTHY_BASELINE')||document.body.textContent.includes('Unhealthy baseline')"));
 ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'SDK inspector desktop has no horizontal overflow');await shot('sdk-desktop');
 ok(errors.length===0,'No browser JavaScript exceptions');ok(requests.every(r=>r.method==='GET'),'Playback made no mutating request');ok(!requests.some(r=>['/run','/session','/state'].includes(r.url)),'Static playback made no inference-service requests');
 fs.writeFileSync(path.join(out,'qa-results.json'),JSON.stringify({status:'PASS',checks,errors,package_manifest:JSON.parse(fs.readFileSync(path.join(folder,'package-manifest.json'),'utf8')),requests},null,2));console.log(JSON.stringify({status:'PASS',checks:checks.length,output:out}));
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:e.message,checks,errors},null,2));console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill();server.close()});
