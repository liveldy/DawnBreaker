"""Administrator API. Every mutation is authenticated, transactional and audited."""
import json
import sqlite3
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from .core import require_user, public_user, balance, credit
from .config import setting
from .db import connect, now
from .plugins import BY_ID, catalog
from pwdlib import PasswordHash
from .content_store import items

router=APIRouter(prefix='/api/admin',tags=['管理员'])
KINDS=['essence','stones']

def require_admin(u=Depends(require_user)):
    if u['role']!='admin': raise HTTPException(403,'仅管理员可以执行此操作')
    return u

def target(db,uid):
    row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not row: raise HTTPException(404,'账号不存在')
    return row

def audit(db,actor,action,uid=None,before=None,after=None):
    db.execute('INSERT INTO audit(actor_id,target_id,action,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)',(actor['id'],uid,action,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),now()))

@router.get('/users')
def users(q:str=Query('',max_length=100),page:int=Query(1,ge=1),u=Depends(require_admin)):
    with connect() as db:
        pattern='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        params=(pattern,pattern)
        where="WHERE username LIKE ? ESCAPE '\\' OR nickname LIKE ? ESCAPE '\\'"
        total=db.execute('SELECT COUNT(*) FROM users '+where,params).fetchone()[0]
        rows=db.execute('SELECT * FROM users '+where+' ORDER BY created_at DESC LIMIT 20 OFFSET ?',(*params,(page-1)*20)).fetchall()
        return {'users':[public_user(r)|{'wallet':{k:balance(db,r['id'],k) for k in KINDS}} for r in rows],'total':total,'page':page}

@router.get('/users/{uid}')
def detail(uid:str,u=Depends(require_admin)):
    with connect() as db:
        row=target(db,uid)
        progress=[dict(r)|{'value':json.loads(r['value'])} for r in db.execute('SELECT plugin_id,key,value FROM progress WHERE user_id=? ORDER BY plugin_id,key',(uid,))]
        events=[dict(r)|{'payload':json.loads(r['payload'])} for r in db.execute('SELECT id,kind,payload,created_at FROM events WHERE user_id=? ORDER BY id DESC LIMIT 100',(uid,))]
        ledger=[dict(r) for r in db.execute("SELECT id,kind,amount,reason,source,created_at FROM ledger WHERE user_id=? AND kind IN ('essence','stones') ORDER BY id DESC LIMIT 100",(uid,))]
        return {'user':public_user(row),'wallet':{k:balance(db,uid,k) for k in KINDS},'plugins':catalog(db,uid),'progress':progress,'events':events,'ledger':ledger}

class Account(BaseModel):
    username:str=Field(min_length=3,max_length=24,pattern='^[a-zA-Z0-9_]+$')
    nickname:str=Field(min_length=1,max_length=30)
    bio:str=Field(default='',max_length=160)
    role:Literal['user','admin']='user'

@router.patch('/users/{uid}')
def edit(uid:str,body:Account,u=Depends(require_admin)):
    with connect(True) as db:
        old=target(db,uid)
        if not body.nickname.strip(): raise HTTPException(422,'昵称不能为空')
        if old['role']=='admin' and body.role!='admin' and db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]<=1: raise HTTPException(409,'至少保留一个管理员账号')
        try: db.execute('UPDATE users SET username=?,nickname=?,bio=?,role=? WHERE id=?',(body.username.casefold(),body.nickname.strip(),body.bio,body.role,uid))
        except sqlite3.IntegrityError: raise HTTPException(409,'用户名已被使用')
        audit(db,u,'修改账号',uid,public_user(old),body.model_dump())
    return {'message':'账号信息已更新'}

class NewAccount(Account):
    password:str=Field(min_length=12,max_length=128)

@router.post('/users',status_code=201)
def create(body:NewAccount,u=Depends(require_admin)):
    uid=uuid.uuid4().hex; hashed=PasswordHash.recommended().hash(body.password)
    with connect(True) as db:
        try: db.execute('INSERT INTO users(id,username,password,nickname,bio,created_at,role) VALUES(?,?,?,?,?,?,?)',(uid,body.username.casefold(),hashed,body.nickname,body.bio,now(),body.role))
        except sqlite3.IntegrityError: raise HTTPException(409,'用户名已被使用')
        audit(db,u,'创建账号',uid,after=body.model_dump(exclude={'password'}))
    return {'message':'账号已创建','id':uid}

class ResetPassword(BaseModel):
    password:str=Field(min_length=12,max_length=128)

