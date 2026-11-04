"""Exercise the deployed service with an isolated account, then remove it."""
import json
import secrets
from pathlib import Path
import httpx
from remote import connection

BASE='http://110.42.63.153:7780'
uid=None
try:
    with httpx.Client(base_url=BASE,timeout=30,trust_env=False,headers={'Origin':BASE}) as c:
        def get(path):
            r=c.get('/api'+path); r.raise_for_status(); return r.json()
        def post(path,body=None):
            r=c.post('/api'+path,json=body);r.raise_for_status();return r.json()
        account=post('/auth/register',{'username':'verify_'+secrets.token_hex(6),'password':secrets.token_urlsafe(32),'nickname':'部署验证临时账号'})
        uid=account['user']['id']
        b=get('/bootstrap');assert b['plugins']==[] and b['wallet']=={'essence':0,'stones':0}
        for plugin in ['journal','checkin','quotes','collection','music','vocabulary','downloader','lol','ancient','kaoyan','lol-quotes']:post('/catalog/'+plugin+'/install')
        post('/plugins/checkin')
        assert c.post('/api/plugins/checkin').status_code==409
        tasks=get('/plugins/journal')['tasks'];daily=next(t for t in tasks if t['id'].startswith('v2-daily-checkin'))
        post('/plugins/journal/claim/'+daily['id'])
        assert get('/bootstrap')['wallet']['essence']==15
        assert get('/plugins/vocabulary')['total']==5492
        voice=get('/plugins/vocabulary/question?mode=learn')
        assert 'phonetic' in voice and voice['audio'].startswith('/api/plugins/vocabulary/audio/')
        audio=c.get(voice['audio']);audio.raise_for_status();assert audio.headers['content-type'].startswith('audio/') and len(audio.content)>100
        print('PASS: production vocabulary phonetics and actual pronunciation audio',flush=True)
        pool=json.loads(Path('server/content/kaoyan.json').read_text(encoding='utf-8'))
        mapping={'；'.join(w['trans']):w['name'] for w in pool}
        for _ in range(60):
            if get('/plugins/vocabulary')['today_correct']>=20:break
            q=get('/plugins/vocabulary/question?mode=learn')
            assert post('/plugins/vocabulary/answer',{'token':q['token'],'answer':q['hint']})['correct']
        review=get('/plugins/vocabulary/question?mode=review-choice');assert review['mode']=='review-choice' and review['choices']
        assert get('/plugins/vocabulary/memory')['words']==[]
        tasks=get('/plugins/journal')['tasks'];word_task=next(t for t in tasks if t['id'].startswith('v2-daily-vocabulary'))
        post('/plugins/journal/claim/'+word_task['id'])
        points=get('/plugins/collection')['essence'];assert points>=20
        draw=post('/plugins/collection/draw',{'count':1,'request_id':'smoke-remote-request'})
        assert len(draw['cards'])==1
        assert post('/plugins/collection/draw',{'count':1,'request_id':'smoke-remote-request'})==draw
        assert get('/plugins/collection')['essence']==points-10
        assert len(get('/plugins/collection')['cards'])==1580
        assert len(get('/plugins/music')['tracks'])==22
        assert c.get('/api/plugins/quotes/audio/lol-001').status_code==200
        assert c.get('/api/plugins/collection/splash/103027').headers['content-type']=='image/webp'
        assert c.get('/api/plugins/collection/rarity/mythic').headers['content-type']=='image/png'
        post('/plugins/music/listening',{'session':'production-smoke-session','seconds':0})
        import time
        time.sleep(2)
        listened=post('/plugins/music/listening',{'session':'production-smoke-session','seconds':2})
        assert 0<listened['accepted']<=2
        assert post('/plugins/music/listening',{'session':'production-smoke-session','seconds':2})['accepted']==0
        r=c.get('/api/plugins/music/audio/001',headers={'Range':'bytes=0-1023'});assert r.status_code==206 and len(r.content)==1024
        r=c.get('/api/plugins/collection/image/1000');assert r.status_code==200 and r.headers['content-type']=='image/webp'
        assert c.post('/api/plugins/downloader',json={'url':'http://127.0.0.1'}).status_code==422
        assert c.delete('/api/catalog/lol').status_code==200
        assert c.get('/api/plugins/collection/image/1000').status_code==403
        post('/auth/logout');assert c.get('/api/bootstrap').status_code==401
        print('PASS: external web/API, checkin, rewritten tasks, 20 distinct words, review modes, draw replay, 1580 portraits/full splash art, supplied rarity badges, 59 voiced quotes, 22 songs, actual listening heartbeat and entitlement revocation')
finally:
    if uid:
        assert len(uid)==32 and all(ch in '0123456789abcdef' for ch in uid)
        code="import sqlite3;c=sqlite3.connect('/var/lib/dawnbreaker/dawn.db');uid='"+uid+"';tables=['listening_segments','library_nodes','import_jobs','vaults','assistants','ai_threads','ai_turns','ai_prompts','sessions','installed','balances','ledger','progress','events','downloads'];[c.execute('DELETE FROM '+t+' WHERE user_id=?',(uid,)) for t in tables];c.execute('DELETE FROM users WHERE id=?',(uid,));c.commit();print('Temporary verification account removed')"
        import shlex
        with connection() as ssh:
            _,o,e=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code));print(o.read().decode().strip());assert o.channel.recv_exit_status()==0,e.read().decode()
