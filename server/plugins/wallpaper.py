"""Cloud wallpaper packages. Only administrators publish; clients render in isolation."""
import hashlib,io,json,stat,uuid,zipfile
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from PIL import Image,ImageOps,UnidentifiedImageError
from ..core import require_plugin
from ..db import connect,DATA,now
MANIFEST={'id':'wallpaper','name':'浮光掠影','description':'为 Windows 桌面制作图像、视频或可交互网页壁纸，支持多显示器。管理员可发布到云端。','category':'桌面与个性化','icon':'Wallpaper','ui':'wallpaper','platforms':['desktop']}
router=APIRouter(prefix='/api/plugins/wallpaper',tags=['浮光掠影']);user=require_plugin('wallpaper');ROOT=DATA/'wallpapers';ROOT.mkdir(exist_ok=True)
LIMIT=100*1024*1024
class Variant(BaseModel):
    kind:Literal['image','video','web']
    entry:str|None=Field(default=None,max_length=240)
    url:str|None=Field(default=None,max_length=2000)
    fit:Literal['cover','contain']='cover'
    @model_validator(mode='after')
    def source(self):
        if bool(self.entry)==bool(self.url):raise ValueError('每端需选择一个本地入口或网页地址')
        if self.url:
            p=urlsplit(self.url)
            if self.kind!='web' or p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('网页地址需为无账号信息的 HTTPS 地址')
        return self
class Manifest(BaseModel):
    format:Literal[1]=1
    title:str=Field(min_length=1,max_length=80)
    description:str=Field(default='',max_length=1000)
    variants:dict[str,Variant]
    @model_validator(mode='after')
    def platforms(self):
        if not self.variants or not set(self.variants)<= {'desktop','mobile'}:raise ValueError('请选择桌面端、移动端或两端')
        return self
def safe_name(value):
    p=PurePosixPath(value)
    reserved={'CON','PRN','AUX','NUL'}|{f'{prefix}{n}' for prefix in ('COM','LPT') for n in range(1,10)}
    return bool(value) and str(p)==value and not p.is_absolute() and '\\' not in value and ':' not in value and not any(x in ('..','.') or x.rstrip(' .')!=x or x.split('.')[0].upper() in reserved for x in p.parts) and not any(ord(c)<32 for c in value) and len(value)<241
def inspect_package(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos=[i for i in archive.infolist() if not i.is_dir()]
            if not infos or len(infos)>512 or sum(i.file_size for i in infos)>200*1024*1024:raise HTTPException(413,'壁纸解压后需小于 200 MB，文件数不超过 512')
            names=set()
            for entry in infos:
                if not safe_name(entry.orig_filename) or entry.orig_filename!=entry.filename or entry.filename.casefold() in names or stat.S_ISLNK(entry.external_attr>>16) or entry.flag_bits&1:raise HTTPException(422,'壁纸包包含重复、不安全路径、符号链接或加密文件')
                names.add(entry.filename.casefold())
            info=archive.getinfo('manifest.json')
            if info.file_size>65536:raise HTTPException(422,'壁纸清单过长')
            manifest=Manifest.model_validate_json(archive.read(info))
            for variant in manifest.variants.values():
                if variant.entry:
                    if not safe_name(variant.entry) or variant.entry not in archive.namelist():raise HTTPException(422,'壁纸入口不存在')
                    extension=Path(variant.entry).suffix.lower()
                    valid={'image':{'.png','.jpg','.jpeg','.webp','.gif'},'video':{'.mp4','.webm'},'web':{'.html','.htm'}}
                    if extension not in valid[variant.kind]:raise HTTPException(422,'入口文件格式与壁纸类型不符')
            thumb=None
            candidate=next((v.entry for v in manifest.variants.values() if v.kind=='image' and v.entry),None)
            if candidate:
                with Image.open(io.BytesIO(archive.read(candidate))) as image:
                    image=ImageOps.exif_transpose(image);image.thumbnail((720,480));buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=85);thumb=buffer.getvalue()
            return manifest.model_dump(),thumb
    except HTTPException:raise
    except (ValueError,KeyError,zipfile.BadZipFile,RuntimeError,UnidentifiedImageError,OSError,Image.DecompressionBombError):raise HTTPException(422,'壁纸包损坏或清单 / 图像格式无效')
def public(row):
    m=json.loads(row['manifest']);return {'id':row['id'],'title':row['title'],'manifest':m,'size':row['size'],'sha256':row['sha256'],'created_at':row['created_at'],'preview':'/api/plugins/wallpaper/'+row['id']+'/preview','download':'/api/plugins/wallpaper/'+row['id']+'/file'}
@router.get('')
def listing(u=Depends(user)):
    with connect() as d:return {'wallpapers':[public(dict(r)) for r in d.execute('SELECT * FROM wallpapers ORDER BY created_at DESC')],'can_publish':u['role']=='admin','max_package_bytes':LIMIT}
@router.post('',status_code=201)
async def publish(file:UploadFile=File(...),u=Depends(user)):
    if u['role']!='admin':raise HTTPException(403,'仅管理员可以上传云端壁纸，本地创作不受限制')
    data=await file.read(LIMIT+1)
    if not data or len(data)>LIMIT:raise HTTPException(413,'壁纸包需小于 100 MB')
    manifest,thumb=inspect_package(data);id=uuid.uuid4().hex;filename=id+'.dawnwallpaper';path=ROOT/filename
    try:
        path.write_bytes(data)
        if thumb:(ROOT/(id+'.jpg')).write_bytes(thumb)
        with connect(True) as d:
            d.execute('INSERT INTO wallpapers VALUES(?,?,?,?,?,?,?,?)',(id,u['id'],manifest['title'],json.dumps(manifest,ensure_ascii=False),filename,len(data),hashlib.sha256(data).hexdigest(),now()));return public(dict(d.execute('SELECT * FROM wallpapers WHERE id=?',(id,)).fetchone()))
    except Exception:path.unlink(missing_ok=True);(ROOT/(id+'.jpg')).unlink(missing_ok=True);raise
def row_for(id):
    with connect() as d:r=d.execute('SELECT * FROM wallpapers WHERE id=?',(id,)).fetchone()
    if not r:raise HTTPException(404,'壁纸不存在')
    return dict(r)
@router.get('/{id}/file')
def download(id:str,u=Depends(user)):
    r=row_for(id);return FileResponse(ROOT/r['filename'],filename=r['id']+'.dawnwallpaper',media_type='application/zip',headers={'X-Checksum-SHA256':r['sha256']})
@router.get('/{id}/preview')
def preview(id:str,u=Depends(user)):
    r=row_for(id);path=ROOT/(r['id']+'.jpg')
    if not path.is_file():raise HTTPException(404,'此壁纸没有图像预览')
    return FileResponse(path,media_type='image/jpeg')
@router.delete('/{id}')
def delete(id:str,u=Depends(user)):
    if u['role']!='admin':raise HTTPException(403,'仅管理员可移除云端壁纸')
    r=row_for(id)
    with connect(True) as d:d.execute('DELETE FROM wallpapers WHERE id=?',(id,))
    (ROOT/r['filename']).unlink(missing_ok=True);(ROOT/(r['id']+'.jpg')).unlink(missing_ok=True)
    return {'message':'云端壁纸已删除，已下载的本地副本保留'}
