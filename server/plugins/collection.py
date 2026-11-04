import json,secrets
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from ..core import require_plugin,installed,balance,credit,state,set_state,emit,today
from ..db import connect
from ..collection_catalog import album_specs,accessible_cards,tree_for,pack_for,media_path

MANIFEST={'id':'collection','name':'珍藏阁','description':'用日光精华开启一份珍藏。选择卡包、单抽或十连，按宇宙与系列浏览卡册。','category':'收藏','icon':'Layers','ui':'collection'}
router=APIRouter(prefix='/api/plugins/collection',tags=['珍藏阁']);user=require_plugin('collection')
ROOT=Path(__file__).parents[1]/'content'
CONFIG=json.loads((ROOT/'cards.json').read_text(encoding='utf-8')) if (ROOT/'cards.json').is_file() else {'cards':[],'cost':10,'probabilities':{'R':75,'SR':20,'SSR':5}}
ALBUMS=json.loads((ROOT/'card-albums.json').read_text(encoding='utf-8')) if (ROOT/'card-albums.json').is_file() else {'albums':[]}
REFUNDS={'R':5,'SR':20,'SSR':50}

def normalize_owned(db,uid):
    owned=state(db,uid,'collection','owned',{})
    indexed={c['id']:c for c in CONFIG['cards']}
    refund=sum(max(0,n-1)*REFUNDS.get(indexed.get(cid,{}).get('rarity'),5) for cid,n in owned.items())
    if refund:
        credit(db,uid,'essence',refund,'重复珍藏分解','collection-unique-v120')
        owned={cid:1 for cid,n in owned.items() if n>0}
        set_state(db,uid,'collection','owned',owned)
    return owned

@router.get('/rarity/{name}')
def rarity_image(name:str,u=Depends(user)):
    if name not in ('limited','legendary','mythic'):raise HTTPException(404,'标识不存在')
    return FileResponse(ROOT/'rarity'/f'{name}.png',media_type='image/png')

@router.get('/splash/{card_id}')
def splash(card_id:str,u=Depends(user)):
    with connect() as db:
        if not any(c['id']==card_id for c in accessible_cards(db,u['id'],CONFIG,ALBUMS)):raise HTTPException(403,'尚未安装对应卡册内容')
    return FileResponse(media_path(ROOT,'splashes/'+card_id+'.webp'),media_type='image/webp')

def find_spec(id):
    return next((a for a in album_specs(ALBUMS) if a['id']==id),None)

@router.get('/image/{card_id}')
def image(card_id:str,u=Depends(user)):
    with connect() as db:
        cards=accessible_cards(db,u['id'],CONFIG,ALBUMS)
        card=next((c for c in cards if c['id']==card_id),None)
        if not card:raise HTTPException(403,'尚未安装对应卡册内容，或该卡片不存在')
    return FileResponse(media_path(ROOT,'cards/'+card_id+'.webp'),media_type='image/webp')

@router.get('/poster/{pack_id}')
def poster(pack_id:str,u=Depends(user)):
    spec=find_spec(pack_id)
    with connect() as db:
        if not spec or not installed(db,u['id'],spec['content_plugin']):raise HTTPException(403,'尚未安装该卡册内容')
    if not spec.get('poster'):raise HTTPException(404,'尚未配置卡包海报')
    return FileResponse(media_path(ROOT,spec['poster']),media_type='image/webp')

