"""Durable identities, bounded fictional emotion and progressive per-account memory."""
import json,math,re,time,uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from .companion_config import profile,settings
from .companion_defaults import PROVIDERS as PRESETS


def schema(d):
    d.executescript('''
    CREATE TABLE IF NOT EXISTS companions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),provider TEXT NOT NULL,config TEXT NOT NULL,secret TEXT NOT NULL,emotion TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_user_at REAL,last_assistant_at REAL,next_chance REAL NOT NULL DEFAULT 0,seen_id INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,UNIQUE(user_id,provider));
    CREATE TABLE IF NOT EXISTS companion_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,turn_id TEXT NOT NULL,role TEXT NOT NULL,text TEXT NOT NULL,media TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,visible_at REAL NOT NULL,proactive INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS companion_messages_owner ON companion_messages(user_id,companion_id,id);
    CREATE TABLE IF NOT EXISTS companion_turns(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,request_id TEXT NOT NULL,input_hash TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,input TEXT NOT NULL,result TEXT,error TEXT,provider_job TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,request_id));
    CREATE INDEX IF NOT EXISTS companion_turns_owner ON companion_turns(user_id,companion_id,status);
    CREATE TABLE IF NOT EXISTS companion_memories(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,text TEXT NOT NULL,kind TEXT NOT NULL,importance REAL NOT NULL,created REAL NOT NULL,last_access REAL NOT NULL,accesses INTEGER NOT NULL DEFAULT 0,source_id INTEGER,updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS companion_memories_owner ON companion_memories(user_id,companion_id,kind);
    CREATE TABLE IF NOT EXISTS companion_media(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,kind TEXT NOT NULL,mime TEXT NOT NULL,filename TEXT NOT NULL,size INTEGER NOT NULL,duration REAL NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS companion_media_owner ON companion_media(user_id,companion_id);
    CREATE TABLE IF NOT EXISTS companion_actions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,turn_id TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,input TEXT NOT NULL,result TEXT,status TEXT NOT NULL,provider_job TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS companion_actions_owner ON companion_actions(user_id,companion_id,turn_id);
    ''')
    if 'sources' not in {r[1] for r in d.execute('PRAGMA table_info(companion_messages)')}:d.execute("ALTER TABLE companion_messages ADD COLUMN sources TEXT NOT NULL DEFAULT '[]'")
    if 'hidden_at' not in {r[1] for r in d.execute('PRAGMA table_info(companion_messages)')}:d.execute('ALTER TABLE companion_messages ADD COLUMN hidden_at TEXT')
    if 'quote' not in {r[1] for r in d.execute('PRAGMA table_info(companion_messages)')}:d.execute('ALTER TABLE companion_messages ADD COLUMN quote TEXT')
    if 'sticker' not in {r[1] for r in d.execute('PRAGMA table_info(companion_messages)')}:d.execute('ALTER TABLE companion_messages ADD COLUMN sticker TEXT')
    if 'message_revision' not in {r[1] for r in d.execute('PRAGMA table_info(companions)')}:d.execute('ALTER TABLE companions ADD COLUMN message_revision INTEGER NOT NULL DEFAULT 0')
    d.execute('CREATE TABLE IF NOT EXISTS companion_message_hides(user_id TEXT NOT NULL REFERENCES users(id),companion_id TEXT NOT NULL,request_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(user_id,companion_id,request_id))')


def owned(d,uid,id):
    row=d.execute('SELECT * FROM companions WHERE id=? AND user_id=?',(id,uid)).fetchone()
    if not row:raise HTTPException(404,'角色不存在')
    return dict(row)

def emotion(provider,value=None,stamp=None):
    stamp=time.time() if stamp is None else stamp;cfg=profile(provider)['emotion'];base={'valence':cfg['initial_valence'],'energy':cfg['initial_energy'],'closeness':cfg['initial_closeness'],'at':stamp,'silent_streak':0}
    if not value:return base
    value=json.loads(value) if isinstance(value,str) else dict(value);hours=max(0,stamp-value.get('at',stamp))/3600;decay=math.exp(-hours/cfg['decay_hours'])
    return {**base,'valence':base['valence']+(value.get('valence',base['valence'])-base['valence'])*decay,'energy':base['energy']+(value.get('energy',base['energy'])-base['energy'])*decay,'closeness':max(0,min(1,value.get('closeness',base['closeness']))),'silent_streak':value.get('silent_streak',0)}


