import base64,io,json,uuid
import pytest
from PIL import Image
from fastapi import HTTPException
from tests.test_api import client
from tests.test_companion import setup,create,send,run,config,ROOT
from server import db,companion_jobs as jobs,companion_agent as agent,companion_search as search

def native_call(protocol,name,args,id='call-1'):
    if protocol=='responses':return {'output':[{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':id}]}
    return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}]}

def final(protocol,bubbles=None):
    text=json.dumps({'bubbles':bubbles or [],'memories':[]})
    return {'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]} if protocol=='responses' else {'choices':[{'message':{'role':'assistant','content':text}}]}

@pytest.mark.parametrize('protocol',['openai','responses'])
def test_native_image_tool_retry_reuses_paid_generation(client,setup,monkeypatch,protocol):
    uid,_=setup;id=create(client,'grok',protocol=protocol);calls=[];out=io.BytesIO();Image.new('RGB',(16,16),'blue').save(out,'PNG')
    def remote(url,body,headers):
        calls.append(url)
        if url.endswith('/images/generations'):return {'data':[{'b64_json':base64.b64encode(out.getvalue()).decode()}]}
        messages=body.get('input') or body['messages']
        if not any(m.get('type')=='function_call_output' or m.get('role')=='tool' for m in messages):return native_call(protocol,'generate_image',{'prompt':'一片蓝色海面'})
        return final(protocol,['海面给你画好了'])
    monkeypatch.setattr(jobs,'request_json',remote)
    original=jobs.parse_reply
    def interrupted(*a,**kw):raise HTTPException(502,'模拟媒体完成后服务中断')
    monkeypatch.setattr(jobs,'parse_reply',interrupted);turn,_=send(client,id,'请给我画一片蓝色海面？');run(uid,turn)
    assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='failed'
    monkeypatch.setattr(jobs,'parse_reply',original);client.post(ROOT+'/turns/'+turn['id']+'/retry');run(uid,turn)
    data=client.get(ROOT+'/'+id+'/messages').json();assert data['latest_turn']['status']=='completed'
    assert len(calls)==3 and sum(url.endswith('/images/generations') for url in calls)==1
    picture=next(m for m in data['messages'] if m['role']=='assistant' and m['media']);assert picture['text']==''
    download=client.get(picture['media'][0]['url']+'?download=true');assert download.status_code==200 and 'attachment' in download.headers['content-disposition']
    assert client.delete(ROOT+'/'+id+'/history').status_code==200
    with db.connect() as d:assert d.execute('SELECT COUNT(*) FROM companion_actions').fetchone()[0]==0

def test_voice_choice_persists_its_transcript_without_duplicate_text_bubble(client,setup,monkeypatch):
    uid,_=setup;id=create(client,'grok');count=[]
    def remote(url,body,headers):
        has_tool=any(m.get('role')=='tool' for m in body['messages'])
        return final('openai') if has_tool else native_call('openai','send_voice',{'text':'今天也很高兴见到你'})
    monkeypatch.setattr(jobs,'request_json',remote)
    monkeypatch.setattr(jobs,'post_json_bytes',lambda *a,**kw:(count.append(1) or (b'voice','audio/mpeg')))
    monkeypatch.setattr(jobs.media,'metadata',lambda path:({'format':{'format_name':'mp3'},'streams':[{'codec_type':'audio'}]},4.2))
    turn,_=send(client,id,'用语音说一句话？');run(uid,turn)
    data=client.get(ROOT+'/'+id+'/messages').json();messages=[m for m in data['messages'] if m['role']=='assistant']
    assert len(messages)==1 and messages[0]['text']=='今天也很高兴见到你' and messages[0]['media'][0]['duration']==4.2 and count==[1]

def test_search_read_loop_sources_and_emotion_are_account_owned(client,setup,monkeypatch):
    uid,_=setup;id=create(client);calls=[]
    def remote(url,body,headers):
        tools=[m for m in body['messages'] if m['role']=='tool'];calls.append(body)
        if not tools:return native_call('openai','search_web',{'query':'DeepSeek vision'})
        if len(tools)==1:return native_call('openai','read_webpage',{'url':'https://api-docs.deepseek.com/guides/vision/','query':'vision'},'read-2')
        return final('openai',['文档里有图像输入的说明 [1]'])
    monkeypatch.setattr(jobs,'request_json',remote)
    monkeypatch.setattr(agent,'search',lambda q:{'results':[{'url':'https://api-docs.deepseek.com/guides/vision/','title':'Vision','snippet':'Vision documentation','engine':'Bing'}]})
    monkeypatch.setattr(agent,'read_page',lambda u,q:{'url':u,'title':'Vision','relevant':True,'content':'Image input supported'})
    turn,_=send(client,id,'查一下现在 DeepSeek 的识图文档？');run(uid,turn)
    data=client.get(ROOT+'/'+id+'/messages').json();assert len(data['messages'][-1]['sources'])==1 and len(calls)==3
    mood=client.get(ROOT+'/'+id+'/emotion');assert mood.status_code==200 and -1<=mood.json()['valence']<=1
    assert '伴侣' not in client.get(ROOT).text

def test_multi_engine_fallback_deduplication_and_relevant_reading(monkeypatch):
    calls=[]
    def engine(name,query):
        calls.append(name)
        if name=='Google':raise OSError()
        return [{'title':'Grok API','url':'https://docs.x.ai/guide','snippet':'Grok API tool calls','engine':name}]
    monkeypatch.setattr(search,'engine_search',engine)
    result=search.search('Grok API');assert set(calls)=={'Google','Bing','DuckDuckGo'} and len(result['results'])==1
    article='''<html><head><title>Grok API</title></head><body><nav><a href="/shop">促销购物导航</a></nav><article><h1>Grok API 工具说明</h1><p>Grok API 支持函数调用，应用可以在对话中调用工具，获取当前资料并继续回复用户。</p><p>Grok API 的工具结果必须正确回传，才能确保模型知道实际操作是否成功。</p><p>这个句子是其他主题的无关广告，不该被当成结果。</p></article><footer>版权所有和网站导航</footer></body></html>'''
    monkeypatch.setattr(search,'fetch',lambda url:(article.encode(),'https://docs.x.ai/guide','text/html'))
    result=search.read_page('https://docs.x.ai/guide','Grok API');assert result['relevant'] and '函数调用' in result['content'] and '促销购物导航' not in result['content'] and '无关广告' not in result['content']
    assert not search.focus('完全不同的主题，讨论制作面包和烘焙。','量子计算')
    assert search.clean_link('https://127.0.0.1/admin','https://www.google.com')==''
    assert search.clean_link('https://example.org/article?utm_source=x&id=4','https://www.google.com')=='https://example.org/article?id=4'

def test_redirect_cannot_reach_private_network(monkeypatch):
    class Response:
        status_code=302;headers={'location':'https://127.0.0.1/secrets'}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def iter_bytes(self):return iter([b''])
    class Client:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def stream(self,*a,**kw):return Response()
    monkeypatch.setattr(search,'configured_proxy',lambda:'http://127.0.0.1:17891');monkeypatch.setattr(search.httpx,'Client',Client)
    with pytest.raises(HTTPException) as error:search.fetch('https://www.google.com/search?q=test')
    assert error.value.status_code==422

def test_reply_segmentation_is_model_decided():
    for count in [1,2,5,8]:assert len(jobs.parse_reply(json.dumps({'bubbles':['message '+str(i) for i in range(count)]}))[0])==count
    assert jobs.parse_reply('{"bubbles":[]}',allow_empty=True)[0]==[]
    assert jobs.parse_reply('{"bubbles":"一条消息"}\n备注')[0]==['一条消息']
    assert jobs.parse_reply('{"text":"自然回复"}')[0]==['自然回复']

def test_pending_video_retry_keeps_upstream_job_and_does_not_replan(client,setup,monkeypatch):
    uid,_=setup;id=create(client,'grok');requests=[];jobs_seen=[]
    def remote(url,body,headers):
        requests.append(body)
        return final('openai',['发给你了']) if any(m.get('role')=='tool' for m in body['messages']) else native_call('openai','generate_video',{'prompt':'海面'})
    def generate(row,turn,body):
        jobs_seen.append(turn.get('provider_job'))
        if not turn.get('provider_job'):
            with db.connect(True) as d:d.execute("UPDATE companion_actions SET provider_job='upstream-existing' WHERE id=?",(turn['action_id'],))
            raise HTTPException(504,'视频仍在生成，重试继续查询')
        return {'media_ids':['resumed-video']}
    monkeypatch.setattr(jobs,'request_json',remote);monkeypatch.setattr(jobs,'generated',generate)
    turn,_=send(client,id,'帮我生成一段海面视频？');run(uid,turn)
    assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='failed'
    client.post(ROOT+'/turns/'+turn['id']+'/retry');run(uid,turn)
    assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='completed'
    assert jobs_seen==[None,'upstream-existing'] and len(requests)==2

def test_bad_final_caption_keeps_finished_media_and_bad_text_can_be_retried(client,setup,monkeypatch):
    uid,_=setup;id=create(client,'grok');requests=[]
    def remote(url,body,headers):
        requests.append(body)
        if len(requests)==1:return native_call('openai','generate_video',{'prompt':'海面'})
        return {'choices':[{'message':{'role':'assistant','content':'{"unexpected": "caption schema"}'}}]}
    monkeypatch.setattr(jobs,'request_json',remote);monkeypatch.setattr(jobs,'generated',lambda *a,**kw:{'media_ids':['finished-video']})
    turn,_=send(client,id,'生成海面视频');run(uid,turn)
    d=client.get(ROOT+'/'+id+'/messages').json();assert d['latest_turn']['status']=='completed' and d['latest_turn']['result']['media_ids']==['finished-video'] and d['latest_turn']['result']['notices']
    requests.clear()
    def text_reply(url,body,headers):
        requests.append(body);return final('openai',['这次读到了']) if len(requests)>1 else {'choices':[{'message':{'role':'assistant','content':'{"unexpected":1}'}}]}
    monkeypatch.setattr(jobs,'request_json',text_reply)
    turn,_=send(client,id,'请回复一句话？');run(uid,turn);assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='failed'
    client.post(ROOT+'/turns/'+turn['id']+'/retry');run(uid,turn);assert client.get(ROOT+'/'+id+'/messages').json()['latest_turn']['status']=='completed' and len(requests)==2
