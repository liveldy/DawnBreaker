import {useEffect,useRef,useState,type CSSProperties} from 'react';
import {X} from 'lucide-react';
import {CollectibleCard,type CardData} from './CardFace';
type Props={count:number;cards:CardData[]|null;onClose:()=>void;onSkip:()=>void;onInspect:(card:CardData)=>void};
export default function DrawReveal({count,cards,onClose,onSkip,onInspect}:Props){
 const ref=useRef<HTMLDialogElement>(null);const[skip,setSkip]=useState(false);
 useEffect(()=>{ref.current?.showModal();window.dispatchEvent(new Event('dawn:modal-open'));return()=>ref.current?.close();},[]);
 return <dialog ref={ref} className={'modal draw-dialog '+(cards?'draw-showing':'draw-opening')} onCancel={event=>{if(!cards)event.preventDefault();else onClose();}} aria-label={cards?'抽卡结果':'正在开启卡包'}>
 <div className="draw-title"><h2>{cards?'这一刻，值得珍藏。':'日光，正在汇聚。'}</h2>{cards?<button className="icon-button" aria-label="关闭抽卡结果" onClick={onClose}><X size={20}/></button>:<button className="draw-skip" disabled={skip} onClick={()=>{setSkip(true);onSkip();}}>{skip?'正在揭晓…':'跳过动画'}</button>}</div>
 {!cards?<div className="summoning" role="status"><div className="summon-orbit" aria-hidden="true"/><div className="summon-pack" aria-hidden="true"><span>破晓</span></div>{Array.from({length:12},(_,i)=><i className="sun-mote" key={i} style={{'--mote':i} as CSSProperties} aria-hidden="true"/>)}<p>开启 {count===1?'一份':'十份'}珍藏</p></div>:<><div className={'draw-results '+(count===1?'draw-single':'draw-ten')+(skip?' reveal-skipped':'')} aria-live="polite">{cards.map((card,index)=><div className="reveal-slot" data-rarity={card.rarity} key={index} style={{'--reveal-delay':index*75+'ms'} as CSSProperties}><CollectibleCard card={card} reveal onInspect={onInspect}/><span className="rarity-sparks" aria-hidden="true">{Array.from({length:6},(_,i)=><i key={i} style={{'--spark':i} as CSSProperties}/>)}</span></div>)}</div><p className="draw-inspect-note">点击卡片查看大图</p><div className="dialog-actions"><button className="primary" onClick={onClose}>收进卡册</button></div></>}
 </dialog>;
}
