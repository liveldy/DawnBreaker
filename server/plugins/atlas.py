"""Live public model feeds; no built-in benchmark snapshot."""
import concurrent.futures,json,threading,time,urllib.request,uuid,logging
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import FileResponse
from ..core import require_plugin,emit,today
from ..db import DATA,now,connect
MANIFEST={'id':'atlas','name':'天眼','description':'模型排行榜、能力与成本图和私有 API 监视。按分钟更新公开数据，查看真实余额、模型与连通状态。','category':'AI','icon':'Radar','ui':'atlas'}
router=APIRouter(prefix='/api/plugins/atlas',tags=['天眼']);user=require_plugin('atlas')
ROOT=Path(__file__).parents[1]/'content/model-atlas';CACHE=DATA/'model-atlas'/'live.json';LOCK=threading.Lock();last_attempt=0;last_error=0.0
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
    try:return json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
def live(force=False):
    global last_attempt,last_error
    previous=cached();stamp=time.time()
    if previous and stamp-previous.get('epoch',0)<60 and (not force or stamp-last_attempt<5):return previous|{'stale':last_error>previous.get('epoch',0),'cached':True}
    if not LOCK.acquire(timeout=1):
        if previous:return previous|{'stale':stamp-previous.get('epoch',0)>120,'refreshing':True}
        raise HTTPException(503,'正在首次获取实时数据，请稍后重试')
    try:
        last_attempt=stamp
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(fetch_source,i) for i in range(3)]
            indexes=futures[0].result();metadata=futures[1].result()
            try:prices=futures[2].result()
            except Exception:prices=previous.get('openrouter',{'data':[]}) if previous else {'data':[]}
        models=metadata if isinstance(metadata,list) else metadata.get('models',metadata.get('data',[]))
        if not indexes.get('general',{}).get('models') or not models:raise ValueError('missing data')
        value={'indexes':indexes,'metadata':models,'openrouter':prices,'fetched_at':now(),'epoch':time.time(),'sources':URLS,'stale':False,'cached':False}
        CACHE.parent.mkdir(mode=0o700,exist_ok=True);temporary=CACHE.with_name('live-'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temporary.replace(CACHE)
        last_error=0.0
        return value
    except Exception as error:
        logging.getLogger(__name__).warning('Atlas refresh failed: %s',type(error).__name__)
        last_error=time.time()
        if previous:return previous|{'stale':True,'error':'上游暂时无法更新，当前显示最近一次成功获取的数据'}
        raise HTTPException(503,'暂时无法获取模型实时数据，请点击重试')
    finally:LOCK.release()
@router.get('/live')
def get(refresh:bool=Query(False),u=Depends(user)):
    data=live(refresh)
    if not data.get('stale'):
        with connect(True) as d:
            if not d.execute("SELECT 1 FROM events WHERE user_id=? AND kind='atlas-refreshed' AND json_extract(payload,'$.date')=?",(u['id'],today())).fetchone():emit(d,u['id'],'atlas-refreshed',{'date':today(),'fetched_at':data['fetched_at']})
    return data
@router.get('/view')
def view(u=Depends(user)):return FileResponse(ROOT/'index.html',media_type='text/html')
@router.get('/assets/{filename}')
def asset(filename:str,u=Depends(user)):
    if filename not in ('styles.css','app.js','model-data.js','ambience.js','bootstrap.js'):raise HTTPException(404,'文件不存在')
    return FileResponse(ROOT/filename)

from .monitors import router as monitor_router
router.include_router(monitor_router)
