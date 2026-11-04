"""Encrypt configured service credentials; never return plaintext credentials in API responses."""
import os,threading
from cryptography.fernet import Fernet
from .db import DATA
LOCK=threading.Lock()
def cipher():
    path=DATA/'keys'/'service-secret.key'
    with LOCK:
        path.parent.mkdir(mode=0o700,exist_ok=True)
        if not path.exists():
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as file:file.write(Fernet.generate_key())
        return Fernet(path.read_bytes())
def seal(value):return cipher().encrypt(value.encode()).decode() if value else ''
def open_secret(value):return cipher().decrypt(value.encode()).decode() if value else ''
