import io,json,threading,time
import pytest
from PIL import Image
from tests.test_api import client,register,install
from tests.test_v130 import create,assistant,thread
from server import db
from server.plugins import constellation as ai
from server.ai_protocol import ModelReply

def test_quota_images_owned_references_and_admin(client,tmp_path,monkeypatch):
    from server import library_storage
    from server.plugins import library
    monkeypatch.setattr(library,'IMAGES',tmp_path/'images');library.IMAGES.mkdir()
    uid=register(client);install(client,'library');doc=create(client)
    assert client.get('/api/plugins/library').json()['storage']['quota_bytes']==64*1048576
    image=io.BytesIO();Image.new('RGB',(12,8),'green').save(image,'PNG')
    uploaded=client.post('/api/plugins/library/images',files={'file':('diagram.png',image.getvalue(),'image/png')});assert uploaded.status_code==201,uploaded.text
    url=uploaded.json()['url'];assert client.get(url).headers['content-type']=='image/webp'
    assert client.post('/api/plugins/library/images',files={'file':('bad.png',b'not an image','image/png')}).status_code==422
    path='/api/plugins/library/nodes/'+doc['id'];body={'title':doc['title'],'markdown':'![diagram]('+url+')','revision':1,'parent_id':None}
    assert client.put(path,json=body).status_code==200
    assert client.delete(url).status_code==409
    assert client.get('/api/plugins/library/images').json()['images'][0]['references']==1
    with db.connect(True) as d:d.execute('UPDATE users SET library_quota_bytes=0 WHERE id=?',(uid,))
    assert client.post('/api/plugins/library/nodes',json={'title':'Too large','markdown':'x'}).status_code==413
    assert client.put(path,json=body|{'markdown':'','revision':2}).status_code==200
    assert client.delete(url).status_code==200
    assert client.patch('/api/admin/users/'+uid+'/library-quota',json={'quota_mb':128}).status_code==403
    with db.connect(True) as d:d.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
    assert client.patch('/api/admin/users/'+uid+'/library-quota',json={'quota_mb':128}).status_code==200
    assert client.get('/api/plugins/library').json()['storage']['quota_bytes']==128*1048576
    client.post('/api/auth/logout');register(client,'reader2');install(client,'library');assert client.get(path).status_code==404 and client.get(url).status_code==404

def test_daily_notes_and_published_holidays(client):
    register(client);install(client,'checkin');day='2026-10-01'
    assert client.put('/api/plugins/checkin/notes/'+day,json={'content':'今天读了一本书。'}).status_code==200
    result=client.get('/api/plugins/checkin?month=2026-10').json()
    assert result['notes'][day]['content']=='今天读了一本书。' and result['holidays']['days'][day]['isOffDay']
    assert client.put('/api/plugins/checkin/notes/2026-02-30',json={'content':'x'}).status_code==422
    client.post('/api/auth/logout');register(client,'notes2');install(client,'checkin')
    assert client.get('/api/plugins/checkin?month=2026-10').json()['notes']=={}

def test_personal_quote_history_does_not_change_other_accounts(client,monkeypatch):
    from server.plugins import quotes_history as q
    register(client);install(client,'quotes');monkeypatch.setattr(q,'today',lambda:'2026-11-01')
    first=client.get('/api/plugins/quotes').json();monkeypatch.setattr(q,'today',lambda:'2026-11-03')
    assert client.get('/api/plugins/quotes/history').json()['total']==3
    assert client.put('/api/plugins/quotes/current',json={'source_day':'2026-11-01'}).status_code==200
    selected=client.get('/api/plugins/quotes').json();assert selected['id']==first['id'] and selected['personal']
    client.post('/api/auth/logout');register(client,'quotes2');install(client,'quotes')
    assert not client.get('/api/plugins/quotes').json()['personal']
    assert client.put('/api/plugins/quotes/current',json={'source_day':'2026-11-01'}).status_code==404

