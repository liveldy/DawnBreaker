import json
import time
import secrets
from pydantic import BaseModel,Field
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from ..core import require_plugin, installed, state, set_state, emit, today
from ..db import connect
from ..content_store import items
from ..listening import record

MANIFEST={'id':'music','name':'弦音余韵','description':'给手边的日常配一段旋律。迷你播放器、逐句文案，让声音留在主界面。','category':'音乐','icon':'Music2','ui':'music'}
router=APIRouter(prefix='/api/plugins/music',tags=['弦音余韵'])
user=require_plugin('music')
ROOT=Path(__file__).parents[1]/'content'

def tracks():
    file=ROOT/'music.json'
    return json.loads(file.read_text(encoding='utf-8')) if file.exists() else []

@router.get('')
def get(u=Depends(user)):
    with connect() as db:
        return {'tracks':items(db,'tracks',tracks()) if installed(db,u['id'],'ancient') else []}

@router.get('/audio/{track_id}')
def audio(track_id:str,u=Depends(user)):
    with connect() as db:
        if not installed(db,u['id'],'ancient'): raise HTTPException(403,'尚未安装音乐内容')
    track=next((t for t in tracks() if t['id']==track_id),None)
    if not track: raise HTTPException(404,'曲目不存在')
    return FileResponse(ROOT/'audio'/track['file'],media_type='audio/mpeg' if track['file'].endswith('.mp3') else 'audio/wav')

class Listening(BaseModel):
    session:str=Field(min_length=8,max_length=80,pattern='^[A-Za-z0-9_-]+$')
    seconds:float=Field(ge=0,le=100000000,allow_inf_nan=False)

@router.post('/listening')
def listening(body:Listening,u=Depends(user)):
    # Players report actual playing time, not track position (seeking earns nothing).
    with connect(True) as db:
        stamp=time.time();entry=state(db,u['id'],'music','listening',{})
        sessions=entry.get('sessions',{});previous=sessions.get(body.session)
        accepted=0
        if previous and body.seconds>=previous['seconds']:
            accepted=min(body.seconds-previous['seconds'],max(0,stamp-previous['stamp']),max(0,stamp-entry.get('stamp',stamp)),35)
        sessions[body.session]={'seconds':body.seconds,'stamp':stamp}
        sessions={k:v for k,v in sessions.items() if stamp-v['stamp']<3600}
        # Paused/replayed heartbeats must not steal the active player's time window.
        set_state(db,u['id'],'music','listening',{'stamp':stamp if accepted>0 else entry.get('stamp',stamp),'sessions':sessions})
        if accepted>0:accepted=record(db,u['id'],'online-'+secrets.token_hex(12),'legacy-online',stamp-accepted,stamp,accepted)
    return {'accepted':accepted}

class Segment(BaseModel):
    id:str=Field(min_length=8,max_length=100,pattern='^[A-Za-z0-9_-]+$')
    start:float=Field(gt=0,allow_inf_nan=False)
    end:float=Field(gt=0,allow_inf_nan=False)
    seconds:float=Field(gt=0,le=120,allow_inf_nan=False)
    track_id:str=Field(max_length=80)
class Sync(BaseModel):
    account_id:str|None=None
    device_id:str=Field(min_length=8,max_length=100,pattern='^[A-Za-z0-9_-]+$')
    segments:list[Segment]=Field(min_length=1,max_length=1000)
@router.post('/sync')
def sync(body:Sync,u=Depends(user)):
    if body.account_id and body.account_id!=u['id']:raise HTTPException(409,'账号已切换，听曲记录留待原账号同步')
    from datetime import datetime
    stamp=time.time();created=datetime.fromisoformat(u['created_at']).timestamp();accepted=[];rejected=[];seconds=0
    with connect(True) as db:
        for segment in body.segments:
            if segment.end>stamp+300 or segment.start<created-300 or segment.end<=segment.start or segment.end-segment.start>121 or segment.seconds>segment.end-segment.start+.5:
                rejected.append(segment.id);continue
            seconds+=record(db,u['id'],segment.id,body.device_id,segment.start,segment.end,min(segment.seconds,segment.end-segment.start));accepted.append(segment.id)
    return {'accepted_ids':accepted,'rejected_ids':rejected,'credited_seconds':seconds,'message':'听曲记录已同步'}
