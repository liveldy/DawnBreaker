"""User-configurable HTTPS APIs with DNS pinning and no redirects/private network access."""
import http.client,ipaddress,json,socket,ssl,os
import httpx
from urllib.parse import urlsplit,urlencode
from fastapi import HTTPException
from .ai_endpoints import is_xai_service
from .xai_egress import configured_proxy

MAX_RESPONSE=16*1024*1024

def upstream_error(status):
    hint={401:'密钥无效或已失效',403:'密钥权限或地区访问受限',402:'账户额度不足',404:'接口或模型不存在，请重新获取可用模型',429:'请求频率或额度达到限制'}.get(status,'请检查接口与模型配置' if status<500 else '上游服务暂时不可用')
    return HTTPException(502,'模型 API 返回 HTTP '+str(status)+'：'+hint)

def xai_network_error():
    return HTTPException(502,'服务器无法连接 xAI，请联系管理员检查服务器出站网络或 xAI 代理配置；客户端的本机代理不会自动作用于服务器。')

def proxy_request(url,body,headers,params,proxy):
    # Administrator-only egress, restricted to exact official xAI HTTPS hosts.
    # CONNECT resolves the official hostname at the proxy. TLS still verifies xAI;
    # inference credentials are never sent in plaintext to the proxy.
    value=urlsplit(proxy)
    if value.scheme not in ('http','https') or not value.hostname or value.path not in ('','/') or value.query or value.fragment or any(c in proxy for c in '\r\n'):
        raise HTTPException(503,'xAI 出站代理配置无效，请联系管理员')
    try:
        with httpx.Client(proxy=proxy,trust_env=False,follow_redirects=False,timeout=httpx.Timeout(120,connect=20)) as client:
            with client.stream('POST' if body is not None else 'GET',url,content=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None,headers=headers,params=params) as response:
                if not 200<=response.status_code<300:raise upstream_error(response.status_code)
                chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>MAX_RESPONSE:raise HTTPException(502,'API 返回内容过大')
                    chunks.append(chunk)
                return json.loads(b''.join(chunks))
    except HTTPException:raise
    except Exception:raise xai_network_error()

def endpoint(value,allow_http=False):
    p=urlsplit(value.strip())
    if p.scheme not in (('https','http') if allow_http else ('https',)) or not p.hostname or p.username or p.password or p.query or p.fragment:raise HTTPException(422,'API 地址需为 HTTPS（自定义接口可用 HTTP），不要附加密钥、查询参数或账号')
    try:literal=ipaddress.ip_address(p.hostname)
    except ValueError:literal=None
    if literal and not literal.is_global:raise HTTPException(422,'API 地址不能指向本机、内网或系统保留地址')
    try:port=p.port or (443 if p.scheme=='https' else 80)
    except ValueError:raise HTTPException(422,'API 端口无效')
    return p,port
def public_addresses(host,port):
    try:addresses=list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))
    except OSError:raise HTTPException(502,'无法解析 API 地址，请检查配置')
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise HTTPException(422,'API 地址不能指向本机、内网或系统保留地址')
    return addresses
def request_json(url,body=None,headers=None,params=None,allow_http=False):
    parsed,port=endpoint(url,allow_http=allow_http)
    request_headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'DawnBreaker',**(headers or {})}
    official_xai=is_xai_service(url);proxy=configured_proxy() if official_xai else ''
    if official_xai and proxy:return proxy_request(url,body,request_headers,params,proxy)
    try:ips=public_addresses(parsed.hostname,port)
    except HTTPException:
        if official_xai:raise xai_network_error()
        raise
    class Pinned(http.client.HTTPSConnection if parsed.scheme=='https' else http.client.HTTPConnection):
        def connect(self):
            last=None
            for ip in ips:
                try:
                    self.sock=socket.create_connection((ip,port),timeout=20)
                    if parsed.scheme=='https':self.sock=self._context.wrap_socket(self.sock,server_hostname=parsed.hostname)
                    self.sock.settimeout(120);return
                except OSError as e:last=e
            raise last or OSError()
    conn=Pinned(parsed.hostname,port,timeout=120,**({'context':ssl.create_default_context()} if parsed.scheme=='https' else {}))
    try:
        payload=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
        conn.request('POST' if body is not None else 'GET',(parsed.path or '/')+('?' + urlencode(params,doseq=True) if params else ''),body=payload,headers=request_headers)
        response=conn.getresponse();data=response.read(MAX_RESPONSE+1)
        if response.status<200 or response.status>=300:raise upstream_error(response.status)
        if len(data)>MAX_RESPONSE:raise HTTPException(502,'API 返回内容过大')
        return json.loads(data)
    except HTTPException:raise
    except Exception:
        if official_xai:raise xai_network_error()
        raise HTTPException(502,'API 暂时无法连接或返回格式无效，请检查配置后重试')
    finally:conn.close()
