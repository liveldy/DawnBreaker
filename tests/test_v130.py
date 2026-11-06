import base64,io,json,time
from datetime import datetime,timedelta
import pytest
from PIL import Image
from tests.test_api import client,register,install
from server import db
from server.plugins import constellation as ai,library,vault,atlas

def create(c,kind='document',parent=None,title='数学笔记',text='$E=mc^2$'):
    r=c.post('/api/plugins/library/nodes',json={'kind':kind,'parent_id':parent,'title':title,'markdown':text})
    assert r.status_code==201,r.text
    return r.json()

def test_library_revision_cycles_isolation_and_text_import(client):
    register(client);install(client,'library');root=create(client,'folder');child=create(client,'folder',root['id']);doc=create(client,parent=child['id'])
    path='/api/plugins/library/nodes/'+doc['id'];body={'title':'新标题','markdown':'$$\\int_0^1 x dx$$','revision':1,'parent_id':child['id']}
    assert client.put(path,json=body).json()['revision']==2
    assert client.put(path,json=body).status_code==409
    assert client.put('/api/plugins/library/nodes/'+root['id'],json=body|{'parent_id':child['id']}).status_code==422
    assert client.delete('/api/plugins/library/nodes/'+child['id']).status_code==409
    r=client.post('/api/plugins/library/imports',files={'file':('example.md','# 标题\n\n$E=mc^2$'.encode(),'text/markdown')})
    assert r.status_code==202 and r.json()['status']=='completed'
    assert client.get(path+'/export').headers['content-type'].startswith('text/markdown')
    client.post('/api/auth/logout');register(client,'reader2');install(client,'library')
    assert client.get(path).status_code==404
    assert client.post('/api/plugins/library/nodes',json={'title':'test','parent_id':root['id']}).status_code==404

def config(**kwargs):return {'name':'星星','family':'gpt','model':'test-model','api_base':'https://api.example.com/v1','api_key':'test-secret-key',**kwargs}
def assistant(c,**kwargs):
    r=c.post('/api/plugins/constellation/assistants',json=config(**kwargs));assert r.status_code==201,r.text;return r.json()
def thread(c,a):return c.post('/api/plugins/constellation/threads',json={'assistant_id':a['id']}).json()['id']

def test_ai_optional_library_key_secrecy_and_protocols(client,monkeypatch,tmp_path):
    from server import secret_store
    monkeypatch.setattr(secret_store,'DATA',tmp_path)
    register(client);install(client,'constellation')
    a=assistant(client);assert a['has_key'] and 'api_key' not in a
    with db.connect() as d:
        encrypted=d.execute('SELECT secret FROM assistants').fetchone()[0];assert 'test-secret-key' not in encrypted
    assert client.post('/api/plugins/constellation/assistants',json=config(workspace_id='abc')).status_code==409
    for url in ['http://api.example.com','https://127.0.0.1','https://user:pass@api.example.com','https://api.example.com/?secret=1']:
        assert client.post('/api/plugins/constellation/assistants',json=config(api_base=url)).status_code==422
    captured=[]
    def response(url,body=None,headers=None):
        captured.append((url,body,headers))
        if url.endswith('/responses'):return {'output':[{'content':[{'type':'output_text','text':'好'}]}]}
        if url.endswith('/messages'):return {'content':[{'type':'text','text':'好'}]}
        if ':generateContent' in url:return {'candidates':[{'content':{'parts':[{'text':'好'}]}}]}
        return {'choices':[{'message':{'content':'好'}}]}
    monkeypatch.setattr(ai,'request_json',response)
    for protocol in ['openai','responses','anthropic','gemini']:
        c=ai.Config(**config(protocol=protocol)).model_dump();assert ai.invoke(c,'key',[{'role':'user','content':'你好'}],'prompt')=='好'
    assert captured[0][1].get('temperature') is None and 'temperature' not in captured[0][1]
    assert captured[1][2]['Authorization']=='Bearer key'

