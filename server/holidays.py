"""Mainland China public holidays and adjusted workdays, with provenance and local cache."""
import json,time,threading,urllib.request
from datetime import date
from pathlib import Path
from .db import DATA
ROOT=Path(__file__).parent/'calendar-data';CACHE=DATA/'calendar';CACHE.mkdir(exist_ok=True)
LOCK=threading.Lock();attempts={}

def valid(value,year):
    if not isinstance(value,dict) or value.get('year')!=year or not isinstance(value.get('days'),list) or not value['days'] or not value.get('papers'):return False
    try:return all(isinstance(v,dict) and isinstance(v.get('name'),str) and isinstance(v.get('isOffDay'),bool) and date.fromisoformat(v['date']).year==year for v in value['days']) and all(isinstance(p,str) and p.startswith('https://www.gov.cn/') for p in value['papers'])
    except (ValueError,KeyError,TypeError):return False

def load(year):
    for path in [CACHE/f'{year}.json',ROOT/f'{year}.json']:
        try:
            value=json.loads(path.read_text('utf8'))
            if valid(value,year):return value
        except (OSError,ValueError):pass
    return None

def fetch(year):
    try:
        url=f'https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json'
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'DawnBreaker calendar'}),timeout=12) as r:data=r.read(512000)
        value=json.loads(data)
        if valid(value,year):
            temporary=CACHE/f'{year}.tmp';temporary.write_bytes(data);temporary.replace(CACHE/f'{year}.json')
    except Exception:pass

def month_info(month):
    year=int(month[:4]);value=load(year)
    if not value and 2020<=year<=2100:
        with LOCK:
            if time.time()-attempts.get(year,0)>3600:
                attempts[year]=time.time();threading.Thread(target=fetch,args=(year,),daemon=True).start()
    return {'days':{v['date']:v for v in value['days'] if v['date'].startswith(month)} if value else {},'available':bool(value),'sources':value.get('papers',[]) if value else [],'note':'中国大陆法定放假及调休，以国务院公布安排为准。' if value else '该年度放假安排尚未取得，不推测调休日；联网后可重试。','data_source':'https://github.com/NateScarlet/holiday-cn'}
