"""Provision an administrator locally on the server, with JSON on stdin.

No public bootstrap endpoint; secrets are never printed or passed as arguments.
"""
import json
import re
import sys
import uuid
from pwdlib import PasswordHash
from .db import init,connect,now

if __name__=='__main__':
    value=json.load(sys.stdin)
    username=value['username'].casefold(); password=value['password']
    if not re.fullmatch('[a-z0-9_]{3,24}',username) or not 12<=len(password)<=128: raise SystemExit('Invalid admin credentials')
    init(); hasher=PasswordHash.recommended()
    with connect(True) as db:
        old=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if old:
            if old['role']!='admin' or not hasher.verify(password,old['password']): raise SystemExit('Account exists; refused to overwrite credentials or elevate an unrelated account')
        else:
            uid=uuid.uuid4().hex
            db.execute("INSERT INTO users(id,username,password,nickname,created_at,role) VALUES(?,?,?,?,?,'admin')",(uid,username,hasher.hash(password),'破晓管理员',now()))
            db.execute('INSERT INTO audit(actor_id,target_id,action,created_at) VALUES(?,?,?,?)',(uid,uid,'服务端初始化管理员',now()))
    print('Administrator ready: '+username)
