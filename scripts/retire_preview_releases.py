"""User-authorized cleanup, only after the stable deployment and binaries verify."""
import hashlib,json,re,shlex
from pathlib import Path
from release_common import ROOT,VERSION,VERSION_CODE
from remote import connection

with connection() as ssh:
    code=r'''
from pathlib import Path
import base64,json,re,shutil,urllib.request,hashlib
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
version=VERSION_LITERAL; sequence=SEQUENCE_LITERAL
assert json.load(urllib.request.urlopen('http://127.0.0.1:7779/api/health'))['version']==version
root=Path('/opt/dawnbreaker/releases').resolve(); current=Path('/opt/dawnbreaker/current').resolve()
assert current.parent==root and current.name.endswith('-v'+version)
public=serialization.load_pem_public_key(Path('/var/lib/dawnbreaker/update-public.pem').read_bytes())
binary_root=Path('/var/lib/dawnbreaker/client-releases').resolve(); keep={'windows.json','android.json'}
for platform in ('windows','android'):
    envelope=json.loads((binary_root/(platform+'.json')).read_text()); signed=base64.b64decode(envelope['signed'])
    public.verify(base64.b64decode(envelope['signature']),signed,padding.PKCS1v15(),hashes.SHA256()); p=json.loads(signed)
    assert p['version']==version and p['version_code']==sequence and p['channel']=='stable'
    file=binary_root/p['filename'];assert file.parent==binary_root and not file.is_symlink()
    assert hashlib.sha256(file.read_bytes()).hexdigest()==p['sha256']; keep.add(file.name)
removed=[]
for file in binary_root.iterdir():
    if file.name not in keep and re.fullmatch(r'DawnBreaker-\d+\.\d+\.\d+-(Windows\.exe|Android\.apk)(\.partial)?',file.name):
        assert file.resolve().parent==binary_root and file.is_file() and not file.is_symlink();file.unlink();removed.append(file.name)
for folder in root.iterdir():
    if folder==current:continue
    if re.fullmatch(r'\d{8}-\d{6}(-v\d+\.\d+\.\d+)?',folder.name):
        assert folder.resolve().parent==root and not folder.is_symlink() and folder.is_dir()
        shutil.rmtree(folder);removed.append(folder.name)
assert list(root.iterdir())==[current]
assert {p.name for p in binary_root.iterdir()}==keep
print(json.dumps({'removed':removed,'current':current.name,'remaining_client_files':sorted(keep)}))
'''.replace('VERSION_LITERAL',repr(VERSION)).replace('SEQUENCE_LITERAL',str(VERSION_CODE))
    # Use the existing deployed public key (the private key never leaves this PC).
    with ssh.open_sftp() as sftp:
        sftp.put(str(ROOT/'clients/desktop/update-public.pem'),'/var/lib/dawnbreaker/update-public.pem')
    _,out,err=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code),timeout=180)
    result=out.read().decode();error=err.read().decode()
    assert out.channel.recv_exit_status()==0,error
    (ROOT/'artifacts/formal-remote-cleanup.json').write_text(result,encoding='utf-8');print(result)