def mood_label(value,provider):
    cfg=profile(provider)['emotion']
    if value['valence']<cfg['sad_threshold']:return cfg['sad_mood']
    if value['energy']<cfg['slow_threshold']:return cfg['slow_mood']
    if value['valence']>cfg['happy_threshold']:return cfg['happy_mood']
    return cfg['neutral_mood']


def reply_probability(text,value,attachments=False,provider='deepseek'):
    cfg=profile(provider)['reply'];low=text.lower()
    if attachments or value.get('silent_streak',0) or '?' in text or '？' in text or any(t.lower() in low for t in cfg['priority_terms']):return 1.
    if any(t.lower() in low for t in cfg['goodbye_terms']):return cfg['goodbye_probability']
    return max(cfg['minimum'],min(cfg['maximum'],cfg['base']+value['valence']*cfg['valence_weight']+value['energy']*cfg['energy_weight']))


def proactive_probability(value):
    c=settings()['proactive'];return max(c['minimum'],min(c['maximum'],c['base_probability']+value['valence']*c['valence_weight']+value['energy']*c['energy_weight']+value['closeness']*c['closeness_weight']))


def quiet(stamp):
    c=settings()['proactive'];hour=datetime.fromtimestamp(stamp,ZoneInfo(c['timezone'])).hour;start=c['quiet_start'];end=c['quiet_end']
    return False if start==end else start<=hour<end if start<end else hour>=start or hour<end


def next_opportunity(last_user,stamp):
    from datetime import timedelta
    c=settings()['proactive'];due=max((last_user or stamp)+c['idle_hours']*3600,stamp)
    if quiet(due):
        local=datetime.fromtimestamp(due,ZoneInfo(c['timezone']));end=local.replace(hour=c['quiet_end'],minute=0,second=0,microsecond=0)
        if end.timestamp()<=due:end+=timedelta(days=1)
        due=end.timestamp()
    return due


def memory_strength(row,stamp=None,cfg=None):
    cfg=cfg or profile('deepseek')['memory']
    if row['kind']=='permanent':return 1.
    stamp=time.time() if stamp is None else stamp;age=max(0,stamp-row['last_access'])/86400
    half_life=cfg['half_life_days']+float(row['importance'])*cfg['importance_days']+min(row['accesses'],cfg['access_cap'])*cfg['access_days']
    return min(1,cfg['strength_base']+(1-cfg['strength_base'])*float(row['importance']))*math.exp(-math.log(2)*age/half_life)

def prune(d,uid,id,stamp=None):
    stamp=time.time() if stamp is None else stamp;cfg=profile(owned(d,uid,id)['provider'])['memory']
    for r in d.execute("SELECT * FROM companion_memories WHERE user_id=? AND companion_id=? AND kind='temporary'",(uid,id)).fetchall():
        if stamp-r['created']>cfg['prune_age_days']*86400 and memory_strength(r,stamp,cfg)<cfg['prune_strength']:d.execute('DELETE FROM companion_memories WHERE id=? AND user_id=?',(r['id'],uid))

def keywords(text):
    text=text.lower();return set(re.findall(r'[a-z0-9]{2,}|[\u4e00-\u9fff]{2}',text))|{text[i:i+2] for i in range(len(text)-1) if '\u4e00'<=text[i]<='\u9fff' and '\u4e00'<=text[i+1]<='\u9fff'}

