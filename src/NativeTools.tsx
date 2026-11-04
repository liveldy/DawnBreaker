import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Capacitor,registerPlugin} from '@capacitor/core';
import {PanelsTopLeft,X} from 'lucide-react';
import type {Bootstrap} from './api';
export const androidMedia=Capacitor.getPlatform()==='android'&&Capacitor.isPluginAvailable('DawnMedia');
declare global {interface Window{dawnMedia?:any}}
export const nativeMedia:any=androidMedia?registerPlugin('DawnMedia'):window.dawnMedia;
export function NativeTools({boot,notify}:{boot:Bootstrap;notify:(s:string)=>void}){
 const[open,setOpen]=useState(false);const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const configure=()=>{nativeMedia?.configure({quotes:boot.plugins.some(p=>p.id==='quotes'),music:boot.plugins.some(p=>p.id==='music'),account:boot.user.id}).catch(()=>{});};configure();window.addEventListener('dawn:quote-changed',configure);return()=>window.removeEventListener('dawn:quote-changed',configure);},[boot.user.id,boot.plugins.map(p=>p.id).join(',')]);
 useEffect(()=>{if(open){window.dispatchEvent(new Event('dawn:modal-open'));dialog.current?.showModal();}return()=>dialog.current?.close();},[open]);
 if(!nativeMedia)return null;
 const widget=async(kind:string)=>{try{const result=await nativeMedia.widget({kind});if(result?.message)notify(result.message);}catch{notify('请在桌面的小组件列表中添加破晓控件。');}};
 return <><button className="nav-item" onClick={()=>setOpen(true)}><PanelsTopLeft size={18}/>桌面控件</button>{open&&createPortal(<dialog ref={dialog} className="modal" onCancel={()=>setOpen(false)}><div className="modal-title"><h2>让日常留在桌面</h2><button className="icon-button" aria-label="关闭" onClick={()=>setOpen(false)}><X/></button></div><div className="native-tools-content"><div className="widget-example"><h3>流光笺</h3><p>每日语录，打开桌面就能看到。</p><button disabled={!boot.plugins.some(p=>p.id==='quotes')} onClick={()=>widget('quotes')}>添加语录控件</button></div><div className="widget-example"><h3>弦音余韵</h3><p>查看当前歌曲，上一首、播放 / 暂停、下一首。</p><button disabled={!boot.plugins.some(p=>p.id==='music')} onClick={()=>widget('music')}>添加音乐控件</button></div><p className="muted">{androidMedia?'播放时会显示系统通知栏控件。部分手机需要在系统设置中允许破晓后台运行。':'关闭主窗口后，音乐继续播放。可在托盘打开主窗口、显示控件或退出程序。'}</p></div></dialog>,document.body)}</>;
}
