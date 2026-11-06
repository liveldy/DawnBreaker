"""One daily server snapshot; user reads never contact upstream providers."""
import concurrent.futures,json,threading,time,urllib.request,uuid,logging,os,hashlib
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from fastapi.responses import FileResponse,JSONResponse
from ..core import require_plugin,emit,today
from ..db import DATA,now,connect
MANIFEST={'id':'atlas','name':'天眼','description':'模型排行榜、能力与成本图和私有 API 监视。每日定时更新公开数据，查看真实余额、模型与连通状态。','category':'AI','icon':'Radar','ui':'atlas'}
router=APIRouter(prefix='/api/plugins/atlas',tags=['天眼']);user=require_plugin('atlas')
ROOT=Path(__file__).parents[1]/'content/model-atlas';CACHE=DATA/'model-atlas'/'live.json';LOCK=threading.Lock();_snapshot_key=None;_snapshot=None
URLS=['https://api.zeroeval.com/leaderboard/indexes/all','https://api.zeroeval.com/leaderboard/models/full','https://openrouter.ai/api/v1/models']
def fetch_source(index):
    url=URLS[index]
    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Origin':'https://llm-stats.com','Referer':'https://llm-stats.com/'}
    error=None
    for candidate in [url]+([url.replace('api.zeroeval.com','api.llm-stats.com')] if index<2 else []):
        try:
            with urllib.request.urlopen(urllib.request.Request(candidate,headers=headers),timeout=25) as r:
                data=r.read(20*1024*1024+1)
                if len(data)>20*1024*1024:raise ValueError('large response')
                return json.loads(data)
        except Exception as e:error=e
    raise error or RuntimeError()
def cached():
    global _snapshot_key,_snapshot
    try:
        stat=CACHE.stat();key=(str(CACHE.resolve()),stat.st_mtime_ns,stat.st_size)
        if key!=_snapshot_key:
            value=json.loads(CACHE.read_text(encoding='utf-8'))
            _snapshot=value;_snapshot_key=key
        return _snapshot
    except (OSError,ValueError):return None
ZONE=ZoneInfo('Asia/Shanghai');UPDATE_HOUR=4

def slot(moment=None):
    value=(moment or datetime.now(ZONE)).astimezone(ZONE)
    due=value.replace(hour=UPDATE_HOUR,minute=0,second=0,microsecond=0)
    return due if value>=due else due-timedelta(days=1)

def state_path():return CACHE.with_name('daily-state.json')

def read_state():
    try:return json.loads(state_path().read_text('utf8'))
    except (OSError,ValueError):return {}

def atomic(path,value):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False),'utf8');temporary.replace(path)

def update_daily(moment=None):
    due=slot(moment);day=due.date().isoformat()
    if not LOCK.acquire(False):return False
    try:
        state=read_state()
        if state.get('day','')>=day:return False
        previous=cached()
        if previous and previous.get('epoch',0)>=due.timestamp():
            atomic(state_path(),{'day':day,'attempted_at':previous.get('fetched_at'),'error':None});return False
        state={'day':day,'attempted_at':now(),'error':None};atomic(state_path(),state)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                indexes,metadata,prices=list(pool.map(fetch_source,range(3)))
            models=metadata if isinstance(metadata,list) else metadata.get('models',metadata.get('data',[]))
            if not indexes.get('general',{}).get('models') or not models or not isinstance(prices.get('data'),list):raise ValueError('missing data')
            value={'indexes':indexes,'metadata':models,'openrouter':prices,'fetched_at':now(),'epoch':time.time(),'sources':URLS}
            atomic(CACHE,value);return True
        except Exception as error:
            logging.getLogger(__name__).warning('Daily atlas update failed: %s',type(error).__name__)
            state['error']='今日上游更新未完成，保留最近一次成功的数据。';atomic(state_path(),state);return False
    finally:LOCK.release()

def live(force=False):
    # refresh=true remains backward-compatible, and only rereads the server snapshot.
    value=cached();state=read_state();due=slot();next_at=due+timedelta(days=1)
    if not value:raise HTTPException(503,'服务器尚未准备好每日模型快照，请稍后刷新显示。')
    stale=value.get('epoch',0)<due.timestamp()
    return value|{'cached':True,'stale':stale,'error':state.get('error') if stale else None,'update_schedule':'每日 04:00（北京时间）','next_update_at':next_at.isoformat()}

def start_scheduler():
    stop=threading.Event()
    if os.environ.get('DAWN_ATLAS_SCHEDULER','1')=='0':return stop
    def work():
        while not stop.is_set():
            try:update_daily()
            except Exception:logging.getLogger(__name__).exception('Daily atlas scheduler failed')
            stop.wait(60)
    threading.Thread(target=work,name='atlas-daily',daemon=True).start();return stop

@router.get('/live')
def get(request:Request,refresh:bool=Query(False),u=Depends(user)):
    data=live(refresh)
    if not data.get('stale'):
        with connect(True) as d:
            if not d.execute("SELECT 1 FROM events WHERE user_id=? AND kind='atlas-refreshed' AND json_extract(payload,'$.date')=?",(u['id'],today())).fetchone():emit(d,u['id'],'atlas-refreshed',{'date':today(),'fetched_at':data['fetched_at']})
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf8')
    etag='W/"'+hashlib.sha256(payload).hexdigest()[:32]+'"'
    headers={'ETag':etag,'Cache-Control':'private, max-age=60','Vary':'Cookie'}
    candidates=request.headers.get('if-none-match','').split(',')
    if any(value.strip().removeprefix('W/') in (etag.removeprefix('W/'),'*') for value in candidates):return Response(status_code=304,headers=headers)
    return Response(payload,media_type='application/json',headers=headers)
@router.get('/view')
def view(u=Depends(user)):return FileResponse(ROOT/'index.html',media_type='text/html')
@router.get('/assets/{filename}')
def asset(filename:str,u=Depends(user)):
    if filename not in ('styles.css','app.js','model-data.js','ambience.js','bootstrap.js'):raise HTTPException(404,'文件不存在')
    return FileResponse(ROOT/filename)

from .monitors import router as monitor_router
router.include_router(monitor_router)
