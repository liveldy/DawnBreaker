"""Publish explicitly allowlisted app source to a new public repo, never the website repo."""
import base64,getpass,json,os,re,subprocess,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
NAME='dawnbreaker'
def git(*args,env=None):
    r=subprocess.run(['git',*args],cwd=ROOT,env=env,capture_output=True)
    if r.returncode:raise RuntimeError('Git operation failed: '+args[0]+'; '+r.stderr.decode('utf8','replace')[:300])
    return r.stdout.decode('utf8','replace').strip()
def main():
    token=getpass.getpass('GitHub token (hidden): ')
    with httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},timeout=60,trust_env=False) as c:
        r=c.get('/user');r.raise_for_status();owner=r.json()['login'];repo='/repos/'+owner+'/'+NAME
        r=c.get(repo)
        if r.status_code==404:
            r=c.post('/user/repos',json={'name':NAME,'description':'破晓 DawnBreaker · Windows / Android / Web / Server · AGPL-3.0-or-later','private':False,'auto_init':False,'has_wiki':False,'has_projects':False});r.raise_for_status()
        else:
            r.raise_for_status()
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
            git('commit','-m','Open source DawnBreaker across Windows, Android, Web and Server')
        url='https://github.com/'+owner+'/'+NAME+'.git'
        remotes=git('remote').splitlines()
        if 'origin' not in remotes:git('remote','add','origin',url)
        elif git('remote','get-url','origin')!=url:raise RuntimeError('Existing origin differs; no remote overwritten')
        auth=base64.b64encode(('x-access-token:'+token).encode()).decode()
        env=os.environ.copy();env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth,GIT_TERMINAL_PROMPT='0')
        git('push','-u','origin','main',env=env)
        sha=git('rev-parse','HEAD');r=c.get(repo+'/commits/main');r.raise_for_status()
        if r.json()['sha']!=sha:raise RuntimeError('Remote commit verification failed')
        print('Published '+str(len(files))+' source files: https://github.com/'+owner+'/'+NAME,flush=True)
        print('Verified commit: '+sha,flush=True)
if __name__=='__main__':main()
