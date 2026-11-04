from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
root=Path(__file__).resolve().parents[1];private=root/'.local/update-signing-private.pem'
private.parent.mkdir(exist_ok=True)
if private.exists():key=serialization.load_pem_private_key(private.read_bytes(),password=None)
else:
    key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
(root/'clients/desktop/update-public.pem').write_bytes(public)
raw=root/'android/app/src/main/res/raw';raw.mkdir(exist_ok=True)
(raw/'update_public.pem').write_bytes(public)
print('Update verification key prepared; private key stays in .local')
