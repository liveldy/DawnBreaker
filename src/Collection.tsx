import {useState,useEffect,useRef,type ReactNode} from 'react';
import {Sun,BookOpen,History,ArrowRight,ChevronRight,Search,X,Check,Info} from 'lucide-react';
import {api,post,number,type Bootstrap} from './api';
import {AlbumCard,CollectibleCard,type CardData,type AlbumNode} from './CardFace';
import DrawReveal from './DrawReveal';
import {useApp} from './context';
import {requestId} from './requestId';
type Pack={id:string;name:string;title:string;subtitle?:string;caption?:string;art_caption?:string;poster:string;cover:string;total:number;cost:number;probabilities:Record<string,number>};
type Catalog={schema_version:number;packs:Pack[];albums:AlbumNode[];cards:CardData[];history:CardData[]};
type Props={boot:Bootstrap;action:(fn:()=>Promise<any>)=>Promise<boolean>;busy:boolean};
function Dialog({title,children,close,className=''}:{title:string;children:ReactNode;close:()=>void;className?:string}){const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{ref.current?.showModal();return()=>ref.current?.close();},[]);return <dialog className={'modal wish-dialog '+className} ref={ref} onCancel={close}><div className="modal-title"><h2>{title}</h2><button className="icon-button" aria-label="关闭" onClick={close}><X size={20}/></button></div>{children}</dialog>;}
function trail(albums:AlbumNode[],path:string[]){const found:AlbumNode[]=[];let nodes=albums;for(const id of path){const node=nodes.find(a=>a.id===id);if(!node)break;found.push(node);nodes=node.children;}return found;}
export default function Collection({boot,action,busy}:Props){
 const{offline}=useApp();
 const[data,setData]=useState<Catalog|null>(null),[error,setError]=useState(''),[mode,setMode]=useState(offline?'albums':'draw'),[packId,setPackId]=useState(''),[path,setPath]=useState<string[]>([]),[ownedOnly,setOwnedOnly]=useState(false),[query,setQuery]=useState(''),[rarity,setRarity]=useState('all'),[page,setPage]=useState(1),[details,setDetails]=useState(false),[inspect,setInspect]=useState<CardData|null>(null),[drawSession,setDrawSession]=useState<{count:number;cards:CardData[]|null}|null>(null);
 const pending=useRef<{id:string;count:number;pack:string}|null>(null),drawing=useRef(false),skip=useRef(false),alive=useRef(true);
 const reload=async()=>{try{const value=await api<Catalog>('/plugins/collection');if(alive.current){setData(value);setError('');}}catch(e){if(alive.current)setError((e as Error).message);}};
 useEffect(()=>{alive.current=true;reload();return()=>{alive.current=false;};},[boot.plugins.map(p=>p.id).join(','),boot.wallet.essence]);
 useEffect(()=>{setPage(1);},[query,rarity,ownedOnly,path.join('/')]);
 const pack=data?.packs.find(p=>p.id===packId)||data?.packs[0];
 const draw=async(count:number)=>{
  if(offline||!pack||drawing.current||busy)return;drawing.current=true;skip.current=matchMedia('(prefers-reduced-motion: reduce)').matches;const began=performance.now();setDrawSession({count,cards:null});
  if(!pending.current||pending.current.count!==count||pending.current.pack!==pack.id)pending.current={id:requestId(),count,pack:pack.id};
  try{
   const ok=await action(async()=>{const response=await post('/plugins/collection/draw',{count,pack_id:pack.id,request_id:pending.current!.id});while(!skip.current&&performance.now()-began<1450)await new Promise(r=>setTimeout(r,50));if(alive.current)setDrawSession({count,cards:response.cards});return response;});
   if(ok){pending.current=null;reload();}else setDrawSession(null);
  }finally{drawing.current=false;}
 };
 const navigate=(next:string[])=>{setPath(next);setQuery('');setRarity('all');setOwnedOnly(false);setPage(1);};
 const switchMode=(next:string)=>{setMode(next);navigate([]);};
 if(error)return <div className="inline-error">{error}<button onClick={reload}>重试</button></div>;
 if(!data)return <div className="loading" role="status">正在打开珍藏阁…</div>;
 const crumbs=trail(data.albums,path),current=crumbs.at(-1),root=crumbs[0],children=current?.children||data.albums;
 const nodes=children.filter(n=>n.name.includes(query));
 const memberIds=new Set(current?.card_ids||[]);
 const cards=data.cards.filter(c=>memberIds.has(c.id)&&(!ownedOnly||!!c.owned)&&(rarity==='all'||c.rarity===rarity)&&c.name.includes(query));
 const grades=[...new Set(data.cards.filter(c=>c.album_id===root?.id).map(c=>c.rarity))];
 const pager=(count:number,noun:string)=><div className="pagination"><span>{count} {noun} · 第 {page} / {Math.max(1,Math.ceil(count/24))} 页</span><button disabled={page===1} onClick={()=>setPage(page-1)}>上一页</button><button disabled={page*24>=count} onClick={()=>setPage(page+1)}>下一页</button></div>;
 return <div className="collection-workspace"><header className="wish-heading"><div><h1>珍藏阁</h1><p>每一份日光，都有新的相遇。</p></div><a className="wish-wallet" href="#/wallet"><Sun size={18}/><span>{number(boot.wallet.essence)}</span><small>日光精华</small></a></header>
 <div className="tabs wish-tabs">{[['draw','抽卡'],['albums','卡册浏览'],['history','抽卡记录']].map(([id,label])=><button key={id} className={mode===id?'selected':''} onClick={()=>switchMode(id)}>{label}</button>)}</div>
 {mode==='draw'?(!pack?<section className="empty"><h2>开启你的第一份珍藏。</h2><p>安装收藏内容后，选择卡包，用日光精华抽取卡片。</p><a className="button primary" href="#/market">浏览内容插件<ArrowRight size={16}/></a></section>:<>
 <div className="pack-selector" aria-label="选择卡包">{data.packs.map(p=><button className={'pack-option '+(p.id===pack.id?'selected':'')} key={p.id} aria-pressed={p.id===pack.id} onClick={()=>setPackId(p.id)}><img src={p.cover} alt=""/><span><strong>{p.name}</strong><small>{number(p.total)} 张珍藏</small></span>{p.id===pack.id&&<Check size={16}/>}</button>)}</div>
 <section className="wish-poster" aria-label={pack.name+'卡包'}><img className="wish-art" src={pack.poster} alt={pack.art_caption||pack.title}/><div className="wish-scrim"/><div className="wish-copy"><p>{pack.name}卡包</p><h2>{pack.title}</h2>{pack.subtitle&&<p className="wish-character">{pack.subtitle}</p>}<p className="wish-caption">{pack.caption}</p></div><button className="wish-details" onClick={()=>setDetails(true)}><Info size={15}/>卡包详情与概率</button>{pack.art_caption&&<span className="wish-art-caption">{pack.art_caption}</span>}</section>
 <div className="wish-actions"><button className="wish-album-link" onClick={()=>switchMode('albums')}><BookOpen size={18}/>浏览卡册<ArrowRight size={16}/></button><div className="wish-draw-buttons"><button disabled={offline||busy||!!drawSession||boot.wallet.essence<pack.cost} onClick={()=>draw(1)}><strong>单抽</strong><span><Sun size={14}/>{number(pack.cost)} 日光精华</span></button><button className="primary" disabled={offline||busy||!!drawSession||boot.wallet.essence<pack.cost*10} onClick={()=>draw(10)}><strong>十连抽</strong><span><Sun size={14}/>{number(pack.cost*10)} 日光精华</span></button></div></div><p className="wish-note">{Object.entries(pack.probabilities).map(([k,v])=>`${k} ${v}%`).join(' · ')} · 无保底{boot.wallet.essence<pack.cost?' · 日光精华不足，可在日常中继续积累。':''}</p>
 </>):mode==='albums'?<>
 <nav className="album-breadcrumb" aria-label="卡册路径"><button onClick={()=>navigate([])}>全部卡册</button>{crumbs.map((node,index)=><span className="album-crumb" key={node.id}><ChevronRight size={14}/><button aria-current={index===crumbs.length-1?'page':undefined} onClick={()=>navigate(path.slice(0,index+1))}>{node.name}</button></span>)}</nav>
 {!current?<div className="album-roots">{data.albums.map(a=><button className="album-root" key={a.id} onClick={()=>navigate([a.id])}><img src={a.poster||a.cover} alt=""/><div><BookOpen size={20}/><span><strong>{a.name}</strong><small>已珍藏 {a.owned} / {number(a.total)}</small></span><ArrowRight size={20}/></div></button>)}</div>:current.kind!=='series'?<>
 <div className="section-heading"><h2>{current.name}</h2><span className="muted">{current.kind==='album'?'宇宙卡册':'系列卡册'}</span></div><label className="search album-category-search"><Search size={16}/><input aria-label="搜索卡册" placeholder="搜索卡册名称" value={query} onChange={e=>setQuery(e.target.value)}/></label>
 <div className="card-gallery album-node-gallery">{nodes.slice((page-1)*24,page*24).map(node=><AlbumCard album={node} key={node.id} onClick={()=>navigate([...path,node.id])}/>)}</div>{!nodes.length&&<div className="empty"><h3>没有找到匹配的卡册。</h3></div>}{pager(nodes.length,'册')}
 </>:<><div className="album-controls"><label className="search"><Search size={16}/><input aria-label="搜索卡片" placeholder="搜索卡片名称" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="筛选稀有度" value={rarity} onChange={e=>setRarity(e.target.value)}><option value="all">全部稀有度</option>{grades.map(g=><option key={g}>{g}</option>)}</select><label className="owned-filter"><input type="checkbox" checked={ownedOnly} onChange={e=>setOwnedOnly(e.target.checked)}/>只看已珍藏</label></div><p className="album-result-count">{cards.length} 张卡片</p><div className="card-gallery">{cards.slice((page-1)*24,page*24).map(card=><CollectibleCard key={card.id} card={card} onInspect={setInspect}/>)}</div>{!cards.length&&<div className="empty"><h3>这里还没有匹配的卡片。</h3><p>试试其他筛选条件，或先抽取一份珍藏。</p></div>}{pager(cards.length,'张')}</>}
 </>:<section className="wish-history"><div className="section-heading"><h2>最近的相遇</h2><span className="muted">保留最近 100 张</span></div>{data.history.length?<div className="card-gallery">{data.history.map((card,i)=><CollectibleCard key={i} card={card} onInspect={setInspect}/>)}</div>:<div className="empty"><History size={24}/><h3>第一份珍藏，还在前方。</h3><p>抽取卡片后，可以在这里回看。</p><button onClick={()=>setMode('draw')}>去抽卡</button></div>}</section>}
 {details&&pack&&<Dialog title={pack.name+'卡包'} close={()=>setDetails(false)}><p className="muted">包含 {number(pack.total)} 张卡片。</p><div className="pack-rates">{Object.entries(pack.probabilities).map(([k,v])=><div key={k}><strong>{k}</strong><span>{v}%</span></div>)}</div><p>每抽消耗 {pack.cost} 日光精华。十连消耗 {pack.cost*10} 日光精华。等级内卡片等概率，无保底；每张卡仅收藏一张；重复卡按品质分别返还 5 / 20 / 50 日光精华。</p><div className="dialog-actions"><button onClick={()=>setDetails(false)}>知道了</button></div></Dialog>}
 {drawSession&&<DrawReveal count={drawSession.count} cards={drawSession.cards} onClose={()=>setDrawSession(null)} onSkip={()=>{skip.current=true;}} onInspect={setInspect}/>}
 {inspect&&<Dialog title="卡片详情" className="card-inspect-dialog" close={()=>setInspect(null)}><div className="card-detail">{inspect.splash&&<img className="card-splash" src={inspect.splash} alt={inspect.name+'完整原画'}/>}<div className="card-detail-copy"><h3>{inspect.name}</h3><p className="card-story">{inspect.description||'这张卡片暂未提供背景描述。'}</p><p className="muted">{inspect.title} · {inspect.owned?'已珍藏':'未珍藏'}{inspect.artist&&' · 画师：'+inspect.artist}</p>{inspect.source_url&&<a className="text-link" href={inspect.source_url} target="_blank" rel="noreferrer">查看图鉴来源 ↗</a>}</div><div className="card-inspect"><CollectibleCard card={inspect} reveal/></div></div></Dialog>}
 </div>;
}
