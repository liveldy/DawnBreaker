import {useEffect,useState,useRef} from 'react';
import {createPortal} from 'react-dom';
import {Capacitor,registerPlugin,type PluginListenerHandle} from '@capacitor/core';
import {RefreshCw,Download,CheckCircle2,X,Monitor,Smartphone} from 'lucide-react';
type Info={platform:string;version:string;release_sequence?:number};type Release={available:boolean;latest:string;notes:string;size:number;ready?:boolean};
type Bridge={getInfo:()=>Promise<Info>;checkUpdate:()=>Promise<Release>;downloadUpdate:()=>Promise<any>;installUpdate:()=>Promise<any>;onProgress?:(cb:(v:{percent:number})=>void)=>()=>void;addListener?:(event:string,cb:(v:{percent:number})=>void)=>Promise<PluginListenerHandle>};
declare global{interface Window{dawnNative?:Bridge}}
const android=registerPlugin<Bridge>('DawnClient');const official='https://liveldy.github.io/dawnbreaker-website/#downloads';
function context(){
 if(window.dawnNative)return {platform:'windows',bridge:window.dawnNative};
 if(Capacitor.isNativePlatform()&&Capacitor.getPlatform()==='android')return {platform:'android',bridge:Capacitor.isPluginAvailable('DawnClient')?android:null};
 return null;
}
function friendly(error:unknown){const message=(error as Error)?.message||'';return /not implemented|unavailable|DawnClient/i.test(message)?'当前安装包的更新接口不可用，请下载新版客户端手动安装。':message||'暂时无法完成更新，请稍后重试。';}
export default function ClientUpdates(){
 const runtime=context(),bridge=runtime?.bridge;const[info,setInfo]=useState<Info|null>(null),[infoFailed,setInfoFailed]=useState(false),[release,setRelease]=useState<Release|null>(null),[open,setOpen]=useState(false),[state,setState]=useState('idle'),[error,setError]=useState(''),[progress,setProgress]=useState(0),[permission,setPermission]=useState(false);const dialog=useRef<HTMLDialogElement>(null);
 const platform=info?.platform||runtime?.platform;const migration=!!bridge&&!!info&&!info.release_sequence&&release?.latest==='1.0.0';const manual=!!runtime&&(!bridge||migration);
 const check=async()=>{
  setError('');setState('checking');
  try{
   if(!bridge){
    const response=await fetch('/api/releases/'+platform+'?current=0.0.0');if(!response.ok)throw Error('暂时无法读取发布版本，请前往官网下载。');
    const body=await response.json();const payload=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(body.signed),(c:string)=>c.charCodeAt(0))));
    if(payload.platform!==platform||!/^\d+\.\d+\.\d+$/.test(payload.version))throw Error('发布版本信息无效，请前往官网下载。');
    setRelease({available:true,latest:payload.version,notes:payload.notes,size:payload.size});setState('idle');return;
   }
   const value=await bridge.checkUpdate();setRelease(value);setState(value.ready?'ready':'idle');
  }catch(e){setError(friendly(e));setState('idle');}
 };
 useEffect(()=>{
  if(!runtime)return;let live=true;let cleanup:(()=>void)|undefined;let listener:PluginListenerHandle|undefined;
  if(bridge){
   bridge.getInfo().then(v=>live&&setInfo(v)).catch(()=>live&&setInfoFailed(true));
   bridge.checkUpdate().then(v=>{if(live){setRelease(v);setState(v.ready?'ready':'idle');}}).catch(()=>{});
   const callback=(v:{percent:number})=>live&&setProgress(v.percent);
   // Capacitor proxies return a function for any property, even absent methods.
   // Select the desktop callback by bridge origin rather than duck-typing onProgress.
   if(window.dawnNative&&bridge===window.dawnNative&&bridge.onProgress)cleanup=bridge.onProgress(callback);else bridge.addListener?.('updateProgress',callback).then(v=>listener=v).catch(()=>{});
  }
  return()=>{live=false;cleanup?.();listener?.remove();};
 },[]);
 useEffect(()=>{if(open)dialog.current?.showModal();else dialog.current?.close();},[open]);
 if(!runtime)return null;
 const download=async()=>{if(!bridge)return;setError('');setState('downloading');setProgress(0);try{await bridge.downloadUpdate();setState('ready');}catch(e){setError(friendly(e));setState('idle');}};
 const install=async()=>{if(!bridge)return;setError('');try{const result=await bridge.installUpdate();if(result.needsPermission)setPermission(true);}catch(e){setError(friendly(e));}};
 const trigger=()=>{setOpen(true);window.dispatchEvent(new Event('dawn:modal-open'));check();};
 return <><button className="nav-item client-update-trigger" onClick={trigger}><RefreshCw size={18} strokeWidth={1.6}/><span>客户端更新</span>{release?.available&&!manual&&<span className="update-dot" aria-label="有新版本"/>}</button>
 {createPortal(<dialog className="modal client-update-dialog" ref={dialog} onCancel={()=>setOpen(false)}><div className="modal-title"><h2>客户端更新</h2><button className="icon-button" aria-label="关闭" onClick={()=>setOpen(false)}><X size={20}/></button></div>
 <div className="client-version">{platform==='android'?<Smartphone size={27}/>:<Monitor size={27}/>}<div><strong>破晓 {platform==='android'?'Android':'Windows'} 客户端</strong><p>{info?'当前版本 '+info.version:manual?'当前安装包未提供版本信息':infoFailed?'暂时无法读取当前版本':'正在读取版本…'}</p></div></div>
 {manual&&<p className="update-manual">{migration?'正式版已统一为 1.0.0，请下载后覆盖安装，账号与数据会保留。':'请前往官网下载正式版，覆盖安装后可使用内置更新。'}</p>}
 {state==='checking'?<p className="muted update-status" role="status">正在检查更新…</p>:release?<><div className="update-status"><CheckCircle2 size={18}/><strong>{manual?'最新发布版本 '+release.latest:release.available?'发现新版本 '+release.latest:'已经是最新版本 '+release.latest}</strong></div>{release.available&&<><p className="update-notes">{release.notes}</p><p className="muted update-size">安装包 {(release.size/1024/1024).toFixed(1)} MB{manual?'':' · 下载后校验更新签名与文件完整性'}</p></>}</>:<p className="muted update-status">点击检查更新，获取最新客户端版本。</p>}
 {state==='downloading'&&<><div className="progress-track"><span style={{width:progress+'%'}}/></div><p className="muted" role="status">正在下载 {progress}%</p></>}
 {permission&&<p className="update-permission">请在系统页面允许破晓安装应用，返回后点击「继续安装」。</p>}{error&&<p className="form-error" role="alert">{error}</p>}
 <div className="dialog-actions"><button disabled={state==='checking'||state==='downloading'} onClick={check}><RefreshCw size={15}/>检查更新</button>{manual?(release?<a className="button primary" href={'/api/releases/'+platform+'/download/'+release.latest}><Download size={15}/>下载{platform==='android'?' APK':' Windows 客户端'}</a>:<a className="button primary" href={official}>前往官网下载</a>):release?.available&&(state==='ready'?<button className="primary" onClick={install}>{permission?'继续安装':'安装更新'}<Download size={15}/></button>:<button className="primary" disabled={state==='downloading'||state==='checking'} onClick={download}><Download size={15}/>{state==='downloading'?'正在下载':'下载更新'}</button>)}</div>
 <p className="update-foot">{platform==='android'?'由 Android 系统安装器确认安装，保留账号与应用数据。':'安装时会重启客户端，保留账号登录与应用数据。'}{infoFailed&&<a href={official}>前往官网下载</a>}</p></dialog>,document.body)}</>;
}
