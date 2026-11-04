"""Server-proxied pronunciation from Youdao Dictionary, cached per word."""
import hashlib
from threading import Lock
import httpx
from fastapi import HTTPException
from .db import DATA

ROOT=DATA/'pronunciation';ROOT.mkdir(exist_ok=True)
LOCK=Lock()

def voice_file(word):
    if not isinstance(word,str) or not word.strip() or len(word)>100: raise HTTPException(422,'词汇内容无效')
    # Word variants in the supplied book (a/an) use their first pronunciation.
    spoken=word.split('/')[0].strip()
    path=ROOT/(hashlib.sha256(spoken.casefold().encode()).hexdigest()+'.mp3')
    with LOCK:
        if path.is_file(): return path
        try:
            with httpx.stream('GET','https://dict.youdao.com/dictvoice',params={'audio':spoken,'type':'2'},timeout=20,follow_redirects=False) as r:
                r.raise_for_status()
                if not r.headers.get('content-type','').startswith('audio/'): raise ValueError('Unexpected response')
                chunks=[];size=0
                for chunk in r.iter_bytes():
                    size+=len(chunk)
                    if size>2*1024*1024: raise ValueError('Response too large')
                    chunks.append(chunk)
                if size<100: raise ValueError('Empty audio')
            temp=path.with_suffix('.tmp');temp.write_bytes(b''.join(chunks));temp.replace(path)
        except (httpx.HTTPError,ValueError,OSError): raise HTTPException(502,'朗读服务暂时不可用，请稍后重试')
    return path
