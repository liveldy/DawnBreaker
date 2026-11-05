"""Free multi-engine discovery and query-focused article extraction, no browser execution."""
import base64,http.client,ipaddress,math,re,socket,ssl
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit,urlunsplit,urljoin,urlencode,parse_qs,parse_qsl
import httpx
from fastapi import HTTPException
from lxml import html,etree
import trafilatura
from .outbound import endpoint,public_addresses
from .xai_egress import configured_proxy
from .companion_state import keywords

SEARCH_HOSTS={'www.google.com','www.bing.com','cn.bing.com','html.duckduckgo.com'}
TRUSTED_PROXY_HOSTS=SEARCH_HOSTS|{'docs.x.ai','api-docs.deepseek.com'}
LIMIT=2*1024*1024

def checked(url):
    value=urlsplit(url)
    parsed,port=endpoint(value._replace(query='',fragment='').geturl())
    if port!=443:raise HTTPException(422,'网页仅支持标准 HTTPS 地址')
    return value

def fetch(url):
    for _ in range(4):
        value=checked(url);host=value.hostname;headers={'User-Agent':'Mozilla/5.0 (compatible; DawnBreaker/1.4; article reader)','Accept':'text/html,application/xhtml+xml,text/plain','Accept-Language':'zh-CN,zh;q=0.9,en;q=0.7','Accept-Encoding':'identity'}
        proxy=''
        if host in TRUSTED_PROXY_HOSTS:
            try:proxy=configured_proxy()
            except HTTPException:pass
        if proxy:
            with httpx.Client(proxy=proxy,trust_env=False,follow_redirects=False,timeout=httpx.Timeout(12,connect=8)) as c:
                with c.stream('GET',url,headers=headers) as r:
                    status=r.status_code;location=r.headers.get('location');mime=r.headers.get('content-type','');parts=[];size=0
                    for part in r.iter_bytes():
                        size+=len(part)
                        if size>LIMIT:raise HTTPException(502,'网页正文超过读取大小限制')
                        parts.append(part)
                    raw=b''.join(parts)
        else:
            ips=public_addresses(host,443)
            class Pinned(http.client.HTTPSConnection):
                def connect(self):
                    last=None
                    for ip in ips:
                        try:self.sock=self._context.wrap_socket(socket.create_connection((ip,443),timeout=8),server_hostname=host);self.sock.settimeout(12);return
                        except OSError as e:last=e
                    raise last or OSError('connection failed')
            c=Pinned(host,443,context=ssl.create_default_context())
            try:
                c.request('GET',(value.path or '/')+('?' +value.query if value.query else ''),headers=headers);r=c.getresponse();status=r.status;location=r.getheader('location');mime=r.getheader('content-type','');raw=r.read(LIMIT+1)
                if len(raw)>LIMIT:raise HTTPException(502,'网页正文超过读取大小限制')
            finally:c.close()
        if status in (301,302,303,307,308) and location:url=urljoin(url,location);continue
        if status!=200:raise HTTPException(502,'网页返回 HTTP '+str(status))
        if not any(kind in mime.lower() for kind in ('text/html','application/xhtml+xml','text/plain','application/rss+xml','text/xml','application/xml')):raise HTTPException(422,'只读取文本网页，不下载程序或文件')
        return raw,url,mime
    raise HTTPException(502,'网页重定向过多')

def clean_link(link,base):
    link=urljoin(base,link);value=urlsplit(link)
    if value.hostname and value.hostname.endswith('google.com') and value.path=='/url':link=(parse_qs(value.query).get('q') or parse_qs(value.query).get('url') or [''])[0]
    elif value.hostname and value.hostname.endswith('bing.com') and value.path.startswith('/ck/'):
        token=(parse_qs(value.query).get('u') or [''])[0]
        if token.startswith('a1'):
            try:link=base64.urlsafe_b64decode(token[2:]+'='*(-len(token[2:])%4)).decode()
            except (ValueError,UnicodeError):return ''
    try:value=checked(link)
    except (HTTPException,ValueError):return ''
    if value.hostname in SEARCH_HOSTS:return ''
    query=urlencode([(k,v) for k,v in parse_qsl(value.query) if not k.startswith('utm_') and k not in ('gclid','fbclid')])
    return urlunsplit((value.scheme,value.netloc.lower(),value.path or '/',query,''))

