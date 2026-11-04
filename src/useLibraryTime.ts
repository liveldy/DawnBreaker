import{useEffect}from'react';
import{api}from'./api';
import{requestId}from'./requestId';

// Report elapsed foreground time, never text length or the computer's wall clock.
export function useLibraryTime(documentId:string|undefined,accountId:string,offline:boolean){
 useEffect(()=>{
  if(!documentId||offline)return;
  const session=requestId();let seconds=0,last=performance.now(),active=document.visibilityState==='visible'&&document.hasFocus(),sending=false,closed=false;
  const tick=()=>{const now=performance.now(),elapsed=(now-last)/1000;if(active&&elapsed>=0&&elapsed<=10)seconds+=elapsed;last=now;};
  const send=(keepalive=false)=>{if(sending&&!keepalive)return;tick();sending=true;void api('/plugins/library/foreground-time',{method:'POST',keepalive,body:JSON.stringify({session,document_id:documentId,seconds})}).catch(()=>{}).finally(()=>{sending=false;});};
  const state=()=>{tick();const next=document.visibilityState==='visible'&&document.hasFocus();if(active!==next){send(true);active=next;}last=performance.now();};
  const leave=()=>{if(closed)return;tick();send(true);active=false;};
  send();const timer=setInterval(tick,1000),report=setInterval(()=>{if(active)send();},15000);
  document.addEventListener('visibilitychange',state);window.addEventListener('focus',state);window.addEventListener('blur',state);window.addEventListener('pagehide',leave);
  return()=>{leave();closed=true;clearInterval(timer);clearInterval(report);document.removeEventListener('visibilitychange',state);window.removeEventListener('focus',state);window.removeEventListener('blur',state);window.removeEventListener('pagehide',leave);};
 },[documentId,accountId,offline]);
}
