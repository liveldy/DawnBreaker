import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {upload} from './workspace';

export type ChatMedia={id:string;kind:'image'|'audio'|'video';url:string;size:number;duration:number};
export type DraftFile={id:string;kind:ChatMedia['kind'];name:string;blob?:Blob;server?:ChatMedia};
export type ChatQuote={id:number;role:string;name:string;text:string;media_kinds:ChatMedia['kind'][]};
export type Outgoing={key:string;owner:string;conversation:string;request_id:string;text:string;files:DraftFile[];quote?:ChatQuote|null;created_at:string;status:'sending'|'failed'|'accepted'|'canceled';error:string};
let database:Promise<IDBDatabase>|undefined;
function db(){return database||(database=new Promise((resolve,reject)=>{const r=indexedDB.open('dawn-chat-outbox',1);r.onupgradeneeded=()=>r.result.createObjectStore('messages',{keyPath:'key'}).createIndex('conversation',['owner','conversation']);r.onsuccess=()=>resolve(r.result);r.onerror=()=>{database=undefined;reject(r.error);};}));}
export async function outboxList(owner:string,conversation:string):Promise<Outgoing[]>{const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction('messages'),r=tx.objectStore('messages').index('conversation').getAll([owner,conversation]);tx.oncomplete=()=>resolve(r.result.sort((a:Outgoing,b:Outgoing)=>a.created_at.localeCompare(b.created_at)));tx.onerror=()=>reject(tx.error);});}
// Acknowledgements and cancellation may race a network response. Never resurrect a removed row.
export async function outboxChange(key:string,change:(old:Outgoing|undefined)=>Outgoing|undefined){const d=await db();return new Promise<void>((resolve,reject)=>{const tx=d.transaction('messages','readwrite'),store=tx.objectStore('messages'),r=store.get(key);r.onsuccess=()=>{const next=change(r.result);if(next)store.put(next);else store.delete(key);};tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('本机存储写入失败'));});}

export function useChatOutbox(owner:string,conversation:string,accepted:()=>void){
 const [items,setItems]=useState<Outgoing[]>([]),[storageError,setStorageError]=useState('');const alive=useRef(true),running=useRef(new Map<string,AbortController>()),callback=useRef(accepted);callback.current=accepted;
 async function refresh(){try{const rows=await outboxList(owner,conversation);if(alive.current){setItems(old=>JSON.stringify(old)===JSON.stringify(rows)?old:rows);setStorageError('');}return rows;}catch(e){if(alive.current)setStorageError('本机未能保存消息，请检查存储空间后重试。');throw e;}}
 async function patch(key:string,fn:(old:Outgoing)=>Outgoing){await outboxChange(key,old=>old?fn(old):old);await refresh();}
 async function discardCanceled(entry:Outgoing){try{await api('/plugins/companion/'+conversation+'/messages/request/'+entry.request_id,{method:'DELETE'});await outboxChange(entry.key,()=>undefined);if(alive.current){await refresh();callback.current();}}catch{/* Keep the hide intent until the connection returns. */}}
 useEffect(()=>{alive.current=true;let cleanup=false;(async()=>{try{const rows=await outboxList(owner,conversation);for(const e of rows)if(e.status==='sending')await outboxChange(e.key,old=>old?{...old,status:'failed',error:'上次发送尚未确认，点击感叹号重发'}:old);if(!cleanup)await refresh();}catch{if(!cleanup)setStorageError('本机消息存储不可用，请检查存储权限。');}})();return()=>{cleanup=true;alive.current=false;running.current.forEach(c=>c.abort());};},[owner,conversation]);
 useEffect(()=>{const canceled=items.filter(e=>e.status==='canceled');if(!canceled.length)return;const flush=()=>{if(navigator.onLine)canceled.forEach(discardCanceled);};flush();const t=setInterval(flush,10000);window.addEventListener('online',flush);return()=>{clearInterval(t);window.removeEventListener('online',flush);};},[items]);
 async function transmit(entry:Outgoing){if(running.current.has(entry.key)||!alive.current)return;const ctrl=new AbortController();running.current.set(entry.key,ctrl);const timeout=setTimeout(()=>ctrl.abort(),30000);
  try{await patch(entry.key,o=>o.status==='canceled'?o:{...o,status:'sending',error:''});let current=(await outboxList(owner,conversation)).find(e=>e.key===entry.key);if(!current||current.status==='canceled')return;
   for(let i=0;i<current.files.length;i++){if(!alive.current||ctrl.signal.aborted)throw Error('发送中断，点击感叹号重发');if(current.files[i].server)continue;const attachment=current.files[i];if(!attachment.blob)throw Error('附件暂时无法读取');const form=new FormData();form.append('file',attachment.blob,attachment.name);const server:ChatMedia=await upload('/plugins/companion/'+conversation+'/upload?kind='+attachment.kind,form,ctrl.signal);await patch(entry.key,o=>({...o,files:o.files.map(f=>f.id===attachment.id?{...f,server}:f)}));current=(await outboxList(owner,conversation)).find(e=>e.key===entry.key);if(!current||current.status==='canceled')return;}
   if(!alive.current||ctrl.signal.aborted)throw Error('发送中断，点击感叹号重发');
   await api('/plugins/companion/'+conversation+'/send',{method:'POST',signal:ctrl.signal,body:JSON.stringify({request_id:current.request_id,text:current.text,media_ids:current.files.map(f=>f.server!.id),kind:'chat',...(current.quote?{reply_to_id:current.quote.id}:{})})});
   await patch(entry.key,o=>o.status==='canceled'?o:{...o,status:'accepted',error:''});if(alive.current)callback.current();
  }catch(e){await outboxChange(entry.key,o=>o&&o.status!=='canceled'?{...o,status:'failed',error:(e as Error).name==='AbortError'?'连接超时，点击感叹号重发':(e as Error).message||'发送失败，点击感叹号重发'}:o);if(alive.current)await refresh();}
  finally{clearTimeout(timeout);running.current.delete(entry.key);}
 }
 async function enqueue(text:string,files:DraftFile[],quote?:ChatQuote|null){const request_id=crypto.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);const entry:Outgoing={key:[owner,conversation,request_id].join(':'),owner,conversation,request_id,text,files,quote,created_at:new Date().toISOString(),status:'failed',error:'尚未发送，点击感叹号重发'};await outboxChange(entry.key,()=>entry);await refresh();return entry;}
 async function acknowledge(ids:string[]){if(!ids.length)return;const rows=await outboxList(owner,conversation);for(const e of rows)if(ids.includes(e.request_id)&&e.status!=='canceled')await outboxChange(e.key,o=>o?.status==='canceled'?o:undefined);await refresh();}
 async function remove(entry:Outgoing){running.current.get(entry.key)?.abort();await patch(entry.key,o=>({...o,status:'canceled'}));await discardCanceled(entry);}
 return {items,storageError,enqueue,transmit,acknowledge,remove};
}
