import json,uuid
import pytest
from fastapi import HTTPException
from tests.test_api import client,register,install
from tests.test_v130 import create,assistant,thread
from server import db,secret_store
from server.plugins import constellation as ai
from server.ai_protocol import ModelReply
from server.ai_memory import prepare,COMPACT_TOKENS,notes

@pytest.fixture
def setup(client,monkeypatch,tmp_path):
    monkeypatch.setattr(secret_store,'DATA',tmp_path);uid=register(client);install(client,'constellation','library')
    folder=create(client,'folder');a=assistant(client,memory_id=folder['id']);return uid,folder,a,thread(client,a)

def say(client,tid,text='继续'):
    r=client.post('/api/plugins/constellation/threads/'+tid+'/chat',json={'request_id':uuid.uuid4().hex,'content':text});assert r.status_code==200,r.text;return r.json()

def test_smalltalk_is_not_copied_into_memory_and_rollups_are_batched(client,setup,monkeypatch):
    uid,folder,a,tid=setup;rollups=[];prompts=[]
    def model(config,key,messages,system,max_tokens=None,tools=None):
        if max_tokens==COMPACT_TOKENS:
            rollups.append(json.loads(messages[0]['content']));return json.dumps({'memory':'','summary':'等待新问题'})
        prompts.append(messages);return ModelReply('你好呀')
    monkeypatch.setattr(ai,'invoke',model)
    for i in range(14):say(client,tid,'寒暄-'+str(i))
    assert 1<=len(rollups)<=4 and max(map(len,prompts))<=9
    # The first rolled-up request is not replayed with the compact summary in later chat calls.
    assert not any('寒暄-0'==m['content'] for p in prompts[5:] for m in p)
    with db.connect() as d:
        t=d.execute('SELECT * FROM ai_threads WHERE id=?',(tid,)).fetchone();assert len(json.loads(t['messages']))==28 and t['context_cursor']>0
        assert not d.execute("SELECT 1 FROM library_nodes WHERE source_job_id=?",('ai-memory:'+a['id'],)).fetchone()

def test_important_memory_is_minimal_and_duplicate_remember_does_not_rewrite(client,setup,monkeypatch):
    uid,folder,a,tid=setup;normal=[]
    def model(config,key,messages,system,max_tokens=None,tools=None):
        if any(m.get('role')=='tool' for m in messages):return ModelReply('记住啦')
        normal.append(system);return ModelReply('',calls=[{'id':'memory-'+str(len(normal)),'name':'remember','arguments':{'markdown':'- 偏好简体中文\n- 偏好简体中文'}}],wire={'role':'assistant','content':None,'tool_calls':[]})
    monkeypatch.setattr(ai,'invoke',model);say(client,tid,'请记住以后使用简体中文');say(client,tid,'再确认一下')
    with db.connect() as d:
        rows=d.execute('SELECT * FROM library_nodes WHERE source_job_id=?',('ai-memory:'+a['id'],)).fetchall();assert len(rows)==1
        assert rows[0]['markdown']=='偏好简体中文' and rows[0]['revision']==1
    assert normal[-1].count('偏好简体中文')==1

def test_old_verbose_memory_is_semantically_compressed_once_without_duplicate_prompt(client,setup,monkeypatch):
    uid,folder,a,tid=setup;old='# 助手 · 长期记忆\n\n'+('## 2026-11-01T12:00:00\n用户：喜欢简体中文。\n助手：好的我会记住。\n'*200);calls=[]
    memory=ai.create_document
    with db.connect(True) as d:
        node=memory(d,uid,folder['id'],'旧记忆',old,'ai-memory:'+a['id'])
    def model(config,key,messages,system,max_tokens=None,tools=None):
        calls.append((max_tokens,system,messages))
        if max_tokens==COMPACT_TOKENS:return json.dumps({'memory':'偏好简体中文','summary':'整理数学笔记；保留公式 $x^2$'})
        assert system.count('偏好简体中文')==1 and len(system)<1500;return ModelReply('继续')
    monkeypatch.setattr(ai,'invoke',model);say(client,tid);say(client,tid)
    assert sum(c[0]==COMPACT_TOKENS for c in calls)==1
    with db.connect() as d:
        stored=d.execute('SELECT * FROM library_nodes WHERE id=?',(node['id'],)).fetchone();assert stored['markdown']=='偏好简体中文' and stored['revision']==2

def test_compaction_failure_retains_memory_and_cursor_and_still_answers(client,setup,monkeypatch):
    uid,folder,a,tid=setup;old='用户：重要事实\n助手：已经记住'
    with db.connect(True) as d:node=ai.create_document(d,uid,folder['id'],'旧记忆',old,'ai-memory:'+a['id'])
    def model(config,key,messages,system,max_tokens=None,tools=None):
        if max_tokens==COMPACT_TOKENS:raise HTTPException(502,'network')
        return ModelReply('正常回答')
    monkeypatch.setattr(ai,'invoke',model);result=say(client,tid);assert result['notice'] and result['reply']=='正常回答'
    with db.connect() as d:
        assert d.execute('SELECT markdown FROM library_nodes WHERE id=?',(node['id'],)).fetchone()[0]==old
        assert d.execute('SELECT context_cursor FROM ai_threads WHERE id=?',(tid,)).fetchone()[0]==0

def test_concurrent_manual_memory_edit_is_not_overwritten(client,setup,monkeypatch):
    uid,folder,a,tid=setup
    with db.connect(True) as d:node=ai.create_document(d,uid,folder['id'],'旧记忆','用户：旧事实','ai-memory:'+a['id'])
    def model(config,key,messages,system,max_tokens=None,tools=None):
        if max_tokens==COMPACT_TOKENS:
            with db.connect(True) as d:d.execute('UPDATE library_nodes SET markdown=?,revision=revision+1 WHERE id=?',('手动新增的重要偏好',node['id']))
            return json.dumps({'memory':'旧事实','summary':''})
        return ModelReply('好')
    monkeypatch.setattr(ai,'invoke',model);say(client,tid)
    with db.connect() as d:assert d.execute('SELECT markdown FROM library_nodes WHERE id=?',(node['id'],)).fetchone()[0]=='手动新增的重要偏好'

def test_no_library_still_has_compact_thread_context_and_secrets_are_redacted():
    history=[{'role':'user' if i%2==0 else 'assistant','content':'消息'+str(i)} for i in range(16)];captured=[]
    def model(*args):captured.append(json.loads(args[2][0]['content']));return json.dumps({'memory':'','summary':'下一步：校对公式'})
    result=prepare(history,0,'继续',8000,'','',False,{},'test-key-146',model)
    assert result['compacted'] and result['cursor']>0 and not result['memory'] and result['summary_prompt']=='下一步：校对公式'
    assert notes('## 用户喜欢数学\nAPI key: test-key-146\n数学\n数学','test-key-146').count('数学')==2
    assert 'test-key-146' not in notes('API key: test-key-146','test-key-146')
