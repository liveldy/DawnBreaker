"""Publish a website-only repository and binary Releases. Never traverse app sources."""
import argparse,base64,getpass,hashlib,json,mimetypes,time,re
from pathlib import Path
import httpx
from release_common import VERSION,NOTES

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('action',choices=['reset-old','release','website','status']);parser.add_argument('--desktop-dir',type=Path,default=root/'release/desktop');parser.add_argument('--repo',choices=['dawnbreaker-website','DawnBreaker'],default='dawnbreaker-website');args=parser.parse_args()
if args.action=='website' and args.repo!='dawnbreaker-website':raise SystemExit('Website publication stays in the website repository')
token=getpass.getpass('GitHub token (hidden): ')
client=httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},trust_env=False,timeout=60)
def request(method,path,**kwargs):
    for attempt in range(4):
        response=client.request(method,path,**kwargs)
        if response.status_code not in (429,500,502,503,504) or attempt==3:break
        time.sleep(2**attempt)
    if not response.is_success:
        try: message=response.json().get('message','Request failed')
        except ValueError: message='Request failed'
        raise RuntimeError(f'GitHub {method} {path}: HTTP {response.status_code}: {message}')
    return response.json() if response.content else {}
owner=request('GET','/user')['login'];name=args.repo;repo='/repos/'+owner+'/'+name
response=client.get(repo)
if response.status_code==404 and args.action!='status':
    details=request('POST','/user/repos',json={'name':name,'private':False,'auto_init':True,'description':'破晓 DawnBreaker 官方网站与客户端发布版（仅网页文件）','has_wiki':False,'has_projects':False})
    print('Created public website-only repository: '+details['html_url'],flush=True)
elif response.is_success: details=response.json()
else:raise RuntimeError('Cannot access website repository: HTTP '+str(response.status_code))
branch=details['default_branch'];state={'owner':owner,'repo':name,'repository':details['html_url'],'website':f'https://{owner}.github.io/{name}/','version':VERSION}
state_path=root/'.local/github-publish-state.json'

if args.action=='reset-old':
    # Explicit user request: remove ALL preview releases, including the old v1.0.0.
    # Require both newly built artifacts and valid signed stable manifests first.
    from cryptography.hazmat.primitives import serialization,hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from release_common import VERSION_CODE
    public=serialization.load_pem_public_key((root/'clients/desktop/update-public.pem').read_bytes())
    for platform,folder,suffix in [('windows','desktop','Windows.exe'),('android','android','Android.apk')]:
        file=root/'release'/folder/f'DawnBreaker-{VERSION}-{suffix}'
        envelope=json.loads((root/'release'/f'{platform}-{VERSION}.json').read_text(encoding='utf-8'))
        signed=base64.b64decode(envelope['signed']);public.verify(base64.b64decode(envelope['signature']),signed,padding.PKCS1v15(),hashes.SHA256());payload=json.loads(signed)
        assert payload['version']==VERSION and payload['version_code']==VERSION_CODE and payload['channel']=='stable'
        assert payload['sha256']==hashlib.sha256(file.read_bytes()).hexdigest() and payload['size']==file.stat().st_size
    releases=[];tags=[]
    for page in range(1,101):
        batch=request('GET',repo+'/releases',params={'per_page':100,'page':page});releases+=batch
        if len(batch)<100:break
    for page in range(1,101):
        batch=request('GET',repo+'/tags',params={'per_page':100,'page':page});tags+=batch
        if len(batch)<100:break
    release_tags={release['tag_name'] for release in releases}
    for release in releases:
        request('DELETE',repo+'/releases/'+str(release['id']))
        print('Deleted previous release and installer assets: '+release['tag_name'],flush=True)
    for tag in tags:
        if tag['name'] in release_tags or re.fullmatch(r'v?\d+\.\d+\.\d+',tag['name']):
            request('DELETE',repo+'/git/refs/tags/'+tag['name'])
            print('Deleted previous version tag: '+tag['name'],flush=True)
    assert request('GET',repo+'/releases')==[]
    state.pop('release',None)

