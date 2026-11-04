"""Deploy the verified update; delete retired currencies as requested."""
from pathlib import Path
import tarfile,shlex,argparse
from datetime import datetime,timezone
from remote import connection
from deploy import command
from release_common import VERSION
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--code-only',action='store_true');parser.add_argument('--collection-pack',help='Upload only one newly imported collection pack, retaining existing media');args=parser.parse_args()
if args.code_only and args.collection_pack:parser.error('Choose code-only or a collection pack')
selected_ids=None;selected_poster=None
if args.collection_pack:
    import json
    selected_ids={c['id'] for c in json.loads((root/'server/content/cards.json').read_text('utf8'))['cards'] if c.get('album_id')==args.collection_pack}
    spec=next((a for a in json.loads((root/'server/content/card-albums.json').read_text('utf8'))['albums'] if a['id']==args.collection_pack),None)
    if not selected_ids or not spec:raise ValueError('Unknown or empty collection pack')
    selected_poster=spec.get('poster')
release='/opt/dawnbreaker/releases/'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-v'+VERSION
archive=root/'artifacts'/('resources-'+VERSION+'.tar.gz')
with tarfile.open(archive,'w:gz',compresslevel=1) if not args.code_only else __import__('contextlib').nullcontext() as tar:
    if args.code_only:print('Reuse previously deployed media resources',flush=True)
    for folder in ['cards','posters','splashes','rarity','voice']:
        if args.code_only:continue
        for file in (root/'server/content'/folder).rglob('*'):
            if file.is_symlink():raise ValueError('Unexpected resource symlink')
            if file.is_file():
                relative=file.relative_to(root/'server/content').as_posix()
                if selected_ids is not None and not (folder in ('cards','splashes') and file.stem in selected_ids or relative==selected_poster):continue
                tar.add(file,arcname=relative)
with connection() as ssh:
    backup='/var/backups/dawnbreaker/'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-before-'+VERSION+'.db'
    code="import sqlite3,os;os.makedirs('/var/backups/dawnbreaker',mode=0o700,exist_ok=True);a=sqlite3.connect('/var/lib/dawnbreaker/dawn.db');b=sqlite3.connect("+repr(backup)+");a.backup(b);b.close();a.close();os.chmod("+repr(backup)+",0o600)"
    command(ssh,'/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code))
    command(ssh,'cp -a /opt/dawnbreaker/current/. '+release)
    # Replace generated web files completely; do not retain old hashed bundles.
    code="from pathlib import Path;import shutil;p=Path("+repr(release+'/dist')+");assert p.parent.parent==Path('/opt/dawnbreaker/releases') and p.name=='dist';shutil.rmtree(p)"
    command(ssh,'/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code))
    with ssh.open_sftp() as sftp:
        def put(local,remote):
            if local.is_dir():
                try:sftp.mkdir(remote)
                except OSError:pass
                for child in local.iterdir():
                    if child.name!='__pycache__':put(child,remote+'/'+child.name)
            else:sftp.put(str(local),remote)
        put(root/'dist',release+'/dist')
        for path in (root/'server').rglob('*.py'):put(path,release+'/'+path.relative_to(root).as_posix())
        put(root/'server/calendar-data',release+'/server/calendar-data')
        for file in ['cards.json','card-albums.json','lol-quotes.json','music.json']:put(root/'server/content'/file,release+'/server/content/'+file)
        for folder in ['ai','model-atlas']:put(root/'server/content'/folder,release+'/server/content/'+folder)
        put(root/'server/content/audio/022.mp3',release+'/server/content/audio/022.mp3')
        put(root/'requirements.txt',release+'/requirements.txt')
        put(root/'deploy/nginx.conf',release+'/deploy/nginx.conf')
        if not args.code_only:
            print('Uploading full art and voiced quote resources',flush=True)
            previous=[-1]
            def progress(done,total):
                percent=int(done/total*10)*10
                if percent!=previous[0]:print('Resources '+str(percent)+'%',flush=True);previous[0]=percent
            sftp.put(str(archive),release+'/resources.tar.gz',callback=progress)
    if not args.code_only:command(ssh,'tar -xzf '+release+'/resources.tar.gz -C '+release+'/server/content && rm -- '+release+'/resources.tar.gz')
    command(ssh,'test -f '+release+'/server/content/splashes/103027.webp && test -f '+release+'/server/content/voice/lol-001.mp3')
    command(ssh,'/opt/dawnbreaker/venv/bin/pip install -q -r '+release+'/requirements.txt',timeout=300)
    command(ssh,'mkdir -p /var/lib/dawnbreaker/model-atlas && chown dawnbreaker:dawnbreaker /var/lib/dawnbreaker/model-atlas && chmod 700 /var/lib/dawnbreaker/model-atlas')
    command(ssh,'cp '+release+'/deploy/nginx.conf /etc/nginx/conf.d/dawnbreaker.conf && nginx -t')
    command(ssh,'ln -sfn '+release+' /opt/dawnbreaker/current && systemctl restart dawnbreaker && systemctl reload nginx')
    command(ssh,'sleep 2; curl --fail --silent http://127.0.0.1:7779/api/health; echo; curl --fail --silent http://127.0.0.1:7780/api/health; echo; systemctl is-active dawnbreaker nginx')
print('Deployed v'+VERSION+'; API :7779, web :7780')