@router.post('/users/{uid}/password')
def password(uid:str,body:ResetPassword,u=Depends(require_admin)):
    hashed=PasswordHash.recommended().hash(body.password)
    with connect(True) as db:
        target(db,uid)
        db.execute('UPDATE users SET password=? WHERE id=?',(hashed,uid))
        db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        audit(db,u,'重置密码并退出全部登录',uid)
    return {'message':'密码已重置，该账号的全部登录已退出'}

class Balances(BaseModel):
    essence:int=Field(ge=0,le=10**12)
    stones:int=Field(ge=0,le=10**12)
    reason:str=Field(min_length=1,max_length=120)

@router.patch('/users/{uid}/balances')
def balances(uid:str,body:Balances,u=Depends(require_admin)):
    with connect(True) as db:
        target(db,uid); old={k:balance(db,uid,k) for k in KINDS}
        for key in KINDS:
            delta=getattr(body,key)-old[key]
            if delta: credit(db,uid,key,delta,'管理员调整：'+body.reason,'admin:'+uuid.uuid4().hex,hooks=False)
        audit(db,u,'调整余额',uid,old,body.model_dump())
    return {'message':'余额已更新，调整已写入收支与管理日志'}

class Plugins(BaseModel):
    installed:list[str]=Field(max_length=100)

@router.put('/users/{uid}/plugins')
def plugins(uid:str,body:Plugins,u=Depends(require_admin)):
    selected=set(body.installed)
    if selected-set(BY_ID): raise HTTPException(422,'包含不存在的插件')
    for p in selected:
        if BY_ID[p].get('parent') and BY_ID[p]['parent'] not in selected: raise HTTPException(409,BY_ID[p]['name']+'缺少所需标准插件')
    with connect(True) as db:
        target(db,uid)
        old=[r[0] for r in db.execute('SELECT plugin_id FROM installed WHERE user_id=?',(uid,))]
        if 'downloader' in old and 'downloader' not in selected and db.execute("SELECT 1 FROM downloads WHERE user_id=? AND status IN ('queued','downloading')",(uid,)).fetchone(): raise HTTPException(409,'请等待该账号下载任务结束')
        for p in set(old)-selected: db.execute('DELETE FROM installed WHERE user_id=? AND plugin_id=?',(uid,p))
        for p in selected-set(old): db.execute('INSERT INTO installed VALUES(?,?,?)',(uid,p,now()))
        audit(db,u,'修改插件安装状态',uid,old,sorted(selected))
    return {'message':'插件安装状态已更新，历史数据保留'}

class ProgressRow(BaseModel):
    plugin_id:str=Field(min_length=1,max_length=60)
    key:str=Field(min_length=1,max_length=200)
    value:object

class Progress(BaseModel):
    rows:list[ProgressRow]=Field(max_length=1000)

@router.put('/users/{uid}/progress')
def progress(uid:str,body:Progress,u=Depends(require_admin)):
    values=[(uid,r.plugin_id,r.key,json.dumps(r.value,ensure_ascii=False)) for r in body.rows]
    if len({(v[1],v[2]) for v in values})!=len(values): raise HTTPException(422,'同一插件内不能有重复键')
    if any(v[1] not in BY_ID for v in values): raise HTTPException(422,'插件不存在')
    with connect(True) as db:
        target(db,uid); old=[dict(r) for r in db.execute('SELECT plugin_id,key,value FROM progress WHERE user_id=?',(uid,))]
        db.execute('DELETE FROM progress WHERE user_id=?',(uid,))
        db.executemany('INSERT INTO progress VALUES(?,?,?,?)',values)
        audit(db,u,'替换插件数据',uid,old,body.model_dump())
    return {'message':'插件数据已保存'}

class EventRow(BaseModel):
    kind:str=Field(min_length=1,max_length=80)
    payload:object

@router.post('/users/{uid}/events')
def add_event(uid:str,body:EventRow,u=Depends(require_admin)):
    with connect(True) as db:
        target(db,uid)
        cur=db.execute('INSERT INTO events(user_id,kind,payload,created_at) VALUES(?,?,?,?)',(uid,body.kind,json.dumps(body.payload,ensure_ascii=False),now()))
        audit(db,u,'新增事件',uid,after=body.model_dump()|{'id':cur.lastrowid})
    return {'message':'事件已新增'}

@router.delete('/users/{uid}/events/{event_id}')
def delete_event(uid:str,event_id:int,u=Depends(require_admin)):
    with connect(True) as db:
        old=db.execute('SELECT * FROM events WHERE user_id=? AND id=?',(uid,event_id)).fetchone()
        if not old: raise HTTPException(404,'事件不存在')
        db.execute('DELETE FROM events WHERE user_id=? AND id=?',(uid,event_id))
        audit(db,u,'删除事件',uid,dict(old))
    return {'message':'事件已删除'}

