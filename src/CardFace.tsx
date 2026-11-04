import type {CSSProperties} from 'react';
import './collection-cards.css';
export type CardData={id:string;name:string;image:string;rarity:string;rarity_badge?:string;splash?:string;description?:string;original_rarity?:string;refund?:number;legacy?:boolean;title?:string;owned?:number;new?:boolean;album_id?:string;series_ids?:string[]};
export type AlbumNode={id:string;name:string;kind:'album'|'universe'|'series';cover:string;poster?:string;total:number;owned:number;children:AlbumNode[];card_ids:string[];description?:string};
type Props={image:string;name:string;subtitle?:string;grade:string;rarityIcon?:string;rarity?:string;badge?:string;dimmed?:boolean;onClick?:()=>void;delay?:number};
/** Shared physical card face for cards, universe/series books, history and reveals. */
export function CardFace({image,name,subtitle,grade,rarityIcon,rarity,badge,dimmed,onClick,delay=0}:Props){
 const content=<><img src={image} alt="" loading="lazy"/><span className="card-art-scrim"/>{badge&&<span className="card-badge">{badge}</span>}<span className="card-lettering">{rarityIcon&&<img className="rarity-art" src={rarityIcon} alt="品质标识"/>}<strong>{name}</strong>{subtitle&&<span className="card-subtitle">{subtitle}</span>}{!rarity&&<span className="card-grade">{grade}</span>}</span><span className="card-corners" aria-hidden="true"/></>;
 const props={className:'card-face'+(dimmed?' card-dimmed':''),'data-rarity':rarity||'album',style:{'--reveal-delay':delay+'ms'} as CSSProperties,title:name};
 return onClick?<button {...props} onClick={onClick} aria-label={name+'，'+grade+(subtitle?'，'+subtitle:'')}>{content}</button>:<article {...props} aria-label={name+'，'+grade}>{content}</article>;
}
export function CollectibleCard({card,onInspect,reveal=false}:{card:CardData;onInspect?:(c:CardData)=>void;reveal?:boolean}){
 return <CardFace image={card.image} name={card.name} subtitle={reveal?(card.refund?'分解 +'+card.refund+' 日光精华':''):card.owned?'已珍藏':'未珍藏'} grade="珍藏卡片" rarityIcon={card.rarity_badge} rarity={card.rarity} badge={reveal&&typeof card.new==='boolean'?(card.new?'新':'已分解'):undefined} dimmed={!reveal&&!card.owned} onClick={onInspect?()=>onInspect(card):undefined}/>;
}
export function AlbumCard({album,onClick}:{album:AlbumNode;onClick:()=>void}){
 return <CardFace image={album.cover} name={album.name} subtitle={'已珍藏 '+album.owned+' / '+album.total} grade={album.kind==='universe'?'宇宙卡册':'系列卡册'} onClick={onClick}/>;
}
