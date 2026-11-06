import hashlib
import os
import re
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from . import db
from .core import require_user, public_user, installed, balance, emit
from .plugins import MODULES, BY_ID, catalog

PASSWORD=PasswordHash.recommended()
DUMMY=PASSWORD.hash(secrets.token_urlsafe(24))
SECURE=os.environ.get('DAWN_SECURE_COOKIES','0')=='1'
RATE=defaultdict(deque); RATE_LOCK=Lock()

@asynccontextmanager
async def lifespan(app):
    db.init()
    with db.connect(True) as conn:
        from .listening import backfill
        backfill(conn)
        from .plugins.collection import normalize_owned
        for row in conn.execute("SELECT user_id FROM progress WHERE plugin_id='collection' AND key='owned'").fetchall():normalize_owned(conn,row[0])
        conn.execute("DELETE FROM progress WHERE plugin_id='journal' AND (key LIKE 'claim:daily-checkin:%' OR key LIKE 'claim:daily-words:%' OR key='claim:seven-checkins')")
        conn.execute("UPDATE downloads SET status='failed',error='服务已重启，请重新提交下载任务' WHERE status IN ('queued','downloading')")
        conn.execute("UPDATE import_jobs SET status='failed',error='服务已重启，请点击重试',updated_at=? WHERE status IN ('queued','running')",(db.now(),))
        conn.execute("UPDATE ai_turns SET status='failed',error='服务已重启，请重新发送' WHERE status IN ('queued','running')")
    from .companion_jobs import recover as recover_companions,start_scheduler
    recover_companions();companion_stop=start_scheduler()
    from .plugins.atlas import start_scheduler as start_atlas_scheduler
    atlas_stop=start_atlas_scheduler()
    try:yield
    finally:companion_stop.set();atlas_stop.set()

app=FastAPI(title='破晓 DawnBreaker',version='1.4.7',lifespan=lifespan)
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware,minimum_size=1024)

@app.middleware('http')
async def protection(request:Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail':'请求来源不匹配'},status_code=403)
        size=request.headers.get('content-length','0')
        path=request.url.path
        max_body=46*1024*1024 if path=='/api/plugins/vault' else 101*1024*1024 if path=='/api/plugins/wallpaper' else 1100000 if path=='/api/plugins/warp' else 12*1024*1024 if path=='/api/plugins/library/images' else 32*1024*1024 if path=='/api/plugins/library/imports' or path.startswith('/api/plugins/companion/') and path.endswith('/upload') else 6*1024*1024 if path=='/api/profile/avatar' or path.startswith('/api/plugins/companion/') and path.endswith('/avatar') else 3*1024*1024 if path.startswith('/api/plugins/library/nodes') else 262144 if path.startswith(('/api/admin/','/api/plugins/constellation/','/api/plugins/companion/','/api/plugins/music/sync','/api/plugins/checkin/notes')) else 16384
        if not size.isdigit() or int(size)>max_body:
            return JSONResponse({'detail':'请求内容过大'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='SAMEORIGIN' if request.url.path=='/api/plugins/atlas/view' else 'DENY'
    if request.url.path=='/api/plugins/atlas/view':response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'self'; object-src 'none'"
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/api'):
        if 'cache-control' not in response.headers:response.headers['Cache-Control']='no-store'
    else:
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: https://ddragon.leagueoflegends.com; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; connect-src 'self'; media-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response

def limit(request):
    key=request.client.host if request.client else 'unknown'
    # Trust only the reverse proxy on loopback, never public forwarded headers.
    if key in ('127.0.0.1','::1'):
        key=request.headers.get('X-Real-IP',key)
    with RATE_LOCK:
        stamp=time.monotonic()
        for stale in [k for k,v in RATE.items() if not v or v[-1]<stamp-900]: RATE.pop(stale,None)
        q=RATE[key]
        while q and q[0]<stamp-900: q.popleft()
        if len(q)>=25: raise HTTPException(429,'操作过于频繁，请 15 分钟后再试')
        q.append(stamp)

class Credentials(BaseModel):
    username:str=Field(min_length=3,max_length=24,pattern=r'^[a-zA-Z0-9_]+$')
    password:str=Field(min_length=8,max_length=128)
    nickname:str=Field(default='',max_length=30)

def session(conn,uid,response):
    raw=secrets.token_urlsafe(48)
    conn.execute('DELETE FROM sessions WHERE expires_at<?',(time.time(),))
    conn.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),uid,time.time()+30*86400))
    response.set_cookie('dawn_session',raw,max_age=30*86400,httponly=True,secure=SECURE,samesite='lax',path='/')

@app.post('/api/auth/register',status_code=201)
def register(body:Credentials,request:Request,response:Response):
    limit(request)
    uid=uuid.uuid4().hex; hashed=PASSWORD.hash(body.password)
    try:
        with db.connect(True) as conn:
            conn.execute('INSERT INTO users(id,username,password,nickname,created_at) VALUES(?,?,?,?,?)',(uid,body.username.casefold(),hashed,body.nickname.strip() or body.username,db.now()))
            session(conn,uid,response)
            user=conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(409,'这个用户名已被使用')
    return {'user':public_user(user)}

@app.post('/api/auth/login')
def login(body:Credentials,request:Request,response:Response):
    limit(request)
    with db.connect() as conn:
        user=conn.execute('SELECT * FROM users WHERE username=?',(body.username.casefold(),)).fetchone()
    valid=PASSWORD.verify(body.password,user['password'] if user else DUMMY)
    if not user or not valid: raise HTTPException(401,'用户名或密码不正确')
    with db.connect(True) as conn: session(conn,user['id'],response)
    return {'user':public_user(user)}

