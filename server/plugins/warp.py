"""Account-owned encrypted profiles; network/VPN execution stays on the client."""
import uuid
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from ..core import require_plugin,state,set_state
from ..db import connect,now
from ..secret_store import seal,open_secret
MANIFEST={'id':'warp','name':'折跃门','description':'基于开源 Mihomo 的 Clash 兼容代理。订阅、本地配置、规则、节点与流量，由设备端运行。','category':'网络工具','icon':'Waypoints','ui':'warp'}
router=APIRouter(prefix='/api/plugins/warp',tags=['折跃门']);user=require_plugin('warp')
class Profile(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    yaml:str=Field(default='',max_length=1000000)
    subscription:str=Field(default='',max_length=4000)
def public(p):return {k:v for k,v in p.items() if k not in ('yaml','subscription')}|{'has_subscription':bool(p.get('subscription'))}
@router.get('')
def listing(u=Depends(user)):
    with connect() as d:profiles=state(d,u['id'],'warp','profiles',[])
    return {'profiles':[public(p) for p in profiles],'core':'Mihomo v1.19.33','source':'https://github.com/MetaCubeX/mihomo','license':'GPL-3.0','note':'代理在 Windows / Android 客户端运行，不将服务器变成公共代理。'}
@router.post('',status_code=201)
def create(body:Profile,u=Depends(user)):
    from urllib.parse import urlsplit
    if not body.yaml.strip() and not body.subscription:raise HTTPException(422,'请选择配置内容或订阅地址')
    if body.subscription:
        p=urlsplit(body.subscription)
        if p.scheme!='https' or not p.hostname or p.username or p.password:raise HTTPException(422,'订阅需为 HTTPS 地址，不要包含账号密码')
    with connect(True) as d:
        profiles=state(d,u['id'],'warp','profiles',[])
        if len(profiles)>=30:raise HTTPException(409,'最多保存 30 个配置')
        p={'id':uuid.uuid4().hex,'name':body.name,'yaml':seal(body.yaml),'subscription':seal(body.subscription),'created_at':now()};profiles.append(p);set_state(d,u['id'],'warp','profiles',profiles);return public(p)
@router.post('/{id}/open')
def reveal(id:str,u=Depends(user)):
    with connect() as d:profile=next((p for p in state(d,u['id'],'warp','profiles',[]) if p['id']==id),None)
    if not profile:raise HTTPException(404,'配置不存在')
    return {'id':id,'name':profile['name'],'yaml':open_secret(profile['yaml']),'subscription':open_secret(profile['subscription'])}
@router.delete('/{id}')
def delete(id:str,u=Depends(user)):
    with connect(True) as d:
        profiles=state(d,u['id'],'warp','profiles',[])
        if not any(p['id']==id for p in profiles):raise HTTPException(404,'配置不存在')
        set_state(d,u['id'],'warp','profiles',[p for p in profiles if p['id']!=id])
    return {'message':'配置已删除；运行中的设备需单独停止或切换配置'}
