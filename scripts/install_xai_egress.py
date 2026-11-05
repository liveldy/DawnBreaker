"""Run as root on the Linux server with a separately verified Mihomo binary.

No subscriptions, nodes or inference credentials are embedded in this installer.
The administrator imports and applies a tested fixed node in the app afterwards.
"""
import argparse,json,os,secrets,shutil,subprocess,pwd
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--core',type=Path,required=True);parser.add_argument('--data',type=Path,default=Path('/var/lib/dawnbreaker'));args=parser.parse_args()
    if os.name!='posix' or os.geteuid()!=0:raise SystemExit('Run as root on the Linux server')
    root=args.data.resolve()/'xai-egress';root.mkdir(parents=True,exist_ok=True,mode=0o700);account=pwd.getpwnam('dawnbreaker')
    binary=Path('/opt/dawnbreaker-xai-egress/mihomo');binary.parent.mkdir(parents=True,exist_ok=True)
    if args.core.resolve()!=binary:shutil.copyfile(args.core,binary)
    binary.chmod(0o755)
    credentials=root/'connection.json'
    if credentials.exists():config=json.loads(credentials.read_text('utf8'))
    else:config={'core':str(binary),'mixed_port':17891,'controller_port':17892,'username':'dawn-xai','password':secrets.token_hex(24),'controller_secret':secrets.token_hex(32)}
    for port in (config['mixed_port'],config['controller_port']):
        import socket
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0 and not credentials.exists():raise SystemExit('Chosen loopback port is already occupied')
    def write(path,value):
        path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8');path.chmod(0o600);os.chown(path,account.pw_uid,account.pw_gid)
    write(credentials,config)
    if not (root/'active.json').exists():write(root/'active.json',{'mixed-port':config['mixed_port'],'allow-lan':False,'bind-address':'127.0.0.1','external-controller':'127.0.0.1:'+str(config['controller_port']),'secret':config['controller_secret'],'authentication':[config['username']+':'+config['password']],'mode':'rule','log-level':'warning','proxies':[],'rules':['MATCH,REJECT']})
    if not (root/'runtime.json').exists():write(root/'runtime.json',{'enabled':False})
    os.chown(root,account.pw_uid,account.pw_gid)
    unit=f'''[Unit]
Description=DawnBreaker administrator-managed fixed xAI egress
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=dawnbreaker
Group=dawnbreaker
WorkingDirectory={root}
ExecStart={binary} -d {root} -f {root}/active.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={root}
[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system/dawnbreaker-xai-egress.service').write_text(unit)
    subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','--now','dawnbreaker-xai-egress'],check=True);subprocess.run(['systemctl','restart','dawnbreaker-xai-egress'],check=True)
    print('Installed loopback-only, authenticated egress. Configure it under Admin > AI egress.')
if __name__=='__main__':main()
