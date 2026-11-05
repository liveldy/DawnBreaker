"""Administrator-managed fixed egress. Subscription refresh never changes live routing."""
import hashlib,http.client,ipaddress,json,os,socket,ssl,subprocess,tempfile,threading,time,uuid
from pathlib import Path
from urllib.parse import urlsplit,quote
import httpx
from fastapi import HTTPException
from . import db
from .secret_store import seal,open_secret
from .egress_nodes import subscription_nodes

ROOT=db.DATA/'xai-egress';LOCK=threading.Lock();KEY='xai-egress'

def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False)
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def configured_proxy():
    path=ROOT/'runtime.json'
    if not path.exists():return os.environ.get('DAWN_XAI_HTTPS_PROXY','').strip()
    try:
        value=json.loads(path.read_text('utf8'))
        if not value.get('enabled'):raise HTTPException(503,'管理员已停用 xAI 出站，请联系管理员启用。')
        proxy=value['proxy_url']
        if not isinstance(proxy,str) or not proxy.strip():raise ValueError('empty proxy')
        return proxy
    except HTTPException:raise
    except Exception:raise HTTPException(503,'xAI 出站配置暂时不可用，请联系管理员')

def connection():
    try:return json.loads((ROOT/'connection.json').read_text('utf8'))
    except Exception:raise HTTPException(503,'服务器尚未部署 xAI 出站组件，请先由维护者安装组件')

def stored():
    with db.connect() as d:
        row=d.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
    return json.loads(row[0]) if row else {}

def profile(value):
    try:return json.loads(open_secret(value['profile'])) if value.get('profile') else {'nodes':[],'url':''}
    except Exception:raise HTTPException(503,'出站配置无法读取，请重新导入订阅')

def public(value=None):
    value=stored() if value is None else value;p=profile(value);url=urlsplit(p.get('url',''))
    return {'available':(ROOT/'connection.json').exists(),'enabled':value.get('enabled',False),'has_subscription':bool(p.get('url')),'subscription_hint':url.netloc+'/…' if url.netloc else '', 'revision':value.get('revision',''),'fetched_at':value.get('fetched_at'),'nodes':[{k:n[k] for k in ('id','name','type')} for n in p['nodes']],'active':value.get('active'),'last_test':value.get('last_test'),'test':value.get('test'),'updated_at':value.get('updated_at')}

