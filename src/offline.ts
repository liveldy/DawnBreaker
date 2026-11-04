import{Capacitor,registerPlugin}from'@capacitor/core';import{requestId}from'./requestId';
declare global{interface Window{dawnOffline?:{info:()=>Promise<any>;clear:()=>Promise<any>;logout:()=>Promise<any>}}}
export const nativeOffline=!!window.dawnOffline||Capacitor.isPluginAvailable('DawnOffline');
export const nativeOfflineBridge:any=window.dawnOffline||(Capacitor.isPluginAvailable('DawnOffline')?registerPlugin('DawnOffline'):null);
const androidLocal=Capacitor.getPlatform()==='android'&&location.hostname==='localhost';
export const REMOTE='http://110.42.63.153:7780';
let disconnected=nativeOffline&&!navigator.onLine;const subscribers=new Set<()=>void>();
export const offlineSnapshot=()=>disconnected;
export const subscribeOffline=(cb:()=>void)=>{subscribers.add(cb);return()=>{subscribers.delete(cb);};};
function connection(value:boolean){if(disconnected!==value){disconnected=value;for(const cb of subscribers)cb();window.dispatchEvent(new Event('dawn:connection-change'));}}
let accountGeneration=0;
let activeAccount=localStorage.getItem('dawn.offline.account')||'';
let database:Promise<IDBDatabase>|null=null;
function db(){return database||(database=new Promise<IDBDatabase>((resolve,reject)=>{const request=indexedDB.open('dawn-offline-v1',1);request.onupgradeneeded=()=>{const d=request.result;d.createObjectStore('cache',{keyPath:'key'}).createIndex('account','account');d.createObjectStore('playback',{keyPath:'id'}).createIndex('account','account');};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);}));}
async function operation(store:string,mode:IDBTransactionMode,fn:(s:IDBObjectStore)=>IDBRequest){const d=await db();return new Promise<any>((resolve,reject)=>{const transaction=d.transaction(store,mode);const request=fn(transaction.objectStore(store));let value:any;request.onsuccess=()=>value=request.result;transaction.oncomplete=()=>resolve(value);transaction.onerror=()=>reject(transaction.error);});}
const cacheable=(path:string)=>path==='/api/bootstrap'||path==='/api/catalog'||path.startsWith('/api/plugins/library')&&!path.includes('/export')||path.startsWith('/api/plugins/collection')||path==='/api/plugins/music'||path.startsWith('/api/plugins/quotes')||path.startsWith('/api/plugins/atlas');
const keyFor=(path:string)=>activeAccount+'|'+path;
const transport=(path:string,options:RequestInit={})=>fetch(androidLocal&&options.method&&options.method!=='GET'?REMOTE+path:path,options);
async function cacheResponse(path:string,response:Response,owner:string,generation:number){
 if(generation!==accountGeneration||path!=='/api/bootstrap'&&owner!==activeAccount)return;
 if(!nativeOffline||!response.ok||!cacheable(path)||!response.headers.get('content-type')?.includes('json'))return;
 try{const value=await response.clone().json();if(path==='/api/bootstrap'&&value.user?.id){activeAccount=value.user.id;localStorage.setItem('dawn.offline.account',activeAccount);}if(activeAccount)await operation('cache','readwrite',s=>s.put({key:keyFor(path),account:activeAccount,path,value,updated_at:Date.now()}));}catch{}
}
async function fromCache(path:string){if(!activeAccount||!cacheable(path))return null;try{const record=await operation('cache','readonly',s=>s.get(keyFor(path)));if(record){connection(true);return new Response(JSON.stringify(record.value),{status:200,headers:{'Content-Type':'application/json','X-Dawn-Offline':'1','X-Dawn-Cached-At':String(record.updated_at)}});}}catch{}return null;}
export async function apiFetch(path:string,options:RequestInit={}):Promise<Response>{
 const method=options.method||'GET';
 if(method==='POST'&&['/api/auth/login','/api/auth/register','/api/auth/logout'].includes(path)){accountGeneration++;activeAccount='';localStorage.removeItem('dawn.offline.account');}
 const generation=accountGeneration,owner=activeAccount;
 if(nativeOffline&&method!=='GET'&&disconnected){
  if(path==='/api/auth/logout'){await nativeOfflineBridge?.logout();activeAccount='';localStorage.removeItem('dawn.offline.account');return new Response(JSON.stringify({message:'已退出本机离线账号'}),{headers:{'Content-Type':'application/json'}});}
  throw Error('当前为离线模式，只可阅读已缓存内容，联网后再试。');
 }
 if(nativeOffline&&method==='GET'&&!navigator.onLine){const cached=await fromCache(path);if(cached)return cached;if(path==='/api/bootstrap'&&!activeAccount)return new Response('{"detail":"首次使用需联网登录"}',{status:401,headers:{'Content-Type':'application/json'}});}
 try{
  const response=await transport(path,{credentials:'include',...options});
  if(response.status===401&&generation===accountGeneration){activeAccount='';localStorage.removeItem('dawn.offline.account');}
  if(nativeOffline&&method==='GET'&&response.status>=500){const cached=await fromCache(path);if(cached)return cached;}
  if(response.headers.get('X-Dawn-Offline')==='1')connection(true);else if(response.ok||response.status===401)connection(false);
  if(method==='GET')await cacheResponse(path,response,owner,generation);
  if(path==='/api/auth/logout'&&response.ok){activeAccount='';localStorage.removeItem('dawn.offline.account');await nativeOfflineBridge?.logout();}
  return response;
 }catch(error){if(nativeOffline){connection(true);if(method==='GET'){const cached=await fromCache(path);if(cached)return cached;if(path==='/api/bootstrap'&&!activeAccount)return new Response('{"detail":"首次使用需联网登录"}',{status:401,headers:{'Content-Type':'application/json'}});}}throw error;}
}
let flushing=false;
export async function flushPlayback(){
 if(!nativeOffline||!activeAccount||disconnected||flushing)return;flushing=true;const account=activeAccount;
 try{const queued=await operation('playback','readonly',s=>s.index('account').getAll(account));for(let at=0;at<queued.length;at+=100){if(account!==activeAccount)break;const batch=queued.slice(at,at+100);const r=await transport('/api/plugins/music/sync',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_id:account,device_id:deviceId(),segments:batch.map(({id,start,end,seconds,track_id}:any)=>({id,start,end,seconds,track_id}))})});if(!r.ok)break;const result=await r.json();for(const id of result.accepted_ids||[])await operation('playback','readwrite',s=>s.delete(id));if(result.rejected_ids?.length)localStorage.setItem('dawn.offline.sync-error','部分听曲记录的设备时间异常，尚未同步。请检查系统时间。');if(result.credited_seconds>0)window.dispatchEvent(new Event('dawn:data-changed'));}}catch{connection(true);}finally{flushing=false;}
}
export function deviceId(){let id=localStorage.getItem('dawn.offline.device');if(!id){id=requestId();localStorage.setItem('dawn.offline.device',id);}return id;}
export async function recordPlayback(track_id:string,seconds:number,end=Date.now()/1000){
 if(!activeAccount||seconds<.1)return;
 if(nativeOffline){await operation('playback','readwrite',s=>s.put({id:requestId(),account:activeAccount,track_id,seconds:Math.min(seconds,120),start:end-Math.min(seconds,120),end}));flushPlayback();window.dispatchEvent(new Event('dawn:cache-changed'));}
}
export async function cacheInfo(){const account=activeAccount;const items=account?await operation('cache','readonly',s=>s.index('account').getAll(account)):[];const records=account?await operation('playback','readonly',s=>s.index('account').getAll(account)):[];const native=await nativeOfflineBridge?.info().catch(()=>({}));return{documents:items.filter((i:any)=>/\/library\/nodes\/[^/]+$/.test(i.path)).length,cards:items.find((i:any)=>i.path==='/api/plugins/collection')?.value.cards?.length||0,queued_seconds:records.reduce((n:number,r:any)=>n+r.seconds,0)+(native?.pending_seconds||0),sync_error:localStorage.getItem('dawn.offline.sync-error'),...native};}
export async function clearCache(){const items=await operation('cache','readonly',s=>s.index('account').getAll(activeAccount));for(const item of items)if(item.path!=='/api/bootstrap'&&item.path!=='/api/catalog')await operation('cache','readwrite',s=>s.delete(item.key));await nativeOfflineBridge?.clear();window.dispatchEvent(new Event('dawn:cache-changed'));}
export async function prefetchDocuments(){const listing=await apiFetch('/api/plugins/library');if(!listing.ok)throw Error('请先安装流萤集并联网登录');const value=await listing.json();for(const doc of value.nodes.filter((n:any)=>n.kind==='document')){const response=await apiFetch('/api/plugins/library/nodes/'+doc.id);if(!response.ok)throw Error('部分文档暂时无法缓存');}}
export async function prefetchCards(progress:(n:number,total:number)=>void){const r=await apiFetch('/api/plugins/collection');if(!r.ok)throw Error('请先安装珍藏阁与卡册内容');const data=await r.json();const urls=[...new Set<string>(data.cards.flatMap((c:any)=>[c.image,c.rarity_badge].filter(Boolean)))];let cursor=0,done=0;await Promise.all(Array.from({length:4},async()=>{while(cursor<urls.length){const url=urls[cursor++];const result=await fetch(url);if(!result.ok)throw Error('部分卡图未能缓存，请稍后重试');await result.arrayBuffer();progress(++done,urls.length);}}));}
if(nativeOffline){window.addEventListener('online',()=>{probeConnection();});window.addEventListener('offline',()=>connection(true));window.addEventListener('dawn:connection-change',()=>{if(!disconnected)flushPlayback();});setInterval(()=>probeConnection(),20000);}
let lastNativeSync='';
export async function probeConnection(){if(!nativeOffline)return;try{const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),5000);const r=await transport('/api/health',{signal:controller.signal,credentials:'include'});clearTimeout(timer);if(r.ok){const wasOffline=disconnected;connection(false);flushPlayback();if(wasOffline)window.dispatchEvent(new Event('dawn:data-changed'));const info=await nativeOfflineBridge?.info().catch(()=>null);if(info?.sync_revision&&info.sync_revision!==lastNativeSync){lastNativeSync=info.sync_revision;window.dispatchEvent(new Event('dawn:data-changed'));}}}catch{connection(true);}}