def test_ai_reviewed_edits_idempotence_conflicts_scopes_and_uninstall(client,monkeypatch,tmp_path):
    from server import secret_store
    monkeypatch.setattr(secret_store,'DATA',tmp_path);register(client);install(client,'constellation','library')
    root=create(client,'folder');doc=create(client,parent=root['id']);outside=create(client)
    a=assistant(client,workspace_id=root['id']);t=thread(client,a);calls=[]
    def model(*args,**kwargs):calls.append(args);return json.dumps({'reply':'修改建议','edits':[{'document_id':doc['id'],'revision':1,'markdown':'new $x^2$'},{'document_id':outside['id'],'revision':1,'markdown':'bad'}]})
    monkeypatch.setattr(ai,'invoke',model)
    url='/api/plugins/constellation/threads/'+t;body={'request_id':'turn-123456','content':'修改文档','document_id':doc['id']}
    assert client.post(url+'/chat',json=body|{'document_id':outside['id']}).status_code==403
    result=client.post(url+'/chat',json=body);assert result.status_code==200,result.text
    assert len(result.json()['edits'])==1 and len(calls)==1
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']==doc['markdown']
    assert client.post(url+'/chat',json=body).json()==result.json() and len(calls)==1
    assert client.post(url+'/chat',json=body|{'content':'different'}).status_code==409
    for _ in range(2):assert client.post(url+'/apply',json={'request_id':body['request_id']}).status_code==200
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['revision']==2
    assert client.get('/api/plugins/library/nodes/'+outside['id']).json()['markdown']==outside['markdown']
    assert client.delete('/api/plugins/library/nodes/'+root['id']).status_code==409
    b2=body|{'request_id':'turn-223456'};assert client.post(url+'/chat',json=b2).status_code==200
    assert client.post(url+'/apply',json={'request_id':b2['request_id']}).status_code==409
    assert client.delete('/api/catalog/library').status_code==200
    assert client.post(url+'/apply',json={'request_id':body['request_id']}).status_code==403
    assert client.post(url+'/chat',json=body|{'request_id':'turn-323456'}).status_code==403
    assert client.post(url+'/chat',json={'request_id':'turn-423456','content':'普通对话'}).status_code==200

def test_vault_opaque_version_and_isolation(client):
    register(client);install(client,'vault');assert client.get('/api/plugins/vault').json()=={'exists':False}
    b64=lambda n:base64.b64encode(b'x'*n).decode()
    value={'version':0,'salt':b64(16),'nonce':b64(12),'ciphertext':b64(64),'iterations':600000,'algorithm':'PBKDF2-SHA256/AES-256-GCM'}
    assert client.put('/api/plugins/vault',json=value).json()['version']==1
    assert client.put('/api/plugins/vault',json=value).status_code==409
    assert client.put('/api/plugins/vault',json=value|{'version':1,'nonce':b64(8)}).status_code==422
    client.post('/api/auth/logout');register(client,'vault2');install(client,'vault');assert not client.get('/api/plugins/vault').json()['exists']

def test_ai_rolls_context_into_library_memory_and_refuses_truncated_edits(client,monkeypatch,tmp_path):
    from server import secret_store
    monkeypatch.setattr(secret_store,'DATA',tmp_path);register(client);install(client,'library','constellation')
    workspace=create(client,'folder');memory=create(client,'folder');doc=create(client,parent=workspace['id'],text='x'*20000)
    a=assistant(client,workspace_id=workspace['id'],memory_id=memory['id'],context_chars=8000);t=thread(client,a);summaries=[]
    def model(config,key,messages,system,max_tokens=None,tools=None):
        if max_tokens==600:summaries.append(messages);return json.dumps({'memory':'用户整理数学笔记','summary':'继续校对公式'},ensure_ascii=False)
        return json.dumps({'reply':'继续整理。','edits':[{'document_id':doc['id'],'revision':1,'markdown':'must not replace truncated content'}]})
    monkeypatch.setattr(ai,'invoke',model)
    for i in range(8):
        result=client.post('/api/plugins/constellation/threads/'+t+'/chat',json={'request_id':'memory-turn-'+str(i),'content':'继续','document_id':doc['id']})
        assert result.status_code==200,result.text
        assert result.json()['edits']==[]
    assert summaries
    nodes=client.get('/api/plugins/library').json()['nodes'];saved=[n for n in nodes if n['parent_id']==memory['id'] and n['kind']=='document'];assert len(saved)==1
    assert '用户整理数学笔记' in client.get('/api/plugins/library/nodes/'+saved[0]['id']).json()['markdown']
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']=='x'*20000

