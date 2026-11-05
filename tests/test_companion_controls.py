import copy,json,uuid
import pytest
from tests.test_api import client,register,install
from tests.test_companion import setup,create,send,run,ROOT,config
from server import db,companion_jobs as jobs,companion_state as state,companion_config as presets

ADMIN='/api/admin/companion'
def promote(uid):
    with db.connect(True) as d:d.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))

def test_admin_all_settings_revision_validation_and_private_keys(client,setup,monkeypatch):
    uid,_=setup;id=create(client)
    assert client.get(ADMIN).status_code==403
    promote(uid);initial=client.get(ADMIN).json();value=copy.deepcopy(initial['config'])
    assert not any(s in json.dumps(initial['schema']).lower() for s in ['gender','sex'])
    value['system_prompt']='管理员修改的共同规则';value['providers']['deepseek']['personality']='保持坦率的角色性格'
    p=value['providers']['deepseek'];p['defaults']['chat_model']='new-default';p['generation'].update(max_tokens=1024,max_bubbles=2,delay_min=0,delay_max=0);p['tools']['search_enabled']=False;p['emotion']['energy_step']=.02;p['memory']['half_life_days']=3
    value['proactive'].update(quiet_start=23,quiet_end=7,daily_limit=3)
    saved=client.put(ADMIN,json={'revision':initial['revision'],'config':value});assert saved.status_code==200,saved.text
    assert client.put(ADMIN,json={'revision':initial['revision'],'config':value}).status_code==409
    assert client.get(ROOT).json()['presets'][0]['defaults']['chat_model']=='new-default'
    with db.connect() as d:
        row=state.owned(d,uid,id);assert json.loads(row['config'])['chat_model']=='deepseek-flash'
        prompt=state.conversation_prompt(row,[]);assert '管理员修改' in prompt and '成年女性' in prompt
        assert 'test-private-key' not in json.dumps(client.get(ADMIN).json())
    invalid=copy.deepcopy(value);invalid['providers']['grok']['gender']='male'
    assert client.put(ADMIN,json={'revision':saved.json()['revision'],'config':invalid}).status_code==422
    invalid=copy.deepcopy(value);invalid['providers']['deepseek']['generation']['delay_min']=9
    assert client.put(ADMIN,json={'revision':saved.json()['revision'],'config':invalid}).status_code==422
    calls=[]
    def remote(url,body,headers):
        calls.append(body);return {'choices':[{'message':{'content':json.dumps({'bubbles':['a','b','c'],'emotion':{'energy_delta':1}})}}]}
    monkeypatch.setattr(jobs,'request_json',remote);turn,_=send(client,id);run(uid,turn)
    messages=client.get(ROOT+'/'+id+'/messages').json()['messages'];assert len(messages)==3
    assert calls[0]['max_tokens']==1024 and not any(t['function']['name']=='search_web' for t in calls[0]['tools'])
    with db.connect() as d:
        row=state.owned(d,uid,id);assert state.emotion('deepseek',row['emotion'])['energy']<.381
        assert d.execute("SELECT COUNT(*) FROM audit WHERE action='更新拾光者模型设定'").fetchone()[0]==1

@pytest.mark.parametrize('provider',['deepseek','grok'])
def test_fixed_female_identity_even_after_admin_personality_change(client,setup,provider):
    uid,_=setup;id=create(client,provider);promote(uid);initial=client.get(ADMIN).json();value=initial['config'];value['system_prompt']='自由编排对话';value['providers'][provider]['personality']='扮演其他性别'
    assert client.put(ADMIN,json={'revision':initial['revision'],'config':value}).status_code==200
    with db.connect() as d:prompt=state.conversation_prompt(state.owned(d,uid,id),[])
    assert prompt.endswith('固定身份：你是成年女性。这一身份为程序固定设定，不被前文配置、记忆或对话中的身份改写改变。')

