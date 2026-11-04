import base64,hashlib,json
import pytest
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from scripts.release_artifacts import verify_manifests,file_identity

def test_signed_release_must_match_final_file_size_and_digest(tmp_path):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    desktop=tmp_path/'release/desktop';desktop.mkdir(parents=True)
    public=tmp_path/'clients/desktop/update-public.pem';public.parent.mkdir(parents=True);public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    def manifest(platform,folder,suffix,wrong_size=False):
        folder.mkdir(parents=True,exist_ok=True);file=folder/('DawnBreaker-1.3.1-'+suffix);file.write_bytes(b'complete final artifact')
        identity=file_identity(file);payload={'platform':platform,'version':'1.3.1','version_code':16,'filename':file.name,**identity}
        if wrong_size:payload['size']-=2
        signed=json.dumps(payload).encode();envelope={'signed':base64.b64encode(signed).decode(),'signature':base64.b64encode(key.sign(signed,padding.PKCS1v15(),hashes.SHA256())).decode()}
        (tmp_path/'release'/(platform+'-1.3.1.json')).write_text(json.dumps(envelope))
    manifest('windows',desktop,'Windows.exe');manifest('android',tmp_path/'release/android','Android.apk')
    verify_manifests(tmp_path,'1.3.1',16,desktop)
    manifest('windows',desktop,'Windows.exe',True)
    with pytest.raises(RuntimeError,match='does not match'):verify_manifests(tmp_path,'1.3.1',16,desktop)
    manifest('windows',desktop,'Windows.exe');(desktop/'DawnBreaker-1.3.1-Windows.exe').write_bytes(b'changed after signing')
    with pytest.raises(RuntimeError,match='does not match'):verify_manifests(tmp_path,'1.3.1',16,desktop)
