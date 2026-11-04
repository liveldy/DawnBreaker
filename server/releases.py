"""Public signed client release metadata. Website has no update controls."""
import base64
import json
import re
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import FileResponse
from .db import DATA

ROOT=DATA/'client-releases'
router=APIRouter(prefix='/api/releases',tags=['客户端更新'])

def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+',value): raise HTTPException(422,'版本号无效')
    return tuple(map(int,value.split('.')))

def manifest(platform):
    if platform not in ('windows','android'): raise HTTPException(404,'不支持的客户端')
    path=ROOT/(platform+'.json')
    if not path.is_file(): raise HTTPException(503,'尚未发布该客户端安装包')
    try:
        envelope=json.loads(path.read_text(encoding='utf-8'))
        payload=json.loads(base64.b64decode(envelope['signed'],validate=True))
        if payload['platform']!=platform or not re.fullmatch(r'[A-Za-z0-9._-]+',payload['filename']): raise ValueError()
        version(payload['version'])
        if not re.fullmatch('[a-f0-9]{64}',payload['sha256']): raise ValueError()
        return envelope,payload
    except (ValueError,KeyError,TypeError): raise HTTPException(503,'客户端发布信息无效')

@router.get('/{platform}')
def latest(platform:str,current:str=Query('0.0.0',pattern=r'^\d+\.\d+\.\d+$'),current_code:int|None=Query(None,ge=1)):
    envelope,payload=manifest(platform)
    return envelope|{'available':payload.get('version_code',0)>current_code if current_code else version(payload['version'])>version(current),'latest':payload['version'],'reset_from_preview':payload.get('reset_from_preview',False)}

@router.get('/{platform}/download/{release_version}')
def download(platform:str,release_version:str):
    _,payload=manifest(platform)
    if payload['version']!=release_version: raise HTTPException(404,'安装包版本不存在，请重新检查更新')
    path=ROOT/payload['filename']
    if not path.is_file() or path.stat().st_size!=payload['size']: raise HTTPException(503,'安装包尚未上传完成')
    return FileResponse(path,filename=payload['filename'],media_type='application/vnd.android.package-archive' if platform=='android' else 'application/octet-stream',headers={'X-Checksum-Sha256':payload['sha256']})
