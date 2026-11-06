"""Account-scoped Markdown/LaTeX library. Node IDs never denote filesystem paths."""
import json,os,sys,uuid,subprocess,threading,hashlib,io,shutil,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form,Response
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field
from ..core import require_plugin
from ..db import connect,now,DATA
from ..milestones import record_edit
from ..library_storage import usage,ensure,text_bytes,IMAGES
from .. import library_images as image_index
from PIL import Image,ImageOps,UnidentifiedImageError

MANIFEST={'id':'library','name':'流萤集','description':'把书籍和文档收进自己的书架。Markdown 与 LaTeX 编辑、公式预览，免费本地 OCR 导入。','category':'阅读与创作','icon':'BookOpen','ui':'library'}
router=APIRouter(prefix='/api/plugins/library',tags=['流萤集']);user=require_plugin('library')
IMPORTS=DATA/'library-imports';IMPORTS.mkdir(exist_ok=True)
POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='dawn-ocr')
IMAGE_LIMIT=threading.BoundedSemaphore(2)

def node(db,uid,id):
    row=db.execute('SELECT * FROM library_nodes WHERE id=? AND user_id=?',(id,uid)).fetchone()
    if not row:raise HTTPException(404,'文档或文件夹不存在')
    return dict(row)
def folder(db,uid,id):
    if id and node(db,uid,id)['kind']!='folder':raise HTTPException(422,'请选择文件夹')
def within(db,uid,id,root):
    seen=set()
    while id:
        if id==root:return True
        if id in seen or len(seen)>32:return False
        seen.add(id);id=node(db,uid,id)['parent_id']
    return False
def create_document(db,uid,parent,title,markdown,source=None):
    if db.execute('SELECT COUNT(*) FROM library_nodes WHERE user_id=?',(uid,)).fetchone()[0]>=10000:raise HTTPException(409,'文档数量已达上限')
    folder(db,uid,parent);ensure(db,uid,text_bytes(title,markdown));id=uuid.uuid4().hex;stamp=now()
    db.execute('INSERT INTO library_nodes VALUES(?,?,?,?,?,?,1,?,?,?)',(id,uid,parent,'document',title,markdown,source,stamp,stamp))
    return node(db,uid,id)

class Create(BaseModel):
    parent_id:str|None=None
    kind:Literal['folder','document']='document'
    title:str=Field(min_length=1,max_length=200)
    markdown:str=Field(default='',max_length=1000000)
class Update(BaseModel):
    revision:int=Field(ge=1)
    title:str=Field(min_length=1,max_length=200)
    markdown:str=Field(max_length=1000000)
    parent_id:str|None=None

class ForegroundTime(BaseModel):
    session:str=Field(min_length=8,max_length=80,pattern='^[A-Za-z0-9_-]+$')
    document_id:str=Field(min_length=1,max_length=80)
    seconds:float=Field(ge=0,le=100000000,allow_inf_nan=False)

@router.post('/foreground-time')
def foreground_time(body:ForegroundTime,u=Depends(user)):
    from ..library_time import record
    with connect(True) as d:
        if node(d,u['id'],body.document_id)['kind']!='document':raise HTTPException(422,'只统计文档页面停留时间')
        return record(d,u['id'],body.session,body.document_id,body.seconds)

@router.get('')
def listing(u=Depends(user)):
    with connect() as d:
        rows=[dict(r) for r in d.execute('SELECT id,parent_id,kind,title,revision,source_job_id,updated_at FROM library_nodes WHERE user_id=? ORDER BY kind DESC,title',(u['id'],))]
        jobs=[dict(r) for r in d.execute('SELECT id,parent_id,title,mode,status,error,document_id,created_at FROM import_jobs WHERE user_id=? AND deleted=0 ORDER BY created_at DESC LIMIT 30',(u['id'],))]
        storage=usage(d,u['id'])
    return {'nodes':rows,'imports':jobs,'storage':storage,'ocr':'Pix2Text','supports':['markdown','latex','pdf','image','doc','docx']}
