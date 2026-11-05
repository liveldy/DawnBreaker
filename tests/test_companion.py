import io,json,time,uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from PIL import Image
from fastapi import HTTPException
from tests.test_api import client,register,install
from server import db,secret_store,companion_state as state,companion_jobs as jobs,companion_media as media
from server.plugins import companion as plugin

ROOT='/api/plugins/companion'
class Queue:
    def __init__(self):self.calls=[]
    def submit(self,*args):self.calls.append(args)

@pytest.fixture
def setup(client,monkeypatch,tmp_path):
    monkeypatch.setattr(secret_store,'DATA',tmp_path)
    monkeypatch.setattr(media,'ROOT',tmp_path/'media')
    pool=Queue();monkeypatch.setattr(jobs,'CHAT_POOL',pool);monkeypatch.setattr(jobs,'MEDIA_POOL',pool)
    uid=register(client);install(client,'companion')
    return uid,pool

def config(provider='deepseek',**extra):
    return dict(provider=provider,protocol='openai',api_base='https://api.deepseek.com/v1' if provider=='deepseek' else 'https://api.x.ai/v1',api_key='test-private-key',chat_model='deepseek-flash' if provider=='deepseek' else 'grok-4.3',image_model='deepseek-flash' if provider=='deepseek' else 'grok-imagine-image',video_model='' if provider=='deepseek' else 'grok-imagine-video',voice_enabled=provider=='grok',voice_id='ara',proactive_enabled=True)|extra

def create(c,provider='deepseek',**extra):
    r=c.post(ROOT,json=config(provider,**extra));assert r.status_code==201,r.text;return r.json()['id']

def send(c,id,text='今天过得怎么样？',**extra):
    body={'request_id':uuid.uuid4().hex,'kind':'chat','text':text,'media_ids':[]}|extra
    r=c.post(ROOT+'/'+id+'/send',json=body);assert r.status_code==202,r.text
    return r.json(),body

def run(uid,turn):
    jobs.run(uid,turn['id'])
    with db.connect(True) as d:d.execute('UPDATE companion_messages SET visible_at=0')