def test_avatar_validation_resize_and_isolation(client,monkeypatch,tmp_path):
    from server import avatars
    monkeypatch.setattr(avatars,'ROOT',tmp_path)
    register(client);image=io.BytesIO();Image.new('RGB',(1200,800),'red').save(image,format='PNG')
    r=client.post('/api/profile/avatar',files={'file':('avatar.png',image.getvalue(),'image/png')});assert r.status_code==200,r.text
    link=client.get('/api/bootstrap').json()['user']['avatar_url'];result=client.get(link);assert result.status_code==200
    assert Image.open(io.BytesIO(result.content)).size==(512,512)
    assert client.post('/api/profile/avatar',files={'file':('avatar.png',b'not an image','image/png')}).status_code==422
    client.post('/api/auth/logout');register(client,'avatar2');assert client.get(link).status_code==404

def test_offline_listening_retry_overlap_and_midnight(client):
    from server.milestones import listening_seconds
    uid=register(client);install(client,'music');stamp=time.time()-60
    def sync(segments,device='desktop-12345'):
        r=client.post('/api/plugins/music/sync',json={'device_id':device,'segments':segments});assert r.status_code==200,r.text;return r.json()
    def segment(id,start,end):return {'id':id,'start':start,'end':end,'seconds':end-start,'track_id':'ancient-001'}
    first=segment('segment-one',stamp,stamp+20);assert sync([first])['credited_seconds']==20
    assert sync([first])['credited_seconds']==0
    assert sync([segment('segment-two',stamp+10,stamp+30)],'android-12345')['credited_seconds']==10
    assert sync([segment('segment-invalid',stamp+10000,stamp+10010)])['rejected_ids']==['segment-invalid']
    from server.listening import record,ZONE
    midnight=datetime(2026,11,3,tzinfo=ZONE).timestamp()
    with db.connect(True) as d:
        assert record(d,uid,'midnight-segment','test-device',midnight-10,midnight+10,20)==20
    with db.connect() as d:
        assert listening_seconds(d,uid)==50
        events=[json.loads(r[0]) for r in d.execute("SELECT payload FROM events WHERE user_id=? AND kind='music-listened'",(uid,))]
        assert any(e['date']=='2026-11-02' and e['seconds']==10 for e in events)
        assert any(e['date']=='2026-11-03' and e['seconds']==10 for e in events)

def test_atlas_fresh_cache_and_truthful_stale(client,monkeypatch,tmp_path):
    register(client);install(client,'atlas');monkeypatch.setattr(atlas,'CACHE',tmp_path/'live.json');monkeypatch.setattr(atlas,'last_attempt',0)
    def source(i):return [{'model_id':'one'}] if i==1 else {'general':{'models':[{'model_id':'one','conservative':10}]}} if i==0 else {'data':[]}
    monkeypatch.setattr(atlas,'fetch_source',source)
    first=client.get('/api/plugins/atlas/live').json();assert not first['stale'] and len(first['metadata'])==1
    monkeypatch.setattr(atlas,'last_attempt',0)
    monkeypatch.setattr(atlas,'fetch_source',lambda _:(_ for _ in ()).throw(OSError()))
    assert client.get('/api/plugins/atlas/live?refresh=true').json()['stale']
    assert client.get('/api/plugins/atlas/live').json()['stale']
    assert client.get('/api/plugins/atlas/view').headers['x-frame-options']=='SAMEORIGIN'
