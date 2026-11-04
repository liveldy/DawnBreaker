import json
import hashlib
import secrets
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException, Request
from .db import connect, now
from .events import dispatch

def today():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()

def require_user(request: Request):
    token = request.cookies.get('dawn_session', '')
    if request.headers.get('Authorization', '').startswith('Bearer '):
        token = request.headers['Authorization'][7:]
    with connect() as db:
        user = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires_at>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    if not user:
        raise HTTPException(401, '请先登录')
    return dict(user)

def installed(db, uid, plugin):
    return db.execute('SELECT 1 FROM installed WHERE user_id=? AND plugin_id=?', (uid, plugin)).fetchone() is not None

def require_plugin(plugin):
    def dependency(request: Request):
        user = require_user(request)
        with connect() as db:
            if not installed(db, user['id'], plugin):
                raise HTTPException(403, '请先安装此插件')
        return user
    return dependency

def state(db, uid, plugin, key, default=None):
    row = db.execute('SELECT value FROM progress WHERE user_id=? AND plugin_id=? AND key=?', (uid, plugin, key)).fetchone()
    return json.loads(row[0]) if row else default

def set_state(db, uid, plugin, key, value):
    db.execute('INSERT INTO progress VALUES(?,?,?,?) ON CONFLICT(user_id,plugin_id,key) DO UPDATE SET value=excluded.value', (uid,plugin,key,json.dumps(value, ensure_ascii=False)))

def balance(db, uid, kind):
    row = db.execute('SELECT amount FROM balances WHERE user_id=? AND kind=?', (uid, kind)).fetchone()
    return row[0] if row else 0

def credit(db, uid, kind, amount, reason, source, hooks=True):
    """Idempotent atomic ledger posting. Never accepts a user-chosen reward."""
    if kind not in ('essence','stones'):
        raise ValueError('Unsupported currency')
    if db.execute('SELECT 1 FROM ledger WHERE user_id=? AND kind=? AND source=?',(uid,kind,source)).fetchone():
        return False
    if balance(db,uid,kind) + amount < 0:
        raise HTTPException(409, '余额不足')
    db.execute('INSERT INTO ledger(user_id,kind,amount,reason,source,created_at) VALUES(?,?,?,?,?,?)',(uid,kind,amount,reason,source,now()))
    db.execute('INSERT OR IGNORE INTO balances VALUES(?,?,0)',(uid,kind))
    db.execute('UPDATE balances SET amount=amount+? WHERE user_id=? AND kind=?',(amount,uid,kind))
    if hooks: dispatch('currency.credited',db,uid,{'kind':kind,'amount':amount,'source':source})
    return True

def emit(db, uid, kind, payload=None):
    db.execute('INSERT INTO events(user_id,kind,payload,created_at) VALUES(?,?,?,?)',(uid,kind,json.dumps(payload or {}),now()))
    dispatch(kind,db,uid,payload or {})

def public_user(user):
    user=dict(user)
    return {k:user[k] for k in ['id','username','nickname','bio','created_at','role']}|{'avatar_url':'/api/profile/avatar/'+user['id']+'?v='+user['avatar'] if user.get('avatar') else None}

