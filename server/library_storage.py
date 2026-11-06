"""Account library quota, shared by direct edits, OCR, images and assistant tools."""
from pathlib import Path
from fastapi import HTTPException
from .db import DATA
DEFAULT=64*1024*1024
IMAGES=DATA/'library-images';IMAGES.mkdir(exist_ok=True)

def text_bytes(title,markdown=''):return len(title.encode('utf8'))+len(markdown.encode('utf8'))

def disk_bytes(folder):
    if not folder.is_dir():return 0
    total=0
    for p in folder.rglob('*'):
        try:
            if p.is_file() and not p.is_symlink():total+=p.stat().st_size
        except FileNotFoundError:pass
    return total

def usage(d,uid):
    row=d.execute('SELECT library_quota_bytes FROM users WHERE id=?',(uid,)).fetchone()
    if not row:raise HTTPException(404,'账号不存在')
    documents=d.execute('SELECT COALESCE(SUM(length(CAST(title AS BLOB))+length(CAST(markdown AS BLOB))),0) FROM library_nodes WHERE user_id=?',(uid,)).fetchone()[0]
    images=d.execute('SELECT COALESCE(SUM(size),0) FROM library_images WHERE user_id=? AND source_job_id IS NULL',(uid,)).fetchone()[0]
    imports=disk_bytes(DATA/'library-imports'/uid)
    used=documents+images+imports;quota=row[0]
    return {'used_bytes':used,'quota_bytes':quota,'available_bytes':max(0,quota-used),'documents_bytes':documents,'images_bytes':images,'imports_bytes':imports}

def ensure(d,uid,extra=0):
    info=usage(d,uid)
    if extra>0 and info['used_bytes']+extra>info['quota_bytes']:
        raise HTTPException(413,f"流萤集空间不足：已用 {info['used_bytes']/1048576:.2f} MB，配额 {info['quota_bytes']/1048576:g} MB。请删除不需要的内容或联系管理员调整。")
    return info
