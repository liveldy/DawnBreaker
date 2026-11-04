import {useEffect,useRef,useState,type RefObject,type Dispatch,type SetStateAction} from 'react';
import {post} from './api';
import {requestId} from './requestId';
import {nativeOffline,recordPlayback,flushPlayback} from './offline';
import {androidMedia,nativeMedia} from './NativeTools';
import{nextTrack,type PlaybackMode}from'./playbackOrder';
let focusedAudio:RefObject<HTMLAudioElement|null>|null=null;
type Track={id:string;name:string;artist:string;duration:number};
export function usePlayback(tracks:Track[],index:number,setIndex:Dispatch<SetStateAction<number>>,audio:RefObject<HTMLAudioElement|null>,notify:(s:string)=>void){
 const[playing,setPlaying]=useState(false),[time,setTime]=useState(0);const current=useRef({tracks,index});current.current={tracks,index};
 const ready=useRef<Promise<any>>(Promise.resolve());
 const[mode,setPlaybackMode]=useState<PlaybackMode>(()=>{const v=localStorage.getItem('dawn:playback-mode');return v==='random'||v==='single'?v:'sequence';});const modeRef=useRef(mode);modeRef.current=mode;
 const setMode=(value:PlaybackMode)=>{setPlaybackMode(value);localStorage.setItem('dawn:playback-mode',value);if(androidMedia)nativeMedia.playbackMode({mode:value}).catch(()=>notify('播放模式暂时无法保存'));};
 useEffect(()=>{if(androidMedia)nativeMedia.playbackMode({mode:modeRef.current}).catch(()=>{});},[]);
 const ownsPlayback=()=>focusedAudio===null||focusedAudio===audio;
 useEffect(()=>{const element=audio.current;const claim=()=>{focusedAudio=audio;window.dispatchEvent(new CustomEvent('dawn:playback-focus',{detail:audio}));};const relinquish=(event:Event)=>{if((event as CustomEvent).detail!==audio)audio.current?.pause();};element?.addEventListener('play',claim);window.addEventListener('dawn:playback-focus',relinquish);return()=>{element?.removeEventListener('play',claim);window.removeEventListener('dawn:playback-focus',relinquish);if(focusedAudio===audio)focusedAudio=null;};},[]);

 const run=(name:string,args?:any)=>nativeMedia?.[name](args).catch(()=>notify('音乐暂时无法播放，请重新选择歌曲。'));
 useEffect(()=>{
  if(!androidMedia||!tracks.length)return;
  ready.current=nativeMedia.playlist({tracks:tracks.map(t=>({id:t.id,name:t.name,artist:t.artist,duration:t.duration}))}).catch(()=>notify('原生播放器暂时无法连接。'));
 },[tracks]);
 const play=()=>{if(androidMedia)ready.current.then(()=>run('play',{index:current.current.index}));else audio.current?.play().catch(()=>notify('音频暂时无法播放'));};
 const pause=()=>{if(androidMedia)run('pause');else audio.current?.pause();};
 useEffect(()=>{const relinquish=()=>pause();window.addEventListener('dawn:audio-focus',relinquish);return()=>window.removeEventListener('dawn:audio-focus',relinquish);},[]);
 const seek=(seconds:number)=>{if(androidMedia)run('seek',{seconds});else if(audio.current)audio.current.currentTime=seconds;};
 const volume=(value:number)=>{if(androidMedia)run('volume',{value});else if(audio.current)audio.current.volume=value;};
 const step=(delta=1,automatic=false)=>{if(androidMedia){run('step',{delta,automatic});return;}const now=current.current;const at=nextTrack(now.index,now.tracks.length,modeRef.current,delta,automatic);if(at===null){pause();return;}if(audio.current)audio.current.currentTime=0;if(at===now.index)play();else window.dispatchEvent(new CustomEvent('dawn-play',{detail:now.tracks[at]?.id}));};
 useEffect(()=>{
  if(!androidMedia)return;
  let live=true;const poll=()=>nativeMedia.getState().then((s:any)=>{if(!live)return;setPlaying(s.playing);setTime(s.position||0);if(s.error)notify(s.error);const at=current.current.tracks.findIndex(t=>t.id===s.id);if(at>=0&&at!==current.current.index)setIndex(at);}).catch(()=>{});
  poll();const timer=setInterval(poll,1000);return()=>{live=false;clearInterval(timer);};
 },[]);
 useEffect(()=>{
  if(androidMedia||!tracks.length)return;
  const session=requestId();let elapsed=0,last=performance.now(),lastBeat=0,lastPosition=audio.current?.currentTime||0,lastTrack='',chunk=0,chunkEnd=0;
  const persist=()=>{if(chunk>.1&&lastTrack)recordPlayback(lastTrack,chunk,chunkEnd).catch(()=>notify('听曲记录暂时无法保存，请检查本机存储空间。'));chunk=0;};
  if(!nativeOffline)post('/plugins/music/listening',{session,seconds:0}).catch(()=>{});
  const tick=()=>{const stamp=performance.now(),a=audio.current;const delta=Math.min((stamp-last)/1000,2);last=stamp;
   const t=current.current.tracks[current.current.index];
   const advance=(a?.currentTime||0)-lastPosition;lastPosition=a?.currentTime||0;
   const active=!!a&&!a.paused&&!a.ended&&a.readyState>=3&&advance>0&&advance<=delta+.5;
   if(lastTrack!==t?.id||!active)persist();lastTrack=t?.id||'';
   if(active){const seconds=Math.min(delta,advance);elapsed+=seconds;chunk+=seconds;chunkEnd=Date.now()/1000;}
   if(stamp-lastBeat>=10000){lastBeat=stamp;if(nativeOffline){persist();flushPlayback();}else post('/plugins/music/listening',{session,seconds:elapsed}).catch(()=>{});}
   if(nativeMedia&&t&&ownsPlayback())nativeMedia.publish({id:t.id,name:t.name,artist:t.artist,playing:!!a&&!a.paused,position:a?.currentTime||0}).catch(()=>{});
  };
  const timer=setInterval(tick,1000);
  const off=nativeMedia?.onCommand((command:string)=>{if(!ownsPlayback())return;const a=audio.current;if(command==='pause')pause();else if(command==='toggle')a?.paused?play():pause();else if(command==='next'||command==='previous')step(command==='next'?1:-1);});
  const stop=()=>persist();window.addEventListener('pagehide',stop);audio.current?.addEventListener('pause',stop);const element=audio.current;
  return()=>{persist();clearInterval(timer);off?.();window.removeEventListener('pagehide',stop);element?.removeEventListener('pause',stop);};
 },[tracks]);
 return {play,pause,seek,volume,playing,time,mode,setMode,step};
}
