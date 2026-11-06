import json,time,uuid
import pytest
from fastapi import HTTPException
from tests.test_api import client,register,install
from tests.test_companion import setup,create,send,run,ROOT
from tests.test_companion_tools import native_call,final
from server import db,companion_jobs as jobs,companion_search as web,companion_agent as agent

@pytest.mark.parametrize('prefix',['先到了\n坐过来\n','```json\n','以下是回复：\n'])
def test_prose_and_envelope_render_only_bubbles(prefix):
    structured={'bubbles':['先到了','坐过来'],'emotion':{'valence_delta':.03},'memories':[{'text':'内部摘要','quote':'然后呢','importance':.55}]}
    bubbles,value=jobs.parse_reply(prefix+json.dumps(structured,ensure_ascii=False))
    assert bubbles==structured['bubbles'] and value['emotion']==structured['emotion'] and value['memories']==structured['memories']

def test_malformed_internal_envelope_is_never_a_plaintext_fallback():
    for text in ['前文\n{"bubbles":["你好"],"emotion":','{"bubbles":["再来\n{\\"memories\\":42}"]}']:
        with pytest.raises(jobs.ReplyFormatError):jobs.parse_reply(text)

def test_old_envelopes_are_sanitized_in_chat_preview_search_and_model_context(client,setup,monkeypatch):
    uid,_=setup;id=create(client);leak='先到了\n坐过来\n'+json.dumps({'bubbles':['先到了','坐过来'],'emotion':{'valence_delta':.03},'memories':[{'text':'内部隐藏摘要'}]},ensure_ascii=False)
    with db.connect(True) as d:d.execute('INSERT INTO companion_messages(user_id,companion_id,turn_id,role,text,created_at,visible_at) VALUES(?,?,?,?,?,?,0)',(uid,id,'old-turn','assistant',leak,db.now()))
    assert client.get(ROOT+'/'+id+'/messages').json()['messages'][0]['text']=='先到了\n坐过来'
    assert 'memories' not in client.get(ROOT).json()['companions'][0]['last_message']['text']
    assert client.get(ROOT+'/'+id+'/messages/search?q=内部隐藏摘要').json()['messages']==[]
    calls=[]
    def model(url,body,headers):calls.append(body);return final('openai',['继续'])
    monkeypatch.setattr(jobs,'request_json',model);turn,_=send(client,id,'然后呢？');run(uid,turn)
    history=[m['content'] for m in calls[0]['messages'] if m['role']=='assistant'];assert history==['先到了\n坐过来']

def test_quotes_are_owned_snapshots_distinct_from_user_facts_and_survive_delete(client,setup,monkeypatch):
    uid,_=setup;id=create(client);calls=[]
    def model(url,body,headers):calls.append(body);return final('openai',['用户生日是五月五日'])
    monkeypatch.setattr(jobs,'request_json',model);turn,_=send(client,id);run(uid,turn)
    source=client.get(ROOT+'/'+id+'/messages').json()['messages'][-1];turn,body=send(client,id,'这条是什么意思？',reply_to_id=source['id']);run(uid,turn)
    current=next(m for m in client.get(ROOT+'/'+id+'/messages').json()['messages'] if m['role']=='user' and m['turn_id']==turn['id'])
    assert current['quote']['text']=='用户生日是五月五日' and current['quote']['id']==source['id']
    input=calls[-1]['messages'][-1]['content'];assert '[本次用户消息]' in input and '不是本轮用户原话' in input and '这条是什么意思' in input
    with db.connect() as d:
        assert d.execute('SELECT text FROM companion_messages WHERE id=?',(current['id'],)).fetchone()[0]=='这条是什么意思？'
        assert not d.execute("SELECT 1 FROM companion_memories WHERE user_id=? AND kind='permanent' AND text LIKE '%生日%'",(uid,)).fetchone()
    assert client.delete(ROOT+'/'+id+'/messages/'+str(source['id'])).status_code==200
    restored=next(m for m in client.get(ROOT+'/'+id+'/messages').json()['messages'] if m['id']==current['id']);assert restored['quote']==current['quote']
    other=create(client,'grok');assert client.post(ROOT+'/'+other+'/send',json={'request_id':uuid.uuid4().hex,'text':'引用','reply_to_id':source['id']}).status_code==404
    client.post('/api/auth/logout');register(client,'quote_other');install(client,'companion');their=create(client)
    assert client.post(ROOT+'/'+their+'/send',json={'request_id':uuid.uuid4().hex,'text':'引用','reply_to_id':source['id']}).status_code==404

def test_quote_keeps_legacy_send_fingerprint_for_pending_142_messages(client,setup):
    uid,_=setup;id=create(client);turn,body=send(client,id);assert client.post(ROOT+'/'+id+'/send',json=body|{'reply_to_id':None}).json()['id']==turn['id']

def test_transient_fetch_retry_cache_plaintext_and_429_cooldown(monkeypatch):
    web.clear_cache();calls=[];monkeypatch.setattr(web.time,'sleep',lambda _:None)
    def temporary(url):
        calls.append(url)
        if len(calls)==1:raise OSError('temporary transport')
        return b'API supports image input formats JPEG and PNG.','https://example.org/docs','text/plain'
    monkeypatch.setattr(web,'_fetch_once',temporary)
    assert web.read_page('https://example.org/docs','image formats')['relevant']
    assert web.read_page('https://example.org/docs','JPEG')['content'] and len(calls)==2
    web.clear_cache();calls.clear()
    def limited(url):calls.append(url);raise web.PageUnavailable(429,120)
    monkeypatch.setattr(web,'_fetch_once',limited)
    for url in ['https://example.org/one','https://example.org/two']:
        with pytest.raises(web.PageUnavailable):web.fetch(url)
    assert len(calls)==1
    web.clear_cache()

@pytest.mark.parametrize('recover',[False,True])
def test_web_failures_use_explicit_snippets_or_alternative_without_duplicate_errors(client,setup,monkeypatch,recover):
    uid,_=setup;id=create(client,'grok')
    def model(url,body,headers):
        results=[m for m in body['messages'] if m.get('role')=='tool']
        if not results:return native_call('openai','search_web',{'query':'test API'})
        if len(results)<3:return native_call('openai','read_webpage',{'url':'https://example.org/blocked','query':'API'},'read-'+str(len(results)))
        if recover and len(results)==3:return native_call('openai','read_webpage',{'url':'https://example.org/works','query':'API'},'other')
        return final('openai',['我看到了可取得的资料'])
    monkeypatch.setattr(jobs,'request_json',model)
    monkeypatch.setattr(agent,'search',lambda q:{'results':[{'url':'https://example.org/blocked','title':'API','snippet':'这是实际搜索摘要'}]})
    def read(url,q):
        if url.endswith('blocked'):raise HTTPException(502,'网页返回 HTTP 429')
        return {'url':url,'title':'可读来源','content':'API 文档正文','relevant':True}
    monkeypatch.setattr(agent,'read_page',read);turn,_=send(client,id,'请搜索 API？');run(uid,turn);result=client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['result']
    assert result['tool_errors']==[]
    assert len(result['notices'])==(0 if recover else 1)
    if not recover:assert '摘要' in result['notices'][0]
