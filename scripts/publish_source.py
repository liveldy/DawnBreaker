"""Publish explicitly allowlisted app source to a new public repo, never the website repo."""
import base64,getpass,json,os,re,subprocess,sys
from pathlib import Path
import httpx
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
NAME='DawnBreaker'
def git(*args,env=None):
    r=subprocess.run(['git',*args],cwd=ROOT,env=env,capture_output=True,timeout=90)
    if r.returncode:raise RuntimeError('Git operation failed: '+args[0]+'; '+r.stderr.decode('utf8','replace')[:300])
    return r.stdout.decode('utf8','replace').strip()
def main():
    token=getpass.getpass('GitHub token (hidden): ')
    with httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},timeout=60,trust_env=False) as c:
        r=c.get('/user');r.raise_for_status();owner=r.json()['login'];repo='/repos/'+owner+'/'+NAME
        statefile=ROOT/'.local/source-repo.json'
        state=json.loads(statefile.read_text('utf8')) if statefile.exists() else {}
        r=c.get(repo)
        if r.status_code==404:
            r=c.post('/user/repos',json={'name':NAME,'description':'破晓 DawnBreaker · Windows / Android / Web / Server · AGPL-3.0-or-later','private':False,'auto_init':False,'has_wiki':False,'has_projects':False});r.raise_for_status()
            statefile.parent.mkdir(exist_ok=True);statefile.write_text(json.dumps({'id':r.json()['id'],'name':NAME}),encoding='utf8')
        else:
            r.raise_for_status()
            if state.get('id')!=r.json()['id'] or state.get('name')!=NAME:raise RuntimeError('Repository already exists and was not created for this task; no changes made')
            if r.json()['private']:raise RuntimeError('Existing repository visibility differs; no changes made')
        if NAME=='dawnbreaker-website':raise RuntimeError('Website repository is not a source target')
        if not (ROOT/'.git').exists():git('init','-b','main')
        git('config','user.name',owner);git('config','user.email',owner+'@users.noreply.github.com')
        paths=['.gitignore','.github','LICENSE','README.md','DESIGN.md','PRODUCT.md','COLLECTIONS.md','package.json','package-lock.json','tsconfig.json','vite.config.ts','capacitor.config.json','index.html','requirements.txt','requirements-dev.txt','src','public','server','clients','android','deploy','scripts','tests','docs','third_party','release-notes','website']
        git('add','--',*paths)
        files=git('ls-files','-z').split('\x00');files=[p for p in files if p]
        forbidden=re.compile(r'(^|/)(data|mods?|node_modules|\.local|\.tooling|\.taste-skill|artifacts|release|build|dist|\.gradle|__pycache__)(/|$)|(^|/)(DawnBreaker\.md|local\.properties|service-secret\.key)$|\.(db|jks|keystore|aar|exe|apk)$',re.I)
        patterns=[re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
        for name in files:
            if forbidden.search(name) or name.startswith(('server/content/','clients/desktop/web/','android/app/src/main/assets/public/','android/app/src/main/assets/linkswift/')):raise RuntimeError('Excluded file staged: '+name)
            path=ROOT/name
            if path.is_symlink():raise RuntimeError('Source symlink needs manual review: '+name)
            data=path.read_bytes()
            if token.encode() in data or any(p.search(data) for p in patterns):raise RuntimeError('Credential pattern found; file withheld: '+name)
        if git('diff','--cached','--name-only'):
            git('commit','-m','Update DawnBreaker to '+json.loads((ROOT/'package.json').read_text('utf8'))['version'])
        url='https://github.com/'+owner+'/'+NAME+'.git'
        remotes=git('remote').splitlines()
        if 'origin' not in remotes:git('remote','add','origin',url)
        elif git('remote','get-url','origin')!=url:raise RuntimeError('Existing origin differs; no remote overwritten')
        # REST Git objects avoid interactive credential helpers and unreliable large smart-HTTP pushes.
        r=c.get(repo+'/git/ref/heads/main')
        if r.status_code in (404,409):
            r=c.put(repo+'/contents/README.md',json={'message':'Initialize open-source DawnBreaker repository','content':base64.b64encode((ROOT/'README.md').read_bytes()).decode(),'branch':'main'});r.raise_for_status()
            r=c.get(repo+'/git/ref/heads/main')
        r.raise_for_status();parent=r.json()['object']['sha']
        previous=c.get(repo+'/git/commits/'+parent);previous.raise_for_status()
        previous=c.get(repo+'/git/trees/'+previous.json()['tree']['sha'],params={'recursive':1});previous.raise_for_status()
        existing={f['sha'] for f in previous.json()['tree'] if f['type']=='blob'}
        entries=git('ls-tree','-r','-z','HEAD').split('\x00');tree=[]
        for entry in filter(None,entries):
            metadata,name=entry.split('\t',1);mode,kind,sha=metadata.split();tree.append({'path':name,'mode':mode,'type':kind,'sha':sha})
        unique={e['sha'] for e in tree}
        def blob(sha):
            data=subprocess.check_output(['git','cat-file','blob',sha],cwd=ROOT)
            response=c.post(repo+'/git/blobs',json={'encoding':'base64','content':base64.b64encode(data).decode()});response.raise_for_status()
            if response.json()['sha']!=sha:raise RuntimeError('Blob hash mismatch')
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(blob,unique-existing))
        r=c.post(repo+'/git/trees',json={'tree':tree});r.raise_for_status();tree_sha=r.json()['sha']
        if tree_sha!=git('rev-parse','HEAD^{tree}'):raise RuntimeError('Source tree verification failed')
        r=c.post(repo+'/git/commits',json={'message':'Publish reviewed DawnBreaker source for all platforms','tree':tree_sha,'parents':[parent] if parent else []});r.raise_for_status();sha=r.json()['sha']
        r=c.patch(repo+'/git/refs/heads/main',json={'sha':sha,'force':False}) if parent else c.post(repo+'/git/refs',json={'ref':'refs/heads/main','sha':sha});r.raise_for_status()
        r=c.get(repo+'/commits/main');r.raise_for_status()
        if r.json()['sha']!=sha:raise RuntimeError('Remote commit verification failed')
        statefile.write_text(json.dumps({'id':state.get('id') or c.get(repo).json()['id'],'name':NAME,'commit':sha,'tree':tree_sha}),encoding='utf8')
        print('Published '+str(len(files))+' source files: https://github.com/'+owner+'/'+NAME,flush=True)
        print('Verified commit: '+sha,flush=True)
if __name__=='__main__':main()
