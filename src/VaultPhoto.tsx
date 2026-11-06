import {useEffect,useRef,useState} from 'react';
import {Download,ImagePlus,Trash2} from 'lucide-react';
import type {VaultPhoto as Photo} from './vaultEntries';
import {readVaultPhoto,downloadVaultPhoto} from './vaultPhotos';

export function VaultPhoto({label,photo,editing,disabled=false,filename,onChange,onLoading,notify}:{label:string;photo?:Photo;editing:boolean;disabled?:boolean;filename:string;onChange?:(photo:Photo|undefined)=>void;onLoading?:(loading:boolean)=>void;notify:(message:string)=>void}){
 const alive=useRef(true),input=useRef<HTMLInputElement>(null),[loading,setLoading]=useState(false);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 return <section className="vault-photo" aria-label={label}>
  <h4>{label}</h4>
  {photo?<img src={photo.data} alt={label} loading="lazy"/>:<div className="vault-photo-empty">未添加照片</div>}
  <div className="vault-photo-actions">
   {editing?<><input ref={input} type="file" accept="image/png,image/jpeg,image/webp" aria-label={'上传'+label} hidden disabled={disabled||loading} onChange={async event=>{
    const file=event.currentTarget.files?.[0];event.currentTarget.value='';if(!file)return;
    setLoading(true);onLoading?.(true);
    try{const value=await readVaultPhoto(file);if(alive.current)onChange?.(value);}catch(error){if(alive.current)notify((error as Error).message);}finally{if(alive.current)setLoading(false);onLoading?.(false);}
   }}/><button type="button" disabled={disabled||loading} onClick={()=>input.current?.click()}><ImagePlus size={16}/>{loading?'读取照片中…':photo?'替换照片':'上传照片'}</button>{photo&&<button type="button" className="icon-button" disabled={disabled||loading} aria-label={'移除'+label} onClick={()=>onChange?.(undefined)}><Trash2 size={16}/></button>}</>:<button type="button" disabled={!photo} onClick={async()=>{if(photo)try{await downloadVaultPhoto(photo,filename);}catch(error){notify((error as Error).message);}}}><Download size={16}/>下载照片</button>}
  </div>
 </section>;
}
