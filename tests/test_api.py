from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from server import db
from server.main import app, RATE
from server.core import credit, today

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB',tmp_path/'test.db')
    RATE.clear()
    with TestClient(app) as client:
        yield client

def register(c,name='tester'):
    r=c.post('/api/auth/register',json={'username':name,'password':'Test-password-2026','nickname':'测试者'})
    assert r.status_code==201,r.text
    return r.json()['user']['id']

def install(c,*ids):
    for plugin in ids:
        r=c.post('/api/catalog/'+plugin+'/install')
        assert r.status_code==200,r.text

def test_core_is_empty_and_plugin_apis_are_guarded(client):
    assert client.get('/api/bootstrap').status_code==401
    register(client)
    b=client.get('/api/bootstrap').json()
    assert b['plugins']==[] and b['wallet']=={'essence':0,'stones':0}
    for p in ['checkin','quotes','journal','vocabulary','collection','music','downloader']:
        assert client.get('/api/plugins/'+p).status_code==403
    assert client.get('/api/plugins/collection/image/1000').status_code==403
    assert len(client.get('/api/catalog').json()['plugins'])==20

def test_authentication_and_sessions(client):
    register(client)
    assert client.post('/api/auth/register',json={'username':'TESTER','password':'Test-password-2026'}).status_code==409
    raw=client.cookies.get('dawn_session')
    with db.connect() as conn:
        row=conn.execute('SELECT password FROM users').fetchone()
        assert row[0].startswith('$argon2')
        token=conn.execute('SELECT token FROM sessions').fetchone()[0]
        assert token==hashlib.sha256(raw.encode()).hexdigest()
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/bootstrap').status_code==401
    assert client.post('/api/auth/login',json={'username':'tester','password':'wrong-password'}).status_code==401
    assert client.post('/api/auth/login',json={'username':'TESTER','password':'Test-password-2026'}).status_code==200
    assert client.post('/api/profile/password',json={'current':'Test-password-2026','new':'new-password-2026'}).status_code==200
    assert client.cookies.get('dawn_session')!=raw
    client.cookies.clear()
    client.cookies.set('dawn_session',raw)
    assert client.get('/api/bootstrap').status_code==401

def test_origin_guard_profile_and_user_isolation(client):
    uid=register(client)
    assert client.patch('/api/profile',json={'nickname':'  日光  ','bio':'今天向前一步'}).status_code==200
    assert client.get('/api/bootstrap').json()['user']['nickname']=='日光'
    assert client.post('/api/catalog/checkin/install',headers={'Origin':'https://evil.example'}).status_code==403
    install(client,'checkin')
    assert client.post('/api/plugins/checkin').status_code==200
    client.post('/api/auth/logout');register(client,'other_user')
    assert client.get('/api/bootstrap').json()['wallet']['essence']==0
    assert client.get('/api/bootstrap').json()['plugins']==[]
    assert client.get('/api/wallet').json()['ledger']==[]

def test_dependencies_and_reinstallation(client):
    register(client)
    assert client.post('/api/catalog/lol/install').status_code==409
    install(client,'collection','lol')
    assert client.delete('/api/catalog/collection').status_code==409
    assert client.delete('/api/catalog/lol').status_code==200
    assert client.get('/api/plugins/collection/image/1000').status_code==403
    assert client.delete('/api/catalog/collection').status_code==200
    assert client.get('/api/plugins/collection').status_code==403
    assert client.post('/api/catalog/unknown/install').status_code==404

def test_concurrent_checkins_and_claims(client):
    uid=register(client);install(client,'checkin','journal','collection')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:client.post('/api/plugins/checkin').status_code,range(8)))
    assert results.count(200)==1 and results.count(409)==7
    assert client.get('/api/bootstrap').json()['wallet']['essence']==10
    task=next(t for t in client.get('/api/plugins/journal').json()['tasks'] if t['kind']=='每日任务')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:client.post('/api/plugins/journal/claim/'+task['id']).status_code,range(4)))
    assert results.count(200)==1
    assert client.get('/api/bootstrap').json()['wallet']['essence']==15
    assert client.get('/api/plugins/collection').json()['essence']==15
    assert client.get('/api/bootstrap').json()['wallet']['stones']==0
    client.delete('/api/catalog/checkin');install(client,'checkin')
    assert client.post('/api/plugins/checkin').status_code==409