def test_ai_native_tools_real_save_memory_and_old_json(client,monkeypatch,tmp_path):
    from server import secret_store
    monkeypatch.setattr(secret_store,'DATA',tmp_path);uid=register(client);install(client,'library','constellation')
    root=create(client,'folder');mem=create(client,'folder');doc=create(client,parent=root['id'],text='原始内容 $x^2$')
    a=assistant(client,workspace_id=root['id'],memory_id=mem['id']);tid=thread(client,a);count=0
    def model(*args,**kwargs):
        nonlocal count
        count+=1
        if count==1:return ModelReply('',reasoning='正在检查文档中的公式。',calls=[{'id':'tool1','name':'replace_text','arguments':{'document_id':doc['id'],'revision':1,'old':'原始内容','new':'已修改内容'}}],wire={'role':'assistant','content':None,'tool_calls':[]})
        return ModelReply('已准备好修改。')
    monkeypatch.setattr(ai,'invoke',model)
    url='/api/plugins/constellation/threads/'+tid
    result=client.post(url+'/chat',json={'request_id':'native-tool-save','content':'修改文档','apply_edits':True});assert result.status_code==200,result.text
    value=result.json();assert value['applied'] and value['reasoning'] and any(e['kind']=='memory_saved' for e in value['trace'])
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']=='已修改内容 $x^2$'
    nodes=client.get('/api/plugins/library').json()['nodes'];memory=next(n for n in nodes if n['parent_id']==mem['id'])
    assert '已保存' in client.get('/api/plugins/library/nodes/'+memory['id']).json()['markdown']
    with db.connect(True) as d:d.execute('UPDATE ai_threads SET messages=? WHERE id=?',(json.dumps([{'role':'assistant','content':json.dumps({'reply':'可读正文','edits':[]},ensure_ascii=False)}]),tid))
    assert client.get(url).json()['messages'][0]['content']=='可读正文'

def test_async_cancel_does_not_commit_staged_documents(client,monkeypatch,tmp_path):
    from server import secret_store
    monkeypatch.setattr(secret_store,'DATA',tmp_path);register(client);install(client,'library','constellation')
    root=create(client,'folder');doc=create(client,parent=root['id']);a=assistant(client,workspace_id=root['id']);tid=thread(client,a)
    entered=threading.Event();release=threading.Event()
    def model(*args,**kwargs):entered.set();release.wait(5);return json.dumps({'reply':'完成','edits':[{'document_id':doc['id'],'revision':1,'markdown':'不得保存'}]})
    monkeypatch.setattr(ai,'invoke',model)
    rid='async-cancel-save';url='/api/plugins/constellation/threads/'+tid
    assert client.post(url+'/chat/start',json={'request_id':rid,'content':'编辑文档','apply_edits':True}).status_code==202
    assert entered.wait(3)
    assert client.get(url).json()['active_turn']['request_id']==rid
    assert client.post('/api/plugins/constellation/turns/'+rid+'/cancel').status_code==200
    release.set()
    for _ in range(30):
        with db.connect() as d:status=d.execute('SELECT status FROM ai_turns WHERE request_id=?',(rid,)).fetchone()[0]
        if status=='cancelled':break
        time.sleep(.02)
    time.sleep(.08)
    assert client.get('/api/plugins/constellation/turns/'+rid).json()['status']=='cancelled'
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']==doc['markdown']

@pytest.mark.parametrize('protocol',['openai','responses','anthropic','gemini'])
def test_provider_thoughts_and_native_tool_roundtrip(protocol):
    from server.ai_protocol import invoke
    from server.ai_workspace import TOOLS
    fixtures={
        'openai':{'choices':[{'message':{'role':'assistant','content':None,'reasoning_content':'provider thought','tool_calls':[{'id':'call-1','type':'function','function':{'name':'read_document','arguments':'{"document_id":"doc"}'}}]}}]},
        'responses':{'output':[{'type':'reasoning','id':'r1','summary':[{'type':'summary_text','text':'provider thought'}]},{'type':'function_call','id':'f1','call_id':'call-1','name':'read_document','arguments':'{"document_id":"doc"}'}]},
        'anthropic':{'content':[{'type':'thinking','thinking':'provider thought','signature':'signed-thought'},{'type':'tool_use','id':'call-1','name':'read_document','input':{'document_id':'doc'}}]},
        'gemini':{'candidates':[{'content':{'parts':[{'text':'provider thought','thought':True},{'functionCall':{'id':'call-1','name':'read_document','args':{'document_id':'doc'}},'thoughtSignature':'signed-thought'}]}}]},
    }
    captured=[]
    def request(c,k,url,body,headers):captured.append(body);return fixtures[protocol]
    config={'model':'test','protocol':protocol,'api_base':'https://api.example.com/v1','max_tokens':8192,'show_reasoning':True}
    result=invoke(config,'test',[{'role':'user','content':'read'}],'system',request,tools=TOOLS)
    assert result.reasoning=='provider thought' and result.calls[0]['arguments']=={'document_id':'doc'}
    working=[{'role':'user','content':'read'},{'role':'assistant','content':str(result),'wire':result.wire},{'role':'tool','tool_call_id':'call-1','provider_id':'call-1','name':'read_document','content':'{"markdown":"read text"}'}]
    if protocol=='gemini':working.append(working[-1]|{'tool_call_id':'call-2','provider_id':'call-2'})
    hidden=invoke(config|{'show_reasoning':False},'test',working,'system',request,tools=TOOLS);assert not hidden.reasoning
    if protocol=='openai':assert captured[-1]['messages'][-2]['reasoning_content']=='provider thought'
    elif protocol=='responses':assert captured[-1]['input'][-1]['call_id']=='call-1'
    elif protocol=='anthropic':assert captured[-1]['messages'][-2]['content'][0]['signature']=='signed-thought'
    else:
        parts=captured[-1]['contents'][-1]['parts'];assert len(parts)==2 and parts[0]['functionResponse']['id']=='call-1'
        assert captured[-1]['contents'][-2]['parts'][-1]['thoughtSignature']=='signed-thought'

