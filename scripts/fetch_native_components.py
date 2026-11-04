"""Fetch exact upstream binaries with pinned hashes. No credentials needed."""
import argparse,hashlib,io,zipfile
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
COMPONENTS={
 'windows':('https://github.com/MetaCubeX/mihomo/releases/download/v1.19.33/mihomo-windows-amd64-compatible-v1.19.33.zip','7aaf636a4f2172dcd8ec34ac4f52797b059195e5afd6409508c963e545f8864d','clients/desktop/bin/mihomo.exe'),
 'android':('https://github.com/oviron/libmihomo-android/releases/download/v0.3.13/libmihomo-android-v0.3.13.aar','c6c2787e5dd888a8f9193501506dfa3a4f8a38fbd51adefccf67d84d0c8e0fb5','android/app/libs/libmihomo-android-v0.3.13.aar'),
}
def fetch(platform):
    url,digest,destination=COMPONENTS[platform]
    with httpx.Client(follow_redirects=True,timeout=180) as client:
        response=client.get(url);response.raise_for_status();data=response.content
    if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError('Upstream checksum mismatch: '+platform)
    if platform=='windows':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members=[n for n in archive.namelist() if n.endswith('.exe')]
            if len(members)!=1:raise RuntimeError('Unexpected core archive')
            data=archive.read(members[0])
    file=ROOT/destination;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    print('Verified '+platform+': '+destination)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('platform',choices=['windows','android','all'],default='all',nargs='?');args=parser.parse_args()
    for name in COMPONENTS if args.platform=='all' else [args.platform]:fetch(name)
