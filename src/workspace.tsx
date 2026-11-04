import {useState,useEffect,useRef,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {X} from 'lucide-react';
import {api,ApiError} from './api';
import{apiFetch}from'./offline';
import {registerPlugin,Capacitor} from '@capacitor/core';
export function useData<T=any>(path:string|null){
 const[data,setData]=useState<T|null>(null),[error,setError]=useState('');const[key,setKey]=useState(0);
 const previous=useRef<string|null>(null);
 useEffect(()=>{let live=true;if(previous.current!==path){setData(null);previous.current=path;}setError('');if(!path)return;api<T>(path).then(d=>live&&setData(d)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[path,key]);
 return{data,error,reload:()=>setKey(k=>k+1),setData};
}
export function Sheet({title,children,close,className=''}:{title:string;children:ReactNode;close:()=>void;className?:string}){
 const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{window.dispatchEvent(new Event('dawn:modal-open'));ref.current?.showModal();return()=>ref.current?.close();},[]);
 return createPortal(<dialog ref={ref} className={'modal workspace-sheet '+className} onCancel={close} onClick={e=>{if(e.target===ref.current)close();}}><div className="modal-title"><h2>{title}</h2><button className="icon-button" aria-label="关闭" onClick={close}><X size={20}/></button></div>{children}</dialog>,document.body);
}
export async function upload(path:string,data:FormData){const r=await apiFetch('/api'+path,{method:'POST',body:data,credentials:'include'});let body;try{body=await r.json();}catch{throw new ApiError(r.status,r.status===413?'文件超过大小限制':'上传暂时失败，请重试');}if(!r.ok)throw new ApiError(r.status,typeof body.detail==='string'?body.detail:'文件格式无效');return body;}
export async function copyText(text:string){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return;}const area=document.createElement('textarea');area.value=text;area.style.cssText='position:fixed;opacity:0;left:0;top:0';document.body.appendChild(area);area.select();const copied=document.execCommand('copy');area.remove();if(!copied)throw Error('复制失败，请手动选择文本复制');}
const files=registerPlugin<{saveText:(options:{filename:string;content:string;mime:string})=>Promise<any>}>('DawnClient');
export async function saveText(filename:string,content:string,mime='text/plain'){
 if(Capacitor.getPlatform()==='android'&&Capacitor.isPluginAvailable('DawnClient')){try{await files.saveText({filename,content,mime});return;}catch(error){if(!/not implemented|unavailable|not found/i.test(String(error)))throw error;}}
 const url=URL.createObjectURL(new Blob([content],{type:mime+';charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