def test_ai_memory_quota_failure_rolls_back_document_and_events(client,monkeypatch,tmp_path):
    from server import secret_store,library_storage
    monkeypatch.setattr(secret_store,'DATA',tmp_path);uid=register(client);install(client,'library','constellation')
    root=create(client,'folder');memory=create(client,'folder');doc=create(client,parent=root['id'],text='original');a=assistant(client,workspace_id=root['id'],memory_id=memory['id']);tid=thread(client,a)
    with db.connect(True) as d:d.execute('UPDATE users SET library_quota_bytes=? WHERE id=?',(library_storage.usage(d,uid)['used_bytes']+5,uid))
    monkeypatch.setattr(ai,'invoke',lambda *args,**kwargs:json.dumps({'reply':'a long answer '*100,'edits':[{'document_id':doc['id'],'revision':1,'markdown':'new'}]}))
    result=client.post('/api/plugins/constellation/threads/'+tid+'/chat',json={'request_id':'quota-atomic-turn','content':'update','apply_edits':True});assert result.status_code==413,result.text
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']=='original'
    with db.connect() as d:
        assert not d.execute("SELECT 1 FROM library_nodes WHERE source_job_id LIKE 'ai-memory:%' AND user_id=?",(uid,)).fetchone()
        assert not d.execute("SELECT 1 FROM events WHERE user_id=? AND kind='assistant-chatted'",(uid,)).fetchone()

def test_unpublished_calendar_is_not_claimed_available():
    from server.holidays import valid
    assert not valid({'year':2027,'papers':[],'days':[]},2027)

def test_import_history_keeps_shared_images_and_last_document_releases_them(client,monkeypatch,tmp_path):
    import uuid
    from server.plugins import library
    uid=register(client);install(client,'library');monkeypatch.setattr(library,'IMPORTS',tmp_path/'imports')
    id=uuid.uuid4().hex;url='/api/plugins/library/imports/'+id+'/assets/image.png'
    source=create(client,text='![original]('+url+')');copy=create(client,text='![copy]('+url+')')
    work=library.job_path(uid,id);(work/'output').mkdir(parents=True);(work/'output/image.png').write_bytes(b'image');(work/'source.pdf').write_bytes(b'source')
    with db.connect(True) as d:
        d.execute('UPDATE library_nodes SET source_job_id=? WHERE id=?',(id,source['id']))
        d.execute("INSERT INTO import_jobs(id,user_id,parent_id,title,filename,mode,status,document_id,created_at,updated_at) VALUES(?,?,NULL,?,'source.pdf','auto','completed',?,?,?)",(id,uid,'OCR',source['id'],db.now(),db.now()))
    assert client.delete('/api/plugins/library/imports/'+id).status_code==200
    assert (work/'output/image.png').is_file() and not (work/'source.pdf').exists()
    assert client.delete('/api/plugins/library/nodes/'+source['id']).status_code==200
    assert (work/'output/image.png').is_file()
    assert client.delete('/api/plugins/library/nodes/'+copy['id']).status_code==200
    assert not work.exists()
