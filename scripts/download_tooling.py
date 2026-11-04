"""Resumable verified download of Google's official Android CLI tools."""
import hashlib
import time
import zipfile
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]/'.tooling'
ROOT.mkdir(exist_ok=True)
FILE=ROOT/'android-tools.zip'
URL='https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip'
TOTAL=155655386
SHA='90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a'
for attempt in range(12):
    size=FILE.stat().st_size if FILE.exists() else 0
    if size==TOTAL: break
    try:
        with httpx.stream('GET',URL,headers={'Range':f'bytes={size}-'},timeout=60,follow_redirects=True) as r:
            r.raise_for_status()
            if size and r.status_code!=206: raise RuntimeError('Server does not support resuming')
            with FILE.open('ab') as f:
                for chunk in r.iter_bytes(): f.write(chunk)
        print(f'Android tools {FILE.stat().st_size*100//TOTAL}%',flush=True)
    except (httpx.HTTPError,RuntimeError) as exc:
        print(f'Resuming Android tools at {FILE.stat().st_size if FILE.exists() else 0} bytes',flush=True)
        time.sleep(1)
assert FILE.stat().st_size==TOTAL,'Incomplete download'
assert hashlib.sha256(FILE.read_bytes()).hexdigest()==SHA,'Checksum mismatch'
with zipfile.ZipFile(FILE) as z:
    for info in z.infolist():
        if info.filename.startswith('cmdline-tools/'):
            info.filename=info.filename.removeprefix('cmdline-tools/')
            if info.filename: z.extract(info,ROOT/'android-sdk'/'cmdline-tools'/'latest')
print('Android tools installed and verified',flush=True)
