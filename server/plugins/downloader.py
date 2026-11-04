"""Bounded server-side yt-dlp jobs. Authenticated files; no user shell commands."""
import logging
import socket
import ipaddress
import uuid
import re
from urllib.parse import urlparse,urljoin
import httpx
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from ..core import require_plugin, installed
from ..db import connect, now, DATA

MANIFEST={'id':'downloader','name':'留痕下载','description':'留下视频，也取回网盘文件。视频由 yt-dlp 处理；客户端网盘助手基于 LinkSwift。','category':'工具','icon':'Download','ui':'downloader'}
router=APIRouter(prefix='/api/plugins/downloader',tags=['留痕下载'])
user=require_plugin('downloader')
POOL=ThreadPoolExecutor(max_workers=2)
ROOT=DATA/'downloads'; ROOT.mkdir(exist_ok=True)
ALLOWED=('youtube.com','youtu.be','bilibili.com','b23.tv','vimeo.com','douyin.com')
FORMAT='bv*[height<=720]+ba/b[height<=720]/b'
USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'

def validate_url(url):
    try:
        parsed=urlparse(url); host=parsed.hostname or ''
        if parsed.scheme not in ('https','http') or parsed.username or parsed.password or parsed.port not in (None,80,443): raise ValueError()
        if not any(host==d or host.endswith('.'+d) for d in ALLOWED): raise ValueError()
        if any(not ipaddress.ip_address(r[4][0]).is_global for r in socket.getaddrinfo(host,None)): raise ValueError()
    except (ValueError,OSError):
        raise HTTPException(422,'请使用支持平台的公开视频链接：YouTube、哔哩哔哩、Vimeo 或抖音')

def resolve_short_link(url):
    if (urlparse(url).hostname or '').casefold()!='b23.tv': return url
    try:
        with httpx.Client(timeout=15,follow_redirects=False,headers={'User-Agent':USER_AGENT}) as client:
            for _ in range(5):
                validate_url(url)
                response=client.get(url)
                if response.is_redirect:
                    url=urljoin(url,response.headers['location']);validate_url(url)
                    if (urlparse(url).hostname or '').endswith('bilibili.com'): return url
                else: break
    except httpx.HTTPError: raise HTTPException(422,'哔哩哔哩短链接暂时无法展开，请粘贴完整视频链接')
    raise HTTPException(422,'短链接无效，请粘贴完整视频链接')

def failure_message(exc,url):
    text=str(exc).lower();bili='bili' in (urlparse(url).hostname or '')
    if any(code in text for code in ('412','403','-352')):
        return ('哔哩哔哩限制了服务器请求（风控或访问权限），请稍后重试或使用无需登录的公开视频。' if bili else '平台拒绝了服务器请求，请检查视频访问权限或稍后重试。')
    if any(word in text for word in ('login','sign in','cookies','premium','vip','会员')): return '该视频需要登录或会员权限，当前仅支持无需登录的公开视频。'
    if 'ffmpeg' in text: return '视频需要合并音画，但服务器合并工具不可用，请联系管理员。'
    if 'requested format' in text: return '该视频没有可用的下载格式或清晰度，请换一个公开视频链接。'
    return '下载失败：链接可能已失效、网络受限或超过 500 MB / 2 小时限制。'

