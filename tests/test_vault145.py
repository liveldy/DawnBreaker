import base64,json
from tests.test_api import client,register,install
from server import db

def envelope(version=0,format_version=None,size=32):
    result={'version':version,'salt':base64.b64encode(b's'*16).decode(),'nonce':base64.b64encode(b'n'*12).decode(),'ciphertext':base64.b64encode(b'x'*size).decode(),'iterations':600000,'algorithm':'PBKDF2-SHA256/AES-256-GCM'}
    if format_version is not None:result['format_version']=format_version
    return result

def test_legacy_upgrade_and_prevent_older_client_overwriting_photos(client):
    uid=register(client);install(client,'vault')
    # Existing envelopes did not carry a format version.
    with db.connect(True) as d:d.execute('INSERT INTO vaults VALUES(?,?,?,?)',(uid,1,json.dumps({k:v for k,v in envelope().items() if k!='version'}),db.now()))
    assert client.get('/api/plugins/vault').json()['version']==1
    assert client.put('/api/plugins/vault',json=envelope(1,3)).json()['version']==2
    original=client.get('/api/plugins/vault').json();assert original['format_version']==3
    old=client.put('/api/plugins/vault',json=envelope(2));assert old.status_code==409 and '更新客户端' in old.text
    stale=client.put('/api/plugins/vault',json=envelope(1,3));assert stale.status_code==409
    assert client.get('/api/plugins/vault').json()==original
    assert client.put('/api/plugins/vault',json=envelope(2,3)).status_code==200

def test_photo_sized_opaque_envelope_and_user_isolation(client):
    register(client);install(client,'vault');body=envelope(0,3,3*1024*1024)
    assert len(body['ciphertext'])>2000000
    assert client.put('/api/plugins/vault',json=body).status_code==200
    stored=client.get('/api/plugins/vault');assert stored.headers['cache-control']=='no-store' and stored.json()['ciphertext']==body['ciphertext']
    client.post('/api/auth/logout');register(client,'other_vault');install(client,'vault');assert client.get('/api/plugins/vault').json()=={'exists':False}
    assert client.put('/api/plugins/vault',json=envelope(0,4)).status_code==422
    assert client.put('/api/plugins/vault',json={**envelope(),'nonce':'invalid'}).status_code==422
