import json
from datetime import date,timedelta
from tests.test_api import client,register,install
from tests.test_v130 import create,assistant,thread
from server import db,api_meter
from server.core import today
from server.plugins import constellation as ai,atlas,monitors
from server.milestones import changed_characters

def task(c,title):return next(t for t in c.get('/api/plugins/journal').json()['tasks'] if t['title']==title)

def test_document_changes_milestones_and_noop_revision(client):
    register(client);install(client,'journal','library');doc=create(client,text='原文')
    assert task(client,'图书管理员')['progress']==0
    path='/api/plugins/library/nodes/'+doc['id'];body={'title':doc['title'],'markdown':'新'*501,'revision':1}
    assert client.put(path,json=body).status_code==200
    assert task(client,'图书管理员')['progress']==1 and task(client,'笔耕不辍')['progress']==0
    assert client.put(path,json=body).status_code==409
    before=task(client,'笔耕不辍')['progress']
    assert client.put(path,json=body|{'revision':2}).status_code==200
    assert task(client,'笔耕不辍')['progress']==before
    id=task(client,'图书管理员')['id'];assert client.post('/api/plugins/journal/claim/'+id).status_code==200
    assert client.post('/api/plugins/journal/claim/'+id).status_code==409
    assert changed_characters('你好世界','你好新世界')==1
    assert changed_characters('a b\nc','ab c')==0

def test_chat_count_archive_delete_and_isolation(client,monkeypatch):
    uid=register(client);install(client,'journal','constellation');a=assistant(client);id=thread(client,a)
    monkeypatch.setattr(ai,'invoke',lambda *a,**k:'回答')
    url='/api/plugins/constellation/threads/'+id;body={'request_id':'count-replay-001','content':'你好'}
    for _ in range(2):assert client.post(url+'/chat',json=body).status_code==200
    assert task(client,'好助手')['progress']==1 and task(client,'心灵的交流')['progress']==1
    assert client.put(url+'/archive',json={'archived':True}).status_code==200
    assert client.get('/api/plugins/constellation/threads',params={'assistant_id':a['id']}).json()['threads']==[]
    assert len(client.get('/api/plugins/constellation/threads',params={'assistant_id':a['id'],'archived':True}).json()['threads'])==1
    assert client.post(url+'/chat',json=body|{'request_id':'count-replay-002'}).status_code==409
    assert client.put(url+'/archive',json={'archived':False}).status_code==200
    with db.connect(True) as d:d.execute("INSERT INTO ai_turns(user_id,request_id,thread_id,status,created_at) VALUES(?,?,?,'running','now')",(uid,'running',id))
    assert client.delete(url).status_code==409
    with db.connect(True) as d:d.execute("DELETE FROM ai_turns WHERE request_id='running'")
    assert client.delete(url).status_code==200 and client.get(url).status_code==404
    assert task(client,'心灵的交流')['progress']==1

def test_speed_shared_records_unique_words_replay_and_errors(client):
    uid=register(client);install(client,'vocabulary','journal')
    value=client.post('/api/plugins/vocabulary/speed/session',json={'mode':'learn','count':20}).json()
    assert len(value['words'])==10 and len({w['expected'] for w in value['words']})==10
    first=value['words'][0];body={'session':value['session'],'token':first['token'],'answer':first['expected']}
    assert client.post('/api/plugins/vocabulary/speed/answer',json=body|{'answer':'bad'}).status_code==422
    assert client.post('/api/plugins/vocabulary/speed/answer',json=body).status_code==200
    assert client.post('/api/plugins/vocabulary/speed/answer',json=body).status_code==200
    assert client.get('/api/plugins/vocabulary').json()['learned']==1
    assert client.get('/api/plugins/vocabulary').json()['today_correct']==1
    review=client.post('/api/plugins/vocabulary/speed/session',json={'mode':'review-spell','count':20}).json();assert len(review['words'])==1
    w=review['words'][0];r=client.post('/api/plugins/vocabulary/speed/answer',json={'session':review['session'],'token':w['token'],'answer':w['expected'],'mistakes':True})
    assert r.status_code==200 and not r.json()['correct']
    with db.connect() as d:memory=json.loads(d.execute("SELECT value FROM progress WHERE user_id=? AND plugin_id='vocabulary' AND key='memory'",(uid,)).fetchone()[0])
    assert memory[w['expected']]['correct_streak']==0 and memory[w['expected']]['review_streak']==0

def test_import_history_delete_keeps_document_and_assets(client):
    uid=register(client);install(client,'library');r=client.post('/api/plugins/library/imports',files={'file':('book.md',b'# Example','text/markdown')}).json()
    assert len(client.get('/api/plugins/library').json()['imports'])==1
    assert client.delete('/api/plugins/library/imports/'+r['id']).status_code==200
    assert client.get('/api/plugins/library').json()['imports']==[]
    assert client.get('/api/plugins/library/nodes/'+r['document_id']).status_code==200
    assert client.post('/api/plugins/library/imports/'+r['id']+'/retry').status_code==404
    client.post('/api/auth/logout');register(client,'foreign');install(client,'library')
    assert client.delete('/api/plugins/library/imports/'+r['id']).status_code==404

