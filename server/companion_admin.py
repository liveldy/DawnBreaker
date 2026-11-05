"""Administrator controls for editable presets; immutable identity is never a form field."""
import hashlib,json,uuid
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,ValidationError
from . import db,companion_config as config
from .admin import require_admin,audit

router=APIRouter(prefix='/api/admin/companion',tags=['拾光者设定'])
class Update(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:str
    config:dict

@router.get('')
def read(u=Depends(require_admin)):
    return config.snapshot()|{'defaults':config.defaults(),'schema':config.Settings.model_json_schema()}

@router.put('')
def save(body:Update,u=Depends(require_admin)):
    try:value=config.Settings.model_validate(body.config).model_dump()
    except ValidationError as error:
        parts=['.'.join(str(x) for x in e['loc'])+': '+e['msg'] for e in error.errors()[:8]]
        raise HTTPException(422,'配置无效：'+'；'.join(parts))
    with db.connect(True) as d:
        old=config.snapshot(d)
        if old['revision']!=body.revision:raise HTTPException(409,'设定已被其他管理员修改，请重新读取后再保存')
        result={'revision':uuid.uuid4().hex,'config':value,'updated_at':db.now()}
        d.execute('INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(config.KEY,json.dumps(result,ensure_ascii=False),result['updated_at']))
        digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        audit(d,u,'更新拾光者模型设定',before={'revision':old['revision'],'sha256':digest(old['config'])},after={'revision':result['revision'],'sha256':digest(value)})
    config.invalidate()
    return result|{'message':'模型设定已保存，下次处理消息时采用新设定'}
