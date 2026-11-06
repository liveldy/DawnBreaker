import io,json,zipfile
import pytest
from fastapi import HTTPException
from tests.test_api import client,register,install
from server import db
from server.core import state,set_state
from server.plugins import monitors,vocabulary,wallpaper
from server.secret_store import seal

def test_provider_presets_and_admin_key_isolation(client,monkeypatch):
    register(client);install(client,'atlas')
    providers=client.get('/api/plugins/atlas/monitors').json()['providers']
    assert len(providers)==18 and not any(p['id']=='meta' for p in providers) and not any(p['id']=='swe' for p in providers)
    row={'provider_id':'openai','api_base':'https://another.example/v1','billing_secret':seal('private-admin')}
    monkeypatch.setattr(monitors,'request_json',lambda *a,**k:pytest.fail('Admin key must not be sent to another origin'))
    report={'errors':[]};monitors.provider_statistics(row,'inference-key',report)
    assert '未转发' in report['statistics_note']

def test_anthropic_cents_and_tokens(monkeypatch):
    calls=[]
    def request(url,**kw):
        calls.append((url,kw))
        if 'cost_report' in url:return {'data':[{'results':[{'amount':'125','currency':'USD'}]}]}
        return {'data':[{'results':[{'uncached_input_tokens':5,'cache_read_input_tokens':7,'cache_creation':{'ephemeral_5m_input_tokens':11},'output_tokens':3}]}]}
    monkeypatch.setattr(monitors,'request_json',request)
    report={'errors':[]};monitors.provider_statistics({'provider_id':'anthropic','api_base':'https://api.anthropic.com/v1','billing_secret':seal('admin-test')},'normal-test',report)
    assert report['spent']==1.25 and report['tokens']==26
    assert 'requests' not in report and all(k['headers']['x-api-key']=='admin-test' for _,k in calls)

def test_queue_three_rounds_history_and_idempotent_answers(client,monkeypatch):
    uid=register(client);install(client,'vocabulary')
    assert client.put('/api/plugins/vocabulary/batch/settings',json={'size':2}).status_code==200
    batch=client.get('/api/plugins/vocabulary/batch').json()
    names=batch['words'];assert len(names)==2 and batch['phase']=='learn'
    for mode in ['learn']*3+['spell']*3:
        session=client.post('/api/plugins/vocabulary/speed/session',json={'mode':'learn','count':50,'queue':True}).json()
        assert session['mode']==('learn' if mode=='learn' else 'test-copy') and len(session['words'])==2
        for w in session['words']:
            answer={'session':session['session'],'token':w['token'],'answer':w['expected'],'seconds':1.5}
            for _ in range(2):assert client.post('/api/plugins/vocabulary/speed/answer',json=answer).status_code==200
    assert client.get('/api/plugins/vocabulary/batch').json()['phase']=='review'
    progress=client.get('/api/plugins/vocabulary/progress').json()['words']
    for w in progress:
        if w['name'] in names:assert w['learn_count']==3 and w['test_count']==3
    history=client.get('/api/plugins/vocabulary/speed/history').json()['sessions']
    assert len(history)==6 and all(s['completed']==2 and s['correct']==2 and s['seconds']==3 for s in history)
    # A completed answer cannot be made again in another account.
    client.post('/api/auth/logout');register(client,'another')
    install(client,'vocabulary')
    assert client.post('/api/plugins/vocabulary/speed/answer',json=answer).status_code==409

def package(entry='desktop/index.html',extra=None):
    manifest={'format':1,'title':'网页壁纸','variants':{'desktop':{'kind':'web','entry':entry}}}
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest));z.writestr(entry,'<!doctype html><title>wallpaper</title>')
        if extra:z.writestr(extra,'x')
    return b.getvalue()

def test_wallpaper_admin_publish_and_paths(client,tmp_path,monkeypatch):
    monkeypatch.setattr(wallpaper,'ROOT',tmp_path)
    uid=register(client);install(client,'wallpaper')
    assert client.post('/api/plugins/wallpaper',files={'file':('a.zip',package())}).status_code==403
    with db.connect(True) as d:d.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
    content=package();r=client.post('/api/plugins/wallpaper',files={'file':('a.zip',content)})
    assert r.status_code==201,r.text
    id=r.json()['id'];assert client.get('/api/plugins/wallpaper/'+id+'/file').content==content
    for bad in ['../escape','a/./b.html','a//b.html','C:/evil','CON.txt','file.','a\\b']:
        assert not wallpaper.safe_name(bad)
        payload=package(extra=bad)
        if bad=='a\\b':payload=package(extra='a/b').replace(b'a/b',b'a\\b')
        with pytest.raises(HTTPException):wallpaper.inspect_package(payload)
    assert client.delete('/api/plugins/wallpaper/'+id).status_code==200

def test_warp_profile_owner_and_encryption(client):
    uid=register(client);install(client,'warp')
    r=client.post('/api/plugins/warp',json={'name':'测试','yaml':'proxies: []\nrules: [MATCH,DIRECT]'})
    assert r.status_code==201
    assert 'yaml' not in r.json()
    id=r.json()['id'];assert 'proxies' in client.post('/api/plugins/warp/'+id+'/open').json()['yaml']
    with db.connect() as d:assert 'proxies' not in state(d,uid,'warp','profiles')[0]['yaml']
    client.post('/api/auth/logout');register(client,'outsider');install(client,'warp')
    assert client.post('/api/plugins/warp/'+id+'/open').status_code==404
