"""Refuse changing or mismatched release artifacts before publishing metadata."""
import base64,hashlib,json
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding

def file_identity(path):
    before=path.stat();digest=hashlib.sha256(path.read_bytes()).hexdigest();after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Artifact still changing: '+path.name)
    return {'size':after.st_size,'sha256':digest}

def verify_manifests(root,version,code,desktop_dir):
    key=serialization.load_pem_public_key((root/'clients/desktop/update-public.pem').read_bytes())
    for platform,folder,suffix in [('windows',desktop_dir,'Windows.exe'),('android',root/'release/android','Android.apk')]:
        envelope=json.loads((root/'release'/f'{platform}-{version}.json').read_text('utf8'))
        signed=base64.b64decode(envelope['signed']);key.verify(base64.b64decode(envelope['signature']),signed,padding.PKCS1v15(),hashes.SHA256());payload=json.loads(signed)
        path=folder/f'DawnBreaker-{version}-{suffix}';identity=file_identity(path)
        if payload['platform']!=platform or payload['version']!=version or payload['version_code']!=code or payload['filename']!=path.name or any(payload[k]!=v for k,v in identity.items()):raise RuntimeError('Signed manifest does not match final artifact: '+platform)
