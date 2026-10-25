/* Upgrade viewer QA against recorded SDK runs. Node 22+ and installed Chrome/Edge.
 * Serves the current viewer on loopback; no browser downloads or provider calls.
 * Optional positional arguments: upgrade-report, text-control-report, uncertain-report.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'evidence', 'upgrade-run', 'browser');
const source = path.join(root, 'patchcourt', 'web', 'index.html');
const reportPaths = {
  upgrade: path.resolve(root, process.argv[2] || 'evidence/upgrade-run/real-sdk/upgrade/report.json'),
  text: path.resolve(root, process.argv[3] || 'evidence/upgrade-run/real-sdk/text-control/report.json'),
  uncertain: path.resolve(root, process.argv[4] || 'evidence/upgrade-run/attempts/sdk-upgrade-first/report.json'),
};
const browser = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(fs.existsSync);
if (!browser) throw new Error('Installed Chrome or Edge required. No browser is downloaded.');
const reports = Object.fromEntries(Object.entries(reportPaths).map(([name, file]) => [name, JSON.parse(fs.readFileSync(file, 'utf8'))]));
assert.equal(reports.upgrade.mode, 'upgrade-run');
assert.equal(reports.upgrade.status, 'NEEDS_REVIEW', 'Use a recorded double-failure upgrade report');
assert.equal(reports.text.status, 'PASS', 'Use a real SDK text-control PASS report');
assert.equal(reports.uncertain.status, 'INCONCLUSIVE', 'Use a recorded inconclusive upgrade report');
fs.mkdirSync(output, {recursive:true});
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'patchcourt-upgrade-browser-'));
const checks = [], errors = [], chooserEvents = [], captures = [];
const pending = new Map();
let server, chrome, socket, sequence = 0, browserVersion, serverOrigin, exported;
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
function get(url) { return new Promise((resolve, reject) => { const request = http.get(url, response => { let body=''; response.setEncoding('utf8'); response.on('data', chunk => body += chunk); response.on('end', () => resolve({status:response.statusCode, body})); }); request.setTimeout(1500, () => request.destroy(new Error('HTTP timeout'))); request.on('error', reject); }); }
async function waitFor(read, label) {
  for (let attempt=0; attempt<80; attempt++) { try { const result=await read(); if(result) return result; } catch (_) {} await sleep(150); }
  throw new Error('Timed out waiting for ' + label);
}
function command(method, params={}) {
  const id=++sequence;
  return new Promise((resolve,reject) => { const timer=setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: '+method));},10000); pending.set(id,{resolve,reject,timer}); socket.send(JSON.stringify({id,method,params})); });
}
async function evaluate(expression) { const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true}); if(result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result.value; }
function check(label, condition) { assert.ok(condition,label); checks.push(label); }
async function screenshot(name, fullPage=false) {
  const params={format:'png',captureBeyondViewport:fullPage};
  if(fullPage) { const layout=await command('Page.getLayoutMetrics'); const size=layout.cssContentSize; params.clip={x:0,y:0,width:Math.ceil(size.width),height:Math.ceil(size.height),scale:1}; }
  const result=await command('Page.captureScreenshot',params); fs.writeFileSync(path.join(output,name),Buffer.from(result.data,'base64')); captures.push(name);
}
async function navigate(name) { await command('Page.navigate',{url:serverOrigin+'/'+name+'/'}); await waitFor(() => evaluate('document.getElementById("run-id").textContent === '+JSON.stringify(reports[name].run_id)),name+' report render'); }
async function viewport(width,height,mobile=false) { await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile}); await evaluate('window.scrollTo(0,0)'); }
async function noOverflow(label) { check(label,await evaluate('document.documentElement.scrollWidth <= window.innerWidth')); }
async function tab(name) { await evaluate('document.querySelector("[data-pane='+name+']").click()'); check(name+' tab activates',await evaluate('!document.getElementById("pane-'+name+'").hidden && document.querySelector("[data-pane='+name+']").getAttribute("aria-pressed")==="true"')); }
async function upload(file) { const doc=await command('DOM.getDocument'); const input=await command('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#file'}); await command('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[file]}); }
async function main() {
  server=http.createServer((request,response) => {
    const pathname=new URL(request.url,'http://127.0.0.1').pathname;
    const match=pathname.match(/^\/(upgrade|text|uncertain)\/(report\.json)?$/);
    if(!match) { response.writeHead(404); response.end('Not found'); return; }
    const isReport=Boolean(match[2]); response.writeHead(200,{'Content-Type':isReport?'application/json':'text/html; charset=utf-8','Cache-Control':'no-store'}); response.end(fs.readFileSync(isReport?reportPaths[match[1]]:source));
  });
  await new Promise((resolve,reject) => {server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  serverOrigin='http://127.0.0.1:'+server.address().port;
  chrome=spawn(browser,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{cwd:root,windowsHide:true,stdio:['ignore','ignore','pipe']});
  chrome.stderr.on('data',()=>{});
  const debugPort=await waitFor(() => {const file=path.join(profile,'DevToolsActivePort');return fs.existsSync(file)&&Number(fs.readFileSync(file,'utf8').split('\n')[0]);},'owned browser debug port');
  const target=await waitFor(async()=>JSON.parse((await get('http://127.0.0.1:'+debugPort+'/json/list')).body).find(item=>item.type==='page'),'owned headless page');
  socket=new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener('message',event=>{
    const message=JSON.parse(event.data);
    if(message.method==='Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if(message.method==='Runtime.consoleAPICalled'&&message.params.type==='error') errors.push(message.params.args.map(arg=>arg.value||arg.description).join(' '));
    if(message.method==='Page.fileChooserOpened') chooserEvents.push(message.params);
    const waiter=pending.get(message.id);if(waiter){clearTimeout(waiter.timer);pending.delete(message.id);message.error?waiter.reject(new Error(JSON.stringify(message.error))):waiter.resolve(message.result);}
  });
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  await command('Page.enable');await command('Runtime.enable');browserVersion=(await command('Browser.getVersion')).product;
  await viewport(1440,1100);await navigate('upgrade');
  check('Real double-failure report renders as NEEDS_REVIEW',await evaluate('document.getElementById("upgrade-summary").textContent.includes("NEEDS REVIEW")'));
  check('Headline makes lost tool calls visible',await evaluate('document.querySelector("#upgrade-summary h2").textContent==="Both releases lose the tool calls."'));
  check('Existing failure is not represented as a new upgrade regression',await evaluate('document.getElementById("upgrade-summary").textContent.includes("do not establish a newly introduced upgrade regression")'));
  check('Both versions and lost 0/2 calls are visible',await evaluate('document.getElementById("upgrade-releases").textContent.includes("1.4.3") && document.getElementById("upgrade-releases").textContent.includes("1.5.0") && [...document.querySelectorAll("#upgrade-releases dd")].filter(el=>el.textContent==="0 / 2 input calls").length===2'));
  check('Both deterministic tasks display FAIL',await evaluate('[...document.querySelectorAll("#upgrade-releases dt")].filter(el=>el.textContent==="Deterministic task").every(el=>el.nextElementSibling.textContent==="FAIL")'));
  check('Environment readiness and matching shared dependencies are visible',await evaluate('document.getElementById("upgrade-summary").textContent.includes("2 / 2 inventories READY") && document.getElementById("upgrade-summary").textContent.includes("Shared dependencies · MATCHED")'));
  check('Zero provider requests and local execution scope are visible',await evaluate('document.getElementById("upgrade-summary").textContent.includes("0 recorded · No model inference")'));
  check('Summary counts remain zero passes, one needs-review',await evaluate('["count-pass","count-fail","count-inconclusive","count-needs_review"].map(id=>document.getElementById(id).textContent).join(",")==="0,0,0,1"'));
  await noOverflow('Desktop summary has no horizontal overflow');await screenshot('desktop-summary.png');
  await evaluate('document.querySelector(".case-button").click()');
  check('Case selection retains the recorded identity',await evaluate('document.getElementById("case-title").textContent.includes("1.4.3")'));
  await tab('protocol');check('Protocol tab exposes all three independent contracts',await evaluate('document.querySelectorAll("#boundary-contracts .gate").length===3'));await screenshot('desktop-protocol.png',true);
  await tab('findings');check('Findings include lost-call evidence for both SDK releases',await evaluate('document.getElementById("pane-findings").textContent.includes("Baseline · 1.4.3 against original input") && document.getElementById("pane-findings").textContent.includes("Candidate · 1.5.0 against original input") && document.getElementById("pane-findings").textContent.includes("SEMANTIC_CHANGE")'));
  await tab('repair');check('Task tab names baseline and candidate with real versions',await evaluate('document.getElementById("pane-repair").textContent.includes("Baseline task · 1.4.3") && document.getElementById("pane-repair").textContent.includes("Candidate task · 1.5.0")'));await screenshot('desktop-task-results.png',true);
  await tab('provenance');
  check('Provenance exposes separate real SDK subprocesses',await evaluate('document.querySelectorAll("#sdk-workers .worker").length===2 && document.getElementById("sdk-workers").textContent.includes("installed-sdk") && document.getElementById("sdk-workers").textContent.includes("Process ID / exit code")'));
  check('Worker source hashes match recorded executed sources',await evaluate('[...document.querySelectorAll("#sdk-workers dd")].filter(el=>el.textContent==="Matches recorded source").length===2'));
  await evaluate('document.querySelector("#sdk-workers summary").click()');check('Source identity disclosure opens',await evaluate('document.querySelector("#sdk-workers details").open && document.querySelector("#sdk-workers details").textContent.includes("Inventory SHA-256")'));
  await evaluate('[...document.querySelectorAll("#sdk-workers summary")].find(el=>el.textContent==="Captured boundary events").click()');check('Captured framework input and adapter output can be inspected',await evaluate('[...document.querySelectorAll("#sdk-workers details")].some(el=>el.open&&el.textContent.includes("framework_input")&&el.textContent.includes("adapter_output"))'));await screenshot('desktop-provenance.png',true);
  for(const width of [390,320]) {await viewport(width,844,true);await noOverflow('Mobile '+width+'px provenance has no horizontal overflow');}
  await viewport(390,844,true);await tab('protocol');await screenshot('mobile-summary-protocol.png',true);
  await tab('provenance');await noOverflow('Mobile 390px expanded provenance has no horizontal overflow');await screenshot('mobile-provenance.png',true);
  await command('Page.setInterceptFileChooserDialog',{enabled:true});await evaluate('document.getElementById("open-file").click()');await waitFor(()=>chooserEvents.length,'Open evidence file chooser');check('Open evidence opens the native file chooser',true);
  await upload(reportPaths.upgrade);await waitFor(()=>evaluate('document.getElementById("notice-text").textContent.startsWith("Loaded report.json.")'),'local file upload');check('Local JSON upload works',true);
  await evaluate('document.getElementById("reload").click()');await waitFor(()=>evaluate('document.getElementById("notice-text").textContent.startsWith("Loaded ./report.json.")'),'reload');check('Reload report loads sibling JSON',true);
  await command('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:output});
  const existing=new Map(fs.readdirSync(output).map(name=>[name,fs.statSync(path.join(output,name)).mtimeMs]));await evaluate('document.getElementById("export").click()');
  exported=await waitFor(()=>fs.readdirSync(output).find(name=>name.startsWith('patchcourt-')&&name.endsWith('.json')&&(!existing.has(name)||fs.statSync(path.join(output,name)).mtimeMs!==existing.get(name))),'JSON download');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(output,exported),'utf8')),reports.upgrade);check('Export JSON preserves the complete recorded report',true);
  await viewport(1440,1100);await navigate('text');
  check('Real text control PASS is scoped to its recorded input',await evaluate('document.querySelector("#upgrade-summary h2").textContent==="Both releases preserve the tested input." && document.getElementById("upgrade-summary").textContent.includes("It does not certify other inputs")'));
  check('Text control does not claim lost tool calls',await evaluate('!document.getElementById("upgrade-summary").textContent.includes("lose the tool calls") && document.getElementById("upgrade-releases").textContent.includes("No input tool calls")'));
  await noOverflow('Text PASS desktop has no horizontal overflow');await screenshot('desktop-text-control.png');
  await viewport(390,844,true);await noOverflow('Text PASS mobile has no horizontal overflow');
  await navigate('uncertain');
  check('Incomplete execution is clearly INCONCLUSIVE',await evaluate('document.querySelector("#upgrade-summary h2").textContent==="The upgrade verdict is unresolved." && document.getElementById("upgrade-summary").textContent.includes("INCONCLUSIVE")'));
  check('Missing executions and tasks remain Not recorded',await evaluate('[...document.querySelectorAll("#upgrade-releases dt")].filter(el=>el.textContent==="SDK subprocess"||el.textContent==="Deterministic task").every(el=>el.nextElementSibling.textContent.toLowerCase()==="not recorded")'));
  await tab('provenance');check('Environment errors are accessible in uncertain provenance',await evaluate('document.querySelectorAll("#sdk-workers .worker-error").length>0'));await noOverflow('Uncertain mobile report has no horizontal overflow');await screenshot('mobile-inconclusive.png',true);
  await viewport(1440,1100);await noOverflow('Uncertain desktop report has no horizontal overflow');await screenshot('desktop-inconclusive.png');
  check('No browser JavaScript errors observed',errors.length===0);
}
main().then(()=>{console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));}).catch(error=>{errors.push(error.stack);process.exitCode=1;console.error(error.stack);}).finally(async()=>{
  fs.writeFileSync(path.join(output,'qa-results.json'),JSON.stringify({checked_at:new Date().toISOString(),status:process.exitCode?'FAIL':'PASS',browser:browserVersion,mode:'installed headless browser, loopback only',viewer_sha256:hash(fs.readFileSync(source)),reports:Object.fromEntries(Object.entries(reportPaths).map(([name,file])=>[name,{path:path.relative(root,file).replaceAll('\\','/'),run_id:reports[name].run_id,status:reports[name].status,sha256:hash(fs.readFileSync(file))}])),exported_report:exported,captures,checks,errors,limits:['No live provider or model calls','Viewer displays recorded provenance without independently authenticating it','Keyboard and screen reader traversal not fully tested']},null,2)+'\n');
  if(socket&&socket.readyState===WebSocket.OPEN){try{await command('Browser.close');}catch(_){}socket.close();}
  if(chrome&&chrome.exitCode===null){chrome.kill();await Promise.race([new Promise(resolve=>chrome.once('exit',resolve)),sleep(3000)]);}
  if(server)await new Promise(resolve=>server.close(resolve));
  for(const waiter of pending.values()){clearTimeout(waiter.timer);}pending.clear();
  const resolved=path.resolve(profile),temp=path.resolve(os.tmpdir())+path.sep;
  if(resolved.startsWith(temp)&&path.basename(resolved).startsWith('patchcourt-upgrade-browser-')){for(let attempt=0;attempt<10;attempt++){try{fs.rmSync(resolved,{recursive:true,force:true});break;}catch(_){await sleep(200);}}}
});
