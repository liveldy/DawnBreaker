import json,uuid
import pytest
from tests.test_api import client,register,install
from tests.test_v130 import create as make_node,assistant as make_assistant,thread as make_thread
from server import db,secret_store
from server.plugins import constellation as ai
from server.ai_protocol import ModelReply,function

@pytest.fixture
def workspace(client,monkeypatch,tmp_path):
    monkeypatch.setattr(secret_store,'DATA',tmp_path);uid=register(client);install(client,'library','constellation')
    root=make_node(client,'folder',title='工作空间');doc=make_node(client,parent=root['id'],title='笔记',text='唯一原文与 $x=1$');discard=make_node(client,parent=root['id'],title='待删文档',text='旧草稿');outside=make_node(client,title='空间外',text='不能访问')
    a=make_assistant(client,workspace_id=root['id']);thread=make_thread(client,a)
    return uid,root,doc,discard,outside,thread

def tools(*calls):return ModelReply(calls=[function(name,args) for name,args in calls])
def results(messages):return [json.loads(m['content']) for m in messages if m['role']=='tool']

@pytest.mark.parametrize('automatic',[False,True])
def test_nested_folders_document_crud_search_move_and_review_commit(client,workspace,monkeypatch,automatic):
    uid,root,doc,discard,outside,thread=workspace;round=[0]
    def model(config,key,messages,system,**kw):
        i=round[0];round[0]+=1;data=results(messages)
        if i==0:
            assert root['id'] in system and 'create_folder' in [t['name'] for t in kw['tools']]
            return tools(('create_folder',{'title':'数学','parent_id':root['id']}))
        if i==1:return tools(('create_folder',{'title':'代数','parent_id':data[0]['temporary_id']}))
        if i==2:
            parent=data[1]['temporary_id'];return tools(('create_document',{'title':'二次方程','parent_id':parent,'markdown':r'$$x^2+1=0$$'}),('rename_document',{'document_id':doc['id'],'revision':1,'title':'综述'}),('move_document',{'document_id':doc['id'],'revision':1,'parent_id':parent}),('replace_text',{'document_id':doc['id'],'revision':1,'old':'唯一原文','new':'更新后的唯一原文'}),('delete_document',{'document_id':discard['id'],'revision':1}))
        if i==3:return tools(('list_nodes',{}),('search_documents',{'query':'二次方程'}))
        assert data[-1]['results'][0]['title']=='二次方程' and any(n['kind']=='folder' and n['title']=='代数' for n in data[-2]['nodes'])
        assert not any(n['id']==discard['id'] for n in data[-2]['nodes'])
        return ModelReply('文件与目录操作已准备完成')
    monkeypatch.setattr(ai,'invoke',model);url='/api/plugins/constellation/threads/'+thread
    response=client.post(url+'/chat',json={'request_id':uuid.uuid4().hex,'content':'创建数学/代数目录，创建二次方程文档；修改、重命名和移动笔记，删除旧草稿并搜索结果','apply_edits':automatic});assert response.status_code==200,response.text
    result=response.json();assert len(result['edits'])==5 and result['applied']==automatic
    if not automatic:
        listing=client.get('/api/plugins/library').json()['nodes'];assert not any(n['title']=='数学' for n in listing)
        assert client.get('/api/plugins/library/nodes/'+discard['id']).status_code==200
        assert client.post(url+'/apply',json={'request_id':result['request_id']}).status_code==200
        assert client.post(url+'/apply',json={'request_id':result['request_id']}).status_code==200
    nodes=client.get('/api/plugins/library').json()['nodes'];math=next(n for n in nodes if n['title']=='数学');algebra=next(n for n in nodes if n['title']=='代数');new=next(n for n in nodes if n['title']=='二次方程');changed=client.get('/api/plugins/library/nodes/'+doc['id']).json()
    assert algebra['parent_id']==math['id'] and new['parent_id']==algebra['id'] and changed['parent_id']==algebra['id']
    assert changed['title']=='综述' and changed['revision']==2 and changed['markdown']=='更新后的唯一原文与 $x=1$'
    assert client.get('/api/plugins/library/nodes/'+new['id']).json()['markdown']==r'$$x^2+1=0$$'
    assert client.get('/api/plugins/library/nodes/'+discard['id']).status_code==404
    assert client.get('/api/plugins/library/nodes/'+outside['id']).json()['markdown']=='不能访问'

