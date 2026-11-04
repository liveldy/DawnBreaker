import {useRef,useState} from 'react';
import {Volume2,LoaderCircle} from 'lucide-react';
export default function VoiceButton({src,notify}:{src:string;notify:(s:string)=>void}){
 const audio=useRef<HTMLAudioElement>(null);const[loading,setLoading]=useState(false);
 const play=async()=>{if(!audio.current)return;try{setLoading(true);audio.current.currentTime=0;await audio.current.play();}catch{notify('语录暂时无法播放，请稍后重试。');}finally{setLoading(false);}};
 return <><audio ref={audio} src={src} preload="none" hidden/><button type="button" className="icon-button quote-voice" aria-label="播放语录" title="播放语录" disabled={loading} onClick={play}>{loading?<LoaderCircle size={18} className="spin"/>:<Volume2 size={18}/>}</button></>;
}
