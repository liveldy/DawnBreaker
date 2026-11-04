from remote import connection
import shlex
code='''import urllib.request,json,concurrent.futures,pathlib
urls=['https://api.zeroeval.com/leaderboard/indexes/all','https://api.zeroeval.com/leaderboard/models/full','https://openrouter.ai/api/v1/models']
def check(i):
 try:
  with urllib.request.urlopen(urls[i],timeout=20) as r:
   data=r.read();value=json.loads(data);p=pathlib.Path('/var/lib/dawnbreaker/model-atlas');p.mkdir(exist_ok=True);(p/('raw-'+str(i)+'.json')).write_bytes(data);return (i,r.status,len(data),type(value).__name__)
 except Exception as e:return (i,type(e).__name__,str(e)[:100])
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for r in pool.map(check,range(3)):print(r,flush=True)
'''
with connection() as ssh:
    _,out,err=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code),timeout=40)
    print(out.read().decode());print(err.read().decode())
