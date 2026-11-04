"""Exercise the public source without optional private media packs."""
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='dawn-source-') as folder:
    os.environ['DAWN_DATA_DIR']=folder
    from fastapi.testclient import TestClient
    from server.main import app
    with TestClient(app) as c:
        assert c.get('/api/health').json()['status']=='ok'
        assert c.post('/api/auth/register',json={'username':'sourcecheck','password':'Source-check-2026'}).status_code==201
        catalog=c.get('/api/catalog').json()['plugins']
        for p in catalog:
            if p['type']=='standard':assert c.post('/api/catalog/'+p['id']+'/install').status_code==200
        for name in ['collection','music','quotes','journal','vocabulary','library','warp','wallpaper']:
            r=c.get('/api/plugins/'+name);assert r.status_code==200,(name,r.text)
        assert c.get('/api/plugins/vocabulary/question').status_code==200
    print('PASS: source-only startup, registration, plugin installation and empty media states')