def test_standalone_plugins_and_content(client):
    register(client);install(client,'journal','music','collection','vocabulary')
    assert client.get('/api/plugins/journal').json()['tasks'][0]['kind']=='每日任务' # vocabulary installed
    client.delete('/api/catalog/vocabulary')
    assert {t['title'] for t in client.get('/api/plugins/journal').json()['tasks']}=={'品味旋律','开抽！','旋律爱好者','绝无仅有'}
    assert client.get('/api/plugins/music').json()['tracks']==[]
    assert client.get('/api/plugins/collection').json()['cards']==[]
    install(client,'ancient','lol','vocabulary')
    assert len(client.get('/api/plugins/music').json()['tracks'])==22
    assert len(client.get('/api/plugins/collection').json()['cards'])==1580
    assert client.get('/api/plugins/vocabulary').json()['total']==10
    install(client,'kaoyan')
    assert client.get('/api/plugins/vocabulary').json()['total']==5492
    audio=client.get('/api/plugins/music/audio/001',headers={'Range':'bytes=0-1023'})
    assert audio.status_code==206 and len(audio.content)==1024
    assert client.get('/api/plugins/collection/image/1000').headers['content-type']=='image/webp'

def test_vocabulary_replay_and_duplicate_rewards(client):
    uid=register(client);install(client,'vocabulary','collection')
    q=client.get('/api/plugins/vocabulary/question?mode=learn').json()
    assert q['hint']
    body={'token':q['token'],'answer':q['hint']}
    assert client.post('/api/plugins/vocabulary/answer',json=body).json()['correct'] is True
    assert client.post('/api/plugins/vocabulary/answer',json=body).status_code==409
    assert client.get('/api/plugins/collection').json()['essence']==0
    q=client.get('/api/plugins/vocabulary/question?mode=spell').json()
    assert q['hint'] is None
    with db.connect() as conn:
        question=json.loads(conn.execute("SELECT value FROM progress WHERE user_id=? AND key='question'",(uid,)).fetchone()[0])
    assert client.post('/api/plugins/vocabulary/answer',json={'token':q['token'],'answer':question['word']['name']}).json()['correct']
    assert client.get('/api/plugins/collection').json()['essence']==0
    assert client.get('/api/plugins/vocabulary').json()['today_correct']==len({body['answer'],question['word']['name']})

def test_draw_atomic_idempotency_insufficient_funds(client):
    uid=register(client);install(client,'collection','lol')
    body={'count':10,'request_id':'test-idempotent-request'}
    assert client.post('/api/plugins/collection/draw',json=body).status_code==409
    with db.connect(True) as conn: credit(conn,uid,'essence',100,'测试初始化','test-seed')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:client.post('/api/plugins/collection/draw',json=body),range(4)))
    assert all(r.status_code==200 for r in results)
    assert all(r.json()==results[0].json() for r in results)
    data=client.get('/api/plugins/collection').json()
    outcome=results[0].json()
    assert data['essence']==outcome['refund'] and sum(c['owned'] for c in data['cards'])==sum(c['new'] for c in outcome['cards'])
    with db.connect(True) as conn:
        from server.core import balance
        amount=balance(conn,uid,'essence')
        if amount:credit(conn,uid,'essence',-amount,'测试清空','empty-seed')
    assert client.post('/api/plugins/collection/draw',json={'count':1,'request_id':'different-request'}).status_code==409

