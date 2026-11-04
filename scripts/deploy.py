"""Build artifacts must be verified locally before this explicit deployment.

Only allowlisted runtime files are uploaded, never source briefs/credentials.
Existing releases are retained; each deployment uses a new release directory.
"""
import os
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from remote import connection

ROOT=Path(__file__).resolve().parents[1]
STAMP=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
ARCHIVE=ROOT/'artifacts'/'dawnbreaker-server.tar.gz'
ARCHIVE.parent.mkdir(exist_ok=True)

def command(ssh,text,timeout=600):
    _,out,err=ssh.exec_command(text,timeout=timeout)
    while True:
        line=out.readline()
        if not line: break
        print(line.rstrip(),flush=True)
    code=out.channel.recv_exit_status()
    error=err.read().decode()
    if error: print(error[-5000:],flush=True)
    if code: raise RuntimeError(f'Remote command failed ({code})')

if __name__=='__main__':
    with tarfile.open(ARCHIVE,'w:gz',compresslevel=2) as tar:
        for relative in ['dist','server','deploy','requirements.txt']:
            tar.add(ROOT/relative,arcname=relative,filter=lambda info:None if '__pycache__' in info.name or info.name.endswith('.pyc') else info)
    print(f'Packaged {ARCHIVE.stat().st_size//1024//1024} MB, credentials excluded',flush=True)
    with connection() as ssh:
        command(ssh,"test -z \"$(ss -ltnH 'sport = :7779')\" && test -z \"$(ss -ltnH 'sport = :7780')\" || systemctl is-active --quiet dawnbreaker")
        command(ssh,'mkdir -p /opt/dawnbreaker/releases /var/lib/dawnbreaker')
        last=[-1]
        def progress(done,total):
            percent=int(done/total*10)*10
            if percent!=last[0]: print(f'Upload {percent}%',flush=True); last[0]=percent
        with ssh.open_sftp() as sftp: sftp.put(str(ARCHIVE),'/opt/dawnbreaker/upload.tar.gz',callback=progress)
        release='/opt/dawnbreaker/releases/'+STAMP
        command(ssh,f'mkdir -p {release} && tar -xzf /opt/dawnbreaker/upload.tar.gz -C {release}')
        command(ssh,'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv nginx',timeout=600)
        command(ssh,'test -x /opt/dawnbreaker/venv/bin/python || python3 -m venv /opt/dawnbreaker/venv')
        command(ssh,f'/opt/dawnbreaker/venv/bin/pip install -q -r {release}/requirements.txt',timeout=600)
        command(ssh,'id dawnbreaker >/dev/null 2>&1 || useradd --system --home /var/lib/dawnbreaker --shell /usr/sbin/nologin dawnbreaker')
        command(ssh,'chown dawnbreaker:dawnbreaker /var/lib/dawnbreaker && chmod 750 /var/lib/dawnbreaker')
        command(ssh,f'ln -sfn {release} /opt/dawnbreaker/current && cp {release}/deploy/dawnbreaker.service /etc/systemd/system/dawnbreaker.service && cp {release}/deploy/nginx.conf /etc/nginx/conf.d/dawnbreaker.conf')
        # A fresh nginx install's sample vhost is outside this app's requested ports.
        command(ssh,'if test -L /etc/nginx/sites-enabled/default && grep -q "Welcome to nginx" /var/www/html/index.nginx-debian.html 2>/dev/null; then unlink /etc/nginx/sites-enabled/default; fi; nginx -t')
        command(ssh,'systemctl daemon-reload && systemctl enable dawnbreaker nginx && systemctl restart dawnbreaker && systemctl reload-or-restart nginx')
        command(ssh,'sleep 2; curl --fail --silent http://127.0.0.1:7779/api/health; echo; curl --fail --silent http://127.0.0.1:7780/api/health; echo; systemctl is-active dawnbreaker nginx; ss -ltnH "sport = :7779 or sport = :7780"')
    print('Deployment verified: API :7779 / web :7780',flush=True)
