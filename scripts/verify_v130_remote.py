"""Exercise deployed plugins, large multipart upload, real OCR, live feeds and durable replay."""
import io,json,secrets,shlex,time
from pathlib import Path
import httpx
from PIL import Image
from remote import connection
uid=None;root=Path(__file__).resolve().parents[1];report={}
try:
 with httpx.Client(base_url='http://110.42.63.153:7780',timeout=100,trust_env=False,headers={'Origin':'http://110.42.63.153:7780'}) as c:
    r=c.post('/api/auth/register',json={'username':'v130qa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24)});r.raise_for_status();uid=r.json()['user']['id']
    for id in ['library','constellation','vault','atlas','music','ancient']:c.post('/api/catalog/'+id+'/install').raise_for_status()
    text='# 大文档验证\n\n$E=mc^2$\n'+'数学笔记。'*60000
    r=c.post('/api/plugins/library/imports',files={'file':('book.md',text.encode('utf-8'),'text/markdown')});r.raise_for_status();doc=r.json()['document_id'];assert c.get('/api/plugins/library/nodes/'+doc).json()['markdown']==text
    image=io.BytesIO();Image.frombytes('RGB',(512,512),secrets.token_bytes(512*512*3)).save(image,format='PNG');assert len(image.getvalue())>262144
    c.post('/api/profile/avatar',files={'file':('avatar.png',image.getvalue(),'image/png')}).raise_for_status();avatar=c.get('/api/bootstrap').json()['user']['avatar_url'];assert c.get(avatar).headers['content-type'].startswith('image/webp');report['large_uploads']=True
    assistants=c.get('/api/plugins/constellation').json();assert len(assistants['families'])==11 and assistants['library_enabled'];c.get(assistants['families'][0]['image']).raise_for_status()
    r=c.post('/api/plugins/constellation/assistants',json={'name':'发布验证助手','family':'gpt','model':'configured-by-user','api_base':'https://api.example.com/v1'});r.raise_for_status();assert 'api_key' not in r.json();report['assistant_portraits']=11
    tracks=c.get('/api/plugins/music').json()['tracks'];assert len(tracks)==22;c.get('/api/plugins/music/audio/'+tracks[-1]['id'],headers={'Range':'bytes=0-99'}).raise_for_status();report['tracks']=22
    end=time.time()-1;body={'account_id':uid,'device_id':'release-verification','segments':[{'id':'release-segment-1234','start':end-20,'end':end,'seconds':20,'track_id':tracks[0]['id']}]};r=c.post('/api/plugins/music/sync',json=body);r.raise_for_status();assert r.json()['credited_seconds']==20;assert c.post('/api/plugins/music/sync',json=body).json()['credited_seconds']==0;assert c.post('/api/plugins/music/sync',json=body|{'account_id':'0'*32}).status_code==409;report['offline_replay_deduplicated']=True
    atlas=c.get('/api/plugins/atlas/live?refresh=true');atlas.raise_for_status();a=atlas.json();assert not a['stale'] and len(a['metadata'])>400;report['atlas']={'models':len(a['metadata']),'ranking':len(a['indexes']['general']['models']),'fetched_at':a['fetched_at']};frame=c.get('/api/plugins/atlas/view');frame.raise_for_status();assert 'DENY' not in frame.headers['x-frame-options'];report['atlas_frame_allowed']=True
    # Use an actual equation image and the deployed background worker under systemd permissions.
    with connection() as ssh:
        with ssh.open_sftp() as s:formula=s.file('/var/lib/dawnbreaker/ocr-verification/formula.png','rb').read()
    r=c.post('/api/plugins/library/imports',data={'mode':'auto'},files={'file':('formula.png',formula,'image/png')});r.raise_for_status();job=r.json()['id']
    for _ in range(90):
        record=next(j for j in c.get('/api/plugins/library').json()['imports'] if j['id']==job)
        if record['status'] in ('completed','failed'):break
        time.sleep(2)
    assert record['status']=='completed',record
    result=c.get('/api/plugins/library/nodes/'+record['document_id']).json()['markdown'];assert '$$' in result and 'E' in result and 'c^' in result;report['ocr_markdown']=result
    print('PASS: deployed library / large uploads / avatar / 11 AI portraits / 22 songs / listening replay / live atlas / real OCR',flush=True)
    (root/'artifacts/v130-production.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
 if uid:
    assert len(uid)==32 and all(x in '0123456789abcdef' for x in uid)
    cleanup="import sqlite3,pathlib,shutil;uid="+repr(uid)+";d=sqlite3.connect('/var/lib/dawnbreaker/dawn.db');tables=['listening_segments','library_nodes','import_jobs','vaults','assistants','ai_threads','ai_turns','ai_prompts','sessions','installed','balances','ledger','progress','events','downloads'];[d.execute('DELETE FROM '+t+' WHERE user_id=?',(uid,)) for t in tables];d.execute('DELETE FROM users WHERE id=?',(uid,));d.commit();p=pathlib.Path('/var/lib/dawnbreaker/library-imports')/uid;shutil.rmtree(p) if p.is_dir() else None;p=pathlib.Path('/var/lib/dawnbreaker/avatars')/(uid+'.webp');p.unlink(missing_ok=True)"
    with connection() as ssh:
        _,o,e=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(cleanup));assert o.channel.recv_exit_status()==0,e.read().decode()
    print('Temporary verification data removed',flush=True)