def test_downloader_rejects_non_public_and_unsupported_urls(client):
    register(client);install(client,'downloader')
    for url in ['http://127.0.0.1:7779/api/health','file:///etc/passwd','https://example.com/video','https://youtube.com@127.0.0.1/a','https://youtube.com:22/a']:
        assert client.post('/api/plugins/downloader',json={'url':url}).status_code==422
    assert client.get('/api/plugins/downloader/not-a-job/file').status_code==404

def test_import_preserves_source_data():
    from pathlib import Path
    import csv
    root=Path('server/content')
    words=json.loads((root/'kaoyan.json').read_text(encoding='utf-8'))
    coordinate=next(w for w in words if w['name']=='coordinate')
    assert len(coordinate['source_rows'])==2
    assert len(list(csv.reader((root/'考研词汇.csv').open(encoding='utf-8-sig'))))==5494
    cards=json.loads((root/'cards.json').read_text(encoding='utf-8'))['cards']
    assert all((root/'cards'/(c['id']+'.webp')).is_file() for c in cards)

def promote(uid):
    with db.connect(True) as conn: conn.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))

def test_admin_authorization_and_roles(client):
    uid=register(client)
    for path in ['/api/admin/users','/api/admin/rules','/api/admin/audit','/api/admin/content/words']:
        assert client.get(path).status_code==403
    assert client.get('/api/bootstrap').json()['user']['role']=='user'
    promote(uid)
    assert client.get('/api/bootstrap').json()['user']['role']=='admin'
    data=client.get('/api/admin/users').json()
    assert data['total']==1 and 'password' not in data['users'][0]
    body={'username':'tester','nickname':'测试者','bio':'','role':'user'}
    assert client.patch('/api/admin/users/'+uid,json=body).status_code==409
    assert client.delete('/api/admin/users/'+uid).status_code==409
    created=client.post('/api/admin/users',json=body|{'username':'new_admin','role':'admin','password':'Another-strong-password-2026'})
    assert created.status_code==201
    assert client.get('/api/admin/users?q=new_admin').json()['total']==1

def test_admin_balances_progress_and_audit(client):
    uid=register(client);promote(uid);install(client,'collection')
    body={'essence':200,'stones':12,'reason':'管理测试'}
    assert client.patch('/api/admin/users/'+uid+'/balances',json=body).status_code==200
    detail=client.get('/api/admin/users/'+uid).json()
    assert detail['wallet']=={k:v for k,v in body.items() if k!='reason'}
    assert client.patch('/api/admin/users/'+uid+'/balances',json=body|{'essence':0}).status_code==200
    assert client.get('/api/bootstrap').json()['wallet']['essence']==0
    assert client.patch('/api/admin/users/'+uid+'/balances',json=body|{'stones':-1}).status_code==422
    rows=[{'plugin_id':'vocabulary','key':'learned','value':['dawn','light']}]
    assert client.put('/api/admin/users/'+uid+'/progress',json={'rows':rows}).status_code==200
    assert client.get('/api/admin/users/'+uid).json()['progress']==rows
    audits=client.get('/api/admin/audit').json()
    assert audits['total']==3
    assert 'Another-strong-password' not in json.dumps(audits)

def test_admin_rules_content_and_password_reset(client):
    uid=register(client);promote(uid);install(client,'quotes','checkin','vocabulary','kaoyan')
    rules=client.get('/api/admin/rules').json()
    assert client.put('/api/admin/rules',json=rules|{'checkin_reward':123,'draw_probabilities':{'SSR':50,'SR':50,'R':1}}).status_code==422
    assert client.put('/api/admin/rules',json=rules|{'checkin_reward':123}).status_code==200
    assert client.post('/api/plugins/checkin').status_code==200
    assert client.get('/api/bootstrap').json()['wallet']['essence']==123
    quote={'id':'sample','text':'管理员修改的金句','author':'管理测试','audio':None}
    assert client.put('/api/admin/content/quotes/sample',json={'value':quote}).status_code==200
    assert client.get('/api/plugins/quotes').json()['text']==quote['text']
    word={'name':'customword','trans':['自定义释义'],'phonetic':''}
    assert client.put('/api/admin/content/words/customword',json={'value':word}).status_code==200
    assert client.get('/api/plugins/vocabulary').json()['total']==5493
    assert client.delete('/api/admin/content/words/customword').status_code==200
    assert client.get('/api/plugins/vocabulary').json()['total']==5492
    assert client.post('/api/admin/users/'+uid+'/password',json={'password':'Reset-strong-password-2026'}).status_code==200
    assert client.get('/api/admin/users').status_code==401
    assert client.post('/api/auth/login',json={'username':'tester','password':'Reset-strong-password-2026'}).status_code==200

