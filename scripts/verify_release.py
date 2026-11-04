"""Verify live release identity/signatures, catalog nesting and stored binary digests."""
import base64,hashlib,json,shlex,secrets
from pathlib import Path
import httpx
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from release_common import VERSION,VERSION_CODE,ROOT
from remote import connection
public=serialization.load_pem_public_key((ROOT/'clients/desktop/update-public.pem').read_bytes())
uid=None
try:
 with httpx.Client(base_url='http://110.42.63.153:7780',trust_env=False,timeout=60,headers={'Origin':'http://110.42.63.153:7780'}) as c:
    assert c.get('/api/health').json()['version']==VERSION
    for platform in ['windows','android']:
        e=c.get('/api/releases/'+platform+'?current=1.0.0&current_code=7');e.raise_for_status();e=e.json();assert e['latest']==VERSION and e['available']
        signed=base64.b64decode(e['signed']);public.verify(base64.b64decode(e['signature']),signed,padding.PKCS1v15(),hashes.SHA256());p=json.loads(signed)
        assert p['version_code']==VERSION_CODE
        assert not c.get('/api/releases/'+platform+'?current='+VERSION).json()['available']
        r=c.get('/api/releases/'+platform+'/download/'+VERSION,headers={'Range':'bytes=0-1023'});assert r.status_code==206 and len(r.content)==1024 and r.headers['x-checksum-sha256']==p['sha256']
        print('PASS: '+platform+' '+VERSION+' signature, version comparison and byte-range download',flush=True)
    r=c.post('/api/auth/register',json={'username':'releaseqa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(32),'nickname':'发布验证临时账号'});r.raise_for_status();uid=r.json()['user']['id']
    for plugin in ['collection','lol']:c.post('/api/catalog/'+plugin+'/install').raise_for_status()
    data=c.get('/api/plugins/collection').json();assert data['schema_version']==2 and data['albums'][0]['name']=='英雄联盟'
    album=data['albums'][0];assert album['total']==1580 and set(album['card_ids'])=={card['id'] for card in data['cards']}
    assert len(album['children'])==104 and all(w['kind']=='universe' and all(s['kind']=='series' for s in w['children']) for w in album['children'])
    world=next(w for w in album['children'] if w['id']=='runeterra');assert world['name']=='符文大陆' and world['children'][0]['total']==173
    print('PASS: production album -> 104 universes -> 168 series, all 1580 stable card IDs',flush=True)
 with connection() as ssh:
    for platform,folder,suffix in [('windows','desktop','Windows.exe'),('android','android','Android.apk')]:
        file=ROOT/'release'/folder/f'DawnBreaker-{VERSION}-{suffix}'
        _,out,err=ssh.exec_command('sha256sum '+shlex.quote('/var/lib/dawnbreaker/client-releases/'+file.name));assert out.read().decode().split()[0]==hashlib.sha256(file.read_bytes()).hexdigest();assert out.channel.recv_exit_status()==0
        print('PASS: production '+platform+' binary digest',flush=True)
finally:
 if uid:
    assert len(uid)==32 and all(ch in '0123456789abcdef' for ch in uid)
    code="import sqlite3;d=sqlite3.connect('/var/lib/dawnbreaker/dawn.db');uid='"+uid+"';[d.execute('DELETE FROM '+t+' WHERE user_id=?',(uid,)) for t in ['sessions','installed','balances','ledger','progress','events','downloads']];d.execute('DELETE FROM users WHERE id=?',(uid,));d.commit()"
    with connection() as ssh:
        _,out,err=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code));assert out.channel.recv_exit_status()==0,err.read().decode()
    print('Temporary production verification account removed',flush=True)