@router.post('/nodes',status_code=201)
def create(body:Create,u=Depends(user)):
    with connect(True) as d:
        folder(d,u['id'],body.parent_id)
        if d.execute('SELECT COUNT(*) FROM library_nodes WHERE user_id=?',(u['id'],)).fetchone()[0]>=10000:raise HTTPException(409,'文档数量已达上限')
        if body.kind=='document':return create_document(d,u['id'],body.parent_id,body.title,body.markdown)
        ensure(d,u['id'],text_bytes(body.title))
        id=uuid.uuid4().hex;stamp=now();d.execute('INSERT INTO library_nodes VALUES(?,?,?,?,?,?,1,NULL,?,?)',(id,u['id'],body.parent_id,'folder',body.title,'',stamp,stamp));return node(d,u['id'],id)
@router.get('/nodes/{id}')
def get(id:str,u=Depends(user)):
    with connect() as d:return node(d,u['id'],id)
@router.put('/nodes/{id}')
def update(id:str,body:Update,u=Depends(user)):
    with connect(True) as d:
        current=node(d,u['id'],id);folder(d,u['id'],body.parent_id)
        if current['revision']!=body.revision:raise HTTPException(409,'文档已在其他位置修改，请重新打开后再保存')
        ensure(d,u['id'],text_bytes(body.title,body.markdown if current['kind']=='document' else '')-text_bytes(current['title'],current['markdown']))
        if body.parent_id and (body.parent_id==id or within(d,u['id'],body.parent_id,id)):raise HTTPException(422,'不能把文件夹移入自身或子目录')
        if current['kind']=='document':record_edit(d,u['id'],id,current['markdown'],body.markdown)
        d.execute('UPDATE library_nodes SET parent_id=?,title=?,markdown=?,revision=revision+1,updated_at=? WHERE id=?',(body.parent_id,body.title,body.markdown if current['kind']=='document' else '',now(),id));result=node(d,u['id'],id)
    cleanup_assets(u['id'],current)
    return result
@router.delete('/nodes/{id}')
def delete(id:str,u=Depends(user)):
    with connect(True) as d:
        current=node(d,u['id'],id)
        if d.execute('SELECT 1 FROM library_nodes WHERE parent_id=? AND user_id=?',(id,u['id'])).fetchone():raise HTTPException(409,'请先移走文件夹内的内容')
        # Configured AI folders cannot disappear beneath a working assistant.
        for row in d.execute('SELECT config FROM assistants WHERE user_id=?',(u['id'],)):
            config=json.loads(row[0])
            if id in (config.get('workspace_id'),config.get('memory_id')):raise HTTPException(409,'此文件夹正在被星丛使用，请先修改助手配置')
        d.execute('DELETE FROM library_nodes WHERE id=?',(id,))
        d.execute('UPDATE import_jobs SET document_id=NULL WHERE user_id=? AND document_id=?',(u['id'],id))
    cleanup_assets(u['id'],current)
    return {'message':'已删除'}
@router.get('/nodes/{id}/export')
def export(id:str,u=Depends(user)):
    with connect() as d:doc=node(d,u['id'],id)
    if doc['kind']!='document':raise HTTPException(422,'请选择文档')
    return Response(doc['markdown'],media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(doc['title']+'.md')})

def job_path(uid,id):
    if not all(c in '0123456789abcdef' for c in uid+id) or len(uid)!=32 or len(id)!=32:raise HTTPException(404,'文件不存在')
    return IMPORTS/uid/id

def cleanup_assets(uid,document):
    candidates=set(re.findall(r'/api/plugins/library/imports/([a-f0-9]{32})/assets/',document.get('markdown','')))
    if document.get('source_job_id'):candidates.add(document['source_job_id'])
    with connect(True) as d:
        for id in candidates:
            job=d.execute('SELECT * FROM import_jobs WHERE id=? AND user_id=?',(id,uid)).fetchone()
            if not job or job['status'] in ('queued','running') or job['document_id'] and d.execute('SELECT 1 FROM library_nodes WHERE id=? AND user_id=?',(job['document_id'],uid)).fetchone():continue
            prefix='/api/plugins/library/imports/'+id+'/assets/'
            if image_index.job_referenced(d,uid,id):continue
            work=job_path(uid,id)
            if work.is_dir():
                try:shutil.rmtree(work);d.execute('DELETE FROM library_images WHERE user_id=? AND source_job_id=?',(uid,id))
                except OSError:pass