if args.action=='release':
    version=VERSION;tag='v'+version
    files=[args.desktop_dir/f'DawnBreaker-{version}-Windows.exe',root/'release/android'/f'DawnBreaker-{version}-Android.apk',root/'release'/f'windows-{version}.json',root/'release'/f'android-{version}.json']
    for file in files:
        if not file.is_file():raise RuntimeError('Missing release artifact: '+file.name)
    source_archive=root/'release'/f'DawnBreaker-{version}-ThirdPartySources.zip'
    if args.repo=='DawnBreaker':
        if not source_archive.is_file():raise RuntimeError('Missing corresponding third-party source archive')
        files.append(source_archive)
    checksums=root/'release/SHA256SUMS.txt'
    checksums.write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files),encoding='utf-8')
    files.append(checksums)
    response=client.get(repo+'/releases/tags/'+tag)
    body=NOTES
    if response.status_code==404:
        release=request('POST',repo+'/releases',json={'tag_name':tag,'target_commitish':branch,'name':'破晓 '+version,'body':body,'draft':True,'prerelease':False})
    elif response.is_success:release=response.json()
    else:raise RuntimeError('Unable to read release')
    existing={asset['name']:asset for asset in request('GET',repo+f"/releases/{release['id']}/assets")}
    for file in files:
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if file.name in existing:
            asset=existing[file.name]
            if asset['size']==file.stat().st_size and asset.get('digest')=='sha256:'+digest:
                print('Verified existing asset '+file.name,flush=True);continue
            # This is our draft release and the exact fixed artifact filename only.
            if not release['draft']:raise RuntimeError('Published asset differs; create a new version instead: '+file.name)
            request('DELETE',repo+'/releases/assets/'+str(asset['id']))
        print('Uploading '+file.name+' ('+str(file.stat().st_size)+' bytes)',flush=True)
        with file.open('rb') as stream:
            response=client.post(f"https://uploads.github.com{repo}/releases/{release['id']}/assets",params={'name':file.name},headers={'Content-Type':mimetypes.guess_type(file.name)[0] or 'application/octet-stream','Content-Length':str(file.stat().st_size)},content=stream,timeout=httpx.Timeout(600,connect=30))
        if response.status_code!=201:raise RuntimeError('Asset upload failed: '+file.name+' HTTP '+str(response.status_code))
        asset=response.json()
        if asset['size']!=file.stat().st_size or asset.get('digest')!='sha256:'+digest:raise RuntimeError('GitHub asset digest mismatch: '+file.name)
        print('SHA256 verified by GitHub: '+file.name,flush=True)
    release=request('PATCH',repo+'/releases/'+str(release['id']),json={'draft':False,'body':body,'make_latest':'true'})
    state['release']=release['html_url'];print('Release published: '+release['html_url'],flush=True)

if args.action=='website':
    web=root/'website'
    # An explicit allowlist is the publication boundary. No project-directory recursion.
    files=[web/'index.html',web/'site.css',web/'site.js',web/'.nojekyll',web/'README.md']
    files+=sorted((web/'assets').glob('*'))
    allowed_extensions={'.html','.css','.js','.webp','.png','.woff2','.txt','.md'}
    for file in files:
        relative=file.relative_to(web)
        if not file.is_file() or (file.name!='.nojekyll' and file.suffix not in allowed_extensions) or len(relative.parts)>2:raise RuntimeError('Unexpected website path: '+str(relative))
        if file.stat().st_size>3*1024*1024:raise RuntimeError('Website asset too large: '+file.name)
    head=request('GET',repo+'/git/ref/heads/'+branch)['object']['sha']
    commit=request('GET',repo+'/git/commits/'+head)
    previous=request('GET',repo+'/git/trees/'+commit['tree']['sha'],params={'recursive':1})
    safe_names={f.relative_to(web).as_posix() for f in files}
    unknown=[f['path'] for f in previous['tree'] if f['type']=='blob' and f['path'] not in safe_names]
    if unknown:raise RuntimeError('Repository contains unexpected files; inspect before publishing: '+', '.join(unknown))
    tree=[]
    for file in files:
        blob=request('POST',repo+'/git/blobs',json={'content':base64.b64encode(file.read_bytes()).decode(),'encoding':'base64'})
        tree.append({'path':file.relative_to(web).as_posix(),'mode':'100644','type':'blob','sha':blob['sha']})
    newtree=request('POST',repo+'/git/trees',json={'base_tree':commit['tree']['sha'],'tree':tree})
    newcommit=request('POST',repo+'/git/commits',json={'message':'Publish DawnBreaker official website and client download links','tree':newtree['sha'],'parents':[head]})
    request('PATCH',repo+'/git/refs/heads/'+branch,json={'sha':newcommit['sha'],'force':False})
    pages=client.get(repo+'/pages')
    if pages.status_code==404:
        request('POST',repo+'/pages',json={'build_type':'legacy','source':{'branch':branch,'path':'/'}})
    elif pages.is_success:
        request('PUT',repo+'/pages',json={'build_type':'legacy','source':{'branch':branch,'path':'/'}})
    else:raise RuntimeError('Cannot inspect GitHub Pages: HTTP '+str(pages.status_code))
    client.post(repo+'/pages/builds')
    state['commit']=newcommit['sha'];state['files']=[f.relative_to(web).as_posix() for f in files]
    print('Website-only files published: '+str(len(files)),flush=True)
    print('Pages: '+state['website'],flush=True)

if args.action=='status':
    pages=client.get(repo+'/pages');build=client.get(repo+'/pages/builds/latest')
    print(json.dumps({'pages':pages.json().get('html_url'),'status':pages.json().get('status'),'build_status':build.json().get('status'),'build_error':build.json().get('error',{}).get('message')},ensure_ascii=True),flush=True)
if state_path.exists():state=json.loads(state_path.read_text(encoding='utf-8'))|state
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
client.close()
