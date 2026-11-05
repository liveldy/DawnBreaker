"""Bounded media transport; keeps credentials out of generated-content downloads."""
import http.client,json,socket,ssl,uuid
from urllib.parse import urlsplit,urlencode
import httpx
from fastapi import HTTPException
from .outbound import endpoint,public_addresses,upstream_error,xai_network_error
from .ai_endpoints import is_xai
from .xai_egress import configured_proxy

CDN=frozenset({'imgen.x.ai','vidgen.x.ai','media.x.ai'})

def wire(url,body=None,headers=None,limit=64*1024*1024,method=None):
    value=urlsplit(url);parsed,port=endpoint(value._replace(query='').geturl());headers={'User-Agent':'DawnBreaker','Accept':'*/*',**(headers or {})};method=method or ('POST' if body is not None else 'GET')
    proxy=configured_proxy() if is_xai(url) or parsed.hostname in CDN else ''
    try:
        if proxy:
            with httpx.Client(proxy=proxy,trust_env=False,follow_redirects=False,timeout=httpx.Timeout(120,connect=20)) as client:
                with client.stream(method,url,content=body,headers=headers) as r:
                    if not 200<=r.status_code<300:raise upstream_error(r.status_code)
                    parts=[];size=0
                    for part in r.iter_bytes():
                        size+=len(part)
                        if size>limit:raise HTTPException(502,'上游媒体超过大小限制')
                        parts.append(part)
                    return b''.join(parts),r.headers.get('content-type','application/octet-stream')
        ips=public_addresses(parsed.hostname,port)
        class Pinned(http.client.HTTPSConnection):
            def connect(self):
                for ip in ips:
                    try:self.sock=self._context.wrap_socket(socket.create_connection((ip,port),timeout=20),server_hostname=parsed.hostname);self.sock.settimeout(120);return
                    except OSError:continue
                raise OSError()
        c=Pinned(parsed.hostname,port,context=ssl.create_default_context())
        try:
            c.request(method,(parsed.path or '/')+('?' + value.query if value.query else ''),body,headers);r=c.getresponse()
            if not 200<=r.status<300:raise upstream_error(r.status)
            data=r.read(limit+1)
            if len(data)>limit:raise HTTPException(502,'上游媒体超过大小限制')
            return data,r.getheader('Content-Type','application/octet-stream')
        finally:c.close()
    except HTTPException:raise
    except Exception:
        if is_xai(url):raise xai_network_error()
        raise HTTPException(502,'媒体服务连接失败，请检查接口、模型权限或文件格式')

def post_json_bytes(url,key,body,limit=32*1024*1024):
    return wire(url,json.dumps(body,ensure_ascii=False).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'},limit)

def transcribe(base,key,audio,model=''):
    boundary='dawn'+uuid.uuid4().hex
    # Omit language for auto-detection; the binary file must be the final field.
    fields=('--'+boundary+'\r\nContent-Disposition: form-data; name="model"\r\n\r\n'+model+'\r\n') if model else ''
    body=(fields+'--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()+audio+('\r\n--'+boundary+'--\r\n').encode()
    data,_=wire(base+'/stt',body,{'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary},1024*1024)
    try:text=json.loads(data)['text']
    except Exception:raise HTTPException(502,'语音识别服务未返回文字')
    if not isinstance(text,str) or not text.strip():raise HTTPException(422,'没有识别到语音，请重新录制')
    return text[:12000]