def test_quote_future_schedule_and_stable_random_fallback(client):
    uid=register(client);install(client,'quotes','lol-quotes')
    assert client.put('/api/admin/quote-schedule',json={'day':today(),'quote_id':'lol-001'}).status_code==403
    with db.connect(True) as d:d.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
    tomorrow=(date.fromisoformat(today())+timedelta(days=1)).isoformat()
    assert client.put('/api/admin/quote-schedule',json={'day':tomorrow,'quote_id':'lol-001'}).status_code==200
    assert client.put('/api/admin/quote-schedule',json={'day':today(),'quote_id':'lol-001'}).status_code==200
    assert client.get('/api/plugins/quotes').json()['id']=='lol-001'
    assert client.delete('/api/admin/quote-schedule/'+today()).status_code==200
    assert client.get('/api/plugins/quotes').json()==client.get('/api/plugins/quotes').json()
    assert client.put('/api/admin/quote-schedule',json={'day':'2020-01-01','quote_id':'lol-001'}).status_code==422

def test_atlas_refresh_only_counts_usable_data_and_daily_all(client,monkeypatch):
    register(client);install(client,'journal','atlas','library','constellation','checkin','vocabulary','music','collection')
    assert task(client,'有始有终')['target']==7
    monkeypatch.setattr(atlas,'live',lambda force:{'stale':True,'fetched_at':'now'})
    assert client.get('/api/plugins/atlas/live?refresh=true').status_code==200
    assert task(client,'静观其变')['progress']==0
    monkeypatch.setattr(atlas,'live',lambda force:{'stale':False,'fetched_at':'now'})
    for _ in range(2):client.get('/api/plugins/atlas/live?refresh=true')
    assert task(client,'静观其变')['progress']==1

def test_monitor_ownership_encryption_partial_stats_and_meter(client,monkeypatch):
    register(client);install(client,'atlas')
    assert client.post('/api/plugins/atlas/monitors',json={'name':'private','api_base':'https://127.0.0.1','api_key':'secret'}).status_code==422
    body={'name':'OpenRouter','api_base':'https://openrouter.ai/api/v1','api_key':'sk-test-monitor'}
    r=client.post('/api/plugins/atlas/monitors',json=body);assert r.status_code==201,r.text
    m=r.json();id=m['id'];base='/api/plugins/atlas/monitors/'+id
    assert 'sk-test-monitor' not in client.get('/api/plugins/atlas/monitors').text
    with db.connect() as d:assert 'sk-test-monitor' not in d.execute('SELECT secret FROM api_monitors').fetchone()[0]
    def get(url,body=None,headers=None):
        if url.endswith('/models'):return {'data':[{'id':'example','pricing':{'prompt':'0.000001','completion':'0.000002'}}]}
        return {'data':{'usage':0,'limit_remaining':12.5}}
    monkeypatch.setattr(monitors,'request_json',get)
    report=client.post(base+'/refresh').json()['report'];assert report['balance']==12.5 and report['spent']==0 and report['requests'] is None
    assert report['models'][0]['input_price']==1
    monkeypatch.setattr(api_meter,'request_json',lambda *a,**k:{'choices':[{'message':{'content':'Hello'}}],'usage':{'total_tokens':12,'completion_tokens':4}})
    r=client.post(base+'/test',json={'model':'example'});assert r.status_code==200,r.text
    assert r.json()['local_usage']['requests']==1 and r.json()['local_usage']['tokens']==12
    assert r.json()['report']['speed']['output_tokens']==4
    assert client.post(base+'/test',json={'model':'example'}).status_code==429
    assert client.post(base+'/key').json()['key']==body['api_key']
    assert client.put(base,json=body|{'api_base':'https://other.example/v1','api_key':''}).status_code==422
    client.post('/api/auth/logout');register(client,'monitor2');install(client,'atlas')
    for suffix in ['/key','/refresh']:assert client.post(base+suffix).status_code==404
    assert client.delete(base).status_code==404

def test_metered_chat_and_approved_document_edit(client,monkeypatch):
    register(client);install(client,'library','constellation','journal','atlas')
    folder=create(client,'folder');doc=create(client,parent=folder['id'],text='原文')
    a=assistant(client,workspace_id=folder['id'])
    m=client.post('/api/plugins/atlas/monitors',json={'name':'同一接口','api_base':'https://api.example.com/v1','api_key':'test-secret-key'}).json()
    response={'reply':'已准备修改','edits':[{'document_id':doc['id'],'revision':1,'markdown':'新的文档内容'}]}
    monkeypatch.setattr(api_meter,'request_json',lambda *a,**k:{'choices':[{'message':{'content':json.dumps(response)}}],'usage':{'total_tokens':21,'completion_tokens':6}})
    t=thread(client,a);url='/api/plugins/constellation/threads/'+t
    for _ in range(2):assert client.post(url+'/chat',json={'request_id':'meter-chat-001','content':'修改文档'}).status_code==200
    counts=client.get('/api/plugins/atlas/monitors').json()['monitors'][0]['local_usage']
    assert counts['requests']==1 and counts['tokens']==21
    assert task(client,'图书管理员')['progress']==0
    for _ in range(2):assert client.post(url+'/apply',json={'request_id':'meter-chat-001'}).status_code==200
    assert task(client,'图书管理员')['progress']==1 and task(client,'心灵的交流')['progress']==1

def test_model_probe_never_forwards_saved_key_to_changed_provider(client,monkeypatch):
    register(client);install(client,'constellation');a=assistant(client)
    calls=[]
    monkeypatch.setattr(ai,'request_json',lambda *args,**kwargs:calls.append(args) or {'data':[{'id':'model'}]})
    body={'api_base':'https://other.example/v1','assistant_id':a['id'],'protocol':'openai'}
    assert client.post('/api/plugins/constellation/models',json=body).status_code==422
    assert calls==[]
    assert client.post('/api/plugins/constellation/models',json=body|{'api_key':'explicit-new-key'}).status_code==200
    assert len(calls)==1