@router.get('')
def get(u=Depends(user)):
    with connect(True) as db:
        cards=accessible_cards(db,u['id'],CONFIG,ALBUMS);owned=normalize_owned(db,u['id'])
        albums=[];packs=[]
        for spec in album_specs(ALBUMS):
            if not installed(db,u['id'],spec['content_plugin']):continue
            pool=[c for c in cards if c['album_id']==spec['id']]
            album=tree_for(spec,pool,owned)
            album['poster']='/api/plugins/collection/poster/'+spec['id'] if spec.get('poster') else album['cover']
            albums.append(album)
            pack=pack_for(spec,CONFIG,db)
            if pack and pool:packs.append(pack|{'poster':album['poster'],'cover':album['cover'],'total':len(pool)})
        visible={c['id'] for c in cards}
        history=[h for h in state(db,u['id'],'collection','history',[]) if h['id'] in visible][:100]
        # Merge history with current metadata so old draws adopt the same album/card presentation.
        indexed={c['id']:c for c in cards}
        history=[h|indexed[h['id']]|{'new':h.get('new',False),'owned':owned.get(h['id'],0)} for h in history]
        fallback=packs[0] if packs else {'cost':CONFIG['cost'],'probabilities':CONFIG['probabilities']}
        return {'schema_version':2,'essence':balance(db,u['id'],'essence'),'currency':'essence','cost':fallback['cost'],'probabilities':fallback['probabilities'],'packs':packs,'albums':albums,'cards':[c|{'owned':owned.get(c['id'],0)} for c in cards],'history':history}

class Draw(BaseModel):
    count:int=Field(ge=1,le=10)
    request_id:str=Field(min_length=8,max_length=80,pattern='^[a-zA-Z0-9_-]+$')
    pack_id:str=Field(default='lol',max_length=80)

@router.post('/draw')
def draw(body:Draw,u=Depends(user)):
    if body.count not in (1,10):raise HTTPException(422,'只支持单抽或十连')
    with connect(True) as db:
        spec=find_spec(body.pack_id)
        if not spec or not installed(db,u['id'],spec['content_plugin']):raise HTTPException(409,'尚未安装卡池内容')
        pack=pack_for(spec,CONFIG,db)
        if not pack:raise HTTPException(409,'该卡册尚未开放抽取')
        existing=state(db,u['id'],'collection','draw:'+body.request_id)
        if existing:
            if existing.get('pack_id',body.pack_id)!=body.pack_id or len(existing['cards'])!=body.count:raise HTTPException(409,'抽卡请求与原记录不一致')
            return existing
        cards=[c for c in accessible_cards(db,u['id'],CONFIG,ALBUMS) if c['album_id']==body.pack_id]
        probabilities=pack['probabilities']
        if type(pack['cost']) is not int or not 1<=pack['cost']<=1000000:raise HTTPException(503,'卡池价格尚未正确配置')
        if not cards or not isinstance(probabilities,dict) or not probabilities or any(type(p) is not int or p<0 for p in probabilities.values()) or sum(probabilities.values())!=100:raise HTTPException(503,'卡池概率尚未正确配置')
        if any(p>0 and not any(c['rarity']==r for c in cards) for r,p in probabilities.items()):raise HTTPException(503,'概率对应的卡池为空')
        if not credit(db,u['id'],'essence',-pack['cost']*body.count,'珍藏阁抽卡','draw:'+body.request_id):raise HTTPException(409,'该抽卡请求已处理，请查看卡册')
        result=[];owned=normalize_owned(db,u['id']);refund=0
        for _ in range(body.count):
            ticket=secrets.randbelow(100);threshold=0
            for rarity,probability in probabilities.items():
                threshold+=probability
                if ticket<threshold:break
            card=secrets.choice([c for c in cards if c['rarity']==rarity])
            is_new=not owned.get(card['id'],0);value=0 if is_new else REFUNDS.get(card['rarity'],5)
            refund+=value
            result.append(card|{'new':is_new,'refund':value,'owned':1});owned[card['id']]=1
        if refund:credit(db,u['id'],'essence',refund,'重复卡分解','draw-refund:'+body.request_id)
        set_state(db,u['id'],'collection','owned',owned)
        set_state(db,u['id'],'collection','history',(result+state(db,u['id'],'collection','history',[]))[:100])
        response={'cards':result,'pack_id':body.pack_id,'refund':refund,'message':f'新增 {sum(c["new"] for c in result)} 张珍藏'+(f'，重复卡分解获得 {refund} 日光精华' if refund else '')}
        set_state(db,u['id'],'collection','draw:'+body.request_id,response);emit(db,u['id'],'draw',{'count':body.count,'pack_id':body.pack_id,'date':today()})
        return response