@router.delete('/users/{uid}')
def delete_user(uid:str,u=Depends(require_admin)):
    with connect(True) as db:
        old=target(db,uid)
        if uid==u['id']: raise HTTPException(409,'不能删除当前登录的管理员')
        if old['role']=='admin' and db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]<=1: raise HTTPException(409,'至少保留一个管理员')
        if db.execute("SELECT 1 FROM downloads WHERE user_id=? AND status IN ('queued','downloading')",(uid,)).fetchone(): raise HTTPException(409,'该账号有处理中的下载任务')
        if db.execute("SELECT 1 FROM ai_turns WHERE user_id=? AND status='running'",(uid,)).fetchone() or db.execute("SELECT 1 FROM import_jobs WHERE user_id=? AND status IN ('queued','running')",(uid,)).fetchone():raise HTTPException(409,'请等待该账号的回答或文档识别完成后再删除')
        for table in ['wallpapers','practice_sessions','api_monitors','ai_turns','ai_threads','ai_prompts','assistants','vaults','import_jobs','library_nodes','listening_segments','sessions','installed','balances','ledger','progress','events','downloads']: db.execute('DELETE FROM '+table+' WHERE user_id=?',(uid,))
        db.execute('DELETE FROM users WHERE id=?',(uid,))
        audit(db,u,'删除账号及全部业务数据',uid,public_user(old))
    return {'message':'账号及其业务数据已删除，管理日志保留'}

class Rules(BaseModel):
    checkin_reward:int=Field(ge=0,le=1000000)
    draw_cost:int=Field(ge=1,le=1000000)
    draw_probabilities:dict[Literal['SSR','SR','R'],int]
    @model_validator(mode='after')
    def probabilities(self):
        if set(self.draw_probabilities)!={'SSR','SR','R'} or sum(self.draw_probabilities.values())!=100 or any(v<0 or v>100 for v in self.draw_probabilities.values()): raise ValueError('概率应包含 SSR/SR/R 且合计为 100')
        return self

@router.get('/rules')
def rules(u=Depends(require_admin)):
    from .plugins.collection import CONFIG
    with connect() as db: return {k:setting(db,k,v) for k,v in {'checkin_reward':10,'draw_cost':CONFIG['cost'],'draw_probabilities':CONFIG['probabilities']}.items()}

@router.put('/rules')
def save_rules(body:Rules,u=Depends(require_admin)):
    with connect(True) as db:
        old={k:setting(db,k,None) for k in body.model_dump()}
        for k,v in body.model_dump().items(): db.execute('INSERT INTO settings VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(k,json.dumps(v),now()))
        audit(db,u,'修改全局规则',before=old,after=body.model_dump())
    return {'message':'全局规则已生效'}

@router.get('/audit')
def audits(page:int=Query(1,ge=1),u=Depends(require_admin)):
    with connect() as db:
        rows=db.execute('SELECT a.*,u.username AS actor FROM audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 30 OFFSET ?',((page-1)*30,)).fetchall()
        return {'rows':[dict(r) for r in rows],'total':db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],'page':page}

def source(kind):
    from .plugins.vocabulary import EXAM
    from .plugins.collection import CONFIG
    from .plugins.music import tracks
    from .plugins.quotes import DEFAULT_QUOTES,PACK
    if kind=='words': return EXAM,'name'
    if kind=='cards': return CONFIG['cards'],'id'
    if kind=='tracks': return tracks(),'id'
    if kind=='quotes': return DEFAULT_QUOTES+PACK,'id'
    raise HTTPException(404,'内容类型不存在')

@router.get('/content/{kind}')
def get_content(kind:str,q:str=Query('',max_length=100),page:int=Query(1,ge=1),u=Depends(require_admin)):
    base,key=source(kind)
    with connect() as db: rows=items(db,kind,base,key)
    filtered=[r for r in rows if q.casefold() in json.dumps(r,ensure_ascii=False).casefold()]
    return {'rows':filtered[(page-1)*20:page*20],'total':len(filtered),'page':page}

class Content(BaseModel):
    value:dict

