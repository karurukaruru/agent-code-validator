/* Local judge QA. Uses installed Chrome/Edge and Node's native CDP WebSocket.
 * No dependency installation, public hosting, or provider API calls.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const http = require('node:http');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'evidence', 'browser');
const profile = path.join(root, 'outputs', 'browser-profile');
const candidates = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const browser = candidates.find(fs.existsSync);
if (!browser) throw new Error('An installed Chrome or Edge is required; no browser is downloaded.');
fs.mkdirSync(output, {recursive:true});
fs.mkdirSync(profile, {recursive:true});
let server, chrome, socket;
const pending = new Map(); let sequence = 0;
const checks = [];
const errors = [];
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
function get(url) { return new Promise((resolve,reject) => { const request=http.get(url,response=>{let body='';response.setEncoding('utf8');response.on('data',chunk=>body+=chunk);response.on('end',()=>resolve({status:response.statusCode,body}));});request.setTimeout(2000,()=>request.destroy(new Error('HTTP timeout')));request.on('error',reject); }); }
async function waitFor(get, label) {
  for (let attempt=0; attempt<60; attempt++) {
    try { const value = await get(); if (value) return value; } catch (_) {}
    await sleep(250);
  }
  throw new Error('Timed out waiting for ' + label);
}
function command(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: ' + method));}, 10000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
function check(label, condition) { assert.ok(condition, label); checks.push(label); }
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', {format:'png',captureBeyondViewport:true});
  fs.writeFileSync(path.join(output,name), Buffer.from(result.data,'base64'));
}
(async () => {
  for (const port of [8766,9229]) if (await get('http://127.0.0.1:'+port).then(()=>true,()=>false)) throw new Error('QA port already in use: '+port+'; refusing to attach to an unrelated service.');
  server = spawn('python', ['-m','patchcourt','serve','outputs/judge-check','--port','8766'], {cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
  server.stderr.on('data', () => {});
  server.stdout.on('data', () => {});
  await waitFor(async () => (await get('http://127.0.0.1:8766')).status===200, 'loopback server');
  chrome = spawn(browser, ['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9229','--user-data-dir='+profile,'about:blank'], {cwd:root,windowsHide:true,stdio:['ignore','ignore','pipe']});
  chrome.stderr.on('data', () => {});
  const target = await waitFor(async () => JSON.parse((await get('http://127.0.0.1:9229/json/list')).body).find(item => item.type === 'page'), 'headless browser');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    const waiter = pending.get(message.id);
    if (waiter) { clearTimeout(waiter.timer);pending.delete(message.id); if(message.error) waiter.reject(new Error(JSON.stringify(message.error))); else waiter.resolve(message.result); }
  });
  await new Promise((resolve,reject) => {socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  await command('Page.enable'); await command('Runtime.enable');
  const browserVersion = await command('Browser.getVersion');
  await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await command('Page.navigate',{url:'http://127.0.0.1:8766'});
  await waitFor(() => evaluate("document.querySelectorAll('.case-button').length === 16"), 'real report render');
  check('Real report auto-loaded with 16 cases', await evaluate("document.querySelectorAll('.case-button').length === 16"));
  check('Offline limitations visible', await evaluate("document.getElementById('notice-text').textContent.includes('Offline run')"));
  check('Recorded summary displayed', await evaluate("['count-pass','count-fail','count-inconclusive','count-needs_review'].map(id=>document.getElementById(id).textContent).join(',')==='3,11,1,1'"));
  check('First authentic source case selected', await evaluate("document.getElementById('case-title').textContent.includes('NVIDIA')"));
  check('Desktop has no horizontal overflow', await evaluate('document.documentElement.scrollWidth <= window.innerWidth'));
  await screenshot('desktop-protocol.png');
  await evaluate("document.querySelector('[data-pane=repair]').click()");
  check('Repair replay exposes restored value 21', await evaluate("!document.getElementById('pane-repair').hidden && document.getElementById('pane-repair').textContent.includes('21')"));
  check('Repair is explicitly not model-generated', await evaluate("document.getElementById('pane-repair').textContent.includes('not model-generated')"));
  await screenshot('desktop-repair.png');
  await evaluate("document.querySelectorAll('.case-button')[1].click();document.querySelector('[data-pane=findings]').click()");
  check('Case selection and findings work', await evaluate("document.getElementById('pane-findings').textContent.includes('LOST_IMAGE')"));
  check('Lab remains BLOCKED', await evaluate("document.getElementById('lab-status').textContent==='BLOCKED'"));
  check('Acceptance gates rendered', await evaluate("document.querySelectorAll('#gates .gate').length===16"));
  await command('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate('window.scrollTo(0,0)');
  check('Mobile has no horizontal overflow', await evaluate('document.documentElement.scrollWidth <= window.innerWidth'));
  await screenshot('mobile-findings.png');
  const upload = await command('DOM.getDocument');
  const fileNode = await command('DOM.querySelector',{nodeId:upload.root.nodeId,selector:'#file'});
  await command('DOM.setFileInputFiles',{nodeId:fileNode.nodeId,files:[path.join(root,'outputs','judge-check','report.json')]});
  await waitFor(() => evaluate("document.getElementById('notice-text').textContent.startsWith('Loaded report.json.')"), 'file upload');
  check('Local report file upload works',true);
  await command('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:output});
  const existingDownloads = new Map(fs.readdirSync(output).map(name=>[name,fs.statSync(path.join(output,name)).mtimeMs]));
  await evaluate("document.getElementById('export').click()");
  const exported = await waitFor(async () => fs.readdirSync(output).find(name=>name.startsWith('patchcourt-')&&name.endsWith('.json')&&(!existingDownloads.has(name)||fs.statSync(path.join(output,name)).mtimeMs!==existingDownloads.get(name))), 'JSON export');
  const downloaded = JSON.parse(fs.readFileSync(path.join(output,exported),'utf8'));
  check('JSON export preserves actual run identity', downloaded.run_id===JSON.parse(fs.readFileSync(path.join(root,'outputs','judge-check','report.json'),'utf8')).run_id);
  check('No runtime exceptions observed',errors.length===0);
  fs.writeFileSync(path.join(output,'qa-results.json'),JSON.stringify({checked_at:new Date().toISOString(),browser:browserVersion.product,mode:'headless loopback',report:'outputs/judge-check/report.json',exported_report:exported,checks,errors,limits:['No live provider/model calls','Not a clean-machine installation test','Keyboard/screen-reader traversal not fully tested']},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS',checks:checks.length,output}));
})().catch(error=>{console.error(error.stack);process.exitCode=1;}).finally(async()=>{
  if(socket && socket.readyState===WebSocket.OPEN){try{await command('Browser.close');}catch(_){}socket.close();}
  if(chrome && chrome.exitCode===null) chrome.kill();
  if(server && server.exitCode===null) server.kill();
});
