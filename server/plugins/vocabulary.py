import json
import secrets
from datetime import date,timedelta
from ..milestones import record_word
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from ..core import require_plugin, installed, state, set_state, today, emit
from ..db import connect,now
from ..word_queue import current as current_batch,eligible as batch_eligible
from ..config import setting
from ..content_store import items

MANIFEST={'id':'vocabulary','name':'飞跃','description':'从一个单词开始。中译拼写、提示跟写与选择测试，学习记录随账号同步。','category':'学习','icon':'Feather','ui':'vocabulary'}
router=APIRouter(prefix='/api/plugins/vocabulary',tags=['飞跃'])
user=require_plugin('vocabulary')
SAMPLES=[{'name':w,'trans':[t]} for w,t in [('dawn','n. 黎明；开端'),('light','n. 光；光线'),('journey','n. 旅程'),('beyond','prep. 超越'),('memory','n. 记忆'),('collect','v. 收集'),('discover','v. 发现'),('cherish','v. 珍惜'),('achieve','v. 实现'),('persist','v. 坚持')]]
for sample,phonetic in zip(SAMPLES,['/dɔːn/','/laɪt/','/ˈdʒɜːni/','/bɪˈjɒnd/','/ˈmeməri/','/kəˈlekt/','/dɪˈskʌvə/','/ˈtʃerɪʃ/','/əˈtʃiːv/','/pəˈsɪst/']): sample['phonetic']=phonetic
WORD_FILE=Path(__file__).parents[1]/'content'/'kaoyan.json'
EXAM=json.loads(WORD_FILE.read_text(encoding='utf-8')) if WORD_FILE.exists() else []

def words(db,uid):
    return items(db,'words',EXAM,key='name') if installed(db,uid,'kaoyan') and EXAM else SAMPLES

@router.get('')
def summary(u=Depends(user)):
    with connect() as db:
        pool=words(db,u['id'])
        learned=state(db,u['id'],'vocabulary','learned',[])
        tested=state(db,u['id'],'vocabulary','tested',[])
        in_pool={w['name'] for w in pool}
        memory=state(db,u['id'],'vocabulary','memory',{})
        remembered={w for w,v in memory.items() if v.get('memorized')}
        return {'memorized':len(remembered&in_pool),'review':len(((set(learned)|set(tested))&in_pool)-remembered),'total':len(pool),'learned':len(set(learned)&in_pool),'tested':len(set(tested)&in_pool),'book':'考研词汇' if installed(db,u['id'],'kaoyan') and EXAM else '示例词汇','today_correct':db.execute("SELECT COUNT(*) FROM events WHERE user_id=? AND kind='word-practiced' AND json_extract(payload,'$.date')=?",(u['id'],today())).fetchone()[0]}

@router.get('/question')
def question(mode:str=Query(default='learn',pattern='^(learn|spell|choice|review-spell|review-choice)$'),queue:bool=False,u=Depends(user)):
    with connect(True) as db:
        pool=words(db,u['id']); tested=state(db,u['id'],'vocabulary','tested',[])
        memory=state(db,u['id'],'vocabulary','memory',{})
        pool=[w for w in pool if not memory.get(w['name'],{}).get('memorized')]
        review=mode.startswith('review-')
        if review:
            eligible=set(tested)|set(state(db,u['id'],'vocabulary','learned',[]))
            pool=[w for w in pool if w['name'] in eligible]
        if queue:
            batch=current_batch(db,u['id'],words(db,u['id']),'kaoyan' if installed(db,u['id'],'kaoyan') else 'sample');pool=batch_eligible(batch,words(db,u['id']),memory);mode={'learn':'learn','test':'spell','review':'review-spell'}.get(batch['phase'],'learn');review=mode.startswith('review-')
        remaining=[w for w in pool if w['name'] not in tested] if not review else [w for w in pool if memory.get(w['name'],{}).get('review_day')!=today()]
        if not pool:return {'empty':True,'message':'本批次今日复习已完成，明天继续；需连续复习三天。' if queue and review and batch['words'] else '已学习或测试的词汇会出现在这里。' if review else '当前词库已全部记忆。'}
        if not pool: raise HTTPException(409,'词库为空，请联系管理员补充内容')
        word=secrets.choice(remaining or pool)
        choices=[]
        if mode.endswith('choice'):
            correct='；'.join(word['trans'])
            other=list(dict.fromkeys('；'.join(w['trans']) for w in pool if w['name']!=word['name'] and '；'.join(w['trans'])!=correct))
            secrets.SystemRandom().shuffle(other)
            choices=other[:3]+[correct]; secrets.SystemRandom().shuffle(choices)
        token=secrets.token_urlsafe(16)
        set_state(db,u['id'],'vocabulary','question',{'token':token,'word':word,'mode':mode,'choices':choices,'day':today()})
        set_state(db,u['id'],'vocabulary','pronunciation',{'token':token,'word':word['name']})
        return {'token':token,'mode':mode,'prompt':word['name'] if mode.endswith('choice') else '；'.join(word['trans']),'hint':word['name'] if mode=='learn' else None,'phonetic':word.get('phonetic',''),'audio':'/api/plugins/vocabulary/audio/'+token,'choices':choices}