def test_download_worker_file_delivery_and_isolation(client,tmp_path,monkeypatch):
    from server.plugins import downloader
    from types import SimpleNamespace
    import yt_dlp
    root=tmp_path/'downloads';root.mkdir()
    monkeypatch.setattr(downloader,'ROOT',root)
    monkeypatch.setattr(downloader,'validate_url',lambda url:None)
    monkeypatch.setattr(downloader,'POOL',SimpleNamespace(submit=lambda fn,*args:fn(*args)))
    class FakeDownloader:
        def __init__(self,opts):self.opts=opts
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def extract_info(self,url,download):
            from pathlib import Path
            Path(self.opts['outtmpl'].replace('%(ext)s','mp4')).write_bytes(b'dawn-download-test')
            self.opts['progress_hooks'][0]({'status':'downloading','downloaded_bytes':18,'total_bytes':18})
            return {'title':'下载验证视频'}
    monkeypatch.setattr(yt_dlp,'YoutubeDL',FakeDownloader)
    register(client);install(client,'downloader')
    result=client.post('/api/plugins/downloader',json={'url':'https://youtu.be/BaW_jenozKc'})
    assert result.status_code==200
    job=result.json()['id']
    assert client.get('/api/plugins/downloader').json()['jobs'][0]['status']=='completed'
    assert client.get('/api/plugins/downloader/'+job+'/file').content==b'dawn-download-test'
    client.post('/api/auth/logout');register(client,'another_downloader');install(client,'downloader')
    assert client.get('/api/plugins/downloader/'+job+'/file').status_code==404

def test_retired_points_are_removed_without_minting_essence(client):
    uid=register(client)
    with db.connect(True) as conn:
        conn.executemany('INSERT INTO balances VALUES(?,?,?)',[(uid,'climb',20),(uid,'collection',50)])
        conn.execute('CREATE TABLE IF NOT EXISTS retired_balances(user_id TEXT,kind TEXT,amount INTEGER)')
        conn.execute('INSERT INTO retired_balances VALUES(?,?,?)',(uid,'collection',99))
        conn.execute('INSERT INTO ledger(user_id,kind,amount,reason,source,created_at) VALUES(?,?,?,?,?,?)',(uid,'climb',20,'旧积分','old-points','2026-11-03'))
    db.init();db.init()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM balances WHERE kind IN ('climb','collection')").fetchone()[0]==0
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='retired_balances'").fetchone()
        assert conn.execute("SELECT COUNT(*) FROM ledger WHERE kind IN ('climb','collection')").fetchone()[0]==0
    assert client.get('/api/bootstrap').json()['wallet']=={'essence':0,'stones':0}

def test_album_classification_and_essence_spending(client):
    uid=register(client);install(client,'collection','lol')
    data=client.get('/api/plugins/collection').json()
    assert 'points' not in data and data['currency']=='essence'
    assert data['packs'][0]['id']=='lol'
    book=data['albums'][0]
    assert book['name']=='英雄联盟' and len(book['children'])>90
    assert all(world['kind']=='universe' and all(s['kind']=='series' for s in world['children']) for world in book['children'])
    assert next(world for world in book['children'] if world['id']=='runeterra')['name']=='符文大陆'
    assert set(book['card_ids'])=={c['id'] for c in data['cards']}
    assert next(c for c in data['cards'] if c['id']=='103027')['categories']
    assert client.get('/api/plugins/collection/poster/lol').headers['content-type']=='image/webp'
    with db.connect(True) as conn: credit(conn,uid,'essence',20,'测试初始化','new-economy-seed')
    r=client.post('/api/plugins/collection/draw',json={'count':1,'request_id':'new-economy-draw','pack_id':'lol'})
    assert r.status_code==200
    assert client.get('/api/bootstrap').json()['wallet']['essence']==10
    assert client.get('/api/wallet').json()['ledger'][0]['amount']==-10

