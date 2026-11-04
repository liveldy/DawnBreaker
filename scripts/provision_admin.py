import json
import secrets
from pathlib import Path
import httpx
from remote import connection

folder=Path(__file__).resolve().parents[1]/'.local';folder.mkdir(exist_ok=True)
file=folder/'admin-credentials.json'
if file.exists(): credentials=json.loads(file.read_text(encoding='utf-8'))
else:
    credentials={'username':'admin','password':secrets.token_urlsafe(24)}
    file.write_text(json.dumps(credentials,ensure_ascii=False,indent=2),encoding='utf-8')
with connection() as ssh:
    stdin,out,err=ssh.exec_command('cd /opt/dawnbreaker/current && DAWN_DATA_DIR=/var/lib/dawnbreaker runuser -u dawnbreaker -- /opt/dawnbreaker/venv/bin/python -m server.bootstrap_admin')
    stdin.write(json.dumps(credentials));stdin.channel.shutdown_write()
    result=out.read().decode();error=err.read().decode()
    if out.channel.recv_exit_status()!=0: raise RuntimeError(error)
    print(result.strip())
base='http://110.42.63.153:7780'
with httpx.Client(base_url=base,trust_env=False,timeout=30) as c:
    r=c.post('/api/auth/login',json=credentials);r.raise_for_status()
    assert c.get('/api/bootstrap').json()['user']['role']=='admin'
    assert c.get('/api/admin/users').status_code==200
    c.post('/api/auth/logout')
(folder/'管理员账号.txt').write_text('破晓管理员（网页、Windows、Android 共用）\n\n网页：http://110.42.63.153:7780\n账号：'+credentials['username']+'\n密码：'+credentials['password']+'\n\n登录后在侧栏进入「管理后台」。可在「个人信息」修改密码。\n',encoding='utf-8-sig')
print('Verified administrator login and permissions; credentials saved to .local/管理员账号.txt')
