from types import SimpleNamespace
from tests.test_api import client,register,install
from tests.test_v130 import create
from server import db,library_time
from server.core import state,set_state,balance

def achievement(c):return next(t for t in c.get('/api/plugins/journal').json()['tasks'] if t['title']=='笔耕不辍')

def test_time_bounds_overlap_suspend_and_scope(client,monkeypatch):
    uid=register(client);install(client,'library','journal');doc=create(client);clock=[1000.]
    monkeypatch.setattr(library_time,'time',SimpleNamespace(time=lambda:clock[0]))
    def beat(s,seconds,id=doc['id']):
        r=client.post('/api/plugins/library/foreground-time',json={'session':s,'document_id':id,'seconds':seconds})
        assert r.status_code==200,r.text
        return r.json()
    assert beat('session-a',0)['accepted_seconds']==0
    assert beat('session-b',0)['accepted_seconds']==0
    clock[0]+=15
    assert beat('session-a',15)['accepted_seconds']==15
    assert beat('session-b',15)['accepted_seconds']==0
    clock[0]+=15
    assert beat('session-b',30)['accepted_seconds']==15
    assert beat('session-a',30)['total_seconds']==30
    clock[0]+=15
    assert beat('session-a',30)['accepted_seconds']==0
    assert beat('session-a',29)['accepted_seconds']==0
    clock[0]+=300
    assert beat('session-a',300)['accepted_seconds']==0
    clock[0]+=15
    assert beat('session-a',315)['accepted_seconds']==15
    clock[0]+=15
    assert beat('session-a',999999)['accepted_seconds']==15
    assert achievement(client)['progress']==1
    folder=create(client,kind='folder')
    assert client.post('/api/plugins/library/foreground-time',json={'session':'session-z','document_id':folder['id'],'seconds':0}).status_code==422
    client.post('/api/auth/logout');register(client,'otherreader');install(client,'library','journal')
    assert client.post('/api/plugins/library/foreground-time',json={'session':'session-a','document_id':doc['id'],'seconds':999999}).status_code==404
    assert achievement(client)['progress']==0

def test_new_milestones_reset_old_claims_and_keep_paid_balance(client):
    uid=register(client);install(client,'library','journal');doc=create(client)
    with db.connect(True) as d:
        set_state(d,uid,'journal','claim:v2-ach-library-0',True)
        d.execute("INSERT INTO events(user_id,kind,payload,created_at) VALUES(?,?,?,?)",(uid,'document-saved','{"characters":500000,"date":"2026-11-05"}','now'))
        before=balance(d,uid,'essence')
    task=achievement(client)
    assert task['progress']==0 and task['level']==1 and not task['claimed'] and task['unit']=='分钟'
    assert [m['target'] for m in task['milestones']]==[20,50,100,200,500,1000,2000]
    assert [m['reward'] for m in task['milestones']]==[{'essence':50},{'essence':2000},{'essence':10000},{'stones':5},{'stones':10},{'stones':20},{'stones':50}]
    assert client.post('/api/plugins/journal/claim/'+task['id']).status_code==409
    with db.connect(True) as d:set_state(d,uid,'library','foreground-time',{'seconds':1200})
    assert client.post('/api/plugins/journal/claim/'+task['id']).status_code==200
    assert client.post('/api/plugins/journal/claim/'+task['id']).status_code==404
    assert achievement(client)['level']==2
    with db.connect() as d:assert balance(d,uid,'essence')==before+50
