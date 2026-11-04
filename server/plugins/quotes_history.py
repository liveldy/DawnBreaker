"""Daily account snapshots and personal overrides; global schedules remain separate."""
import json,hashlib
from datetime import date,timedelta
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from ..core import require_plugin,today,state,set_state
from ..db import connect,now
from .quotes import available
router=APIRouter();user=require_plugin('quotes')

def save_day(d,uid,day,q):
    snapshot={k:v for k,v in q.items() if k not in ('date','personal','history_since')}
    d.execute('INSERT INTO quote_history VALUES(?,?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET quote_id=excluded.quote_id,snapshot=excluded.snapshot,updated_at=excluded.updated_at',(uid,day,q['id'],json.dumps(snapshot,ensure_ascii=False),now()))

def default_for(d,uid,day,pool):
    schedule=d.execute('SELECT quote_id FROM quote_schedule WHERE day=?',(day,)).fetchone()
    if schedule:
        q=next((q for q in pool if q['id']==schedule[0]),None)
        if q:return q
    previous=state(d,uid,'quotes','daily',{})
    if previous.get('day')==day:
        q=next((q for q in pool if q['id']==previous.get('id')),None)
        if q:return q
    choices=sorted(pool,key=lambda q:q['id']);index=int(hashlib.sha256((uid+':'+day).encode()).hexdigest(),16)%len(choices)
    return choices[index]

def ensure_history(d,uid,pool):
    start=state(d,uid,'quotes','history-since')
    if not start:
        previous=state(d,uid,'quotes','daily',{});old_day=previous.get('day','')
        try:
            if date.fromisoformat(old_day)<=date.fromisoformat(today()):
                q=next((q for q in pool if q['id']==previous.get('id')),None)
                if q:save_day(d,uid,old_day,q)
        except ValueError:pass
        start=today();set_state(d,uid,'quotes','history-since',start)
    existing={r[0] for r in d.execute('SELECT day FROM quote_history WHERE user_id=? AND day>=?',(uid,start))}
    cursor=date.fromisoformat(start);end=date.fromisoformat(today())
    while cursor<=end:
        day=cursor.isoformat()
        if day not in existing:save_day(d,uid,day,default_for(d,uid,day,pool))
        cursor+=timedelta(days=1)
    return start

def present(q,day,pool):
    enabled=any(p['id']==q['id'] and p.get('audio') for p in pool)
    return q|{'date':day,'audio':'/api/plugins/quotes/audio/'+q['id'] if enabled else None}

def current(u):
    with connect(True) as d:
        pool=available(d,u['id'])
        if not pool:raise HTTPException(409,'金句内容为空，请联系管理员补充')
        start=ensure_history(d,u['id'],pool);result=default_for(d,u['id'],today(),pool)
        override=state(d,u['id'],'quotes','override',{});personal=override.get('day')==today() and bool(override.get('snapshot'))
        set_state(d,u['id'],'quotes','daily',{'day':today(),'id':result['id']})
        if personal:result=override['snapshot']
        save_day(d,u['id'],today(),result)
        return present(result,today(),pool)|{'personal':personal,'history_since':start,'override_from':override.get('source_day') if personal else None}

@router.get('/history')
def history(page:int=Query(1,ge=1),u=Depends(user)):
    with connect(True) as d:
        pool=available(d,u['id']);start=ensure_history(d,u['id'],pool) if pool else today()
        rows=d.execute('SELECT * FROM quote_history WHERE user_id=? ORDER BY day DESC LIMIT 30 OFFSET ?',(u['id'],(page-1)*30)).fetchall()
        total=d.execute('SELECT COUNT(*) FROM quote_history WHERE user_id=?',(u['id'],)).fetchone()[0]
        return {'quotes':[present(json.loads(r['snapshot']),r['day'],pool) for r in rows],'total':total,'page':page,'history_since':start,'note':'从启用历史记录起按日保存；此前仅保留可确认的历史，不补写未知语录。'}

class Replace(BaseModel):
    source_day:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')

@router.put('/current')
def replace(body:Replace,u=Depends(user)):
    with connect(True) as d:
        row=d.execute('SELECT * FROM quote_history WHERE user_id=? AND day=?',(u['id'],body.source_day)).fetchone()
        if not row:raise HTTPException(404,'历史语录不存在')
        value=json.loads(row['snapshot']);set_state(d,u['id'],'quotes','override',{'day':today(),'source_day':body.source_day,'snapshot':value});save_day(d,u['id'],today(),value)
    return {'message':'已替换今日语录，仅对当前账号生效'}

@router.delete('/current')
def restore(u=Depends(user)):
    with connect(True) as d:set_state(d,u['id'],'quotes','override',{})
    return {'message':'已恢复今日默认语录'}