@router.get('/audio/{token}')
def pronunciation(token:str,u=Depends(user)):
    from ..pronunciation import voice_file
    from fastapi.responses import FileResponse
    with connect() as db: entry=state(db,u['id'],'vocabulary','pronunciation')
    if not entry or entry['token']!=token: raise HTTPException(404,'题目已更新，请使用当前词汇的朗读按钮')
    return FileResponse(voice_file(entry['word']),media_type='audio/mpeg')

class Answer(BaseModel):
    token:str=Field(max_length=80)
    answer:str=Field(max_length=500)

def grade(db,uid,q,actual):
    expected='；'.join(q['word']['trans']) if q['mode'].endswith('choice') else q['word']['name']
    correct=actual.strip().casefold()==expected.casefold()
    word=q['word']['name'];memory=state(db,uid,'vocabulary','memory',{})
    entry=memory.setdefault(word,{'correct_streak':0,'review_streak':0})
    category='learn' if q['mode'].startswith('learn') else 'review' if q['mode'].startswith('review') else 'test'
    entry[category+'_count']=entry.get(category+'_count',0)+1
    if correct and category!='review':entry[category+'_passes']=entry.get(category+'_passes',0)+1
    key='learned' if q['mode'].startswith('learn') else 'tested'
    previous=state(db,uid,'vocabulary',key,[])
    if word not in previous:previous.append(word)
    set_state(db,uid,'vocabulary',key,previous)
    record_word(db,uid,word)
    if not q['mode'].startswith('learn'):entry['correct_streak']=entry.get('correct_streak',0)+1 if correct else 0
    if q['mode'].startswith('review-'):
        if not correct:entry.update(review_streak=0,review_failed_day=today())
        elif entry.get('review_day')!=today() and entry.get('review_failed_day')!=today():
            yesterday=(date.fromisoformat(today())-timedelta(days=1)).isoformat()
            entry['review_streak']=entry.get('review_streak',0)+1 if entry.get('review_day')==yesterday else 1
            entry['review_day']=today()
            entry['review_passes']=entry.get('review_passes',0)+1
    if entry.get('correct_streak',0)>=3 and entry.get('review_streak',0)>=3:entry.update(memorized=True,memorized_at=today())
    set_state(db,uid,'vocabulary','memory',memory)
    if correct:
        key='learned' if q['mode'].startswith('learn') else 'tested'
        previous=state(db,uid,'vocabulary',key,[])
        if q['word']['name'] not in previous: previous.append(q['word']['name'])
        set_state(db,uid,'vocabulary',key,previous)
        if not q['mode'].startswith('learn'):
            # Record each tested word once per Shanghai day, without retired points.
            if not db.execute("SELECT 1 FROM events WHERE user_id=? AND kind='word-correct' AND json_extract(payload,'$.date')=? AND json_extract(payload,'$.word')=?",(uid,today(),q['word']['name'])).fetchone():
                emit(db,uid,'word-correct',{'date':today(),'word':q['word']['name']})
    return {'memorized':entry.get('memorized',False),'correct':correct,'expected':expected,'translation':'；'.join(q['word']['trans']),'message':'记住这一小步。' if correct else '再看一遍，下次会更熟悉。'}

@router.post('/answer')
def answer(body:Answer,u=Depends(user)):
    with connect(True) as db:
        q=state(db,u['id'],'vocabulary','question')
        if not q or q['token']!=body.token:raise HTTPException(409,'题目已作答或已更新，请获取下一题')
        result=grade(db,u['id'],q,body.answer)
        set_state(db,u['id'],'vocabulary','question',None)
        return result

@router.get('/memory')
def memory_library(u=Depends(user)):
    with connect() as db:
        memory=state(db,u['id'],'vocabulary','memory',{})
        return {'words':[w|{'memorized_at':memory[w['name']]['memorized_at']} for w in words(db,u['id']) if memory.get(w['name'],{}).get('memorized')]}

class SpeedStart(BaseModel):
    mode:str=Field(pattern='^(learn|learn-spell|test-copy|spell|review-copy|review-spell)$')
    count:int=Field(default=20,ge=1,le=200)
    queue:bool=False
class SpeedAnswer(BaseModel):
    session:str=Field(max_length=80)
    token:str=Field(max_length=80)
    answer:str=Field(max_length=500)
    mistakes:bool=False
    seconds:float=Field(default=0,ge=0,le=86400,allow_inf_nan=False)