def parse_results(raw,url,engine):
    doc=html.fromstring(raw);out=[]
    if engine=='Bing':nodes=doc.xpath('//li[contains(concat(" ",normalize-space(@class)," ")," b_algo ")]')
    elif engine=='DuckDuckGo':nodes=doc.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," result ")]')
    else:nodes=[n.getparent() for n in doc.xpath('//a[.//h3]')]
    for node in nodes:
        anchors=node.xpath('.//h2/a|.//a[.//h3]|.//a[contains(@class,"result__a")]')
        if not anchors:continue
        a=anchors[0];link=clean_link(a.get('href',''),url);title=' '.join(a.text_content().split())[:220]
        if not link or not title:continue
        snippets=node.xpath('.//div[contains(@class,"b_caption")]//p|.//*[contains(@class,"result__snippet")]|.//div[contains(@class,"VwiC3b")]')
        snippet=' '.join(' '.join(s.text_content().split()) for s in snippets)[:600]
        out.append({'title':title,'url':link,'snippet':snippet,'engine':engine})
        if len(out)==8:break
    return out

def engine_search(engine,query):
    host={'Google':'https://www.google.com/search?','Bing':'https://www.bing.com/search?','DuckDuckGo':'https://html.duckduckgo.com/html/?'}[engine]
    rows=[]
    try:
        raw,url,_=fetch(host+urlencode({'q':query,'num':8}));rows=parse_results(raw,url,engine)
    except Exception:
        if engine!='Bing':raise
    if not rows and engine=='Bing':
        raw,url,_=fetch(host+urlencode({'q':query,'format':'rss'}));doc=etree.fromstring(raw,parser=etree.XMLParser(resolve_entities=False,no_network=True))
        for item in doc.findall('.//item')[:8]:
            link=clean_link(item.findtext('link',''),url)
            if link:rows.append({'title':item.findtext('title','')[:220],'url':link,'snippet':item.findtext('description','')[:600],'engine':'Bing'})
    return rows

def search(query):
    query=str(query).strip()[:300]
    if not query:raise HTTPException(422,'搜索词不能为空')
    results=[];engines={}
    def attempt(engine):
        try:return engine,engine_search(engine,query),''
        except Exception:return engine,[],'暂时不可用'
    with ThreadPoolExecutor(max_workers=2) as pool:
        for engine,rows,error in pool.map(attempt,['Google','Bing']):
            engines[engine]=error or ('已返回结果' if rows else '没有可读取结果');results.extend(rows)
    if len(results)<3:
        engine,rows,error=attempt('DuckDuckGo');engines[engine]=error or ('已返回结果' if rows else '没有可读取结果');results.extend(rows)
    tokens=keywords(query);seen=set();ranked=[]
    for item in results:
        if item['url'] in seen:continue
        seen.add(item['url']);score=len(tokens&keywords(item['title']))*2+len(tokens&keywords(item['snippet']));ranked.append((score,item))
    ranked.sort(key=lambda v:v[0],reverse=True)
    return {'query':query,'engines':engines,'results':[item for _,item in ranked[:8]],'note':'摘要不是网页全文；必要时继续精读来源正文' if ranked else '多个搜索引擎均未返回可读取结果，请勿编造搜索结论'}

def focus(text,query,limit=8500):
    lines=[line.strip() for line in text.splitlines() if len(line.strip())>4];tokens=keywords(query)-{'什么','怎么','如何','the','and','of','is'}
    scored=sorted([(len(tokens&keywords(line))/math.sqrt(max(1,len(line)/160)),i) for i,line in enumerate(lines)],reverse=True)
    selected=set()
    for score,i in scored[:10]:
        if score<=0:continue
        selected.add(i)
        context=keywords(lines[i])-{'可以','用户','这个','内容','说明','一个','支持','相关'}
        for near in (i-1,i+1):
            if 0<=near<len(lines) and len(context&keywords(lines[near]))>=2:selected.add(near)
    return '\n\n'.join(lines[i] for i in sorted(selected))[:limit] if selected else ''

def read_page(url,query):
    try:
        raw,final,mime=fetch(str(url)[:2000]);doc=html.fromstring(raw);titles=doc.xpath('//title/text()');title=' '.join(titles)[:220]
        text=raw.decode('utf-8',errors='replace') if 'text/plain' in mime else trafilatura.extract(raw,favor_precision=True,include_comments=False,include_tables=False,include_links=False) or ''
        content=focus(text,str(query)[:300])
        return {'url':final,'title':title,'content':content,'relevant':bool(content),'note':'' if content else '正文未找到与问题直接相关的段落，不将导航、广告或无关内容作为依据'}
    except HTTPException:raise
    except Exception:raise HTTPException(502,'网页暂时无法读取，可更换搜索结果中的其他来源')
