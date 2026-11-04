"""Deployment helper; credentials are read in memory from the user's brief.

Never copy the brief to deployment archives. No secrets in CLI arguments/logs.
"""
import re
import sys
from pathlib import Path
import paramiko

def connection():
    brief = Path('DawnBreaker.md').read_text(encoding='utf-8')
    host = re.search(r'IP地址：([^\s]+)', brief)[1]
    username = re.search(r'用户名：([^\s]+)', brief)[1]
    password = re.search(r'远程密码：([^\s]+)', brief)[1]
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    # Persist a first-seen host key; subsequent connections verify it.
    known = Path.home() / '.ssh' / 'known_hosts'
    known.parent.mkdir(exist_ok=True)
    if not known.exists(): known.touch()
    client.load_host_keys(str(known))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password, timeout=15, look_for_keys=False, allow_agent=False)
    return client

if __name__ == '__main__':
    with connection() as ssh:
        if sys.argv[1]=='inspect':
            command='uname -a; cat /etc/os-release; command -v python3; python3 --version; command -v docker; df -h /; ss -ltnp; ls -ld /opt/dawnbreaker 2>/dev/null || true'
        elif sys.argv[1]=='services':
            command='command -v nginx; command -v ffmpeg; command -v curl; ss -ltn; systemctl is-active nginx || true; test -d /opt/dawnbreaker && echo DAWN_DIRECTORY_EXISTS || true'
        else:
            raise SystemExit('Unknown operation')
        _,out,err=ssh.exec_command(command,timeout=30)
        print(out.read().decode()); print(err.read().decode())
