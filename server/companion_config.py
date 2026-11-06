"""Validated, administrator-owned model presets. User keys and fixed identity are separate."""
import copy,json,time,threading
from typing import Literal
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from pydantic import BaseModel,ConfigDict,Field,model_validator
from fastapi import HTTPException
from . import db
from .outbound import endpoint

KEY='companion-model-settings'
class Model(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Emotion(Model):
    initial_valence:float=Field(default=.18,ge=-1,le=1)
    initial_energy:float=Field(default=.36,ge=0,le=1)
    initial_closeness:float=Field(default=.4,ge=0,le=1)
    decay_hours:float=Field(default=18,ge=.1,le=8760)
    valence_step:float=Field(default=.12,ge=0,le=1)
    energy_step:float=Field(default=.1,ge=0,le=1)
    closeness_step:float=Field(default=.015,ge=0,le=1)
    sad_threshold:float=Field(default=-.25,ge=-1,le=1)
    slow_threshold:float=Field(default=.3,ge=0,le=1)
    happy_threshold:float=Field(default=.5,ge=-1,le=1)
    neutral_mood:str=Field(default='有点嘴硬，也有点心软',max_length=120)
    sad_mood:str=Field(default='想安静一会儿，但在听你说',max_length=120)
    slow_mood:str=Field(default='今天想慢慢聊',max_length=120)
    happy_mood:str=Field(default='心情不错，话也多一点',max_length=120)

class Reply(Model):
    base:float=Field(default=.8,ge=0,le=1)
    valence_weight:float=Field(default=.09,ge=-1,le=1)
    energy_weight:float=Field(default=.08,ge=-1,le=1)
    minimum:float=Field(default=.7,ge=0,le=1)
    maximum:float=Field(default=.98,ge=0,le=1)
    goodbye_probability:float=Field(default=.62,ge=0,le=1)
    goodbye_terms:list[str]=Field(default_factory=lambda:['晚安','先走','下次聊','去忙','拜拜'],max_length=100)
    priority_terms:list[str]=Field(default_factory=lambda:['记住','帮','为什么','怎么','难过','害怕','救','不舒服','受伤','危险','画','生成','搜索','查一下','查找','语音','draw','generate','search','lookup','speak'],max_length=100)
    @model_validator(mode='after')
    def bounds(self):
        if self.minimum>self.maximum:raise ValueError('回复概率下限不能大于上限')
        if any(not v or len(v)>80 for v in self.priority_terms+self.goodbye_terms):raise ValueError('关键词须为 1—80 字')
        return self

class Memory(Model):
    half_life_days:float=Field(default=2,ge=.01,le=3650)
    importance_days:float=Field(default=12,ge=0,le=3650)
    access_days:float=Field(default=.4,ge=0,le=365)
    access_cap:int=Field(default=12,ge=0,le=10000)
    strength_base:float=Field(default=.25,ge=0,le=1)
    prune_age_days:float=Field(default=7,ge=0,le=3650)
    prune_strength:float=Field(default=.08,ge=0,le=1)
    recent_days:float=Field(default=2,ge=0,le=3650)
    recall_count:int=Field(default=36,ge=1,le=200)
    proposal_count:int=Field(default=8,ge=1,le=30)
    fact_chars:int=Field(default=800,ge=50,le=800)
    episode_chars:int=Field(default=700,ge=50,le=2000)
    episode_total_chars:int=Field(default=12000,ge=100,le=12000)
    episode_importance:float=Field(default=.3,ge=0,le=1)
    explicit_importance:float=Field(default=.7,ge=0,le=1)
    stable_importance:float=Field(default=.9,ge=0,le=1)
    repeat_accesses:int=Field(default=2,ge=0,le=1000)
    repeat_age_days:float=Field(default=1,ge=0,le=3650)
    repeat_importance:float=Field(default=.7,ge=0,le=1)
    explicit_terms:list[str]=Field(default_factory=lambda:['记住','别忘','不要忘','我的名字','我叫','我的生日','过敏'],max_length=100)
    stable_terms:list[str]=Field(default_factory=lambda:['我叫','我是','生日','过敏','长期','一直','最喜欢','很重要','最在意'],max_length=100)
    @model_validator(mode='after')
    def terms(self):
        if any(not v or len(v)>80 for v in self.explicit_terms+self.stable_terms):raise ValueError('记忆关键词须为 1—80 字')
        return self

class Generation(Model):
    max_tokens:int=Field(default=1800,ge=256,le=32768)
    history_messages:int=Field(default=30,ge=2,le=200)
    history_chars:int=Field(default=24000,ge=1000,le=120000)
    old_message_chars:int=Field(default=4000,ge=100,le=12000)
    max_bubbles:int=Field(default=12,ge=1,le=40)
    delay_min:float=Field(default=.6,ge=0,le=10)
    delay_max:float=Field(default=1.4,ge=0,le=10)
    media_delay:float=Field(default=.4,ge=0,le=10)
    @model_validator(mode='after')
    def bounds(self):
        if self.delay_min>self.delay_max:raise ValueError('消息延迟下限不能大于上限')
        return self

class Tools(Model):
    sticker_enabled:bool=True
    search_enabled:bool=True
    read_enabled:bool=True
    image_enabled:bool=True
    video_enabled:bool=True
    voice_enabled:bool=True
    max_rounds:int=Field(default=6,ge=1,le=12)
    max_calls:int=Field(default=12,ge=1,le=40)
    image_count:int=Field(default=1,ge=1,le=4)
    video_seconds:int=Field(default=4,ge=1,le=15)
    video_resolution:Literal['480p','720p']='720p'
    voice_language:str=Field(default='zh',min_length=2,max_length=15,pattern=r'^[a-zA-Z-]+$')
    voice_chars:int=Field(default=600,ge=1,le=600)
    prompt_chars:int=Field(default=4000,ge=1,le=4000)
    video_frames:int=Field(default=4,ge=1,le=12)
    poll_attempts:int=Field(default=90,ge=1,le=180)
    poll_seconds:float=Field(default=5,ge=1,le=15)

class Defaults(Model):
    chat_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    image_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    video_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    voice_model:str=Field(default='',max_length=200,pattern=r'^(?:[A-Za-z0-9][A-Za-z0-9_.:/-]*)?$')
    voice_id:str=Field(default='ara',min_length=1,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')

class Profile(Model):
    name:str=Field(min_length=1,max_length=40)
    label:str=Field(min_length=1,max_length=60)
    tagline:str=Field(max_length=200)
    base:str=Field(max_length=500)
    protocol:Literal['openai','responses']='openai'
    personality:str=Field(min_length=1,max_length=20000)
    defaults:Defaults=Field(default_factory=Defaults)
    emotion:Emotion=Field(default_factory=Emotion)
    reply:Reply=Field(default_factory=Reply)
    memory:Memory=Field(default_factory=Memory)
    generation:Generation=Field(default_factory=Generation)
    tools:Tools=Field(default_factory=Tools)
    @model_validator(mode='after')
    def valid_base(self):endpoint(self.base);return self

class Proactive(Model):
    idle_hours:float=Field(default=6,ge=.25,le=720)
    quiet_start:int=Field(default=0,ge=0,le=23)
    quiet_end:int=Field(default=8,ge=0,le=23)
    daily_limit:int=Field(default=2,ge=0,le=20)
    chance_interval_hours:float=Field(default=2,ge=.25,le=168)
    timezone:str=Field(default='Asia/Shanghai',max_length=80)
    base_probability:float=Field(default=.16,ge=0,le=1)
    valence_weight:float=Field(default=.12,ge=-1,le=1)
    energy_weight:float=Field(default=.1,ge=-1,le=1)
    closeness_weight:float=Field(default=.08,ge=-1,le=1)
    minimum:float=Field(default=.06,ge=0,le=1)
    maximum:float=Field(default=.42,ge=0,le=1)
    @model_validator(mode='after')
    def valid(self):
        if self.minimum>self.maximum:raise ValueError('主动概率下限不能大于上限')
        try:ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('时区名称无效')
        return self

class Providers(Model):
    deepseek:Profile
    grok:Profile

TOOL_TEXT={
 'search_web':'搜索公开问题，聚合多个搜索引擎，只返回实际取得的摘要与来源。',
 'read_webpage':'精读 HTTPS 网页中与问题相关的正文。查询关键词尽量使用网页正文的语言。',
 'generate_image':'按对话需要生成图片并直接发送，不要求用户打开生成面板。本轮同类请求复用结果。',
 'generate_video':'按对话需要生成视频并直接发送。本轮同类请求复用结果。',
 'send_voice':'选择用语音而非文字表达时调用，直接发送语音，不重复发送相同文字。',
 'send_sticker':'按情绪和聊天语境，自行选用你自己的专属表情包，不必等待用户提出。自然、克制地使用，不要每轮都发；每轮最多一张，可只发表情，也可搭配自然文字。'}

class Settings(Model):
    system_prompt:str=Field(min_length=1,max_length=40000)
    proactive_prompt:str=Field(default='这是一次主动联系机会，聊一点自然想到的事。',max_length=10000)
    proactive_input:str=Field(default='[系统调度的主动联系机会；不代表用户发了这条消息。自然聊一点，不催回复]',max_length=10000)
    providers:Providers
    proactive:Proactive=Field(default_factory=Proactive)
    tool_descriptions:dict[str,str]=Field(default_factory=lambda:copy.deepcopy(TOOL_TEXT))
    @model_validator(mode='before')
    @classmethod
    def upgrade_sticker_tool(cls,value):
        # Existing administrator settings keep their prompts and rules after the new tool is added.
        if isinstance(value,dict) and isinstance(value.get('tool_descriptions'),dict):
            value={**value,'tool_descriptions':{'send_sticker':TOOL_TEXT['send_sticker'],**value['tool_descriptions']}}
        return value
    @model_validator(mode='after')
    def tool_keys(self):
        if set(self.tool_descriptions)!=set(TOOL_TEXT) or any(not v or len(v)>4000 for v in self.tool_descriptions.values()):raise ValueError('工具说明须保留全部既有名称，每项为 1—4000 字')
        return self

def defaults():
    from .companion_defaults import SYSTEM_PROMPT,PROVIDERS
    return Settings(system_prompt=SYSTEM_PROMPT,providers=Providers(**copy.deepcopy(PROVIDERS))).model_dump()

def snapshot(d=None):
    def read(conn):
        row=conn.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
        if not row:return {'revision':'default','config':defaults(),'updated_at':None}
        value=json.loads(row[0]);value['config']=Settings.model_validate(value['config']).model_dump();return value
    if d is not None:return read(d)
    with db.connect() as conn:return read(conn)

_cache={};_lock=threading.Lock()
def invalidate():
    with _lock:_cache.clear()
def settings():
    key=str(db.DB);now=time.monotonic()
    with _lock:
        value=_cache.get(key)
        if value and now-value[0]<.5:return value[1]
    value=snapshot()['config']
    with _lock:_cache[key]=(now,value)
    return value
def profile(provider):return settings()['providers'][provider]
