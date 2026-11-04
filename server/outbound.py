"""User-configurable HTTPS APIs with DNS pinning and no redirects/private network access."""
import http.client,ipaddress,json,socket,ssl
from urllib.parse import urlsplit,urlencode
from fastapi import HTTPException

def endpoint(value):
    p=urlsplit(value.strip())
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:raise HTTPException(422,'API 地址需为 HTTPS，不要在地址中填写密钥、查询参数或账号')
    try:literal=ipaddress.ip_address(p.hostname)
    except ValueError:literal=None
    if literal and not literal.is_global:raise HTTPException(422,'API 地址不能指向本机、内网或系统保留地址')
    try:port=p.port or 443
    except ValueError:raise HTTPException(422,'API 端口无效')
    return p,port
def public_addresses(host,port):
    try:addresses=list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))
    except OSError:raise HTTPException(502,'无法解析 API 地址，请检查配置')
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise HTTPException(422,'API 地址不能指向本机、内网或系统保留地址')
    return addresses
def request_json(url,body=None,headers=None,params=None):
    parsed,port=endpoint(url);ips=public_addresses(parsed.hostname,port)
    class Pinned(http.client.HTTPSConnection):
        def connect(self):
            last=None
            for ip in ips:
                try:self.sock=self._context.wrap_socket(socket.create_connection((ip,port),timeout=20),server_hostname=parsed.hostname);self.sock.settimeout(120);return
                except OSError as e:last=e
            raise last or OSError()
    conn=Pinned(parsed.hostname,port,timeout=120,context=ssl.create_default_context())
    try:
        payload=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
        conn.request('POST' if body is not None else 'GET',(parsed.path or '/')+('?' + urlencode(params,doseq=True) if params else ''),body=payload,headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'DawnBreaker/1.2.1',**(headers or {})})
        response=conn.getresponse();data=response.read(16*1024*1024+1)
        if response.status<200 or response.status>=300:raise HTTPException(502,'模型 API 返回 HTTP '+str(response.status)+'，请检查接口、密钥和模型 ID')
        if len(data)>16*1024*1024:raise HTTPException(502,'API 返回内容过大')
        return json.loads(data)
    except HTTPException:raise
    except Exception:raise HTTPException(502,'API 暂时无法连接或返回格式无效，请检查配置后重试')
    finally:conn.close()
