export type PlaybackMode='sequence'|'random'|'single';
export function nextTrack(index:number,length:number,mode:PlaybackMode,delta=1,automatic=false,random=Math.random):number|null{
 if(length<1)return null;
 if(automatic&&mode==='single')return index;
 if(automatic&&mode==='sequence'&&index>=length-1)return null;
 if(mode==='random'&&length>1){const value=Math.min(length-2,Math.floor(random()*(length-1)));return value>=index?value+1:value;}
 return(index+delta+length)%length;
}
