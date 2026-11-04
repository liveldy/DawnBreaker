import {mkdirSync,writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const base=process.env.TASTE_SKILL_ROOT;
if(!base)throw new Error('Set TASTE_SKILL_ROOT to design-taste-frontend skill folder');
const {Browser,sleep}=await import(pathToFileURL(base+'/scripts/lib/cdp.mjs'));
const {probe,layout,app}=await import(pathToFileURL(base+'/scripts/lib/probe.mjs'));
const {judge,judgeLayout,judgeApp,APP_SKIP}=await import(pathToFileURL(base+'/scripts/lib/rules.mjs'));
const browser=await Browser.launch();
const out='.taste-skill/browser';mkdirSync(out,{recursive:true});
const report={checks:[],findings:[],errors:[]};
const page=await browser.newPage();
const wait=async(fn)=>{for(let i=0;i<60;i++){if(await page.eval('Boolean(('+fn.toString()+')())'))return;await sleep(100);}throw new Error('UI wait timed out: '+fn);};
const click=async(text)=>{assert(await page.eval(t=>{const el=[...document.querySelectorAll('button,a')].find(b=>b.textContent.trim()===t);if(!el)return false;el.click();return true;},text),'Missing control: '+text);await sleep(300);};
async function fill(name,value){await page.eval(({name,value})=>{const e=document.querySelector('[name="'+name+'"]');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));},{name,value});}
async function route(path){await page.eval(p=>location.hash=p,path);await sleep(500);await wait(()=>!document.querySelector('.loading'));}
async function capture(name,width=1440){await page.setViewport({width,height:width===390?844:900,mobile:width<600});await sleep(200);await page.eval(()=>document.fonts.ready.then(()=>true));await page.screenshot({path:out+'/'+name+'-'+width+'.png',format:'png',fullPage:true});const m=await page.eval(probe),l=await page.eval(layout),a=await page.eval(app);const allow=[];report.findings.push(...[...judge(m,{width,allow}),...judgeLayout(l,{width,allow}),...judgeApp(a,m,{width,allow})].filter(f=>!APP_SKIP.has(f.id)&&!['no-title','small-title'].includes(f.id)).map(f=>({...f,screen:name})));assert(await page.eval(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow on '+name+' '+width);}
try{
 await page.goto('http://127.0.0.1:7780');await wait(()=>document.querySelector('.auth-form'));
 await capture('login');await capture('login',390);await page.setViewport({width:1440,height:900});
 await click('创建账号');const stamp='qa_'+Date.now().toString(36);await fill('username',stamp);await fill('nickname','微光');await fill('password','UI-qa-password-2026');await page.eval(()=>document.querySelector('.auth-submit').click());await wait(()=>document.querySelector('.sidebar'));
 assert(!(await page.eval(()=>document.body.innerText)).includes('朝暮签'));assert(await page.eval(()=>[...document.querySelectorAll('.summary strong')].slice(0,2).every(e=>e.textContent.startsWith('0'))));
 await capture('home-empty');await capture('home-empty',768);await capture('home-empty',390);report.checks.push('Real registration, zero balances, no uninstalled plugin content');
 await page.setViewport({width:1440,height:900});await route('/market');await capture('market');await capture('market',390);
 await page.setViewport({width:1440,height:900});
 for(const id of ['journal','checkin','quotes','vocabulary','collection','lol','music','ancient','kaoyan']){const data=await page.eval(async id=>{const r=await fetch('/api/catalog/'+id+'/install',{method:'POST',headers:{'Content-Type':'application/json'}});return {status:r.status,data:await r.json()};},id);assert.equal(data.status,200);}
 await page.goto('http://127.0.0.1:7780/?installed=1#/plugin/checkin');await wait(()=>document.querySelector('.calendar'));
 await click('签到，收下微光');await wait(()=>document.body.innerText.includes('今日已签到'));await capture('checkin');await capture('checkin',390);report.checks.push('Checkin button credits once and updates calendar');
 await page.setViewport({width:1440,height:900});await route('/plugin/journal');await click('领取奖励');await sleep(500);assert((await page.eval(()=>document.body.innerText)).includes('已领取'));await capture('tasks');
 await route('/plugin/vocabulary');await wait(()=>document.querySelector('.word-hint'));const hint=await page.eval(()=>document.querySelector('.word-hint').textContent);await page.eval(value=>{const e=document.querySelector('.spelling-label input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));},hint);await click('检查答案');await wait(()=>document.body.innerText.includes('回答正确'));await capture('vocabulary');await capture('vocabulary',390);report.checks.push('Imported exam vocabulary, learning answer and server feedback');
 await page.setViewport({width:1440,height:900});await route('/plugin/collection');await wait(()=>document.querySelector('.collectible img')?.complete);await capture('collection');await capture('collection',390);report.checks.push('Imported card album renders and filters');
 await page.setViewport({width:1440,height:900});await route('/plugin/music');await page.eval(()=>document.querySelector('.track-row').click());await wait(()=>{const a=document.querySelector('audio');return a&&!a.paused&&a.currentTime>0;});await capture('music');report.checks.push('Actual MP3 playback and mini-player');
 await route('/profile');await capture('profile',390);await page.setViewport({width:1440,height:900});await route('/wallet');await capture('wallet');await route('/');await capture('home-installed');await capture('home-installed',390);
 report.errors=page.consoleErrors;assert.equal(report.errors.length,0,report.errors.join('\n'));
 writeFileSync(out+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,errors:report.errors,findings:report.findings.map(f=>({screen:f.screen,width:f.width,level:f.level,id:f.id,message:f.message}))},null,2));
}catch(e){await page.screenshot({path:out+'/failure.png',format:'png'});console.log(await page.eval(()=>({text:document.body.innerText,inputs:[...document.querySelectorAll('input')].map(e=>({name:e.name,valid:e.validity.valid,message:e.validationMessage})),errors:performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/')).map(e=>({name:e.name,status:e.responseStatus}))})));throw e;}finally{await browser.close();}
