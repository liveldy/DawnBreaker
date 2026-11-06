import hashlib,json
import pytest
from PIL import Image
from fastapi import HTTPException
from tests.test_api import client,register,install
from tests.test_companion import setup,create,send,run,ROOT
from tests.test_companion_tools import native_call,final
from server import db,companion_jobs as jobs,companion_agent as agent,companion_stickers as stickers,companion_config as presets

@pytest.fixture
def art(tmp_path,monkeypatch):
    root=tmp_path/'stickers';monkeypatch.setattr(stickers,'ROOT',root)
    for provider,color in [('deepseek','blue'),('grok','red')]:
        (root/provider).mkdir(parents=True)
        for i in range(1,10):Image.new('RGBA',(24,24),color).save(root/provider/(f'{i:02}.png'))
    return root

@pytest.mark.parametrize('provider,protocol',[('deepseek','openai'),('grok','responses')])
def test_model_chooses_own_sticker_without_user_request_or_image_generation(client,setup,art,monkeypatch,provider,protocol):
    uid,_=setup;id=create(client,provider,protocol=protocol,image_model='',video_model='',voice_enabled=False);calls=[]
    def model(url,body,headers):
        calls.append(body);messages=body.get('input') or body['messages']
        if not any(m.get('role')=='tool' or m.get('type')=='function_call_output' for m in messages):return native_call(protocol,'send_sticker',{'sticker_id':'09'})
        return final(protocol,[])
    monkeypatch.setattr(jobs,'request_json',model)
    monkeypatch.setattr(jobs,'generated',lambda *a:(_ for _ in ()).throw(AssertionError('Stickers must not call image generation')))
    turn,body=send(client,id,'我考试通过啦！');run(uid,turn);data=client.get(ROOT+'/'+id+'/messages').json();assert data['latest_turn']['status']=='completed'
    sent=[m for m in data['messages'] if m.get('sticker')];assert len(sent)==1 and sent[0]['sticker']['id']=='09'
    expected=stickers.PACKS[provider][8][0];assert sent[0]['sticker']['name']==expected and sent[0]['text']=='[表情包：'+expected+']'
    image=client.get(sent[0]['sticker']['url']);assert image.status_code==200 and image.headers['content-type']=='image/png'
    assert hashlib.sha256(image.content).digest()==hashlib.sha256((art/provider/'09.png').read_bytes()).digest()
    assert image.headers['cache-control']=='private, max-age=86400'  # Explicit per-account asset policy survives middleware.
    advertised=next(t for t in calls[0]['tools'] if (t.get('name') or t.get('function',{}).get('name'))=='send_sticker');parameters=advertised.get('parameters') or advertised['function']['parameters']
    assert parameters['properties']['sticker_id']['enum']==[f'{i:02}' for i in range(1,10)]
    assert '不必等用户要求' in str(calls[0])
    assert client.post(ROOT+'/'+id+'/send',json=body).json()['id']==turn['id']
    with db.connect() as d:assert d.execute('SELECT COUNT(*) FROM companion_media WHERE user_id=?',(uid,)).fetchone()[0]==0
    client.post('/api/auth/logout');register(client,'other_sticker');install(client,'companion')
    assert client.get(sent[0]['sticker']['url']).status_code==404

def test_repeated_sticker_calls_and_retry_publish_once_and_quote_retains_meaning(client,setup,art,monkeypatch):
    uid,_=setup;id=create(client);calls=[]
    def model(url,body,headers):
        calls.append(body);results=[m for m in body['messages'] if m.get('role')=='tool']
        if not results:return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'one','type':'function','function':{'name':'send_sticker','arguments':'{"sticker_id":"09"}'}},{'id':'two','type':'function','function':{'name':'send_sticker','arguments':'{"sticker_id":"01"}'}}]}}]}
        return final('openai',['太好了'])
    monkeypatch.setattr(jobs,'request_json',model);original=jobs.parse_reply
    monkeypatch.setattr(jobs,'parse_reply',lambda *a,**kw:(_ for _ in ()).throw(HTTPException(502,'模拟投递前中断')))
    turn,_=send(client,id,'好开心？');run(uid,turn);assert not any(m.get('sticker') for m in client.get(ROOT+'/'+id+'/messages').json()['messages'])
    monkeypatch.setattr(jobs,'parse_reply',original);client.post(ROOT+'/turns/'+turn['id']+'/retry');run(uid,turn)
    data=client.get(ROOT+'/'+id+'/messages').json();sent=[m for m in data['messages'] if m.get('sticker')];assert len(sent)==1 and sent[0]['sticker']['id']=='09'
    with db.connect() as d:assert d.execute("SELECT COUNT(*) FROM companion_actions WHERE name='send_sticker'").fetchone()[0]==1
    quoted,_=send(client,id,'你刚刚这个表情是什么意思？',reply_to_id=sent[0]['id']);run(uid,quoted)
    message=next(m for m in client.get(ROOT+'/'+id+'/messages').json()['messages'] if m['role']=='user' and m['turn_id']==quoted['id'])
    assert message['quote']['media_kinds']==['sticker'] and '开心完成' in message['quote']['text']
    assert client.delete(ROOT+'/'+id+'/messages/'+str(sent[0]['id'])).status_code==200
    assert next(m for m in client.get(ROOT+'/'+id+'/messages').json()['messages'] if m['id']==message['id'])['quote']['text']==message['quote']['text']

def test_stickers_optional_disabled_invalid_ids_and_legacy_admin_preferences(client,setup,art):
    uid,_=setup;id=create(client)
    with db.connect() as d:row=dict(d.execute('SELECT * FROM companions WHERE id=?',(id,)).fetchone())
    assert any(t['name']=='send_sticker' for t in agent.definitions(row))
    for invalid in ['00','10','grok/01','../01']:
        with pytest.raises(HTTPException):stickers.path('deepseek',invalid)
    legacy=presets.defaults();legacy['system_prompt']='保留管理员自己的系统提示词';legacy['providers']['deepseek']['name']='自定义名称';legacy['tool_descriptions'].pop('send_sticker')
    for p in legacy['providers'].values():p['tools'].pop('sticker_enabled')
    stored={'revision':'legacy-admin','config':legacy,'updated_at':None}
    with db.connect(True) as d:d.execute('INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)',(presets.KEY,json.dumps(stored,ensure_ascii=False),db.now()))
    presets.invalidate();upgraded=presets.snapshot();assert upgraded['revision']=='legacy-admin' and upgraded['config']['system_prompt']==legacy['system_prompt'] and upgraded['config']['providers']['deepseek']['name']=='自定义名称'
    assert upgraded['config']['providers']['deepseek']['tools']['sticker_enabled']
    upgraded['config']['providers']['deepseek']['tools']['sticker_enabled']=False
    with db.connect(True) as d:d.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(upgraded),presets.KEY))
    presets.invalidate();assert not any(t['name']=='send_sticker' for t in agent.definitions(row))

def test_source_only_install_does_not_advertise_missing_art(client,setup,monkeypatch,tmp_path):
    uid,_=setup;id=create(client);monkeypatch.setattr(stickers,'ROOT',tmp_path/'not-installed')
    with db.connect() as d:row=dict(d.execute('SELECT * FROM companions WHERE id=?',(id,)).fetchone())
    assert stickers.catalog('deepseek')==[] and not any(t['name']=='send_sticker' for t in agent.definitions(row))
    assert client.get(ROOT+'/'+id+'/stickers/01').status_code==404
