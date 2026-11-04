"""Read-only verification of the public site/release and source publication boundary."""
import hashlib,json,time
from pathlib import Path
import httpx
from release_common import VERSION,ROOT
repo='https://api.github.com/repos/liveldy/DawnBreaker'
website_repo='https://api.github.com/repos/liveldy/dawnbreaker-website'
site='https://liveldy.github.io/dawnbreaker-website/'
with httpx.Client(trust_env=False,timeout=30,headers={'Cache-Control':'no-cache'}) as c:
    release=c.get(repo+'/releases/latest');release.raise_for_status();release=release.json()
    assert release['tag_name']=='v'+VERSION
    assets={a['name']:a for a in release['assets']}
    for folder,suffix in [('desktop','Windows.exe'),('android','Android.apk')]:
        file=ROOT/'release'/folder/f'DawnBreaker-{VERSION}-{suffix}'
        assert assets[file.name]['digest']=='sha256:'+hashlib.sha256(file.read_bytes()).hexdigest()
    tree=c.get(website_repo+'/git/trees/main',params={'recursive':1});tree.raise_for_status()
    paths={f['path'] for f in tree.json()['tree'] if f['type']=='blob'}
    expected={'index.html','site.css','site.js','.nojekyll','README.md'}|{'assets/'+p.name for p in (ROOT/'website/assets').iterdir() if p.is_file()}
    assert paths==expected,(paths-expected,expected-paths)
    print('PASS: latest GitHub Release '+VERSION+'; both binary SHA256 digests match; website repository has only '+str(len(paths))+' website files',flush=True)
    for attempt in range(40):
        r=c.get(site);r.raise_for_status()
        if r.content==(ROOT/'website/index.html').read_bytes():break
        time.sleep(3)
    else:raise RuntimeError('GitHub Pages has not served the latest index yet')
    for name in ['site.css','site.js']:
        response=c.get(site+name);response.raise_for_status();assert response.content==(ROOT/'website'/name).read_bytes(),name+' differs'
    assert 'possibilities' not in r.text and f'DawnBreaker-{VERSION}-Windows.exe' in r.text and f'DawnBreaker-{VERSION}-Android.apk' in r.text
    assert 'http://110.42.63.153:7780' in r.text
    print('PASS: live single-page official website exactly matches local HTML/CSS/JS and both '+VERSION+' download links',flush=True)
