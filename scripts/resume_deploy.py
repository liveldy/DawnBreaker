"""Resume an uploaded release after an interrupted dependency install.

Also synchronize current application source and the final verified web build.
"""
from pathlib import Path
from remote import connection
from deploy import command

ROOT=Path(__file__).resolve().parents[1]
with connection() as ssh:
    with ssh.open_sftp() as sftp:
        names=[n for n in sftp.listdir('/opt/dawnbreaker/releases') if n[:8].isdigit()]
        if not names: raise RuntimeError('No uploaded release to resume')
        release='/opt/dawnbreaker/releases/'+max(names)
        def put(local,remote):
            if local.is_dir():
                try: sftp.mkdir(remote)
                except OSError: pass
                for p in local.iterdir():
                    if p.name!='__pycache__': put(p,remote+'/'+p.name)
            else: sftp.put(str(local),remote)
        put(ROOT/'dist',release+'/dist')
        for p in (ROOT/'server').rglob('*.py'): put(p,release+'/'+p.relative_to(ROOT).as_posix())
        put(ROOT/'deploy',release+'/deploy')
        put(ROOT/'requirements.txt',release+'/requirements.txt')
        print('Synchronized final web and API source',flush=True)
    command(ssh,f'/opt/dawnbreaker/venv/bin/pip install -q --timeout 60 --retries 4 --resume-retries 6 -i https://mirrors.aliyun.com/pypi/simple -r {release}/requirements.txt',timeout=900)
    command(ssh,'id dawnbreaker >/dev/null 2>&1 || useradd --system --home /var/lib/dawnbreaker --shell /usr/sbin/nologin dawnbreaker')
    command(ssh,'chown dawnbreaker:dawnbreaker /var/lib/dawnbreaker && chmod 750 /var/lib/dawnbreaker')
    command(ssh,f'ln -sfn {release} /opt/dawnbreaker/current && cp {release}/deploy/dawnbreaker.service /etc/systemd/system/dawnbreaker.service && cp {release}/deploy/nginx.conf /etc/nginx/conf.d/dawnbreaker.conf')
    command(ssh,'if test -L /etc/nginx/sites-enabled/default && grep -q "Welcome to nginx" /var/www/html/index.nginx-debian.html 2>/dev/null; then unlink /etc/nginx/sites-enabled/default; fi; nginx -t')
    command(ssh,'systemctl daemon-reload && systemctl enable dawnbreaker nginx && systemctl restart dawnbreaker && systemctl reload-or-restart nginx')
    command(ssh,'sleep 2; curl --fail --silent http://127.0.0.1:7779/api/health; echo; curl --fail --silent http://127.0.0.1:7780/api/health; echo; systemctl is-active dawnbreaker nginx; ss -ltnH "sport = :7779 or sport = :7780"')
print('Deployment verified: API :7779 / web :7780',flush=True)