def test_phonetics_pronunciation_and_no_testing_currency(client,tmp_path,monkeypatch):
    register(client);install(client,'vocabulary')
    question=client.get('/api/plugins/vocabulary/question').json()
    assert question['phonetic'] and question['audio'].startswith('/api/plugins/vocabulary/audio/')
    from server import pronunciation
    path=tmp_path/'voice.mp3';path.write_bytes(b'ID3'+b'voice'*30)
    monkeypatch.setattr(pronunciation,'voice_file',lambda word:path)
    r=client.get(question['audio']);assert r.status_code==200 and r.headers['content-type']=='audio/mpeg'
    client.post('/api/plugins/vocabulary/answer',json={'token':question['token'],'answer':question['hint']})
    assert client.get(question['audio']).status_code==200
    assert client.get('/api/bootstrap').json()['wallet']=={'essence':0,'stones':0}
    assert client.get('/api/plugins/vocabulary/audio/unknown').status_code==404

def test_bilibili_dash_format_selection():
    import yt_dlp
    from server.plugins.downloader import FORMAT
    info={'id':'test-dash','title':'音画分离测试','formats':[
        {'format_id':'video','url':'https://example.com/video.mp4','ext':'mp4','height':720,'vcodec':'avc1.64001f','acodec':'none'},
        {'format_id':'audio','url':'https://example.com/audio.m4a','ext':'m4a','vcodec':'none','acodec':'mp4a.40.2'}]}
    with yt_dlp.YoutubeDL({'quiet':True,'format':FORMAT,'simulate':True}) as ydl:
        result=ydl.process_ie_result(info,download=False)
    assert len(result['requested_formats'])==2

def test_bilibili_error_message_does_not_leak_urls():
    from server.plugins.downloader import failure_message
    message=failure_message(Exception('HTTP Error 412 https://cdn.example/private?token=secret'),'https://www.bilibili.com/video/BV123')
    assert '哔哩哔哩' in message and 'secret' not in message and 'https' not in message

def test_client_release_endpoints(client,tmp_path,monkeypatch):
    import base64
    from server import releases
    monkeypatch.setattr(releases,'ROOT',tmp_path)
    content=b'test-client-package';import hashlib
    payload={'platform':'windows','version':'1.1.0','filename':'DawnBreaker-1.1.0-Windows.exe','size':len(content),'sha256':hashlib.sha256(content).hexdigest(),'notes':'test'}
    envelope={'signed':base64.b64encode(json.dumps(payload).encode()).decode(),'signature':'test-signature'}
    (tmp_path/'windows.json').write_text(json.dumps(envelope))
    (tmp_path/payload['filename']).write_bytes(content)
    assert client.get('/api/releases/windows?current=1.0.0').json()['available']
    assert not client.get('/api/releases/windows?current=1.1.0').json()['available']
    assert client.get('/api/releases/windows/download/1.1.0').content==content
    assert client.get('/api/releases/windows/download/1.0.0').status_code==404
    assert client.get('/api/releases/other').status_code==404
    payload.update(version='1.0.0',version_code=7,reset_from_preview=True)
    envelope['signed']=base64.b64encode(json.dumps(payload).encode()).decode();(tmp_path/'windows.json').write_text(json.dumps(envelope))
    assert client.get('/api/releases/windows?current=1.3.0&current_code=6').json()['available']
    assert not client.get('/api/releases/windows?current=1.0.0&current_code=7').json()['available']
    assert client.get('/api/releases/windows?current=1.3.0').json()['reset_from_preview']

