"""Account-scoped aliases for uploaded and imported images, with no duplicate files."""
import hashlib,re,uuid
from urllib.parse import quote
from PIL import Image,UnidentifiedImageError

def next_ref(d,uid):
    d.execute('INSERT OR IGNORE INTO library_image_sequences VALUES(?,(SELECT COALESCE(MAX(ref),0)+1 FROM library_images WHERE user_id=?))',(uid,uid))
    ref=d.execute('SELECT next_ref FROM library_image_sequences WHERE user_id=?',(uid,)).fetchone()[0]
    d.execute('UPDATE library_image_sequences SET next_ref=next_ref+1 WHERE user_id=?',(uid,));return ref

def aliases(row):
    values=['/api/plugins/library/images/'+row['id']]
    if row['ref'] is not None:values.append('img/'+str(row['ref']))
    if row['source_job_id']:
        prefix='/api/plugins/library/imports/'+row['source_job_id']+'/assets/'
        values.extend([prefix+row['source_asset'],prefix+quote(row['source_asset'],safe='/')])
    return list(dict.fromkeys(values))

def referenced(markdown,row):
    return bool(re.search(r'(?<![A-Za-z0-9_/-])(?:'+'|'.join(re.escape(v) for v in aliases(row))+r')(?![A-Za-z0-9_/-])',markdown))

def references(d,uid,row):
    return sum(referenced(r[0],row) for r in d.execute("SELECT markdown FROM library_nodes WHERE user_id=? AND kind='document'",(uid,)))

def physical(row):
    from .plugins import library
    if not row['source_job_id']:return library.IMAGES/row['user_id']/row['filename']
    root=library.job_path(row['user_id'],row['source_job_id'])/'output';path=(root/row['source_asset']).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Invalid import asset')
    return path

def index_import(d,uid,job):
    from .plugins.library import job_path
    if not d.execute('SELECT 1 FROM library_indexed_imports WHERE job_id=? AND user_id=?',(job['id'],uid)).fetchone():
        root=job_path(uid,job['id'])/'output'
        for path in sorted(root.rglob('*')) if root.is_dir() else []:
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.gif'):continue
            relative=path.relative_to(root).as_posix()
            if d.execute('SELECT 1 FROM library_images WHERE user_id=? AND source_job_id=? AND source_asset=?',(uid,job['id'],relative)).fetchone():continue
            try:
                with Image.open(path) as image:
                    if image.format not in ('PNG','JPEG','WEBP','GIF') or image.width*image.height>24000000:continue
                    mime=Image.MIME[image.format];image.verify()
            except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):continue
            d.execute('INSERT INTO library_images(id,user_id,filename,mime,size,sha256,created_at,ref,source_job_id,source_asset,name) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,uid,path.name,mime,path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest(),job['created_at'],next_ref(d,uid),job['id'],relative,job['title']+' · '+path.name))
        d.execute('INSERT OR IGNORE INTO library_indexed_imports VALUES(?,?)',(job['id'],uid))
    return [dict(r) for r in d.execute('SELECT * FROM library_images WHERE user_id=? AND source_job_id=? ORDER BY ref',(uid,job['id']))]

def backfill(d,uid):
    for row in d.execute('SELECT id FROM library_images WHERE user_id=? AND ref IS NULL ORDER BY created_at,id',(uid,)).fetchall():d.execute('UPDATE library_images SET ref=? WHERE id=?',(next_ref(d,uid),row['id']))
    jobs=d.execute("SELECT * FROM import_jobs WHERE user_id=? AND status='completed' AND id NOT IN (SELECT job_id FROM library_indexed_imports WHERE user_id=?)",(uid,uid)).fetchall()
    for job in jobs:index_import(d,uid,dict(job))

def shorten(markdown,rows):
    for row in rows:
        for url in aliases(row):
            if url.startswith('/api/'):markdown=markdown.replace(url,'img/'+str(row['ref']))
    return markdown

def job_referenced(d,uid,id):
    prefix='/api/plugins/library/imports/'+id+'/assets/'
    if d.execute('SELECT 1 FROM library_nodes WHERE user_id=? AND instr(markdown,?)>0',(uid,prefix)).fetchone():return True
    return any(references(d,uid,dict(row)) for row in d.execute('SELECT * FROM library_images WHERE user_id=? AND source_job_id=?',(uid,id)))