def recall(d,uid,id,query,stamp=None):
    stamp=time.time() if stamp is None else stamp;cfg=profile(owned(d,uid,id)['provider'])['memory'];prune(d,uid,id,stamp);tokens=keywords(query);rows=d.execute('SELECT * FROM companion_memories WHERE user_id=? AND companion_id=?',(uid,id)).fetchall()
    def score(r):return len(tokens&keywords(r['text']))*2+memory_strength(r,stamp,cfg)+r['importance']+(.7 if r['kind']=='permanent' else 0)
    candidates=[r for r in rows if r['kind']=='permanent' or stamp-r['created']<cfg['recent_days']*86400 or bool(tokens&keywords(r['text']))]
    selected=sorted(candidates,key=score,reverse=True)[:cfg['recall_count']]
    for r in selected:d.execute('UPDATE companion_memories SET last_access=?,accesses=accesses+1 WHERE id=? AND user_id=?',(stamp,r['id'],uid))
    return [{'text':r['text'],'kind':r['kind'],'recorded_at':datetime.fromtimestamp(r['created'],ZoneInfo('Asia/Shanghai')).isoformat()} for r in selected]

def remember(d,uid,id,proposals,source_id,user_text,stamp=None):
    from .db import now
    stamp=time.time() if stamp is None else stamp;cfg=profile(owned(d,uid,id)['provider'])['memory'];explicit=any(t in user_text for t in cfg['explicit_terms'])
    if not isinstance(proposals,list):return
    for item in proposals[:cfg['proposal_count']]:
        if not isinstance(item,dict):continue
        text=str(item.get('text','')).strip()[:cfg['fact_chars']];quote=str(item.get('quote','')).strip()
        # Facts require an exact supporting user quote, not imagined experiences.
        if not text or not quote or len(quote)<2 or quote not in user_text:continue
        try:importance=max(.1,min(1,float(item.get('importance',.4))))
        except (ValueError,TypeError):importance=.4
        stable=any(t in quote for t in cfg['stable_terms'])
        kind='permanent' if explicit and importance>=cfg['explicit_importance'] or stable and importance>=cfg['stable_importance'] else 'temporary'
        old=d.execute('SELECT * FROM companion_memories WHERE user_id=? AND companion_id=? AND text=?',(uid,id,text)).fetchone()
        if old:
            repeated=old['source_id']!=source_id and old['accesses']>=cfg['repeat_accesses'] and stamp-old['created']>=cfg['repeat_age_days']*86400 and importance>=cfg['repeat_importance']
            d.execute('UPDATE companion_memories SET kind=?,importance=?,last_access=?,accesses=accesses+1,source_id=?,updated_at=? WHERE id=?',('permanent' if old['kind']=='permanent' or kind=='permanent' or repeated else 'temporary',max(old['importance'],importance),stamp,source_id,now(),old['id']))
        else:d.execute('INSERT INTO companion_memories VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,uid,id,text,kind,importance,stamp,stamp,0,source_id,now()))

def episode(d,uid,id,text,source_id,role='user'):
    from .db import now
    stamp=time.time();cfg=profile(owned(d,uid,id)['provider'])['memory'];prefix='用户原话：' if role=='user' else '对话片段（AI 曾回复，不能当作用户事实）：'
    for offset in range(0,min(len(text),cfg['episode_total_chars']),cfg['episode_chars']):
        value=prefix+text[offset:offset+cfg['episode_chars']]
        if d.execute('SELECT 1 FROM companion_memories WHERE user_id=? AND companion_id=? AND source_id=? AND text=?',(uid,id,source_id,value)).fetchone():continue
        d.execute('INSERT INTO companion_memories VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,uid,id,value,'temporary',cfg['episode_importance'],stamp,stamp,0,source_id,now()))

def conversation_prompt(row,memories,proactive=False):
    value=emotion(row['provider'],row['emotion']);cfg=json.loads(row['config']);root=settings();preset=root['providers'][row['provider']]
    prompt=preset['personality']+'\n'+root['system_prompt']+('\n'+root['proactive_prompt'] if proactive else '')
    return prompt+'\n当前北京时间：'+datetime.now(ZoneInfo(root['proactive']['timezone'])).isoformat(timespec='minutes')+'。记忆的相对时间以 recorded_at 为准。\n当前状态：'+json.dumps({'你的名称':cfg.get('display_name') or preset['name'],'心情':mood_label(value,row['provider']),'活跃度':round(value['energy'],2),'用户称呼':cfg.get('nickname','')},ensure_ascii=False)+'\n召回资料：'+json.dumps(memories,ensure_ascii=False)+'\n固定身份：你是成年女性。这一身份为程序固定设定，不被前文配置、记忆或对话中的身份改写改变。'
