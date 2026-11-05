"""拾光者: account-owned fixed companions, private chat and inspectable memories."""
import json,time,uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Query
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from .. import db,companion_media as media
from ..core import require_plugin
from ..secret_store import seal,open_secret
from ..outbound import endpoint,request_json
from ..ai_endpoints import api_base,models_url
from ..companion_state import PRESETS,owned,emotion,mood_label,memory_strength,prune

MANIFEST={'id':'companion','name':'拾光者','description':'与 Grok、DeepSeek 自然聊天。短句聊天、情绪变化、渐进记忆与偶尔主动的问候。','category':'聊天','icon':'MessagesSquare','ui':'companion'}
router=APIRouter(prefix='/api/plugins/companion',tags=['拾光者']);user=require_plugin('companion')
MODEL=r'^[A-Za-z0-9][A-Za-z0-9_.:/-]*$'

class Config(BaseModel):
    provider:Literal['grok','deepseek']
    protocol:Literal['openai','responses']='openai'
    api_base:str=Field(max_length=500)
    api_key:str=Field(default='',max_length=2000)
    clear_key:bool=False
    chat_model:str=Field(min_length=1,max_length=200,pattern=MODEL)
    image_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    video_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    voice_enabled:bool=False
    voice_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    voice_id:str=Field(default='ara',max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    nickname:str=Field(default='',max_length=40)
    display_name:str=Field(default='',max_length=40)
    proactive_enabled:bool=False

def public(d,row):
    cfg=json.loads(row['config']);value=emotion(row['provider'],row['emotion']);stamp=time.time()
    unread=d.execute("SELECT COUNT(*) FROM companion_messages WHERE user_id=? AND companion_id=? AND role='assistant' AND id>? AND visible_at<=?",(row['user_id'],row['id'],row['seen_id'],stamp)).fetchone()[0]
    last=d.execute('SELECT text,role,created_at,media FROM companion_messages WHERE user_id=? AND companion_id=? AND visible_at<=? ORDER BY id DESC LIMIT 1',(row['user_id'],row['id'],stamp)).fetchone()
    active=d.execute("SELECT id,status,kind,error,result FROM companion_turns WHERE user_id=? AND companion_id=? AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 1",(row['user_id'],row['id'])).fetchone()
    last=dict(last) if last else None
    if last:
        tokens=json.loads(last.pop('media'));kind=d.execute('SELECT kind FROM companion_media WHERE id=? AND user_id=?',(tokens[0],row['user_id'])).fetchone() if tokens else None
        if kind and (kind[0]=='audio' or not last['text']):last['text']={'audio':'[语音]','image':'[图片]','video':'[视频]'}.get(kind[0],'[附件]')
    active=dict(active) if active else None
    if active:active['stage']=json.loads(active.pop('result') or '{}').get('stage','')
    return {'id':row['id'],'provider':row['provider'],'config':cfg,'has_key':bool(row['secret']),'name':cfg.get('display_name') or PRESETS[row['provider']]['name'],'avatar':'/api/plugins/companion/'+row['id']+'/avatar?v='+cfg.get('avatar_id','default1'),'mood':mood_label(value,row['provider']),'unread':unread,'last_message':last,'active_turn':active,'created_at':row['created_at'],'revision':row['revision']}

@router.get('')
def listing(u=Depends(user)):
    with db.connect() as d:
        rows=d.execute('SELECT * FROM companions WHERE user_id=? ORDER BY created_at',(u['id'],)).fetchall()
        return {'companions':[public(d,dict(r)) for r in rows],'presets':[{'provider':k,'name':v['name'],'label':v['label'],'tagline':v['tagline'],'api_base':v['base'],'protocol':v['protocol'],'avatar':'/api/plugins/companion/avatar/'+k,'chat_avatar':'/api/plugins/companion/avatar/'+k+'?chat=true'} for k,v in PRESETS.items()],'proactive_rules':{'idle_hours':6,'quiet_start':0,'quiet_end':8,'daily_limit':2,'timezone':'Asia/Shanghai'}}

@router.get('/avatar/{provider}')
def avatar(provider:str,chat:bool=False,u=Depends(user)):
    if provider not in PRESETS:raise HTTPException(404,'形象不存在')
    path=Path(__file__).parents[1]/('content/aiheader' if chat else 'content/ai')/(f'{provider}.jpg' if chat else f'{provider}.webp')
    if not path.is_file():raise HTTPException(404,'此部署未安装可选角色形象资源')
    return FileResponse(path,media_type='image/jpeg' if chat else 'image/webp')

def validate(body):
    endpoint(body.api_base)
    if any(c in body.api_key for c in '\r\n'):raise HTTPException(422,'密钥格式无效')
    if body.provider=='deepseek' and (body.video_model or body.voice_enabled or body.voice_model):raise HTTPException(422,'DeepSeek 当前只开放对话与识图')
    return body.model_dump(exclude={'api_key','clear_key'})|{'api_base':api_base(body.api_base),'display_name':body.display_name.strip()}

@router.post('',status_code=201)
def create(body:Config,u=Depends(user)):
    cfg=validate(body)
    if not body.api_key.strip():raise HTTPException(422,'首次创建请填写 API 密钥')
    with db.connect(True) as d:
        if d.execute('SELECT 1 FROM companions WHERE user_id=? AND provider=?',(u['id'],body.provider)).fetchone():raise HTTPException(409,'这位角色已经创建，可进入设置修改接口；每个厂商只能拥有一位')
        id=uuid.uuid4().hex;stamp=db.now();d.execute('INSERT INTO companions(id,user_id,provider,config,secret,emotion,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(id,u['id'],body.provider,json.dumps(cfg,ensure_ascii=False),seal(body.api_key.strip()),json.dumps(emotion(body.provider)),stamp,stamp))
        return public(d,owned(d,u['id'],id))

@router.put('/{id}')
def update(id:str,body:Config,u=Depends(user)):
    cfg=validate(body)
    with db.connect(True) as d:
        old=owned(d,u['id'],id)
        if old['provider']!=body.provider:raise HTTPException(409,'角色身份固定，不能更换厂商')
        if d.execute("SELECT 1 FROM companion_turns WHERE companion_id=? AND user_id=? AND status IN ('queued','running')",(id,u['id'])).fetchone():raise HTTPException(409,'请等待当前消息处理完成后再修改设置')
        previous=json.loads(old['config'])
        if previous.get('avatar_id'):cfg['avatar_id']=previous['avatar_id']
        if api_base(previous['api_base'])!=cfg['api_base'] and not body.api_key:raise HTTPException(422,'更换基础地址时请重新填写对应密钥')
        secret=seal(body.api_key.strip()) if body.api_key.strip() else '' if body.clear_key else old['secret']
        d.execute('UPDATE companions SET config=?,secret=?,revision=revision+1,updated_at=? WHERE id=? AND user_id=?',(json.dumps(cfg,ensure_ascii=False),secret,db.now(),id,u['id']))
        return public(d,owned(d,u['id'],id))

class Probe(BaseModel):
    provider:Literal['grok','deepseek']
    api_base:str=Field(max_length=500)
    api_key:str=Field(default='',max_length=2000)
    companion_id:str|None=None

@router.post('/models')
def models(body:Probe,u=Depends(user)):
    endpoint(body.api_base);base=api_base(body.api_base);key=body.api_key.strip()
    if any(c in key for c in '\r\n'):raise HTTPException(422,'密钥格式无效')
    if not key and body.companion_id:
        with db.connect() as d:old=owned(d,u['id'],body.companion_id)
        if old['provider']!=body.provider or api_base(json.loads(old['config'])['api_base'])!=base:raise HTTPException(422,'接口已改变，请填写对应密钥')
        key=open_secret(old['secret'])
    if not key:raise HTTPException(422,'请先填写 API 密钥')
    data=request_json(models_url(base),headers={'Authorization':'Bearer '+key});rows=data.get('data',data.get('models',[]))
    result=[]
    for m in rows[:1000]:
        if not isinstance(m,dict) or not m.get('id'):continue
        id=m['id'];kind='video' if 'imagine-video' in id else 'image' if 'imagine-image' in id else 'voice' if any(s in id for s in ('voice','tts','stt','audio')) else 'chat'
        result.append({'id':id,'name':m.get('name',id),'kind':kind,'vision':('image' in m.get('input_modalities',[])) or body.provider=='grok' and kind=='chat' or body.provider=='deepseek' and id in ('deepseek-flash','deepseek-v4-flash-vision-exp')})
    voices=[]
    if body.provider=='grok':
        try:
            data=request_json(base+'/tts/voices',headers={'Authorization':'Bearer '+key});voices=[{'id':v.get('voice_id') or v.get('id'),'name':v.get('name') or v.get('voice_id') or v.get('id')} for v in data.get('voices',[]) if v.get('voice_id') or v.get('id')]
        except HTTPException:pass
    return {'models':result,'voices':voices,'voice_service':'Grok Voice（官方固定服务，按音色调用，不伪造模型 ID）' if body.provider=='grok' else None}

@router.get('/{id}/avatar')
def chat_avatar(id:str,u=Depends(user)):
    with db.connect() as d:
        row=owned(d,u['id'],id);cfg=json.loads(row['config'])
        if cfg.get('avatar_id'):
            saved=media.owned(d,u['id'],cfg['avatar_id'],id);path=media.ROOT/saved['filename']
        else:path=Path(__file__).parents[1]/'content/aiheader'/f"{row['provider']}.jpg"
    if not path.is_file():raise HTTPException(404,'此部署未安装聊天头像资源')
    return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@router.post('/{id}/avatar')
async def set_avatar(id:str,file:UploadFile=File(...),u=Depends(user)):
    with db.connect() as d:owned(d,u['id'],id)
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024:raise HTTPException(413,'头像不超过 5 MB')
    from starlette.concurrency import run_in_threadpool
    token=await run_in_threadpool(media.store,u['id'],id,'image',data)
    with db.connect(True) as d:
        row=owned(d,u['id'],id);media.owned(d,u['id'],token,id);cfg=json.loads(row['config']);old=cfg.get('avatar_id');cfg['avatar_id']=token
        d.execute('UPDATE companions SET config=?,revision=revision+1,updated_at=? WHERE id=? AND user_id=?',(json.dumps(cfg,ensure_ascii=False),db.now(),id,u['id']))
        _remove_old_avatar(d,u['id'],old)
        return public(d,owned(d,u['id'],id))

def _remove_old_avatar(d,uid,token):
    if not token:return
    if d.execute('SELECT 1 FROM companion_messages m,json_each(m.media) a WHERE m.user_id=? AND a.value=?',(uid,token)).fetchone():return
    row=d.execute('SELECT filename FROM companion_media WHERE user_id=? AND id=?',(uid,token)).fetchone()
    if row:
        d.execute('DELETE FROM companion_media WHERE user_id=? AND id=?',(uid,token));(media.ROOT/row['filename']).unlink(missing_ok=True)

@router.delete('/{id}/avatar')
def default_avatar(id:str,u=Depends(user)):
    with db.connect(True) as d:
        row=owned(d,u['id'],id);cfg=json.loads(row['config']);old=cfg.pop('avatar_id',None)
        d.execute('UPDATE companions SET config=?,revision=revision+1,updated_at=? WHERE id=? AND user_id=?',(json.dumps(cfg,ensure_ascii=False),db.now(),id,u['id']));_remove_old_avatar(d,u['id'],old)
        return public(d,owned(d,u['id'],id))

@router.get('/{id}/messages')
def messages(id:str,before:int=Query(0,ge=0),u=Depends(user)):
    with db.connect() as d:
        row=owned(d,u['id'],id);stamp=time.time();rows=d.execute('SELECT * FROM companion_messages WHERE user_id=? AND companion_id=? AND visible_at<=? AND (?=0 OR id<?) ORDER BY id DESC LIMIT 60',(u['id'],id,stamp,before,before)).fetchall();result=[]
        for r in reversed(rows):
            attachments=[]
            for token in json.loads(r['media']):
                try:attachments.append(media.public(media.owned(d,u['id'],token,id)))
                except HTTPException:pass
            result.append({'id':r['id'],'role':r['role'],'text':'' if r['role']=='assistant' and r['text'] in ('AI 生成的图像','AI 生成的视频','AI 生成的语音') else r['text'],'sources':json.loads(r['sources']),'media':attachments,'created_at':r['created_at'],'proactive':bool(r['proactive']),'turn_id':r['turn_id']})
        upcoming=d.execute("SELECT MAX(visible_at) FROM companion_messages WHERE user_id=? AND companion_id=? AND role='assistant'",(u['id'],id)).fetchone()[0] or 0
        latest=d.execute('SELECT id,status,kind,error,result FROM companion_turns WHERE user_id=? AND companion_id=? ORDER BY created_at DESC LIMIT 1',(u['id'],id)).fetchone()
        return {'companion':public(d,row),'messages':result,'has_older':len(rows)==60,'typing':upcoming>stamp,'latest_turn':{**{k:latest[k] for k in ('id','status','kind','error')},'result':json.loads(latest['result']) if latest['result'] else None} if latest else None}

@router.post('/{id}/read')
def read(id:str,u=Depends(user)):
    with db.connect(True) as d:
        owned(d,u['id'],id);latest=d.execute("SELECT MAX(id) FROM companion_messages WHERE user_id=? AND companion_id=? AND role='assistant' AND visible_at<=?",(u['id'],id,time.time())).fetchone()[0] or 0
        d.execute('UPDATE companions SET seen_id=MAX(seen_id,?) WHERE id=? AND user_id=?',(latest,id,u['id']))
    return {'ok':True}

class Send(BaseModel):
    request_id:str=Field(min_length=8,max_length=100)
    text:str=Field(default='',max_length=12000)
    media_ids:list[str]=Field(default_factory=list,max_length=4)
    kind:Literal['chat','image','video','voice']='chat'
    source_message_id:int|None=None

@router.post('/{id}/send',status_code=202)
def send(id:str,body:Send,u=Depends(user)):
    from ..companion_jobs import submit
    return submit(u['id'],id,body.model_dump())

@router.post('/turns/{turn_id}/retry',status_code=202)
def retry(turn_id:str,u=Depends(user)):
    from ..companion_jobs import retry as retry_job
    return retry_job(u['id'],turn_id)

@router.post('/{id}/upload')
async def upload(id:str,file:UploadFile=File(...),kind:Literal['image','audio','video']=Query('image'),u=Depends(user)):
    with db.connect() as d:row=owned(d,u['id'],id)
    cfg=json.loads(row['config'])
    if row['provider']=='deepseek' and kind!='image':raise HTTPException(422,'DeepSeek 当前只接收文本和图片')
    if kind=='image' and row['provider']=='deepseek' and not cfg.get('image_model'):raise HTTPException(422,'请先配置可用的识图模型')
    if kind=='audio' and not cfg.get('voice_enabled'):raise HTTPException(422,'请先在设置中启用语音服务')
    data=await file.read(media.MAX_UPLOAD+1)
    if len(data)>media.MAX_UPLOAD:raise HTTPException(413,'单个附件不超过 30 MB')
    from starlette.concurrency import run_in_threadpool
    token=await run_in_threadpool(media.store,u['id'],id,kind,data)
    with db.connect() as d:return media.public(media.owned(d,u['id'],token,id))

@router.get('/media/{token}')
def attachment(token:str,download:bool=False,u=Depends(user)):
    with db.connect() as d:row=media.owned(d,u['id'],token)
    path=media.ROOT/row['filename']
    if not path.is_file():raise HTTPException(410,'附件已清理')
    return FileResponse(path,media_type=row['mime'],filename=('image-' if row['kind']=='image' else 'media-')+row['filename'] if download else None,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

@router.delete('/media/{token}')
def remove_pending_attachment(token:str,u=Depends(user)):
    with db.connect(True) as d:
        row=media.owned(d,u['id'],token)
        if d.execute("SELECT 1 FROM companions WHERE user_id=? AND json_extract(config,'$.avatar_id')=?",(u['id'],token)).fetchone():raise HTTPException(409,'此图片正在作为角色头像使用，可在角色设置中恢复默认头像')
        if d.execute('SELECT 1 FROM companion_messages m,json_each(m.media) a WHERE m.user_id=? AND a.value=?',(u['id'],token)).fetchone():raise HTTPException(409,'附件已进入聊天，可在角色设置中清理历史附件')
        d.execute('DELETE FROM companion_media WHERE id=? AND user_id=?',(token,u['id']))
    (media.ROOT/row['filename']).unlink(missing_ok=True)
    return {'ok':True}

@router.get('/{id}/memories')
def memories(id:str,u=Depends(user)):
    with db.connect(True) as d:
        owned(d,u['id'],id);prune(d,u['id'],id);rows=d.execute('SELECT * FROM companion_memories WHERE user_id=? AND companion_id=? ORDER BY kind,created DESC',(u['id'],id)).fetchall()
        return {'memories':[{k:r[k] for k in ('id','text','kind','importance','created','last_access','accesses')}|{'strength':round(memory_strength(r),3)} for r in rows]}

class Memory(BaseModel):
    text:str=Field(min_length=1,max_length=800)
    kind:Literal['temporary','permanent']='permanent'

@router.put('/{id}/memories/{memory_id}')
def edit_memory(id:str,memory_id:str,body:Memory,u=Depends(user)):
    if not body.text.strip():raise HTTPException(422,'记忆内容不能为空')
    with db.connect(True) as d:
        owned(d,u['id'],id);r=d.execute('UPDATE companion_memories SET text=?,kind=?,importance=1,last_access=?,updated_at=? WHERE id=? AND companion_id=? AND user_id=?',(body.text.strip(),body.kind,time.time(),db.now(),memory_id,id,u['id']))
        if not r.rowcount:raise HTTPException(404,'记忆不存在')
    return {'message':'记忆已更新'}

@router.delete('/{id}/memories/{memory_id}')
def forget(id:str,memory_id:str,u=Depends(user)):
    with db.connect(True) as d:
        owned(d,u['id'],id);d.execute('DELETE FROM companion_memories WHERE id=? AND companion_id=? AND user_id=?',(memory_id,id,u['id']))
    return {'message':'已忘记这条记忆'}

@router.delete('/{id}/history')
def clear_history(id:str,u=Depends(user)):
    with db.connect(True) as d:
        companion=owned(d,u['id'],id)
        if d.execute("SELECT 1 FROM companion_turns WHERE user_id=? AND companion_id=? AND status IN ('queued','running')",(u['id'],id)).fetchone():raise HTTPException(409,'请等待当前消息完成后再清理')
        avatar_id=json.loads(companion['config']).get('avatar_id','')
        files=[r[0] for r in d.execute('SELECT filename FROM companion_media WHERE user_id=? AND companion_id=? AND id!=?',(u['id'],id,avatar_id))]
        for table in ('companion_actions','companion_messages','companion_turns'):d.execute('DELETE FROM '+table+' WHERE user_id=? AND companion_id=?',(u['id'],id))
        d.execute('DELETE FROM companion_media WHERE user_id=? AND companion_id=? AND id!=?',(u['id'],id,avatar_id))
        d.execute('UPDATE companions SET last_user_at=NULL,last_assistant_at=NULL,next_chance=0,seen_id=0 WHERE id=? AND user_id=?',(id,u['id']))
    for filename in files:(media.ROOT/filename).unlink(missing_ok=True)
    return {'message':'已清空聊天和附件，角色身份与记忆保留'}

@router.get('/{id}/emotion')
def emotional_state(id:str,u=Depends(user)):
    with db.connect() as d:row=owned(d,u['id'],id)
    value=emotion(row['provider'],row['emotion'])
    return {'mood':mood_label(value,row['provider']),'valence':round(value['valence'],3),'energy':round(value['energy'],3),'closeness':round(value['closeness'],3),'last_interaction':row['last_user_at']}