def update(job,**values):
    with connect(True) as db:
        db.execute('UPDATE downloads SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),job))

def run(job,url):
    import yt_dlp
    folder=ROOT/job; folder.mkdir(exist_ok=True)
    def hook(d):
        if d['status']=='downloading':
            size=d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            if size>500*1024*1024: raise ValueError('视频超过 500 MB 限制')
            update(job,status='downloading',percent=min(99,round(d.get('downloaded_bytes',0)/size*100,1)) if size else 0)
    try:
        update(job,status='downloading')
        opts={'outtmpl':str(folder/'video.%(ext)s'),'format':FORMAT,'merge_output_format':'mp4','noplaylist':True,'max_filesize':500*1024*1024,'socket_timeout':20,'retries':1,'fragment_retries':1,'progress_hooks':[hook],'quiet':True,'no_warnings':True,'restrictfilenames':True,'cachedir':False,'allowed_extractors':['youtube.*','bilibili.*','vimeo.*','douyin.*'],'match_filter':lambda info,**kw:'视频时长超过 2 小时' if (info.get('duration') or 0)>7200 else None}
        if 'bilibili.com' in (urlparse(url).hostname or ''): opts['http_headers']={'User-Agent':USER_AGENT,'Referer':'https://www.bilibili.com/'}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info=ydl.extract_info(url,download=True)
            if not info: raise ValueError('没有可下载的视频')
            files=[p for p in folder.iterdir() if re.fullmatch(r'video\.(mp4|mkv|webm|mov|flv|mp3|m4a)',p.name)]
            if not files: raise ValueError('下载未生成文件，可能超出大小限制')
            if files[0].stat().st_size>500*1024*1024: raise ValueError('Final video exceeds 500 MB')
            update(job,status='completed',percent=100,title=(info.get('title') or '视频')[:200],filename=str(files[0].relative_to(ROOT)))
    except Exception as exc:
        logging.getLogger('dawn.download').info('Job %s failed: %s',job,type(exc).__name__)
        # External errors often contain URLs and tokens; keep them out of responses.
        update(job,status='failed',error=failure_message(exc,url))

class Job(BaseModel):
    url:str=Field(min_length=8,max_length=2000)

@router.get('')
def jobs(u=Depends(user)):
    with connect() as db:
        rows=db.execute('SELECT id,url,title,status,percent,error,created_at FROM downloads WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(u['id'],)).fetchall()
        return {'jobs':[dict(r) for r in rows]}

@router.post('')
def create(body:Job,u=Depends(user)):
    validate_url(body.url)
    resolved=resolve_short_link(body.url)
    with connect(True) as db:
        if db.execute("SELECT COUNT(*) FROM downloads WHERE user_id=? AND status IN ('queued','downloading')",(u['id'],)).fetchone()[0]>=2: raise HTTPException(429,'最多同时处理 2 个任务')
        if db.execute('SELECT COUNT(*) FROM downloads WHERE user_id=?',(u['id'],)).fetchone()[0]>=50: raise HTTPException(409,'下载记录已达 50 条，请先清理旧记录')
        job=uuid.uuid4().hex
        db.execute('INSERT INTO downloads(id,user_id,url,title,status,created_at) VALUES(?,?,?,?,?,?)',(job,u['id'],body.url,'等待解析','queued',now()))
    POOL.submit(run,job,resolved)
    return {'message':'已加入下载队列','id':job}

@router.get('/{job}/file')
def download(job:str,u=Depends(user)):
    with connect() as db:
        row=db.execute('SELECT * FROM downloads WHERE id=? AND user_id=?',(job,u['id'])).fetchone()
    if not row or row['status']!='completed': raise HTTPException(404,'文件尚未准备好')
    path=(ROOT/row['filename']).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file(): raise HTTPException(404,'文件不存在')
    return FileResponse(path,filename='DawnBreaker-'+job[:8]+path.suffix)

@router.delete('/{job}')
def delete(job:str,u=Depends(user)):
    with connect(True) as db:
        row=db.execute('SELECT * FROM downloads WHERE id=? AND user_id=?',(job,u['id'])).fetchone()
        if not row: raise HTTPException(404,'任务不存在')
        if row['status'] in ('queued','downloading'): raise HTTPException(409,'任务正在处理中')
        db.execute('DELETE FROM downloads WHERE id=?',(job,))
    folder=(ROOT/job).resolve()
    if folder.is_relative_to(ROOT) and folder.is_dir():
        import shutil
        shutil.rmtree(folder)
    return {'message':'已删除下载记录与文件'}