def save(value,actor,action):
    value['updated_at']=db.now()
    with db.connect(True) as d:
        d.execute('INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(KEY,json.dumps(value,ensure_ascii=False),value['updated_at']))
        safe=public(value)
        d.execute('INSERT INTO audit(actor_id,target_id,action,before_json,after_json,created_at) VALUES(?,?,?,?,?,?)',(actor,None,action,'null',json.dumps({k:safe[k] for k in ('enabled','revision','fetched_at','active')},ensure_ascii=False),db.now()))

def fetch_subscription(url):
    from .outbound import endpoint,public_addresses
    parsed=urlsplit(url)
    if parsed.fragment or len(url)>4000:raise HTTPException(422,'订阅地址格式无效')
    clean=parsed._replace(query='').geturl();p,port=endpoint(clean);ips=public_addresses(p.hostname,port)
    class Pinned(http.client.HTTPSConnection):
        def connect(self):
            for ip in ips:
                try:self.sock=self._context.wrap_socket(socket.create_connection((ip,port),timeout=10),server_hostname=p.hostname);self.sock.settimeout(20);return
                except OSError:continue
            raise OSError('unreachable')
    c=Pinned(p.hostname,port,context=ssl.create_default_context())
    try:
        c.request('GET',(p.path or '/')+('?' + parsed.query if parsed.query else ''),headers={'User-Agent':'clash.meta/DawnBreaker','Accept':'text/plain,application/yaml,application/json'})
        r=c.getresponse()
        if r.status!=200:raise HTTPException(502,'订阅读取失败（HTTP '+str(r.status)+'），请核对地址；不接受跳转')
        raw=r.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise HTTPException(422,'订阅文件超过 2 MB')
        return raw
    except HTTPException:raise
    except Exception:raise HTTPException(502,'无法安全读取订阅，请检查地址、证书与服务器网络')
    finally:c.close()

def import_subscription(url,actor):
    value=stored();url=url.strip() or profile(value).get('url','')
    if not url:raise HTTPException(422,'请输入订阅地址')
    try:nodes=subscription_nodes(fetch_subscription(url))
    except (ValueError,TypeError,UnicodeError):raise HTTPException(422,'订阅没有可读取的受支持节点，请使用节点链接或 Clash 订阅')
    value.update(profile=seal(json.dumps({'url':url,'nodes':nodes},ensure_ascii=False)),revision=uuid.uuid4().hex,fetched_at=db.now(),test=None)
    save(value,actor,'更新 xAI 出站订阅（未切换节点）');return public(value)

def proxy_url(c,port=None):return 'http://'+quote(c['username'],safe='')+':'+quote(c['password'],safe='')+'@127.0.0.1:'+str(port or c['mixed_port'])

def build_config(node,c,port=None,controller=True):
    fixed=dict(node['config']);fixed['name']='xai-fixed'
    value={'mixed-port':port or c['mixed_port'],'allow-lan':False,'bind-address':'127.0.0.1','mode':'rule','log-level':'warning','ipv6':False,'authentication':[c['username']+':'+c['password']],'dns':{'enable':True,'ipv6':False,'enhanced-mode':'redir-host','default-nameserver':['223.5.5.5'],'proxy-server-nameserver':['223.5.5.5','1.12.12.12'],'nameserver':['https://1.1.1.1/dns-query#xai-fixed']},'proxies':[fixed],'rules':['MATCH,xai-fixed']}
    if controller:value.update({'external-controller':'127.0.0.1:'+str(c['controller_port']),'secret':c['controller_secret']})
    return value

def health(proxy):
    start=time.monotonic()
    try:
        with httpx.Client(proxy=proxy,trust_env=False,timeout=httpx.Timeout(20,connect=10),follow_redirects=False) as c:
            r=c.get('https://www.cloudflare.com/cdn-cgi/trace');r.raise_for_status();trace=dict(line.split('=',1) for line in r.text.splitlines() if '=' in line);ip=trace.get('ip');assert ip and ipaddress.ip_address(ip).is_global
            # No inference key and no billable model call are used for this test.
            r=c.get('https://api.x.ai/v1/models')
            if r.status_code not in (200,401):raise ValueError()
            return {'ok':True,'exit_ip':ip,'region':trace.get('loc'),'latency_ms':round((time.monotonic()-start)*1000),'checked_at':db.now(),'epoch':time.time()}
    except Exception:return {'ok':False,'error':'节点无法完成 xAI 的 TLS / HTTP 连通检查，未使用任何模型密钥','checked_at':db.now(),'epoch':time.time()}

def chosen(value,node_id,revision):
    if not revision or value.get('revision')!=revision:raise HTTPException(409,'订阅已更新，请重新选择节点')
    node=next((n for n in profile(value)['nodes'] if n['id']==node_id),None)
    if not node:raise HTTPException(422,'请选择当前订阅中的节点')
    return node

def test_candidate(node_id,revision,actor):
    value=stored();node=chosen(value,node_id,revision);c=connection();ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    process=None
    with tempfile.TemporaryDirectory(prefix='test-',dir=ROOT) as folder:
        path=Path(folder);atomic(path/'config.json',build_config(node,c,port,False))
        try:
            process=subprocess.Popen([c['core'],'-d',folder,'-f',str(path/'config.json')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(60):
                if process.poll() is not None:break
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.1)
            result=health(proxy_url(c,port))
        except Exception:result={'ok':False,'error':'无法启动独立节点测试，当前出口未改变','checked_at':db.now(),'epoch':time.time()}
        finally:
            if process is not None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    value['test']=result|{'node_id':node_id,'revision':revision};save(value,actor,'测试 xAI 候选节点（未切换）');return public(value)

def reload_core(config,c):
    try:
        with httpx.Client(trust_env=False,timeout=15) as client:
            r=client.put('http://127.0.0.1:'+str(c['controller_port'])+'/configs',params={'force':'true'},headers={'Authorization':'Bearer '+c['controller_secret']},json={'payload':json.dumps(config)})
            if r.status_code not in (200,204):raise ValueError()
    except Exception:raise HTTPException(502,'出站组件未能应用配置，当前设置未保存')

def activate(node_id,revision,actor):
    value=stored();node=chosen(value,node_id,revision);tested=value.get('test') or {}
    if not tested.get('ok') or tested.get('node_id')!=node_id or tested.get('revision')!=revision or time.time()-tested.get('epoch',0)>600:raise HTTPException(409,'请先测试所选节点，测试通过后 10 分钟内应用')
    c=connection();config=build_config(node,c);path=ROOT/'active.json';old=json.loads(path.read_text('utf8')) if path.exists() else None
    runtime=ROOT/'runtime.json';old_runtime=json.loads(runtime.read_text('utf8')) if runtime.exists() else None
    reload_core(config,c)
    try:
        atomic(path,config);atomic(ROOT/'runtime.json',{'enabled':True,'proxy_url':proxy_url(c)})
        value.update(enabled=True,active={'node_id':node_id,'name':node['name'],'type':node['type'],'exit_ip':tested.get('exit_ip'),'region':tested.get('region'),'applied_at':db.now()},last_test=tested)
        save(value,actor,'应用固定 xAI 出站节点')
    except Exception:
        try:
            if old:reload_core(old,c);atomic(path,old)
            if old_runtime is not None:atomic(runtime,old_runtime)
            else:runtime.unlink(missing_ok=True)
        except Exception:
            atomic(runtime,{'enabled':False})
            raise HTTPException(502,'出站配置保存失败，已暂停 xAI 请求，请管理员检查后重试')
        raise
    return public(value)

def enabled(enabled,actor):
    value=stored();c=connection()
    if enabled and not value.get('active'):raise HTTPException(409,'请先测试并应用一个固定节点')
    runtime=ROOT/'runtime.json';old=json.loads(runtime.read_text('utf8')) if runtime.exists() else None
    value['enabled']=enabled;atomic(runtime,{'enabled':enabled,'proxy_url':proxy_url(c)})
    try:save(value,actor,'启用 xAI 固定出站' if enabled else '停用 xAI 出站')
    except Exception:
        if old is not None:atomic(runtime,old)
        else:runtime.unlink(missing_ok=True)
        raise
    return public(value)

def test_current(actor):
    value=stored()
    if not value.get('enabled'):raise HTTPException(409,'xAI 出站已停用')
    result=health(configured_proxy());previous=(value.get('active') or {}).get('exit_ip')
    if result.get('ok') and previous and result.get('exit_ip')!=previous:result.update(ip_changed=True,warning='上游节点出口 IP 已变化；当前节点保持不变，请管理员检查')
    value['last_test']=result;save(value,actor,'检查当前 xAI 出站');return public(value)
