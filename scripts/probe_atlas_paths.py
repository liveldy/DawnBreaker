from remote import connection
import shlex
code='''import urllib.request,concurrent.futures
urls=['https://api.zeroeval.com/leaderboard/indexes/all','https://api.llm-stats.com/leaderboard/indexes/all','https://llm-stats.com/api/leaderboard/indexes/all','https://r.jina.ai/https://api.zeroeval.com/leaderboard/indexes/all','https://r.jina.ai/https://api.zeroeval.com/leaderboard/models/full']
def check(url):
 try:
  q=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Referer':'https://llm-stats.com/','Origin':'https://llm-stats.com'})
  with urllib.request.urlopen(q,timeout=35) as r:
   data=r.read();return (url,r.status,len(data),data[:160].decode(errors='replace'))
 except urllib.error.HTTPError as e:return (url,e.code,e.read()[:180].decode(errors='replace'))
 except Exception as e:return(url,type(e).__name__,str(e)[:90])
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 for r in pool.map(check,urls):print(r,flush=True)
'''
with connection() as ssh:
    _,out,err=ssh.exec_command('/opt/dawnbreaker/venv/bin/python -c '+shlex.quote(code),timeout=55)
    print(out.read().decode());print(err.read().decode())
