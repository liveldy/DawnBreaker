import io,os,secrets
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from fastapi.responses import FileResponse
from PIL import Image,ImageOps,UnidentifiedImageError
from .core import require_user
from .db import connect,DATA
router=APIRouter(prefix='/api/profile/avatar',tags=['头像']);ROOT=DATA/'avatars';ROOT.mkdir(exist_ok=True)
@router.post('')
async def upload(file:UploadFile=File(...),u=Depends(require_user)):
    content=await file.read(5*1024*1024+1)
    if not content or len(content)>5*1024*1024:raise HTTPException(413,'头像图片需小于 5 MB')
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>20000000:raise ValueError()
            im=ImageOps.exif_transpose(im);im=ImageOps.fit(im.convert('RGB'),(512,512),method=Image.Resampling.LANCZOS)
            output=io.BytesIO();im.save(output,'WEBP',quality=88)
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):raise HTTPException(422,'请上传有效的 PNG、JPEG 或 WebP 图片，尺寸不要超过 2000 万像素')
    token=secrets.token_hex(8);target=ROOT/(u['id']+'.webp');temporary=ROOT/(u['id']+'.'+token+'.tmp');temporary.write_bytes(output.getvalue());temporary.replace(target)
    with connect(True) as d:d.execute('UPDATE users SET avatar=? WHERE id=?',(token,u['id']))
    return {'message':'头像已更新','avatar_url':'/api/profile/avatar/'+u['id']+'?v='+token}
@router.get('/{uid}')
def get(uid:str,u=Depends(require_user)):
    if uid!=u['id'] and u['role']!='admin':raise HTTPException(404,'头像不存在')
    if len(uid)!=32 or any(c not in '0123456789abcdef' for c in uid):raise HTTPException(404,'头像不存在')
    path=ROOT/(uid+'.webp')
    if not path.is_file():raise HTTPException(404,'头像不存在')
    return FileResponse(path,media_type='image/webp')
@router.delete('')
def reset(u=Depends(require_user)):
    with connect(True) as d:d.execute("UPDATE users SET avatar='' WHERE id=?",(u['id'],))
    return {'message':'已恢复默认头像'}