@router.put('/content/{kind}/{entry_id:path}')
def save_content(kind:str,entry_id:str,body:Content,u=Depends(require_admin)):
    base,key=source(kind); value=body.value.copy();value['id']=entry_id
    if len(entry_id)>200: raise HTTPException(422,'内容 ID 过长')
    def text(field,limit):
        if not isinstance(value.get(field),str) or not 0<len(value[field])<=limit: raise HTTPException(422,field+' 内容无效')
    with connect(True) as db:
        old=next((r for r in items(db,kind,base,key) if r['id']==entry_id),None)
        if kind=='words':
            text('name',100)
            if not isinstance(value.get('trans'),list) or not value['trans'] or any(not isinstance(v,str) or len(v)>2000 for v in value['trans']): raise HTTPException(422,'trans 应为非空释义数组')
        if kind=='quotes':
            text('text',2000);text('author',200)
            if value.get('audio'):
                from .plugins.quotes import VOICE
                path=(VOICE/str(value['audio'])).resolve()
                if not path.is_relative_to(VOICE.resolve()) or not path.is_file(): raise HTTPException(422,'语音文件需先放入服务端 content/voice，填写该目录下的文件名')
        if kind in ('cards','tracks'):
            if not old: raise HTTPException(422,'图像和音频条目需先由服务端导入资源')
            text('name',200)
            if kind=='cards':
                if value.get('rarity') not in ('SSR','SR','R'): raise HTTPException(422,'稀有度应为 SSR / SR / R')
                value['image']=old['image']
            else:
                text('artist',200)
                if not isinstance(value.get('lyrics'),list) or len(value['lyrics'])>1000: raise HTTPException(422,'歌词格式无效')
                for line in value['lyrics']:
                    if not isinstance(line,dict) or not isinstance(line.get('text'),str) or len(line['text'])>1000 or not isinstance(line.get('time'),(float,int)) or line['time']<0: raise HTTPException(422,'歌词需包含 time 秒数与 text 文本')
                value['lyrics'].sort(key=lambda l:l['time'])
                value['file']=old['file'];value['duration']=old['duration']
        db.execute('INSERT INTO content_edits VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value=excluded.value',(kind,entry_id,json.dumps(value,ensure_ascii=False)))
        audit(db,u,'修改内容：'+kind+':'+entry_id,before=old,after=value)
    return {'message':'内容已保存，立即生效'}

@router.delete('/content/{kind}/{entry_id:path}')
def delete_content(kind:str,entry_id:str,u=Depends(require_admin)):
    base,key=source(kind)
    with connect(True) as db:
        old=next((r for r in items(db,kind,base,key) if r['id']==entry_id),None)
        if not old: raise HTTPException(404,'内容不存在')
        if kind=='cards' and sum(r['rarity']==old['rarity'] for r in items(db,kind,base,key))<=1: raise HTTPException(409,'每个抽卡稀有度至少保留一张卡片')
        db.execute('INSERT INTO content_edits VALUES(?,?,NULL) ON CONFLICT(kind,id) DO UPDATE SET value=NULL',(kind,entry_id))
        audit(db,u,'删除内容：'+kind+':'+entry_id,before=old)
    return {'message':'内容已移除，原始资源文件保留'}

class QuoteSchedule(BaseModel):
    day:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    quote_id:str=Field(min_length=1,max_length=100)
@router.get('/quote-schedule')
def quote_schedule(u=Depends(require_admin)):
    from .plugins.quotes import DEFAULT_QUOTES,PACK
    with connect() as d:return {'schedule':[dict(r) for r in d.execute('SELECT * FROM quote_schedule ORDER BY day')],'quotes':items(d,'quotes',DEFAULT_QUOTES+PACK)}
@router.put('/quote-schedule')
def schedule_quote(body:QuoteSchedule,u=Depends(require_admin)):
    from datetime import date
    from .core import today
    from .plugins.quotes import DEFAULT_QUOTES,PACK
    try:date.fromisoformat(body.day)
    except ValueError:raise HTTPException(422,'日期无效')
    if body.day<today():raise HTTPException(422,'请选择今天或未来的日期')
    with connect(True) as d:
        if not any(q['id']==body.quote_id for q in items(d,'quotes',DEFAULT_QUOTES+PACK)):raise HTTPException(404,'语录不存在')
        before=d.execute('SELECT quote_id FROM quote_schedule WHERE day=?',(body.day,)).fetchone()
        d.execute('INSERT INTO quote_schedule VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET quote_id=excluded.quote_id,updated_at=excluded.updated_at',(body.day,body.quote_id,now()))
        audit(d,u,'quote.schedule',before=dict(before) if before else None,after=body.model_dump())
    return {'message':'每日语录已安排'}
@router.delete('/quote-schedule/{day}')
def unschedule_quote(day:str,u=Depends(require_admin)):
    with connect(True) as d:
        before=d.execute('SELECT * FROM quote_schedule WHERE day=?',(day,)).fetchone()
        d.execute('DELETE FROM quote_schedule WHERE day=?',(day,));audit(d,u,'quote.unschedule',before=dict(before) if before else None,after={'day':day})
    return {'message':'已恢复随机语录'}
