"""Verify exact geography data before including it in either native client."""
import hashlib,json,time,io,zipfile
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
def fetch():
    manifest=json.loads((ROOT/'third_party/geodata/manifest.json').read_text())
    folder=ROOT/'.tooling/geodata';folder.mkdir(parents=True,exist_ok=True);snapshot=None
    with httpx.Client(follow_redirects=True,timeout=180) as client:
        for entry in manifest['files']:
            target=folder/entry['name']
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==entry['sha256']:continue
            temporary=target.with_suffix('.partial');data=bytearray()
            try:
                for offset in range(0,entry['size'],1048576):
                    end=min(entry['size']-1,offset+1048575)
                    for attempt in range(4):
                        try:
                            r=client.get(entry['url']+'?dawn-range='+str(offset),headers={'Range':f'bytes={offset}-{end}','Accept-Encoding':'identity'})
                            r.raise_for_status()
                            if r.status_code==200 and len(r.content)==entry['size']:data=bytearray(r.content);break
                            if r.status_code!=206 or not r.headers.get('content-range','').startswith(f'bytes {offset}-{end}/') or len(r.content)!=end-offset+1:raise RuntimeError('Unexpected geography download range')
                            data.extend(r.content);break
                        except Exception:
                            if attempt==3:raise
                            time.sleep(attempt+1)
                    if len(data)==entry['size']:break
                if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise RuntimeError('Upstream rolling snapshot changed')
            except Exception:
                if snapshot is None:
                    response=client.get(manifest['release_snapshot'],headers={'Accept-Encoding':'identity'});response.raise_for_status()
                    if len(response.content)>64*1024*1024:raise RuntimeError('Geography source archive too large')
                    snapshot=zipfile.ZipFile(io.BytesIO(response.content))
                member=snapshot.getinfo('geodata/'+entry['name'])
                if member.file_size!=entry['size']:raise RuntimeError('Snapshot data size mismatch')
                data=snapshot.read(member)
            if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise RuntimeError('Geodata checksum mismatch: '+entry['name'])
            temporary.write_bytes(data);temporary.replace(target);print('Verified '+entry['name'],flush=True)
if __name__=='__main__':fetch()
