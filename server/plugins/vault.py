"""Opaque end-to-end encrypted vault. The master password/key never reaches the API."""
import base64,json
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from ..core import require_plugin
from ..db import connect,now
MANIFEST={'id':'vault','name':'暗格','description':'用独立主密码收好密码、卡片与个人信息。内容在本机加密后同步，支持自定义字段与导出。','category':'隐私','icon':'LockKeyhole','ui':'vault'}
router=APIRouter(prefix='/api/plugins/vault',tags=['暗格']);user=require_plugin('vault')
class Envelope(BaseModel):
    version:int=Field(ge=0)
    salt:str=Field(max_length=64)
    nonce:str=Field(max_length=64)
    ciphertext:str=Field(max_length=45*1024*1024)
    format_version:int=Field(default=2,ge=1,le=3)
    iterations:int=Field(ge=600000,le=600000)
    algorithm:str=Field(pattern='^PBKDF2-SHA256/AES-256-GCM$')
@router.get('')
def get(u=Depends(user)):
    with connect() as d:row=d.execute('SELECT * FROM vaults WHERE user_id=?',(u['id'],)).fetchone()
    return {'exists':False} if not row else json.loads(row['envelope'])|{'exists':True,'version':row['version'],'updated_at':row['updated_at']}
@router.put('')
def save(body:Envelope,u=Depends(user)):
    try:
        salt=base64.b64decode(body.salt,validate=True);iv=base64.b64decode(body.nonce,validate=True);data=base64.b64decode(body.ciphertext,validate=True)
        if len(salt)!=16 or len(iv)!=12 or len(data)<16:raise ValueError()
    except Exception:raise HTTPException(422,'加密数据格式无效')
    with connect(True) as d:
        current=d.execute('SELECT version,envelope FROM vaults WHERE user_id=?',(u['id'],)).fetchone()
        if current and json.loads(current['envelope']).get('format_version',2)>body.format_version:raise HTTPException(409,'密码箱已包含照片等新版资料，请更新客户端后再编辑')
        if (current['version'] if current else 0)!=body.version:raise HTTPException(409,'密码箱已被其他设备更新，请锁定后重新解锁再编辑')
        version=body.version+1
        d.execute('INSERT INTO vaults VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET version=excluded.version,envelope=excluded.envelope,updated_at=excluded.updated_at',(u['id'],version,json.dumps(body.model_dump(exclude={'version'})),now()))
    return {'version':version,'message':'已加密保存'}
