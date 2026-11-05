"""Persistent chat/media jobs and a non-coercive, capped proactive scheduler."""
import base64,hashlib,json,math,re,secrets,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from . import db,companion_media as media
from .core import installed
from .secret_store import open_secret
from .outbound import request_json
from .ai_endpoints import api_base
from .ai_protocol import invoke
from .companion_transport import wire,transcribe,post_json_bytes
from .companion_state import owned,emotion,mood_label,reply_probability,proactive_probability,quiet,next_opportunity,recall,remember,episode,conversation_prompt

CHAT_POOL=ThreadPoolExecutor(max_workers=4,thread_name_prefix='companion-chat')
MEDIA_POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='companion-media')

def public_turn(row):return {k:row[k] for k in ('id','status','kind','error')}

def submit(uid,id,body,proactive=False):
    kind='proactive' if proactive else body['kind'];stamp=time.time();request_id=body['request_id'];fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with db.connect(True) as d:
        row=owned(d,uid,id);cfg=json.loads(row['config'])
        if not installed(d,uid,'companion'):raise HTTPException(403,'请先安装拾光者')
        if not row['secret']:raise HTTPException(422,'请先在设置中填写 API 密钥')
        prior=d.execute('SELECT * FROM companion_turns WHERE user_id=? AND request_id=?',(uid,request_id)).fetchone()
        if prior:
            if prior['input_hash']!=fingerprint or prior['companion_id']!=id:raise HTTPException(409,'请求标识已被其他消息使用')
            return public_turn(prior)
        if d.execute("SELECT 1 FROM companion_turns WHERE companion_id=? AND user_id=? AND status IN ('queued','running')",(id,uid)).fetchone():raise HTTPException(409,'她还在回复上一条，稍等一下再发')
        if not proactive and not body['text'].strip() and not body.get('media_ids') and kind!='voice':raise HTTPException(422,'写点什么，或选择一个附件')
        if kind in ('image','video','voice') and row['provider']!='grok':raise HTTPException(422,'DeepSeek 当前不支持生成图像、视频或语音')
        if kind in ('image','video') and not cfg.get(kind+'_model'):raise HTTPException(422,'请先配置对应的生成模型')
        if kind=='voice' and not cfg.get('voice_enabled'):raise HTTPException(422,'请先启用语音服务并选择音色')
        for token in body.get('media_ids',[]):
            attachment=media.owned(d,uid,token,id)
            if row['provider']=='deepseek' and attachment['kind']!='image':raise HTTPException(422,'DeepSeek 当前只支持文本与图片')
            if row['provider']=='deepseek' and not cfg.get('image_model'):raise HTTPException(422,'请先配置识图模型')
            if attachment['kind']=='audio' and not cfg.get('voice_enabled'):raise HTTPException(422,'请先启用语音服务')
        token=uuid.uuid4().hex;created=db.now()
        d.execute('INSERT INTO companion_turns(id,user_id,companion_id,request_id,input_hash,kind,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(token,uid,id,request_id,fingerprint,kind,'queued',json.dumps(body,ensure_ascii=False),created,created))
        if not proactive:
            text=body['text'].strip() or ('发段语音给我' if kind=='voice' else '')
            d.execute('INSERT INTO companion_messages(user_id,companion_id,turn_id,role,text,media,created_at,visible_at) VALUES(?,?,?,?,?,?,?,?)',(uid,id,token,'user',text,json.dumps(body.get('media_ids',[])),created,stamp))
            d.execute('UPDATE companions SET last_user_at=?,next_chance=?,updated_at=? WHERE id=?',(stamp,next_opportunity(stamp,stamp),created,id))
        result={'id':token,'status':'queued','kind':kind,'error':None}
    (MEDIA_POOL if kind in ('image','video','voice') else CHAT_POOL).submit(run,uid,token)
    return result

def retry(uid,token):
    with db.connect(True) as d:
        turn=d.execute('SELECT * FROM companion_turns WHERE id=? AND user_id=?',(token,uid)).fetchone()
        if not turn:raise HTTPException(404,'消息任务不存在')
        owned(d,uid,turn['companion_id'])
        if turn['status']!='failed':return public_turn(turn)
        if turn['kind']=='proactive':raise HTTPException(422,'主动消息不手动重试，可以直接开始聊天')
        if d.execute("SELECT 1 FROM companion_turns WHERE user_id=? AND companion_id=? AND status IN ('queued','running')",(uid,turn['companion_id'])).fetchone():raise HTTPException(409,'有消息正在处理中')
        d.execute("UPDATE companion_turns SET status='queued',error=NULL,updated_at=? WHERE id=?",(db.now(),token));kind=turn['kind']
    (MEDIA_POOL if kind in ('image','video','voice') else CHAT_POOL).submit(run,uid,token)
    return {'id':token,'status':'queued','kind':kind,'error':None}

def parse_reply(raw):
    text=str(raw).strip();text=re.sub(r'^```(?:json)?\s*|\s*```$','',text)
    try:value=json.loads(text)
    except ValueError:
        if text.startswith(('{','[')):raise HTTPException(502,'伴侣回复格式无法读取，请重试')
        value={'bubbles':[s.strip() for s in re.split(r'\n{2,}',text) if s.strip()]}
    if not isinstance(value,dict) or not isinstance(value.get('bubbles'),list):raise HTTPException(502,'伴侣回复格式无法读取，请重试')
    bubbles=[str(s).strip().rstrip('。') for s in value['bubbles'][:6] if isinstance(s,str) and s.strip()]
    if not bubbles:raise HTTPException(502,'没有收到可读取的回复，请重试')
    return bubbles,value

def update_emotion(old,proposal):
    for name,limit,low,high in [('valence',.12,-1,1),('energy',.1,0,1),('closeness',.015,0,1)]:
        try:delta=float(proposal.get(name+'_delta',0))
        except (ValueError,TypeError):delta=0
        if not math.isfinite(delta):delta=0
        old[name]=max(low,min(high,old[name]+max(-limit,min(limit,delta))))
    old.update(at=time.time(),silent_streak=0);return old

def chat(row,turn,body):
    uid=row['user_id'];id=row['id'];cfg=json.loads(row['config']);key=open_secret(row['secret']);base=api_base(cfg['api_base']);proactive=turn['kind']=='proactive';attachments=[]
    with db.connect(True) as d:
        history=d.execute('SELECT * FROM companion_messages WHERE user_id=? AND companion_id=? ORDER BY id DESC LIMIT 30',(uid,id)).fetchall();memory=recall(d,uid,id,body.get('text',''));source=next((r['id'] for r in history if r['turn_id']==turn['id'] and r['role']=='user'),None)
        for token in body.get('media_ids',[]):attachments.append(media.owned(d,uid,token,id))
    value=emotion(row['provider'],row['emotion']);draw=secrets.randbelow(1_000_000)/1_000_000
    if not proactive and any(r['role']=='assistant' for r in history) and draw>reply_probability(body.get('text',''),value,bool(attachments)):
        value['silent_streak']=value.get('silent_streak',0)+1;return {'silent':True,'emotion':value,'bubbles':[],'source_id':source,'user_text':body.get('text','')}
    messages=[];remaining=24000
    # Keep the newest turn when trimming a long conversation.
    for r in history:
        if attachments and r['turn_id']==turn['id']:continue
        if remaining<=0:break
        content=r['text'][:min(12000 if r['turn_id']==turn['id'] else 4000,remaining)];remaining-=len(content)
        if r['turn_id']!=turn['id'] and json.loads(r['media']):content+='\n[此前发送的附件，内容见相邻回复]'
        if content:messages.append({'role':r['role'],'content':content})
    messages.reverse()
    latest=body.get('text','').strip();image_inputs=[];notices=[]
    for attachment in attachments:
        if attachment['kind']=='image':image_inputs.append(media.data_url(attachment))
        elif attachment['kind']=='video':
            image_inputs.extend(media.frames(attachment));latest+='\n[这段视频的四个采样关键帧，不代表全部画面]'
            if cfg.get('voice_enabled'):
                info,_=media.metadata(media.ROOT/attachment['filename'])
                if any(s.get('codec_type')=='audio' for s in info.get('streams',[])):
                    try:latest+='\n[视频音轨转写] '+transcribe(base,key,media.wav(attachment),cfg.get('voice_model',''))
                    except HTTPException as error:
                        if error.status_code!=422 or '没有识别到语音' not in str(error.detail):raise
                        latest+='\n[音轨中没有可识别语音，按采样画面分析]';notices.append('视频已分析 4 个关键帧；音轨中没有可识别语音')
            else:latest+='\n[未分析音轨]'
        elif attachment['kind']=='audio':latest+='\n[语音转写] '+transcribe(base,key,media.wav(attachment),cfg.get('voice_model',''))
    if attachments:
        # Replace the current user message, never put user images into a system/assistant role.
        messages.append({'role':'user','content':latest or '看看我发来的内容'})
    if proactive:messages.append({'role':'user','content':'[系统调度的主动联系机会；不代表用户发了这条消息。自然聊一点，不催回复] '})
    model=cfg['image_model'] if image_inputs and row['provider']=='deepseek' else cfg['chat_model']
    config={'family':row['provider'],'protocol':cfg['protocol'],'api_base':base,'model':model,'max_tokens':1800,'show_reasoning':False}
    if image_inputs:
        protocol=cfg['protocol'];parts=[{'type':'input_text' if protocol=='responses' else 'text','text':messages[-1]['content']}]
        parts.extend([{'type':'input_image','image_url':url} if protocol=='responses' else {'type':'image_url','image_url':{'url':url}} for url in image_inputs])
        messages[-1]['content']=parts
    raw=invoke(config,key,messages,conversation_prompt(row,memory,proactive),lambda config,key,url,body,headers:request_json(url,body,headers));bubbles,result=parse_reply(raw)
    return {'bubbles':bubbles,'emotion':update_emotion(value,result.get('emotion') if isinstance(result.get('emotion'),dict) else {}),'memories':result.get('memories',[]),'source_id':source,'user_text':latest,'notices':notices}

def generated(row,turn,body):
    cfg=json.loads(row['config']);base=api_base(cfg['api_base']);key=open_secret(row['secret']);headers={'Authorization':'Bearer '+key};kind=turn['kind'];prompt=body['text'].strip()[:4000]
    if kind=='voice':
        text=prompt
        if body.get('source_message_id'):
            with db.connect() as d:r=d.execute("SELECT text FROM companion_messages WHERE id=? AND user_id=? AND companion_id=? AND role='assistant'",(body['source_message_id'],row['user_id'],row['id'])).fetchone()
            if not r:raise HTTPException(404,'要朗读的消息不存在')
            text=r['text']
        if not text:raise HTTPException(422,'请填写语音文字，或选择一条消息朗读')
        if len(text)>600:raise HTTPException(422,'单条语音最多朗读 600 字，请选择较短的消息')
        data,mime=post_json_bytes(base+'/tts',key,{'text':text,'voice_id':cfg['voice_id'],'language':'zh','with_timestamps':True})
        if 'json' in mime:
            try:data=base64.b64decode(json.loads(data)['audio'],validate=True)
            except Exception:raise HTTPException(502,'语音服务未返回有效音频')
        token=media.store(row['user_id'],row['id'],'audio',data)
    elif kind=='image':
        data=request_json(base+'/images/generations',{'model':cfg['image_model'],'prompt':prompt,'n':1,'response_format':'b64_json'},headers)
        try:
            image=data['data'][0];raw=base64.b64decode(image['b64_json'],validate=True) if image.get('b64_json') else wire(image['url'],limit=30*1024*1024)[0]
        except (ValueError,KeyError,IndexError,TypeError):raise HTTPException(502,'图像服务未返回可用图片')
        token=media.store(row['user_id'],row['id'],'image',raw)
    else:
        job=turn.get('provider_job')
        if not job:
            data=request_json(base+'/videos/generations',{'model':cfg['video_model'],'prompt':prompt,'duration':4,'resolution':'720p'},headers);job=data.get('request_id')
            if not isinstance(job,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',job):raise HTTPException(502,'视频服务没有返回可用任务 ID')
            with db.connect(True) as d:d.execute('UPDATE companion_turns SET provider_job=? WHERE id=? AND user_id=?',(job,turn['id'],row['user_id']))
        for _ in range(90):
            data=request_json(base+'/videos/'+quote(job,safe=''),headers=headers)
            if data.get('status')=='done':break
            if data.get('status') in ('failed','expired'):raise HTTPException(502,'视频生成失败或任务已过期，请重新发起生成')
            time.sleep(5)
        else:raise HTTPException(504,'视频仍在生成，可稍后重试继续查询，不会重复创建上游任务')
        try:raw=wire(data['video']['url'],limit=64*1024*1024)[0]
        except (KeyError,TypeError):raise HTTPException(502,'视频服务未返回有效视频')
        token=media.store(row['user_id'],row['id'],'video',raw)
    return {'media_ids':[token],'bubbles':[],'label':'AI 生成的'+{'image':'图像','video':'视频','voice':'语音'}[kind]}

def run(uid,token):
    try:
        with db.connect(True) as d:
            turn=d.execute('SELECT * FROM companion_turns WHERE id=? AND user_id=?',(token,uid)).fetchone()
            if not turn or turn['status']!='queued':return
            if not installed(d,uid,'companion'):raise HTTPException(409,'拾光者已卸载，不再调用模型')
            row=owned(d,uid,turn['companion_id']);turn=dict(turn);d.execute("UPDATE companion_turns SET status='running',updated_at=? WHERE id=?",(db.now(),token))
        body=json.loads(turn['input']);result=generated(row,turn,body) if turn['kind'] in ('image','video','voice') else chat(row,turn,body)
        with db.connect(True) as d:
            if not installed(d,uid,'companion'):raise HTTPException(409,'拾光者已卸载，本次结果未投递')
            current=owned(d,uid,row['id']);cfg=json.loads(current['config']);stamp=time.time()
            if turn['kind']=='proactive' and (not cfg.get('proactive_enabled') or current['last_user_at']!=row['last_user_at'] or quiet(stamp)):raise HTTPException(409,'主动联系条件已改变，本次消息不再投递')
            if result.get('emotion'):d.execute('UPDATE companions SET emotion=? WHERE id=?',(json.dumps(result['emotion']),row['id']))
            if result.get('user_text') and result.get('source_id'):
                text=result['user_text'];episode(d,uid,row['id'],text,result['source_id'])
                proposals=result.get('memories',[])
                proposals=proposals if isinstance(proposals,list) else []
                if re.search(r'记住|别忘|不要忘',text):proposals=proposals+[{'text':text[:800],'quote':text[:800],'importance':1}]
                remember(d,uid,row['id'],proposals,result['source_id'],text)
            delay=0
            for text in result.get('bubbles',[]):
                message=d.execute('INSERT INTO companion_messages(user_id,companion_id,turn_id,role,text,created_at,visible_at,proactive) VALUES(?,?,?,?,?,?,?,?)',(uid,row['id'],token,'assistant',text,db.now(),stamp+delay,int(turn['kind']=='proactive')))
                episode(d,uid,row['id'],text,message.lastrowid,'assistant')
                delay+=.6+secrets.randbelow(800)/1000
            if result.get('media_ids'):d.execute('INSERT INTO companion_messages(user_id,companion_id,turn_id,role,text,media,created_at,visible_at) VALUES(?,?,?,?,?,?,?,?)',(uid,row['id'],token,'assistant',result.get('label',''),json.dumps(result['media_ids']),db.now(),stamp))
            if not result.get('silent'):d.execute('UPDATE companions SET last_assistant_at=?,updated_at=? WHERE id=?',(stamp,db.now(),row['id']))
            summary={'silent':bool(result.get('silent')),'bubble_count':len(result.get('bubbles',[])),'media_ids':result.get('media_ids',[]),'notices':result.get('notices',[])}
            d.execute("UPDATE companion_turns SET status='completed',result=?,updated_at=? WHERE id=? AND user_id=?",(json.dumps(summary),db.now(),token,uid))
    except Exception as error:
        message=str(error.detail) if isinstance(error,HTTPException) else '这条消息处理失败，请重试；已有聊天和记忆保留'
        with db.connect(True) as d:d.execute("UPDATE companion_turns SET status='failed',error=?,updated_at=? WHERE id=? AND user_id=?",(message,db.now(),token,uid))

def scheduler_tick(stamp=None,draw=None):
    stamp=time.time() if stamp is None else stamp;draw=draw or (lambda:secrets.randbelow(1_000_000)/1_000_000)
    if quiet(stamp):return
    with db.connect() as d:rows=d.execute("SELECT c.* FROM companions c JOIN installed i ON i.user_id=c.user_id AND i.plugin_id='companion' WHERE c.last_user_at IS NOT NULL AND c.next_chance<=?",(stamp,)).fetchall()
    for raw in rows:
        row=dict(raw);cfg=json.loads(row['config'])
        if not cfg.get('proactive_enabled') or not row['secret'] or stamp-row['last_user_at']<6*3600:continue
        day=datetime.fromtimestamp(stamp,ZoneInfo('Asia/Shanghai')).date().isoformat();chance=proactive_probability(emotion(row['provider'],row['emotion'],stamp))
        with db.connect(True) as d:
            current=owned(d,row['user_id'],row['id'])
            if current['next_chance']>stamp or current['last_user_at']!=row['last_user_at']:continue
            attempts=d.execute("SELECT COUNT(*) FROM companion_turns WHERE user_id=? AND kind='proactive' AND request_id LIKE ?",(row['user_id'],'proactive:'+day+':%')).fetchone()[0]
            d.execute('UPDATE companions SET next_chance=? WHERE id=?',(next_opportunity(current['last_user_at'],stamp+2*3600),row['id']))
            if attempts>=2 or draw()>chance:continue
        try:submit(row['user_id'],row['id'],{'request_id':'proactive:'+day+':'+uuid.uuid4().hex,'kind':'chat','text':'','media_ids':[]},True)
        except HTTPException:pass

def start_scheduler():
    stop=threading.Event()
    def loop():
        while not stop.wait(60):
            try:scheduler_tick()
            except Exception:pass
    thread=threading.Thread(target=loop,name='companion-proactive',daemon=True);thread.start();return stop

def recover():
    with db.connect(True) as d:
        pending=d.execute("SELECT user_id,id,kind,provider_job FROM companion_turns WHERE status IN ('queued','running')").fetchall()
        for r in pending:
            if r['kind']=='video' and r['provider_job']:
                d.execute("UPDATE companion_turns SET status='queued' WHERE id=?",(r['id'],));MEDIA_POOL.submit(run,r['user_id'],r['id'])
            else:d.execute("UPDATE companion_turns SET status='failed',error='服务重启中断了消息，可手动重试',updated_at=? WHERE id=?",(db.now(),r['id']))
