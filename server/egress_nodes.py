"""Read subscription nodes only; never import listeners, rules or remote providers."""
import base64,hashlib,json
from urllib.parse import urlsplit,parse_qs,unquote

def decode64(value):return base64.urlsafe_b64decode(value+'='*(-len(value)%4)).decode('utf-8')

def subscription_nodes(raw):
    text=raw.decode('utf-8-sig').strip();nodes=[]
    if text.startswith(('{','[')):
        value=json.loads(text);nodes=value.get('proxies',[]) if isinstance(value,dict) else value
    elif '\nproxies:' in '\n'+text:
        import yaml
        class NoAliases(yaml.SafeLoader):
            def compose_node(self,parent,index):
                if self.check_event(yaml.AliasEvent):raise ValueError('订阅不支持 YAML 引用')
                return super().compose_node(parent,index)
        value=yaml.load(text,Loader=NoAliases);nodes=value.get('proxies',[]) if isinstance(value,dict) else []
    else:
        if '://' not in text:text=decode64(text)
        for line in text.splitlines():
            try:
                p=urlsplit(line.strip());q=parse_qs(p.query);one=lambda k,default='':q.get(k,[default])[0]
                node={'name':unquote(p.fragment)[:160] or p.hostname,'server':p.hostname,'port':p.port,'type':p.scheme}
                if p.scheme=='ss':
                    auth=unquote(p.username or '')
                    cipher,password=(auth,unquote(p.password)) if p.password is not None else decode64(auth).split(':',1)
                    node.update(cipher=cipher,password=password)
                    if one('plugin'):continue
                elif p.scheme in ('trojan','anytls'):
                    node.update(password=unquote(p.username or ''),sni=one('sni') or one('peer'),**{'skip-cert-verify':False})
                elif p.scheme=='vless':
                    node['uuid']=unquote(p.username or '');node['tls']=one('security') in ('tls','reality');node['servername']=one('sni');node['client-fingerprint']=one('fp','chrome')
                    if one('flow'):node['flow']=one('flow')
                    if one('security')=='reality':node['reality-opts']={'public-key':one('pbk'),'short-id':one('sid')}
                    network=one('type','tcp')
                    if network=='ws':node.update(network='ws',**{'ws-opts':{'path':one('path','/'),'headers':{'Host':one('host')}}})
                    elif network=='grpc':node.update(network='grpc',**{'grpc-opts':{'grpc-service-name':one('serviceName')}})
                    elif network!='tcp':continue
                elif p.scheme=='vmess':
                    v=json.loads(decode64(line.strip()[8:]));node={'name':str(v.get('ps','VMess')),'type':'vmess','server':v['add'],'port':int(v['port']),'uuid':v['id'],'alterId':int(v.get('aid',0)),'cipher':v.get('scy','auto'),'tls':v.get('tls')=='tls','servername':v.get('sni','')}
                    if v.get('net')=='ws':node.update(network='ws',**{'ws-opts':{'path':v.get('path','/'),'headers':{'Host':v.get('host','')}}})
                    elif v.get('net','tcp')!='tcp':continue
                else:continue
                nodes.append(node)
            except (ValueError,TypeError,KeyError,UnicodeError):continue
    if not isinstance(nodes,list) or len(nodes)>1000:raise ValueError('订阅节点过多或格式无效')
    allowed={'name','type','server','port','cipher','password','uuid','alterId','tls','sni','servername','client-fingerprint','reality-opts','network','ws-opts','grpc-opts','xhttp-opts','ech-opts','encryption','flow','udp','alpn','username','skip-cert-verify','plugin','plugin-opts','packet-encoding'}
    result=[];seen=set()
    for value in nodes:
        if not isinstance(value,dict) or value.get('type') not in ('ss','vless','vmess','trojan','anytls','http','socks5'):continue
        node={k:v for k,v in value.items() if k in allowed};name=str(node.get('name',''))[:160]
        if any(label in name for label in ('剩余流量','套餐到期','过期时间','订阅到期')):continue
        if not isinstance(node.get('server'),str) or not node['server'] or not isinstance(node.get('port'),int) or not 1<=node['port']<=65535:continue
        if node.get('skip-cert-verify'):continue
        if node.get('plugin') and node['plugin'] not in ('obfs','v2ray-plugin','gost-plugin','shadow-tls','restls','jls','kcptun'):continue
        node['name']=name or node['server'];node['skip-cert-verify']=False
        id=hashlib.sha256(json.dumps(node,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
        if id not in seen:result.append({'id':id,'name':node['name'],'type':node['type'],'config':node});seen.add(id)
    if not result:raise ValueError('订阅没有可用的受支持节点（支持 SS / VLESS / VMess / Trojan / AnyTLS / HTTP / SOCKS5）')
    return result
