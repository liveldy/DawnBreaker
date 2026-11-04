import calendar
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from ..core import require_plugin, today, credit, emit
from ..db import connect
from ..config import setting
from ..holidays import month_info
from ..db import now
from pydantic import BaseModel,Field

MANIFEST = {'id':'checkin','name':'朝暮签','description':'在每一个平常日子里，收下一份日光。每日签到获得日光精华。','category':'日常','icon':'CalendarDays','ui':'checkin'}
router = APIRouter(prefix='/api/plugins/checkin', tags=['朝暮签'])
user = require_plugin('checkin')

@router.get('')
def get(month: str = Query(default='',pattern=r'^$|^\d{4}-\d{2}$'), u=Depends(user)):
    month = month or today()[:7]
    try:
        y,m = map(int,month.split('-')); first,days = calendar.monthrange(y,m)
    except ValueError:
        raise HTTPException(422,'月份无效')
    with connect() as db:
        reward=setting(db,'checkin_reward',10)
        dates = [r[0].split(':')[1] for r in db.execute("SELECT source FROM ledger WHERE user_id=? AND kind='essence' AND source LIKE 'checkin:%' ORDER BY source",(u['id'],))]
        notes={r['day']:{'content':r['content'],'updated_at':r['updated_at']} for r in db.execute('SELECT day,content,updated_at FROM checkin_notes WHERE user_id=? AND day LIKE ?',(u['id'],month+'-%'))}
    current = date.fromisoformat(today()); streak = 0
    if today() not in dates:
        current -= timedelta(days=1)
    while current.isoformat() in dates:
        streak += 1; current -= timedelta(days=1)
    return {'today':today(),'month':month,'offset':first,'days':days,'dates':[d for d in dates if d.startswith(month)],'checked':today() in dates,'streak':streak,'total':len(dates),'reward':reward,'notes':notes,'holidays':month_info(month)}

@router.post('')
def check(u=Depends(user)):
    with connect(True) as db:
        reward=setting(db,'checkin_reward',10)
        if not credit(db,u['id'],'essence',reward,'每日签到','checkin:'+today()):
            raise HTTPException(409,'今天已经签到，明天再见')
        emit(db,u['id'],'checkin',{'date':today()})
    return {'message':f'签到成功，收下 {reward} 点日光精华'}

class Note(BaseModel):
    content:str=Field(default='',max_length=20000)

def valid_day(day):
    try:
        value=date.fromisoformat(day)
        if value.isoformat()!=day or not 1900<=value.year<=2100:raise ValueError()
    except ValueError:raise HTTPException(422,'日期无效')
    return day

@router.put('/notes/{day}')
def save_note(day:str,body:Note,u=Depends(user)):
    valid_day(day)
    with connect(True) as d:
        if body.content.strip():d.execute('INSERT INTO checkin_notes VALUES(?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET content=excluded.content,updated_at=excluded.updated_at',(u['id'],day,body.content,now()))
        else:d.execute('DELETE FROM checkin_notes WHERE user_id=? AND day=?',(u['id'],day))
    return {'message':'每日记录已保存' if body.content.strip() else '每日记录已清空','day':day}