def test_review_conflict_rolls_back_all_folder_create_and_delete_operations(client,workspace,monkeypatch):
    uid,root,doc,discard,outside,thread=workspace
    def model(config,key,messages,system,**kw):
        if not results(messages):return tools(('create_folder',{'title':'不能部分创建'}),('append_document',{'document_id':doc['id'],'revision':1,'markdown':'追加'}),('delete_document',{'document_id':discard['id'],'revision':1}))
        return ModelReply('请审阅')
    monkeypatch.setattr(ai,'invoke',model);url='/api/plugins/constellation/threads/'+thread
    result=client.post(url+'/chat',json={'request_id':uuid.uuid4().hex,'content':'调整文档','apply_edits':False}).json()
    assert client.put('/api/plugins/library/nodes/'+doc['id'],json={'revision':1,'title':doc['title'],'markdown':'用户的新版本','parent_id':root['id']}).status_code==200
    assert client.post(url+'/apply',json={'request_id':result['request_id']}).status_code==409
    assert not any(n['title']=='不能部分创建' for n in client.get('/api/plugins/library').json()['nodes'])
    assert client.get('/api/plugins/library/nodes/'+discard['id']).status_code==200
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']=='用户的新版本'

def test_tools_do_not_access_outside_workspace_or_delete_directories(client,workspace,monkeypatch):
    uid,root,doc,discard,outside,thread=workspace
    def model(config,key,messages,system,**kw):
        data=results(messages)
        if not data:return tools(('read_document',{'document_id':outside['id']}),('delete_document',{'document_id':outside['id'],'revision':1}),('create_folder',{'title':'越权目录','parent_id':outside['id']}),('delete_document',{'document_id':root['id'],'revision':1}))
        assert len(data)==4 and all('error' in d for d in data);return ModelReply('这些操作不在工作空间权限内')
    monkeypatch.setattr(ai,'invoke',model);result=client.post('/api/plugins/constellation/threads/'+thread+'/chat',json={'request_id':uuid.uuid4().hex,'content':'验证范围','apply_edits':True});assert result.status_code==200
    assert result.json()['edits']==[] and client.get('/api/plugins/library/nodes/'+outside['id']).status_code==200

def test_quota_failure_is_atomic_for_new_folders_and_documents(client,workspace,monkeypatch):
    uid,root,doc,discard,outside,thread=workspace
    with db.connect(True) as d:d.execute('UPDATE users SET library_quota_bytes=256 WHERE id=?',(uid,))
    def model(config,key,messages,system,**kw):
        data=results(messages)
        if not data:return tools(('create_folder',{'title':'不能留下空目录'}))
        if len(data)==1:return tools(('create_document',{'title':'过大文档','parent_id':data[0]['temporary_id'],'markdown':'x'*1000}))
        return ModelReply('准备好了')
    monkeypatch.setattr(ai,'invoke',model);result=client.post('/api/plugins/constellation/threads/'+thread+'/chat',json={'request_id':uuid.uuid4().hex,'content':'创建目录与文档','apply_edits':True});assert result.status_code==413,result.text
    assert not any(n['title']=='不能留下空目录' for n in client.get('/api/plugins/library').json()['nodes'])

def test_reading_all_chunks_allows_complete_document_update(client,workspace,monkeypatch):
    uid,root,doc,discard,outside,thread=workspace;text='a'*50000
    with db.connect(True) as d:d.execute('UPDATE library_nodes SET markdown=? WHERE id=?',(text,doc['id']))
    def model(config,key,messages,system,**kw):
        data=results(messages)
        if not data:return tools(('read_document',{'document_id':doc['id'],'offset':0,'limit':30000}))
        if len(data)==1:return tools(('read_document',{'document_id':doc['id'],'offset':30000,'limit':30000}))
        if len(data)==2:return tools(('write_document',{'document_id':doc['id'],'revision':1,'markdown':text+'\n$z=2$'}))
        assert 'error' not in data[-1];return ModelReply('已经准备完整文档')
    monkeypatch.setattr(ai,'invoke',model);result=client.post('/api/plugins/constellation/threads/'+thread+'/chat',json={'request_id':uuid.uuid4().hex,'content':'完整读取后添加公式','apply_edits':True});assert result.status_code==200,result.text
    assert client.get('/api/plugins/library/nodes/'+doc['id']).json()['markdown']==text+'\n$z=2$'
