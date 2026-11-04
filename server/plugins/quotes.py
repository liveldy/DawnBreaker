import json,secrets
from datetime import date
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from ..core import require_plugin, today, installed,state,set_state
from ..content_store import items
from ..db import connect

MANIFEST = {'id':'quotes','name':'流光笺','description':'每天一句，给日常留一点回声。支持有声金句播放。','category':'日常','icon':'Quote','ui':'quotes'}
router = APIRouter(prefix='/api/plugins/quotes',tags=['流光笺'])
DEFAULT_QUOTES=[{'id':'sample','text':'不必等到万事俱备，第一缕光也能照亮脚下。','author':'破晓 · 示例金句','audio':None}]
VOICE=Path(__file__).parents[1]/'content'/'voice'
PACK=json.loads((VOICE.parent/'lol-quotes.json').read_text(encoding='utf-8')) if (VOICE.parent/'lol-quotes.json').exists() else []
def available(db,uid):
    pool=items(db,'quotes',DEFAULT_QUOTES+PACK)
    return [q for q in pool if not q.get('content_plugin') or installed(db,uid,q['content_plugin'])]


@router.get('')
def quote(u=Depends(require_plugin('quotes'))):
    with connect(True) as db:
        quotes=available(db,u['id'])
        if not quotes:raise HTTPException(409,'金句内容为空，请联系管理员补充')
        schedule=db.execute('SELECT quote_id FROM quote_schedule WHERE day=?',(today(),)).fetchone()
        chosen=state(db,u['id'],'quotes','daily',{})
        result=next((q for q in quotes if schedule and q['id']==schedule[0]),None)
        if not result:result=next((q for q in quotes if chosen.get('day')==today() and q['id']==chosen.get('id')),None) or secrets.choice(quotes)
        set_state(db,u['id'],'quotes','daily',{'day':today(),'id':result['id']})
    return result|{'date':today(),'audio':'/api/plugins/quotes/audio/'+result['id'] if result.get('audio') else None}

@router.get('/audio/{quote_id}')
def voice(quote_id:str,u=Depends(require_plugin('quotes'))):
    with connect() as db: quotes=available(db,u['id'])
    quote=next((q for q in quotes if q['id']==quote_id),None)
    if not quote or not quote.get('audio'): raise HTTPException(404,'此金句没有语音')
    path=(VOICE/quote['audio']).resolve()
    if not path.is_relative_to(VOICE.resolve()) or not path.is_file(): raise HTTPException(404,'语音文件不存在')
    return FileResponse(path)