def run_import(uid,id):
    with connect(True) as d:
        job=d.execute('SELECT * FROM import_jobs WHERE id=? AND user_id=?',(id,uid)).fetchone()
        if not job:return
        d.execute("UPDATE import_jobs SET status='running',updated_at=? WHERE id=?",(now(),id))
    work=job_path(uid,id);output=work/'result.json'
    word=Path(job['filename']).suffix.lower() in ('.doc','.docx')
    executable=sys.executable if word else os.environ.get('DAWN_OCR_PYTHON','/opt/dawnbreaker/ocr-venv/bin/python')
    try:
        if not Path(executable).is_file():raise RuntimeError('OCR 引擎尚未就绪，请稍后重试；仍可直接导入 Markdown / LaTeX 文件。')
        result=subprocess.run([executable,str(Path(__file__).parents[1]/('word_worker.py' if word else 'ocr_worker.py')),str(work/job['filename']),str(output),job['mode']],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240 if word else 1200)
        if result.returncode!=0 or not output.is_file():raise RuntimeError(result.stderr.strip()[-300:] if word and result.returncode==2 else '转换未完成，请检查文件是否完整、未加密，或拆分后重试。')
        converted=json.loads(output.read_text(encoding='utf-8'));content=converted['markdown'];warning='；'.join(converted.get('warnings',[])) or None
        if not content.strip():raise RuntimeError('没有识别到内容，请检查文件或切换识别模式。')
        if len(content)>1000000:raise RuntimeError('识别内容过长，请拆分书籍后重试。')
        output.unlink(missing_ok=True)
        with connect(True) as d:
            content=image_index.shorten(content,image_index.index_import(d,uid,dict(job)))
            ensure(d,uid,len(content.encode('utf8')))
            doc=create_document(d,uid,job['parent_id'],job['title'],content,id)
            d.execute("UPDATE import_jobs SET status='completed',document_id=?,error=?,updated_at=? WHERE id=?",(doc['id'],warning,now(),id))
    except Exception as e:
        if isinstance(e,HTTPException) and e.status_code==413:
            generated=work/'output'
            if generated.is_dir():shutil.rmtree(generated)
            output.unlink(missing_ok=True)
        message=str(e.detail) if isinstance(e,HTTPException) else str(e) if isinstance(e,RuntimeError) else '识别超时或服务暂不可用，请重试或拆分文件。'
        with connect(True) as d:d.execute("UPDATE import_jobs SET status='failed',error=?,updated_at=? WHERE id=?",(message,now(),id))

