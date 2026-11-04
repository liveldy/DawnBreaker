"""Adapt the user's reference site exactly, replacing snapshot loading with live server feeds."""
from pathlib import Path
import httpx
R=Path(__file__).resolve().parents[1];source=R/'artifacts/atlas-reference';out=R/'server/content/model-atlas';out.mkdir(exist_ok=True)
if not (source/'ambience.js').exists():
    r=httpx.get('https://liveldy.github.io/last-token/model-atlas/ambience.js',trust_env=False,timeout=30);r.raise_for_status();(source/'ambience.js').write_bytes(r.content)
html=(source/'index.html').read_text(encoding='utf-8').replace('href="styles.css"','href="/api/plugins/atlas/assets/styles.css"')
html=html.replace('<script src="data/models-snapshot.js"></script>','').replace('<script src="data/model-data.js"></script>','<script src="/api/plugins/atlas/assets/model-data.js"></script>').replace('<script src="ambience.js"></script>','<script src="/api/plugins/atlas/assets/ambience.js"></script>').replace('<script src="app.js"></script>','<script src="/api/plugins/atlas/assets/bootstrap.js"></script>')
html=html.replace('本页显示的是打包在工程里的数据快照。','本页通过服务端代理每 60 秒获取公开数据；更新时间以最近一次成功获取为准。上游失败时会明确标记缓存。')
html=html.replace('<title>模型能力图鉴 · 能力 × 成本</title>','<title>天眼 · 模型能力图鉴</title>')
(out/'index.html').write_text(html,encoding='utf-8')
for name in ['styles.css','model-data.js','ambience.js']:
    original=source/('data-model-data.js' if name=='model-data.js' else name);(out/name).write_bytes(original.read_bytes())
app=(source/'app.js').read_text(encoding='utf-8')
start=app.index('  function canRefresh()');end=app.index('  function rebuildAll()',start)
app=app[:start]+'''  function canRefresh(){return !WALLPAPER;}
  function refresh(loud){
    if(loud)setStatus('正在拉取实时数据…');
    return window.dawnAtlasFetch(true).then(function(data){
      var org=state.org;state.data=data;indexData();state.live=!data.stale;rebuildAll();
      if(org){state.org=org;applyBoardFilter();}
      setStatus((data.stale?'上游暂未更新 · 缓存 ':'实时数据 · ')+when(data.snapshotAt)+' · 每60秒自动更新',data.stale?'warn':'ok');
      return true;
    }).catch(function(e){setStatus('暂时无法更新：'+e.message+'（保留上次成功数据）','warn');return false;});
  }
''' + app[end:]
app+='\nsetInterval(function(){if(document.visibilityState===\'visible\'&&window.ModelAtlas)window.ModelAtlas.refresh(false);},60000);\n'
(out/'app.js').write_text(app,encoding='utf-8')
(out/'bootstrap.js').write_text('''(function(){
 window.dawnAtlasFetch=async function(force){const r=await fetch('/api/plugins/atlas/live'+(force?'?refresh=true':''),{credentials:'include'});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'数据暂不可用');const result=ModelData.buildDataset(data.metadata,data.indexes,Array.isArray(data.openrouter)?data.openrouter:(data.openrouter.data||[]));result.snapshotAt=data.fetched_at;result.stale=!!data.stale;return result;};
 async function boot(){try{window.MODEL_SNAPSHOT=await window.dawnAtlasFetch(false);const script=document.createElement('script');script.src='/api/plugins/atlas/assets/app.js';document.body.appendChild(script);}catch(error){const main=document.querySelector('main')||document.body;main.textContent='';const message=document.createElement('p');message.textContent=error.message;message.style.padding='40px';const retry=document.createElement('button');retry.textContent='重新获取';retry.className='ctl';retry.onclick=()=>location.reload();message.appendChild(retry);main.appendChild(message);}}
 boot();
})();''',encoding='utf-8')
print('Prepared live model atlas using the supplied reference layout; no bundled model snapshot')