@app.post('/api/auth/logout')
def logout(request:Request,response:Response):
    raw=request.cookies.get('dawn_session','')
    with db.connect(True) as conn: conn.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(raw.encode()).hexdigest(),))
    response.delete_cookie('dawn_session',path='/')
    return {'message':'已退出登录'}

@app.get('/api/bootstrap')
def bootstrap(u=Depends(require_user)):
    with db.connect() as conn:
        return {'user':public_user(u),'wallet':{k:balance(conn,u['id'],k) for k in ['essence','stones']},'plugins':[p for p in catalog(conn,u['id']) if p['installed']],'version':'1.4.7'}

class Profile(BaseModel):
    nickname:str=Field(min_length=1,max_length=30)
    bio:str=Field(default='',max_length=160)

@app.patch('/api/profile')
def profile(body:Profile,u=Depends(require_user)):
    if not body.nickname.strip(): raise HTTPException(422,'昵称不能为空')
    with db.connect(True) as conn: conn.execute('UPDATE users SET nickname=?,bio=? WHERE id=?',(body.nickname.strip(),body.bio.strip(),u['id']))
    return {'message':'个人信息已保存'}

class ChangePassword(BaseModel):
    current:str=Field(min_length=8,max_length=128)
    new:str=Field(min_length=8,max_length=128)

@app.post('/api/profile/password')
def change_password(body:ChangePassword,request:Request,response:Response,u=Depends(require_user)):
    limit(request)
    if not PASSWORD.verify(body.current,u['password']): raise HTTPException(400,'当前密码不正确')
    new_hash=PASSWORD.hash(body.new)
    with db.connect(True) as conn:
        conn.execute('UPDATE users SET password=? WHERE id=?',(new_hash,u['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
        session(conn,u['id'],response)
    return {'message':'密码已更新，其他设备的登录已退出'}

@app.get('/api/catalog')
def get_catalog(u=Depends(require_user)):
    with db.connect() as conn: return {'plugins':catalog(conn,u['id'])}

@app.post('/api/catalog/{plugin_id}/install')
def install(plugin_id:str,u=Depends(require_user)):
    plugin=BY_ID.get(plugin_id)
    if not plugin: raise HTTPException(404,'插件不存在')
    with db.connect(True) as conn:
        if installed(conn,u['id'],plugin_id): raise HTTPException(409,'插件已安装')
        if plugin.get('parent') and not installed(conn,u['id'],plugin['parent']):
            raise HTTPException(409,'请先安装 '+BY_ID[plugin['parent']]['name'])
        conn.execute('INSERT INTO installed VALUES(?,?,?)',(u['id'],plugin_id,db.now()))
        emit(conn,u['id'],'install',{'plugin':plugin_id})
    return {'message':plugin['name']+'已安装'}

@app.delete('/api/catalog/{plugin_id}')
def uninstall(plugin_id:str,u=Depends(require_user)):
    if plugin_id not in BY_ID: raise HTTPException(404,'插件不存在')
    with db.connect(True) as conn:
        if not installed(conn,u['id'],plugin_id): raise HTTPException(404,'插件未安装')
        children=[p['name'] for p in BY_ID.values() if p.get('parent')==plugin_id and installed(conn,u['id'],p['id'])]
        if children: raise HTTPException(409,'请先卸载内容插件：'+'、'.join(children))
        if plugin_id=='downloader' and conn.execute("SELECT 1 FROM downloads WHERE user_id=? AND status IN ('queued','downloading')",(u['id'],)).fetchone(): raise HTTPException(409,'请等待下载完成后再卸载')
        conn.execute('DELETE FROM installed WHERE user_id=? AND plugin_id=?',(u['id'],plugin_id))
        emit(conn,u['id'],'uninstall',{'plugin':plugin_id})
    return {'message':'已卸载，历史数据保留，重新安装后可继续使用'}

@app.get('/api/wallet')
def wallet(page:int=Query(1,ge=1),u=Depends(require_user)):
    with db.connect() as conn:
        total=conn.execute("SELECT COUNT(*) FROM ledger WHERE user_id=? AND kind IN ('essence','stones')",(u['id'],)).fetchone()[0]
        rows=conn.execute("SELECT kind,amount,reason,created_at FROM ledger WHERE user_id=? AND kind IN ('essence','stones') ORDER BY id DESC LIMIT 20 OFFSET ?",(u['id'],(page-1)*20)).fetchall()
        return {'balances':{k:balance(conn,u['id'],k) for k in ['essence','stones']},'ledger':[dict(r) for r in rows],'total':total,'page':page}

@app.get('/api/health')
def health():
    with db.connect() as conn: conn.execute('SELECT 1').fetchone()
    return {'status':'ok','service':'DawnBreaker','version':'1.4.7'}

for module in MODULES: app.include_router(module.router)
from .admin import router as admin_router
app.include_router(admin_router)
from .admin_egress import router as egress_router
app.include_router(egress_router)
from .releases import router as releases_router
app.include_router(releases_router)
from .avatars import router as avatar_router
app.include_router(avatar_router)
from .companion_admin import router as companion_admin_router
app.include_router(companion_admin_router)

DIST=Path(__file__).parents[1]/'dist'
if DIST.exists() and os.environ.get('DAWN_SERVE_WEB','1')=='1':
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/{path:path}',include_in_schema=False)
    def frontend(path:str):
        if path.startswith(('api/','media/')): raise HTTPException(404,'接口不存在')
        file=(DIST/path).resolve()
        if file.is_relative_to(DIST.resolve()) and file.is_file(): return FileResponse(file)
        return FileResponse(DIST/'index.html')
