"""Durable per-book batches. No completion is inferred from opening a question."""
import uuid
from .core import state,set_state,today,emit
from .db import now
def phase_of(words,memory):
    pending=[memory.get(w,{}) for w in words if not memory.get(w,{}).get('memorized')]
    if any(v.get('learn_passes',0)<3 for v in pending):return 'learn'
    if any(v.get('test_passes',0)<3 for v in pending):return 'test'
    if any(v.get('review_passes',0)<3 or v.get('review_streak',0)<3 for v in pending):return 'review'
    return 'completed'
def current(db,uid,pool,book,size=None):
    key='batch:'+book;batch=state(db,uid,'vocabulary',key,{})
    settings=state(db,uid,'vocabulary','batch-settings',{'size':50})
    memory=state(db,uid,'vocabulary','memory',{});names={w['name'] for w in pool}
    previous=state(db,uid,'vocabulary','finished-batches:'+book,[])
    if batch and batch['words'] and phase_of(batch['words'],memory)=='completed':
        previous=list(dict.fromkeys(previous+batch['words']));set_state(db,uid,'vocabulary','finished-batches:'+book,previous)
        emit(db,uid,'word-batch-completed',{'date':today(),'id':batch['id'],'book':book,'count':len(batch['words'])});batch={}
    if not batch:
        eligible=[w['name'] for w in pool if w['name'] not in previous and not memory.get(w['name'],{}).get('memorized')]
        n=size or settings['size'];batch={'id':uuid.uuid4().hex,'words':eligible[:n],'created_at':now(),'book':book,'size':n}
        set_state(db,uid,'vocabulary',key,batch)
    phase=phase_of(batch['words'],memory)
    def passed(w,kind):
        v=memory.get(w,{})
        return 3 if v.get('memorized') else min(3,v.get(kind+'_passes',0),v.get('review_streak',0) if kind=='review' else 3)
    return batch|{'phase':phase,'round_progress':{k:sum(passed(w,k) for w in batch['words']) for k in ['learn','test','review']},'round_target':len(batch['words'])*3,'completed_words':len(previous),'total':len(names),'message':'复习需连续三天成功，完成三阶段各三轮后进入下一批。'}
def eligible(batch,pool,memory):
    kind=batch['phase'];key=kind+'_passes';ids=set(batch['words'])
    rows=[w for w in pool if w['name'] in ids and not memory.get(w['name'],{}).get('memorized') and (memory.get(w['name'],{}).get(key,0)<3 or kind=='review' and memory.get(w['name'],{}).get('review_streak',0)<3)]
    if kind=='review':rows=[w for w in rows if memory.get(w['name'],{}).get('review_day')!=today() and memory.get(w['name'],{}).get('review_failed_day')!=today()]
    return sorted(rows,key=lambda w:memory.get(w['name'],{}).get(key,0))
