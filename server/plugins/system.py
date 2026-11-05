"""Per-account installation only; device information stays on the local client."""
from fastapi import APIRouter,Depends
from ..core import require_plugin
MANIFEST={'id':'system','name':'系统管理','description':'查看本机系统、内存与存储信息，整理破晓内存，打开系统管理工具。','category':'设备工具','icon':'Cpu','ui':'system','platforms':['desktop','mobile']}
router=APIRouter(prefix='/api/plugins/system',tags=['系统管理']);user=require_plugin('system')
@router.get('')
def get(u=Depends(user)):
    return {'local_only':True,'platforms':MANIFEST['platforms']}