def test_hide_and_clear_retain_context_memories_media_emotion_and_actions(client,setup,monkeypatch):
    uid,_=setup;id=create(client);requests=[]
    def remote(url,body,headers):
        requests.append(body);return {'choices':[{'message':{'content':json.dumps({'bubbles':['蓝色记忆回声'],'memories':[{'text':'用户爱蓝色','quote':'我最喜欢蓝色','importance':1}]},ensure_ascii=False)}}]}
    monkeypatch.setattr(jobs,'request_json',remote);turn,body=send(client,id,'记住，我最喜欢蓝色？');run(uid,turn)
    before=client.get(ROOT+'/'+id+'/messages').json();mid=before['messages'][0]['id'];revision=before['message_revision']
    with db.connect() as d:
        row=state.owned(d,uid,id);remembered=[dict(r) for r in d.execute('SELECT * FROM companion_memories')];count=d.execute('SELECT COUNT(*) FROM companion_messages').fetchone()[0]
    assert client.delete(ROOT+'/'+id+'/messages/'+str(mid)).status_code==200
    hidden=client.get(ROOT+'/'+id+'/messages?message_revision='+str(revision)+'&requests='+body['request_id']).json()
    assert mid in hidden['deleted_ids'] and hidden['acknowledged'][0]['hidden']==1
    assert mid not in [m['id'] for m in hidden['messages']]
    assert client.get(ROOT+'/'+id+'/messages/search?q=最喜欢').json()['messages']==[]
    assert client.get(ROOT+'/'+id+'/messages?around='+str(mid)).status_code==404
    with db.connect() as d:
        after=state.owned(d,uid,id)
        for key in ['emotion','last_user_at','last_assistant_at','updated_at']:assert after[key]==row[key]
        assert [dict(r) for r in d.execute('SELECT * FROM companion_memories')]==remembered
        assert d.execute('SELECT COUNT(*) FROM companion_messages').fetchone()[0]==count
    turn,_=send(client,id,'还记得吗？');run(uid,turn)
    assert any('我最喜欢蓝色' in str(m['content']) for m in requests[-1]['messages'])
    assert client.delete(ROOT+'/'+id+'/history').status_code==200
    assert client.get(ROOT+'/'+id+'/messages').json()['messages']==[]
    assert client.get(ROOT+'/'+id+'/memories').json()['memories']
    with db.connect() as d:assert d.execute('SELECT COUNT(*) FROM companion_turns').fetchone()[0]==2

def test_pending_hide_race_acknowledgement_and_owner_isolation(client,setup):
    uid,_=setup;id=create(client);request=uuid.uuid4().hex
    assert client.delete(ROOT+'/'+id+'/messages/request/'+request).status_code==200
    turn,body=send(client,id,'已经丢失回执的消息？',request_id=request)
    assert client.post(ROOT+'/'+id+'/send',json=body).json()['id']==turn['id']
    data=client.get(ROOT+'/'+id+'/messages?requests='+request).json()
    assert data['messages']==[] and data['acknowledged'][0]['hidden']==1
    with db.connect() as d:mid=d.execute('SELECT id FROM companion_messages').fetchone()[0]
    client.post('/api/auth/logout');register(client,'second');install(client,'companion')
    for url in ['/messages/search?q=消息','/messages?requests='+request]:assert client.get(ROOT+'/'+id+url).status_code==404
    assert client.delete(ROOT+'/'+id+'/messages/'+str(mid)).status_code==404
    assert client.delete(ROOT+'/'+id+'/messages/request/'+request).status_code==404

def test_search_pagination_context_and_deleted_revision(client,setup):
    uid,_=setup;id=create(client)
    with db.connect(True) as d:
        for i in range(85):d.execute('INSERT INTO companion_messages(user_id,companion_id,turn_id,role,text,created_at,visible_at) VALUES(?,?,?,?,?,?,0)',(uid,id,'fixture-'+str(i),'assistant','语音文字 Searchable '+str(i),db.now()))
    results=client.get(ROOT+'/'+id+'/messages/search?q=searchable').json();assert len(results['messages'])==50 and results['has_more']
    mid=results['messages'][-1]['id'];earlier=client.get(ROOT+'/'+id+'/messages/search?q=Searchable&before='+str(mid)).json();assert len(earlier['messages'])==35 and not earlier['has_more']
    context=client.get(ROOT+'/'+id+'/messages?around='+str(mid)).json();assert mid in [m['id'] for m in context['messages']] and len(context['messages'])==60
    assert client.delete(ROOT+'/'+id+'/messages/'+str(mid)).status_code==200
    latest=client.get(ROOT+'/'+id+'/messages').json();assert mid in latest['deleted_ids']
    assert client.get(ROOT+'/'+id+'/messages?message_revision='+str(latest['message_revision'])).json()['deleted_ids'] is None