def local(hour,day=5):return datetime(2026,11,day,hour,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()

def test_fixed_identities_keys_capability_and_account_isolation(client,setup):
    uid,pool=setup;a=create(client);b=create(client,'grok')
    assert client.post(ROOT,json=config()).status_code==409
    assert client.put(ROOT+'/'+a,json=config('grok')).status_code==409
    assert client.post(ROOT,json=config(video_model='no')).status_code==422
    data=client.get(ROOT).json();assert len(data['companions'])==2 and 'test-private-key' not in json.dumps(data)
    with db.connect() as d:assert d.execute('SELECT secret FROM companions WHERE id=?',(a,)).fetchone()[0]!='test-private-key'
    r=client.put(ROOT+'/'+a,json=config(api_key='',api_base='https://other.example/v1'));assert r.status_code==422
    client.post('/api/auth/logout');register(client,'other');install(client,'companion')
    assert client.get(ROOT+'/'+a+'/messages').status_code==404
    assert client.put(ROOT+'/'+b,json=config('grok')).status_code==404
    assert client.get(ROOT).json()['companions']==[]

def test_model_discovery_and_saved_key_destination_guard(client,setup,monkeypatch):
    id=create(client);calls=[]
    def remote(url,body=None,headers=None):
        calls.append((url,headers));return {'data':[{'id':'deepseek-flash','input_modalities':['text','image']},{'id':'deepseek-v4-pro'}]}
    monkeypatch.setattr(plugin,'request_json',remote)
    r=client.post(ROOT+'/models',json={'provider':'deepseek','api_base':'https://api.deepseek.com/v1','companion_id':id});assert r.status_code==200
    assert [m['vision'] for m in r.json()['models']]==[True,False]
    assert calls[0][1]['Authorization']=='Bearer test-private-key'
    assert client.post(ROOT+'/models',json={'provider':'deepseek','api_base':'https://other.example/v1','companion_id':id}).status_code==422
    assert len(calls)==1

def test_chat_idempotency_bubbles_personality_and_permanent_fact(client,setup,monkeypatch):
    uid,pool=setup;id=create(client);calls=[]
    def remote(url,body,headers):
        calls.append(body);return {'choices':[{'message':{'content':json.dumps({'bubbles':['才没有在等你。','芒果过敏这件事记下了 💙'],'emotion':{'energy_delta':.9},'memories':[{'text':'用户对芒果过敏','quote':'我对芒果过敏','importance':1},{'text':'不存在的用户信息','quote':'没有说过','importance':1}]},ensure_ascii=False)}}]}
    monkeypatch.setattr(jobs,'request_json',remote)
    turn,body=send(client,id,'记住，我对芒果过敏')
    assert client.post(ROOT+'/'+id+'/send',json=body).json()['id']==turn['id'] and len(pool.calls)==1
    assert client.post(ROOT+'/'+id+'/send',json=body|{'text':'changed'}).status_code==409
    assert client.put(ROOT+'/'+id,json=config()).status_code==409
    run(uid,turn);data=client.get(ROOT+'/'+id+'/messages').json()
    assert [m['text'] for m in data['messages']][1:]==['才没有在等你','芒果过敏这件事记下了 💙']
    assert data['latest_turn']['status']=='completed'
    system=calls[0]['messages'][0]['content'];assert '蓝色鲸鱼娘' in system and '本性稳定' in system and calls[0]['thinking']=={'type':'disabled'}
    memories=client.get(ROOT+'/'+id+'/memories').json()['memories'];assert any(m['kind']=='permanent' and m['text']=='用户对芒果过敏' for m in memories)
    assert not any(m['text']=='不存在的用户信息' for m in memories)
    assert any(m['text'].startswith('用户原话') for m in memories)
    assert client.post(ROOT+'/'+id+'/read').status_code==200
    assert client.get(ROOT).json()['companions'][0]['unread']==0
    m=next(m for m in memories if m['text']=='用户对芒果过敏')
    assert client.put(ROOT+'/'+id+'/memories/'+m['id'],json={'text':'用户对芒果过敏，避免推荐','kind':'permanent'}).status_code==200
    assert client.delete(ROOT+'/'+id+'/memories/'+m['id']).status_code==200
    assert client.delete(ROOT+'/'+id+'/history').status_code==200
    assert client.get(ROOT+'/'+id+'/messages').json()['messages']==[]
    assert client.get(ROOT+'/'+id+'/memories').json()['memories']

@pytest.mark.parametrize('protocol',['openai','responses'])
def test_private_vision_payload_and_attachment_limits(client,setup,monkeypatch,protocol):
    uid,_=setup;id=create(client,protocol=protocol);out=io.BytesIO();Image.new('RGB',(12,16),'red').save(out,'PNG')
    r=client.post(ROOT+'/'+id+'/upload?kind=image',files={'file':('evil-name.exe',out.getvalue(),'application/octet-stream')});assert r.status_code==200,r.text
    attachment=r.json();assert client.get(attachment['url']).headers['content-type']=='image/jpeg'
    assert client.post(ROOT+'/'+id+'/upload?kind=image',files={'file':('fake.png',b'not an image','image/png')}).status_code==422
    assert client.post(ROOT+'/'+id+'/upload?kind=audio',files={'file':('a.wav',b'x','audio/wav')}).status_code==422
    calls=[]
    def remote(url,body,headers):
        calls.append(body);content='{"bubbles":["看到红色啦"],"memories":[]}'
        return {'choices':[{'message':{'content':content}}]} if protocol=='openai' else {'output':[{'type':'message','content':[{'type':'output_text','text':content}]}]}
    monkeypatch.setattr(jobs,'request_json',remote)
    turn,_=send(client,id,'看到了什么？',media_ids=[attachment['id']]);run(uid,turn)
    payload=calls[0]['messages'][-1] if protocol=='openai' else calls[0]['input'][-1]
    assert payload['role']=='user' and payload['content'][1]['type']==('image_url' if protocol=='openai' else 'input_image')
    assert client.delete(attachment['url']).status_code==409
    client.post('/api/auth/logout');register(client,'other');install(client,'companion')
    assert client.get(attachment['url']).status_code==404

def test_memory_decay_provenance_permanence_and_recall(client,setup):
    uid,_=setup;id=create(client)
    with db.connect(True) as d:
        state.remember(d,uid,id,[{'text':'我叫小明','quote':'我叫小明','importance':1}],1,'记住我叫小明',local(12)-86400*500)
        state.episode(d,uid,id,'今天吃了苹果',2)
        d.execute("UPDATE companion_memories SET created=?,last_access=? WHERE kind='temporary'",(local(12)-86400*500,local(12)-86400*500))
        state.prune(d,uid,id,local(12));assert d.execute('SELECT COUNT(*) FROM companion_memories').fetchone()[0]==1
        recalled=state.recall(d,uid,id,'我的名字',local(12));assert len(recalled)==1 and recalled[0]['text']=='我叫小明' and recalled[0]['kind']=='permanent' and recalled[0]['recorded_at'].endswith('+08:00')
        assert state.memory_strength(d.execute('SELECT * FROM companion_memories').fetchone(),local(12)+1e9)==1
    value=state.emotion('deepseek',{'valence':-.8,'energy':.1,'closeness':.7,'at':0},local(12))
    assert value['closeness']==.7 and value['valence']>.17
    assert state.reply_probability('帮我一下',value)==1 and state.reply_probability('hi',value)<1
    assert state.reply_probability('hi',value|{'silent_streak':1})==1

def test_proactive_quiet_six_hours_probability_backoff_and_daily_cap(client,setup):
    uid,pool=setup;id=create(client);second=create(client,'grok')
    assert state.quiet(local(0)) and state.quiet(local(7)) and not state.quiet(local(8)) and not state.quiet(local(23))
    assert state.next_opportunity(local(21),local(21))==local(8,6)
    def ready(last,stamp,who=id):
        with db.connect(True) as d:d.execute('UPDATE companions SET last_user_at=?,next_chance=? WHERE id=?',(last,stamp,who))
    ready(local(1),local(7));jobs.scheduler_tick(local(7),lambda:0);assert not pool.calls
    ready(local(8),local(13));jobs.scheduler_tick(local(13),lambda:0);assert not pool.calls
    ready(local(6),local(12));jobs.scheduler_tick(local(12),lambda:1);assert not pool.calls
    jobs.scheduler_tick(local(12)+30,lambda:0);assert not pool.calls
    ready(local(6),local(12));jobs.scheduler_tick(local(12),lambda:0);assert len(pool.calls)==1
    with db.connect(True) as d:d.execute("UPDATE companion_turns SET status='completed'")
    ready(local(6),local(14));jobs.scheduler_tick(local(14),lambda:0);assert len(pool.calls)==2
    with db.connect(True) as d:d.execute("UPDATE companion_turns SET status='completed'")
    ready(local(6),local(16),second);jobs.scheduler_tick(local(16),lambda:0);assert len(pool.calls)==2
    ready(local(6),local(16));jobs.scheduler_tick(local(16),lambda:0);assert len(pool.calls)==2

def test_failed_request_retry_and_video_job_recovery_do_not_duplicate(client,setup,monkeypatch):
    uid,pool=setup;id=create(client,'grok');counter=[]
    def failed(*args,**kwargs):raise HTTPException(502,'upstream unavailable')
    monkeypatch.setattr(jobs,'request_json',failed);turn,_=send(client,id);run(uid,turn)
    assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='failed'
    assert client.post(ROOT+'/turns/'+turn['id']+'/retry').status_code==202
    with db.connect() as d:assert d.execute("SELECT COUNT(*) FROM companion_messages WHERE role='user'").fetchone()[0]==1
    with db.connect(True) as d:d.execute("UPDATE companion_turns SET status='failed'")
    video,_=send(client,id,'一片蓝色海面',kind='video')
    with db.connect(True) as d:d.execute("UPDATE companion_turns SET status='running',provider_job='existing-job' WHERE id=?",(video['id'],))
    jobs.recover();assert pool.calls[-1][2]==video['id']
    def remote(url,body=None,headers=None):
        counter.append(url);assert body is None;return {'status':'done','video':{'url':'https://vidgen.x.ai/output/test.mp4'}}
    monkeypatch.setattr(jobs,'request_json',remote);monkeypatch.setattr(jobs,'wire',lambda *a,**k:(b'video','video/mp4'))
    monkeypatch.setattr(media,'store',lambda *a,**k:'mock-token')
    run(uid,video);assert counter==['https://api.x.ai/v1/videos/existing-job']

def test_audio_fixed_service_and_generation_download_has_no_key(client,setup,monkeypatch):
    uid,_=setup;id=create(client,'grok');calls=[]
    monkeypatch.setattr(jobs,'post_json_bytes',lambda url,key,body:(calls.append((url,body)) or (b'audio','audio/mpeg')))
    monkeypatch.setattr(media,'store',lambda *a,**k:'media-token')
    turn,_=send(client,id,'你好',kind='voice');run(uid,turn)
    assert calls[0]==('https://api.x.ai/v1/tts',{'text':'你好','voice_id':'ara','language':'zh','with_timestamps':True})
    monkeypatch.setattr(jobs,'request_json',lambda *a,**k:{'data':[{'url':'https://imgen.x.ai/test.jpg'}]})
    downloads=[];monkeypatch.setattr(jobs,'wire',lambda *a,**kw:(downloads.append((a,kw)) or (b'image','image/jpeg')))
    turn,_=send(client,id,'蓝色海面',kind='image');run(uid,turn)
    assert 'headers' not in downloads[0][1]

def test_custom_name_avatar_private_storage_and_history_cleanup(client,setup):
    uid,_=setup;id=create(client)
    assert client.get(ROOT).json()['companions'][0]['name']=='DeepSeek'
    out=io.BytesIO();Image.new('RGB',(64,64),'blue').save(out,'PNG')
    r=client.post(ROOT+'/'+id+'/avatar',files={'file':('avatar.png',out.getvalue(),'image/png')});assert r.status_code==200,r.text
    avatar=r.json()['avatar'];token=r.json()['config']['avatar_id']
    assert client.get(avatar).status_code==200 and 'no-store' in client.get(avatar).headers['cache-control']
    r=client.put(ROOT+'/'+id,json=config(display_name='蓝鲸'))
    assert r.status_code==200 and r.json()['name']=='蓝鲸' and r.json()['config']['avatar_id']==token
    assert client.delete(ROOT+'/media/'+token).status_code==409
    assert client.delete(ROOT+'/'+id+'/history').status_code==200
    assert client.get(avatar).status_code==200
    assert client.post(ROOT+'/'+id+'/avatar',files={'file':('invalid.png',b'not-image','image/png')}).status_code==422
    client.post('/api/auth/logout');register(client,'other');install(client,'companion')
    assert client.get(avatar).status_code==404
    assert client.post(ROOT+'/'+id+'/avatar',files={'file':('avatar.png',out.getvalue(),'image/png')}).status_code==404
    client.post('/api/auth/logout');client.post('/api/auth/login',json={'username':'tester','password':'Test-password-2026'})
    r=client.delete(ROOT+'/'+id+'/avatar');assert r.status_code==200 and r.json()['avatar'].endswith('default1')
    with db.connect() as d:assert not d.execute('SELECT 1 FROM companion_media WHERE id=?',(token,)).fetchone()

def test_stt_omits_invalid_auto_language_and_keeps_file_last(monkeypatch):
    from server import companion_transport as transport
    calls=[]
    def capture(url,body,headers,limit):calls.append((url,body));return b'{"text":"hello"}','application/json'
    monkeypatch.setattr(transport,'wire',capture)
    assert transport.transcribe('https://api.x.ai/v1','key',b'WAV','grok-voice-transcribe-2.0')=='hello'
    raw=calls[0][1];assert b'name="language"' not in raw and raw.index(b'name="model"')<raw.index(b'name="file"')

def test_video_without_speech_still_understands_frames(client,setup,monkeypatch):
    uid,_=setup;id=create(client,'grok')
    monkeypatch.setattr(media,'metadata',lambda path:({'format':{'format_name':'mp4'},'streams':[{'codec_type':'video'},{'codec_type':'audio'}]},2))
    token=media.store(uid,id,'video',b'test-media-fixture')
    monkeypatch.setattr(media,'frames',lambda row:['data:image/jpeg;base64,AA==']*4)
    monkeypatch.setattr(media,'wav',lambda row:b'WAV')
    def silence(*args):raise HTTPException(422,'没有识别到语音，请重新录制')
    monkeypatch.setattr(jobs,'transcribe',silence)
    def remote(url,body,headers):
        assert len(body['messages'][-1]['content'])==5
        return {'choices':[{'message':{'content':'{"bubbles":["海面很安静"],"memories":[]}'}}]}
    monkeypatch.setattr(jobs,'request_json',remote)
    turn,_=send(client,id,'视频中有什么？',media_ids=[token]);run(uid,turn)
    data=client.get(ROOT+'/'+id+'/messages').json();assert data['latest_turn']['status']=='completed' and data['latest_turn']['result']['notices']
    assert data['messages'][-1]['text']=='海面很安静'
