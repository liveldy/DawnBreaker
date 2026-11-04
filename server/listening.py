"""Union playback intervals across devices; retries and overlapping playback never double count."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from .core import emit
from .db import now
ZONE=ZoneInfo('Asia/Shanghai')
def record(db,uid,id,device,start,end,seconds,emit_events=True):
    if db.execute('SELECT 1 FROM listening_segments WHERE user_id=? AND id=?',(uid,id)).fetchone():return 0.0
    rows=db.execute('SELECT start,end FROM listening_segments WHERE user_id=? AND start<? AND end>? ORDER BY start',(uid,end,start)).fetchall()
    uncovered=[];cursor=start
    for row in rows:
        left=max(start,row['start']);right=min(end,row['end'])
        if left>cursor:uncovered.append((cursor,left))
        cursor=max(cursor,right)
    if cursor<end:uncovered.append((cursor,end))
    budget=min(seconds,sum(b-a for a,b in uncovered));credited=budget
    db.execute('INSERT INTO listening_segments VALUES(?,?,?,?,?,?,?,?)',(uid,id,device,start,end,seconds,credited,now()))
    if emit_events:
        for left,right in uncovered:
            while left<right and budget>0:
                local=datetime.fromtimestamp(left,ZONE);midnight=datetime.combine(local.date()+timedelta(days=1),datetime.min.time(),tzinfo=ZONE).timestamp();cut=min(right,midnight);value=min(cut-left,budget)
                if value>0:emit(db,uid,'music-listened',{'date':local.date().isoformat(),'seconds':value,'segment':id})
                budget-=value;left=cut
    return credited
def backfill(db):
    # Old online heartbeats already granted progress. Register their time windows without granting again.
    if db.execute("SELECT 1 FROM settings WHERE key='listening-intervals-v1'").fetchone():return
    import json
    for row in db.execute("SELECT id,user_id,payload,created_at FROM events WHERE kind='music-listened'").fetchall():
        payload=json.loads(row['payload']);seconds=float(payload.get('seconds',0));stamp=datetime.fromisoformat(row['created_at']).timestamp()
        if seconds>0:record(db,row['user_id'],'legacy-'+str(row['id']),'legacy',stamp-seconds,stamp,seconds,False)
    db.execute("INSERT INTO settings VALUES('listening-intervals-v1','true',?)",(now(),))