@router.post('/speed/session')
def speed_session(body:SpeedStart,u=Depends(user)):
    with connect(True) as d:
        memory=state(d,u['id'],'vocabulary','memory',{});eligible=set(state(d,u['id'],'vocabulary','learned',[]))|set(state(d,u['id'],'vocabulary','tested',[]))
        pool=[w for w in words(d,u['id']) if not memory.get(w['name'],{}).get('memorized') and (not body.mode.startswith('review') or w['name'] in eligible)]
        batch=None;mode=body.mode
        if body.queue:
            batch=current_batch(d,u['id'],words(d,u['id']),'kaoyan' if installed(d,u['id'],'kaoyan') else 'sample')
            mode={'learn':('learn' if body.mode in ('learn','test-copy','review-copy') else 'learn-spell'),'test':('test-copy' if body.mode in ('learn','test-copy','review-copy') else 'spell'),'review':('review-copy' if body.mode in ('learn','test-copy','review-copy') else 'review-spell')}.get(batch['phase'],'learn')
            pool=batch_eligible(batch,words(d,u['id']),memory)
        else:secrets.SystemRandom().shuffle(pool)
        pool=pool[:body.count]
        session=secrets.token_urlsafe(18);questions=[{'token':secrets.token_urlsafe(16),'word':w,'mode':mode} for w in pool]
        d.execute("UPDATE practice_sessions SET status='interrupted',finished_at=? WHERE user_id=? AND status='running'",(now(),u['id']))
        d.execute('INSERT INTO practice_sessions(id,user_id,mode,source,batch_id,count,status,started_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?)',(session,u['id'],mode,'batch' if body.queue else 'free',batch['id'] if batch else None,len(questions),'running' if questions else 'completed',now(),None if questions else now()))
        set_state(d,u['id'],'vocabulary','speed-session',{'id':session,'questions':questions,'index':0,'results':{}})
        return {'session':session,'mode':mode,'batch':batch,'words':[{'token':q['token'],'expected':q['word']['name'],'prompt':'；'.join(q['word']['trans']),'phonetic':q['word'].get('phonetic',''),'copy':body.mode in ('learn','test-copy','review-copy')} for q in questions]}
@router.post('/speed/answer')
def speed_answer(body:SpeedAnswer,u=Depends(user)):
    with connect(True) as d:
        session=state(d,u['id'],'vocabulary','speed-session')
        if not session or session['id']!=body.session:raise HTTPException(409,'练习已结束或在其他窗口重新开始')
        if body.token in session['results']:return session['results'][body.token]
        at=session['index']
        if at>=len(session['questions']) or session['questions'][at]['token']!=body.token:raise HTTPException(409,'请按顺序完成练习')
        q=session['questions'][at]
        if body.answer.strip().casefold()!=q['word']['name'].casefold():raise HTTPException(422,'请先完成当前单词')
        result=grade(d,u['id'],q,'' if body.mistakes else body.answer)
        completed=at+1;finished=completed==len(session['questions'])
        d.execute('UPDATE practice_sessions SET completed=?,correct=correct+?,seconds=seconds+?,status=?,finished_at=? WHERE id=? AND user_id=?',(completed,int(not body.mistakes),body.seconds,'completed' if finished else 'running',now() if finished else None,body.session,u['id']))
        session['results'][body.token]=result;session['index']+=1;set_state(d,u['id'],'vocabulary','speed-session',session)
        return result

@router.get('/batch')
def batch_info(u=Depends(user)):
    with connect(True) as d:return current_batch(d,u['id'],words(d,u['id']),'kaoyan' if installed(d,u['id'],'kaoyan') else 'sample')
class BatchSettings(BaseModel):
    size:int=Field(default=50,ge=1,le=200)
@router.put('/batch/settings')
def batch_settings(body:BatchSettings,u=Depends(user)):
    with connect(True) as d:set_state(d,u['id'],'vocabulary','batch-settings',{'size':body.size})
    return {'message':'下一批次使用新的词数，当前批次保留'}
@router.get('/progress')
def progress_table(q:str=Query('',max_length=100),page:int=Query(1,ge=1),u=Depends(user)):
    with connect() as d:
        memory=state(d,u['id'],'vocabulary','memory',{});rows=[w for w in words(d,u['id']) if not q or q.casefold() in (w['name']+' '+' '.join(w['trans'])).casefold()]
        return {'total':len(rows),'page':page,'words':[w|{k:memory.get(w['name'],{}).get(k,0) for k in ['learn_count','test_count','review_count','learn_passes','test_passes','review_passes']}|{'memorized':bool(memory.get(w['name'],{}).get('memorized'))} for w in rows[(page-1)*50:page*50]],'note':'次数从本版开始逐次记录；既有已记忆状态保留。'}
@router.get('/speed/history')
def speed_history(u=Depends(user)):
    with connect() as d:return {'sessions':[dict(r) for r in d.execute('SELECT * FROM practice_sessions WHERE user_id=? ORDER BY started_at DESC LIMIT 100',(u['id'],))]}
@router.post('/speed/{id}/finish')
def finish_speed(id:str,u=Depends(user)):
    with connect(True) as d:
        if not d.execute('SELECT 1 FROM practice_sessions WHERE id=? AND user_id=?',(id,u['id'])).fetchone():raise HTTPException(404,'练习记录不存在')
        d.execute("UPDATE practice_sessions SET status='interrupted',finished_at=? WHERE id=? AND user_id=? AND status='running'",(now(),id,u['id']))
    return {'message':'练习记录已保存'}
