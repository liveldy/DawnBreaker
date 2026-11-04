"""Bundle verified native sources and the pinned geography snapshot."""
import hashlib,json,zipfile
from pathlib import Path
from release_common import ROOT,VERSION

def main():
    sources={
        'mihomo-v1.19.33.zip':ROOT/'artifacts/research-v120/mihomo-v1.19.33.zip',
        'libmihomo-android-v0.3.13.zip':ROOT/'artifacts/research-v120/libmihomo-android-v0.3.13.zip',
        'meta-rules-dat-source.zip':ROOT/'artifacts/v130-research/meta-rules-dat-source.zip',
    }
    if any(not p.is_file() for p in sources.values()):raise RuntimeError('Download pinned upstream core-source archives listed in third_party/NOTICE.md first')
    target=ROOT/'release'/f'DawnBreaker-{VERSION}-ThirdPartySources.zip'
    manifest=json.loads((ROOT/'third_party/geodata/manifest.json').read_text())
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for name,path in sources.items():out.write(path,name)
        for entry in manifest['files']:
            path=ROOT/'.tooling/geodata'/entry['name']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise RuntimeError('Geography data checksum mismatch')
            out.write(path,'geodata/'+entry['name'])
        for name in ['manifest.json','LICENSE','README.md']:out.write(ROOT/'third_party/geodata'/name,'geodata/'+name)
        out.writestr('README.md','# DawnBreaker corresponding source\n\nMihomo v1.19.33 and libmihomo-android v0.3.13: GPL-3.0. Geography data snapshot, upstream build-source archive and notices are included. The source commit and file hashes are in geodata/manifest.json. LinkSwift, DawnBreaker integrations, platform build files, license notices and build instructions are available at https://github.com/liveldy/DawnBreaker . See third_party/NOTICE.md.\n')
    print('Built '+target.name)
if __name__=='__main__':main()
