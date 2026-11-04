"""Production regression, using a disposable account and no paid AI calls."""
import json,secrets,shlex
from pathlib import Path
import httpx
from remote import connection
uid=None
try:
 with httpx.Client(base_url='http://110.42.63.153:7780',trust_env=False,timeout=120,headers={'Origin':'http://110.42.63.153:7780'}) as c:
    r=c.post('/api/auth/register',json={'username':'release110_'+secrets.token_hex(4),'password':secrets.token_urlsafe(30)});r.raise_for_status();uid=r.json()['user']['id']
    for plugin in ['journal','library','constellation','atlas','vocabulary']:c.post('/api/catalog/'+plugin+'/install').raise_for_status()
    doc=c.post('/api/plugins/library/nodes',json={'title':'正式版验证','markdown':'原文'}).json()
    r=c.put('/api/plugins/library/nodes/'+doc['id'],json={'title':doc['title'],'markdown':'新'*501,'revision':1});r.raise_for_status()
    tasks=c.get('/api/plugins/journal').json()['tasks'];assert next(t for t in tasks if t['title']=='图书管理员')['progress']==1
    assert next(t for t in tasks if t['title']=='笔耕不辍')['progress']==500
    job=c.post('/api/plugins/library/imports',files={'file':('qa.md',b'# QA','text/markdown')}).json()
    c.delete('/api/plugins/library/imports/'+job['id']).raise_for_status();assert c.get('/api/plugins/library/nodes/'+job['document_id']).status_code==200
    families=c.get('/api/plugins/constellation').json()['families'];assert len(families)==11 and all(f['name'].isascii() and f['api_base'].startswith('https://') for f in families)
    a=c.post('/api/plugins/constellation/assistants',json={'name':'验证助手','family':'gpt','model':'qa-model','api_base':'https://api.example.com/v1'}).json()
    assert c.post('/api/plugins/constellation/models',json={'assistant_id':a['id'],'api_base':'https://other.example/v1','protocol':'openai'}).status_code==422
    t=c.post('/api/plugins/constellation/threads',json={'assistant_id':a['id']}).json()['id'];base='/api/plugins/constellation/threads/'+t
    c.put(base+'/archive',json={'archived':True}).raise_for_status();assert c.get('/api/plugins/constellation/threads',params={'assistant_id':a['id']}).json()['threads']==[]
    c.put(base+'/archive',json={'archived':False}).raise_for_status();c.delete(base).raise_for_status()
    assert c.put('/api/admin/quote-schedule',json={'day':'2099-01-01','quote_id':'sample'}).status_code==403
    speed=c.post('/api/plugins/vocabulary/speed/session',json={'mode':'learn','count':2}).json();w=speed['words'][0]
    body={'session':speed['session'],'token':w['token'],'answer':w['expected'],'mistakes':True}
    for _ in range(2):assert not c.post('/api/plugins/vocabulary/speed/answer',json=body).json()['correct']
    assert c.get('/api/plugins/vocabulary').json()['learned']==1 and c.get('/api/plugins/vocabulary').json()['today_correct']==1
    key='verification-only-'+secrets.token_hex(8)
    m=c.post('/api/plugins/atlas/monitors',json={'name':'发布验证','api_base':'https://api.example.com/v1','api_key':key}).json()
    assert key not in c.get('/api/plugins/atlas/monitors').text
    assert c.post('/api/plugins/atlas/monitors/'+m['id']+'/key').json()['key']==key
    c.delete('/api/plugins/atlas/monitors/'+m['id']).raise_for_status()
    live=c.get('/api/plugins/atlas/live?refresh=true');live.raise_for_status();assert live.json()['indexes']['general']['models']
    assert c.get('/').content==(Path(__file__).resolve().parents[1]/'dist/index.html').read_bytes()
    print('PASS: production document/milestone events, history deletion, English providers, archive/restore/delete, admin authorization, speed replay/shared records, private monitor key lifecycle and live atlas')
finally:
 if uid:
    assert len(uid)==32 and all(c in '0123456789abcdef' for c in uid)
    code="import sqlite3;d=sqlite3.connect('/var/lib/dawnbreaker/dawn.db');uid="+repr(uid)+";tables=[r[0] for r in d.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")];[(d.execute('DELETE FROM '+t+' WHERE user_id=?',(uid,))) for t in tables if t.replace('_','').isalnum() and 'user_id' in [r[1] for r in d.execute('PRAGMA table_info('+t+')')]];d.execute('DELETE FROM users WHERE id=?',(uid,));d.commit()"
    with connection() as ssh:
        _,out,err=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code));assert out.channel.recv_exit_status()==0,err.read().decode()
    print('Temporary production verification account removed')
