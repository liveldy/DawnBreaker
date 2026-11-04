"""Bound foreground document time by server time, across tabs and devices."""
import time
from .core import state,set_state

def record(db,uid,session,document,seconds):
    stamp=time.time();entry=state(db,uid,'library','foreground-time',{})
    sessions=entry.get('sessions',{});previous=sessions.get(session);accepted=0
    if previous and previous.get('document')==document and seconds>=previous['seconds']:
        elapsed=stamp-previous['stamp']
        # Sleeping clients cannot claim an unobserved interval on resume.
        if 0<=elapsed<=40:
            accepted=min(seconds-previous['seconds'],elapsed,max(0,stamp-entry.get('stamp',stamp)),35)
    sessions[session]={'document':document,'seconds':seconds,'stamp':stamp}
    sessions={k:v for k,v in sessions.items() if 0<=stamp-v['stamp']<3600}
    sessions=dict(sorted(sessions.items(),key=lambda item:item[1]['stamp'],reverse=True)[:64])
    total=entry.get('seconds',0)+accepted
    set_state(db,uid,'library','foreground-time',{'seconds':total,'stamp':stamp if accepted>0 else entry.get('stamp',stamp),'sessions':sessions})
    return {'accepted_seconds':accepted,'total_seconds':total,'minutes':int(total//60)}

def minutes(db,uid):return int(state(db,uid,'library','foreground-time',{}).get('seconds',0)//60)
