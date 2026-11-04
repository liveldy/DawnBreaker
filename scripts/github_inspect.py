"""Read GitHub identity/permissions with a token entered only through stdin."""
import getpass,json,httpx
from pathlib import Path
token=getpass.getpass('GitHub token (hidden): ')
with httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},timeout=30,trust_env=False) as client:
    response=client.get('/user')
    if response.status_code!=200:raise SystemExit('GitHub authentication failed: HTTP '+str(response.status_code))
    login=response.json()['login'];name='dawnbreaker-website'
    repo=client.get('/repos/'+login+'/'+name)
    state={'login':login,'scopes':response.headers.get('x-oauth-scopes'),'repo':name,'exists':repo.status_code==200,'permissions':repo.json().get('permissions') if repo.status_code==200 else None,'status':repo.status_code}
    Path('.local/github-state.json').write_text(json.dumps(state),encoding='utf-8')
    print(json.dumps(state,ensure_ascii=True))
