import calendar
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from ..core import require_plugin, today, credit, emit
from ..db import connect
from ..config import setting

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
    current = date.fromisoformat(today()); streak = 0
    if today() not in dates:
        current -= timedelta(days=1)
    while current.isoformat() in dates:
        streak += 1; current -= timedelta(days=1)
    return {'today':today(),'month':month,'offset':first,'days':days,'dates':[d for d in dates if d.startswith(month)],'checked':today() in dates,'streak':streak,'total':len(dates),'reward':reward}

@router.post('')
def check(u=Depends(user)):
    with connect(True) as db:
        reward=setting(db,'checkin_reward',10)
        if not credit(db,u['id'],'essence',reward,'每日签到','checkin:'+today()):
            raise HTTPException(409,'今天已经签到，明天再见')
        emit(db,u['id'],'checkin',{'date':today()})
    return {'message':f'签到成功，收下 {reward} 点日光精华'}

