"""Private fixed-egress controls; ordinary accounts cannot read subscription metadata."""
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from .admin import require_admin
from . import xai_egress as manager

router=APIRouter(prefix='/api/admin/xai-egress',tags=['管理员出站'])
class Subscription(BaseModel):
    url:str=Field(default='',max_length=4000)
class Node(BaseModel):
    node_id:str=Field(min_length=1,max_length=64)
    revision:str=Field(min_length=1,max_length=64)
class Enabled(BaseModel):
    enabled:bool

def mutate(fn,*args):
    if not manager.LOCK.acquire(blocking=False):raise HTTPException(409,'其他管理员正在处理出站配置，请稍候刷新')
    try:return fn(*args)
    finally:manager.LOCK.release()

@router.get('')
def get(u=Depends(require_admin)):return manager.public()
@router.post('/subscription')
def subscription(body:Subscription,u=Depends(require_admin)):return mutate(manager.import_subscription,body.url,u['id'])
@router.post('/test-node')
def test_node(body:Node,u=Depends(require_admin)):return mutate(manager.test_candidate,body.node_id,body.revision,u['id'])
@router.post('/apply')
def apply(body:Node,u=Depends(require_admin)):return mutate(manager.activate,body.node_id,body.revision,u['id'])
@router.post('/enabled')
def enabled(body:Enabled,u=Depends(require_admin)):return mutate(manager.enabled,body.enabled,u['id'])
@router.post('/test-current')
def test_current(u=Depends(require_admin)):return mutate(manager.test_current,u['id'])