@router.post('/imports',status_code=202)
async def import_file(file:UploadFile=File(...),parent_id:str=Form(''),mode:Literal['auto','document','formula']=Form('auto'),u=Depends(user)):
    extension=Path(file.filename or '').suffix.lower();title=Path(file.filename or '新文档').stem[:200]
    if extension not in ('.md','.markdown','.txt','.tex','.doc','.docx','.pdf','.png','.jpg','.jpeg','.webp'):raise HTTPException(422,'支持 Word（DOC / DOCX）、Markdown、LaTeX、PDF、PNG、JPEG、WebP')
    content=await file.read(30*1024*1024+1)
    if not content or len(content)>30*1024*1024:raise HTTPException(413,'文件需小于 30 MB')
    parent_id=parent_id or None
    with connect(True) as d:
        folder(d,u['id'],parent_id)
        if extension in ('.md','.markdown','.txt','.tex'):
            try:text=content.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:text=content.decode('gb18030')
                except UnicodeDecodeError:raise HTTPException(422,'请使用 UTF-8 或 GB18030 文本文件')
            if len(text)>1000000:raise HTTPException(413,'文档文本过长，请拆分后导入')
            if extension=='.tex':text='$$\n'+text+'\n$$' if '\\documentclass' not in text else text
            id=uuid.uuid4().hex;stamp=now();doc=create_document(d,u['id'],parent_id,title,text,id)
            d.execute('INSERT INTO import_jobs(id,user_id,parent_id,title,filename,mode,status,document_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,u['id'],parent_id,title,'',mode,'completed',doc['id'],stamp,stamp))
            return {'id':id,'status':'completed','document_id':doc['id']}
        if d.execute("SELECT COUNT(*) FROM import_jobs WHERE status IN ('queued','running')").fetchone()[0]>=8 or d.execute("SELECT COUNT(*) FROM import_jobs WHERE user_id=? AND status IN ('queued','running')",(u['id'],)).fetchone()[0]>=2:raise HTTPException(429,'已有文件正在识别，请稍候')
        ensure(d,u['id'],len(content))
        id=uuid.uuid4().hex;work=job_path(u['id'],id);work.mkdir(parents=True,mode=0o700);filename='source'+extension;(work/filename).write_bytes(content)
        stamp=now();d.execute('INSERT INTO import_jobs(id,user_id,parent_id,title,filename,mode,status,error,document_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,NULL,NULL,?,?)',(id,u['id'],parent_id,title,filename,mode,'queued',stamp,stamp))
    POOL.submit(run_import,u['id'],id)
    return {'id':id,'status':'queued'}
@router.post('/imports/{id}/retry')
def retry(id:str,u=Depends(user)):
    with connect(True) as d:
        job=d.execute('SELECT * FROM import_jobs WHERE id=? AND user_id=?',(id,u['id'])).fetchone()
        if not job or job['deleted']:raise HTTPException(404,'导入记录不存在')
        if job['status']!='failed':raise HTTPException(409,'仅可重试失败的识别任务')
        if d.execute("SELECT COUNT(*) FROM import_jobs WHERE status IN ('queued','running')").fetchone()[0]>=8:raise HTTPException(429,'识别队列已满，请稍候')
        d.execute("UPDATE import_jobs SET status='queued',error=NULL,updated_at=? WHERE id=?",(now(),id))
    POOL.submit(run_import,u['id'],id);return {'message':'已重新加入识别队列'}
@router.delete('/imports/{id}')
def remove_import(id:str,u=Depends(user)):
    with connect(True) as d:
        job=d.execute('SELECT * FROM import_jobs WHERE id=? AND user_id=? AND deleted=0',(id,u['id'])).fetchone()
        if not job:raise HTTPException(404,'导入记录不存在')
        if job['status'] in ('queued','running'):raise HTTPException(409,'识别完成后可删除记录')
        # Retain document-linked image assets; deleting history must not break a book.
        d.execute('UPDATE import_jobs SET deleted=1 WHERE id=?',(id,))
        work=job_path(u['id'],id)
        if work.is_dir():
            references=image_index.job_referenced(d,u['id'],id)
            if not job['document_id'] and not references:
                shutil.rmtree(work)
                d.execute('DELETE FROM library_images WHERE user_id=? AND source_job_id=?',(u['id'],id))
            elif job['filename']:(work/job['filename']).unlink(missing_ok=True)
    return {'message':'导入记录已删除，文档及其图片保留'}
@router.get('/imports/{id}/assets/{asset:path}')
def asset(id:str,asset:str,u=Depends(user)):
    with connect() as d:
        if not d.execute('SELECT 1 FROM import_jobs WHERE id=? AND user_id=?',(id,u['id'])).fetchone():raise HTTPException(404,'文件不存在')
    root=job_path(u['id'],id)/'output';path=(root/asset).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise HTTPException(404,'图片不存在')
    return FileResponse(path)

def prepare_image(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('PNG','JPEG','WEBP','GIF') or image.width*image.height>24000000:raise ValueError()
            image=ImageOps.exif_transpose(image);out=io.BytesIO();image.save(out,'WEBP',quality=90);data=out.getvalue()
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):raise HTTPException(422,'请使用有效的 PNG、JPEG、WebP 或 GIF 图片，尺寸不超过 2400 万像素')
    return data

@router.post('/images',status_code=201)
async def upload_image(file:UploadFile=File(...),u=Depends(user)):
    data=await file.read(10*1024*1024+1)
    if not data or len(data)>10*1024*1024:raise HTTPException(413,'图片需小于 10 MB')
    if not IMAGE_LIMIT.acquire(False):raise HTTPException(429,'图片处理繁忙，请稍后重试')
    try:data=await run_in_threadpool(prepare_image,data)
    finally:IMAGE_LIMIT.release()
    id=uuid.uuid4().hex;filename=id+'.webp';directory=IMAGES/u['id'];directory.mkdir(parents=True,exist_ok=True)
    path=directory/filename
    try:
        with connect(True) as d:
            ensure(d,u['id'],len(data));path.write_bytes(data)
            ref=image_index.next_ref(d,u['id'])
            d.execute('INSERT INTO library_images(id,user_id,filename,mime,size,sha256,created_at,ref,name) VALUES(?,?,?,?,?,?,?,?,?)',(id,u['id'],filename,'image/webp',len(data),hashlib.sha256(data).hexdigest(),now(),ref,(file.filename or '图片')[:200]))
    except Exception:path.unlink(missing_ok=True);raise
    return {'id':id,'url':'/api/plugins/library/images/'+id,'reference':'img/'+str(ref),'size':len(data),'name':(file.filename or '图片')[:200]}

@router.get('/images')
def images(u=Depends(user)):
    with connect(True) as d:
        image_index.backfill(d,u['id'])
        rows=[dict(r) for r in d.execute('SELECT * FROM library_images WHERE user_id=? ORDER BY ref DESC',(u['id'],))]
        for row in rows:
            row['url']='/api/plugins/library/images/'+row['id'];row['reference']='img/'+str(row['ref']);row['references']=image_index.references(d,u['id'],row);row['source']='import' if row['source_job_id'] else 'upload'
            for field in ('filename','source_asset','sha256','user_id'):row.pop(field,None)
        return {'images':rows,'storage':usage(d,u['id'])}

@router.get('/images/ref/{ref}')
def image_ref(ref:int,u=Depends(user)):
    with connect(True) as d:
        image_index.backfill(d,u['id']);row=d.execute('SELECT * FROM library_images WHERE user_id=? AND ref=?',(u['id'],ref)).fetchone()
    if not row:raise HTTPException(404,'图片不存在')
    path=image_index.physical(dict(row))
    if not path.is_file():raise HTTPException(404,'图片不存在')
    return FileResponse(path,media_type=row['mime'])

@router.get('/images/{id}')
def image(id:str,u=Depends(user)):
    with connect() as d:row=d.execute('SELECT * FROM library_images WHERE id=? AND user_id=?',(id,u['id'])).fetchone()
    if not row:raise HTTPException(404,'图片不存在')
    path=image_index.physical(dict(row))
    if not path.is_file():raise HTTPException(404,'图片不存在')
    return FileResponse(path,media_type=row['mime'])

@router.delete('/images/{id}')
def delete_image(id:str,u=Depends(user)):
    with connect(True) as d:
        row=d.execute('SELECT * FROM library_images WHERE id=? AND user_id=?',(id,u['id'])).fetchone()
        if not row:raise HTTPException(404,'图片不存在')
        url='/api/plugins/library/images/'+id
        if image_index.references(d,u['id'],dict(row)):raise HTTPException(409,'图片仍被文档引用，请先在文档中移除图片')
        d.execute('DELETE FROM library_images WHERE id=? AND user_id=?',(id,u['id']))
    image_index.physical(dict(row)).unlink(missing_ok=True)
    return {'message':'图片已删除，空间已释放'}
