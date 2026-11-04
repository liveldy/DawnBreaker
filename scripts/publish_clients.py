"""Sign release manifests locally; upload binaries without private keys."""
import base64,hashlib,json,argparse
from release_common import VERSION_CODE,SUMMARY
from release_artifacts import file_identity
from pathlib import Path
from datetime import datetime,timezone
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from remote import connection
from deploy import command
root=Path(__file__).resolve().parents[1]
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
key=serialization.load_pem_private_key((root/'.local/update-signing-private.pem').read_bytes(),password=None)
platforms={'windows':root/'release/desktop'/f'DawnBreaker-{version}-Windows.exe','android':root/'release/android'/f'DawnBreaker-{version}-Android.apk'}
parser=argparse.ArgumentParser();parser.add_argument('--desktop-dir',type=Path,default=root/'release/desktop');parser.add_argument('--platform',choices=['all','windows','android'],default='all');args=parser.parse_args();platforms['windows']=args.desktop_dir/f'DawnBreaker-{version}-Windows.exe'
if args.platform!='all':platforms={args.platform:platforms[args.platform]}
envelopes={}
for platform,file in platforms.items():
    if not file.is_file():raise RuntimeError('Build is missing: '+str(file))
    payload={'platform':platform,'version':version,'version_code':VERSION_CODE,'filename':file.name,**file_identity(file),'notes':SUMMARY,'channel':'stable','reset_from_preview':version=='1.0.0','published_at':datetime.now(timezone.utc).isoformat()}
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    envelopes[platform]={'signed':base64.b64encode(encoded).decode(),'signature':base64.b64encode(key.sign(encoded,padding.PKCS1v15(),hashes.SHA256())).decode(),'algorithm':'RSA-SHA256'}
    (root/'release'/f'{platform}-{version}.json').write_text(json.dumps(envelopes[platform]),encoding='utf-8')
with connection() as ssh:
    command(ssh,'mkdir -p /var/lib/dawnbreaker/client-releases && chmod 755 /var/lib/dawnbreaker/client-releases')
    with ssh.open_sftp() as sftp:
        for platform,file in platforms.items():
            remote='/var/lib/dawnbreaker/client-releases/'+file.name
            last=[-1]
            def progress(done,total):
                value=int(done/total*5)*20
                if value!=last[0]:print(platform+' upload '+str(value)+'%',flush=True);last[0]=value
            sftp.put(str(file),remote+'.partial',callback=progress)
            expected=json.loads(base64.b64decode(envelopes[platform]['signed']))
            code="import pathlib,hashlib;p=pathlib.Path("+repr(remote+'.partial')+");assert p.stat().st_size=="+str(expected['size'])+";assert hashlib.sha256(p.read_bytes()).hexdigest()=="+repr(expected['sha256'])
            command(ssh,'/opt/dawnbreaker/venv/bin/python -c '+__import__('shlex').quote(code))
            if file_identity(file)!={k:expected[k] for k in ('size','sha256')}:raise RuntimeError('Local artifact changed during upload')
            sftp.posix_rename(remote+'.partial',remote)
            with sftp.file('/var/lib/dawnbreaker/client-releases/'+platform+'.json.partial','w') as f:f.write(json.dumps(envelopes[platform]))
            sftp.posix_rename('/var/lib/dawnbreaker/client-releases/'+platform+'.json.partial','/var/lib/dawnbreaker/client-releases/'+platform+'.json')
print('Published signed Windows and Android releases '+version)
