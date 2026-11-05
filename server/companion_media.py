"""Private, validated companion attachments and bounded short-video keyframes."""
import base64,hashlib,io,json,os,shutil,subprocess,tempfile,uuid
from pathlib import Path
from PIL import Image,ImageOps,UnidentifiedImageError
from fastapi import HTTPException
from . import db

ROOT=db.DATA/'companion-media';QUOTA=256*1024*1024;MAX_UPLOAD=30*1024*1024

def metadata(path):
    tool=shutil.which('ffprobe')
    if not tool:raise HTTPException(503,'服务器尚未安装媒体处理工具，请联系管理员')
    try:
        r=subprocess.run([tool,'-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=20,check=True);value=json.loads(r.stdout)
        return value,float(value.get('format',{}).get('duration',0))
    except (subprocess.SubprocessError,ValueError,TypeError):raise HTTPException(422,'无法读取音视频，请使用有效的常见音视频文件')

def picture(data):
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.width*im.height>24_000_000:raise ValueError()
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2048,2048));out=io.BytesIO();im.save(out,'JPEG',quality=90);return out.getvalue()
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):raise HTTPException(422,'图片格式无效或超过 2400 万像素')

def store(uid,id,kind,data,mime='',validate=True):
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not data or len(data)>64*1024*1024:raise HTTPException(413,'媒体文件为空或超过 64 MB')
    duration=0
    if kind=='image':data=picture(data);ext='jpg';mime='image/jpeg'
    elif kind in ('audio','video'):
        with tempfile.NamedTemporaryFile(dir=ROOT,suffix='.upload',delete=False) as f:f.write(data);temporary=Path(f.name)
        try:
            info,duration=metadata(temporary);streams=info.get('streams',[])
            if kind=='audio' and (not any(s.get('codec_type')=='audio' for s in streams) or duration<=0 or duration>180):raise HTTPException(422,'语音需有声音且不超过 3 分钟')
            if kind=='video' and (not any(s.get('codec_type')=='video' for s in streams) or duration<=0 or duration>60):raise HTTPException(422,'视频需不超过 60 秒')
            format_name=info.get('format',{}).get('format_name','')
            if 'webm' in format_name or 'matroska' in format_name:ext='webm';mime='video/webm' if kind=='video' else 'audio/webm'
            elif 'ogg' in format_name:ext='ogg';mime='audio/ogg'
            elif 'wav' in format_name:ext='wav';mime='audio/wav'
            elif 'mp3' in format_name:ext='mp3';mime='audio/mpeg'
            elif any(x in format_name for x in ('mp4','mov','m4a','3gp')):ext='mp4' if kind=='video' else 'm4a';mime='video/mp4' if kind=='video' else 'audio/mp4'
            else:raise HTTPException(422,'支持 MP4、WebM、MP3、M4A、WAV 或 OGG')
        finally:temporary.unlink(missing_ok=True)
    else:raise HTTPException(422,'附件类型无效')
    token=uuid.uuid4().hex;filename=token+'.'+ext;path=ROOT/filename
    try:
        with db.connect(True) as d:
            used=d.execute('SELECT COALESCE(SUM(size),0) FROM companion_media WHERE user_id=?',(uid,)).fetchone()[0]
            if used+len(data)>QUOTA:raise HTTPException(413,'拾光者附件空间已满（256 MB），请先清理不再需要的聊天附件')
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data)
            d.execute('INSERT INTO companion_media VALUES(?,?,?,?,?,?,?,?,?)',(token,uid,id,kind,mime,filename,len(data),duration,db.now()))
    except Exception:path.unlink(missing_ok=True);raise
    return token

def owned(d,uid,id,companion_id=None):
    row=d.execute('SELECT * FROM companion_media WHERE id=? AND user_id=?',(id,uid)).fetchone()
    if not row or companion_id and row['companion_id']!=companion_id:raise HTTPException(404,'附件不存在')
    return dict(row)

def public(row):return {k:row[k] for k in ('id','kind','mime','size','duration')}|{'url':'/api/plugins/companion/media/'+row['id']}

def data_url(row):
    path=ROOT/row['filename']
    if not path.is_file():raise HTTPException(410,'附件文件已清理')
    return 'data:'+row['mime']+';base64,'+base64.b64encode(path.read_bytes()).decode()

def frames(row):
    tool=shutil.which('ffmpeg')
    if not tool:raise HTTPException(503,'服务器尚未安装视频处理工具')
    output=[];path=ROOT/row['filename']
    for i in range(4):
        at=min(max(0,row['duration']-.05),row['duration']*i/4)
        try:
            r=subprocess.run([tool,'-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-vf','scale=1024:1024:force_original_aspect_ratio=decrease','-f','image2pipe','-vcodec','mjpeg','pipe:1'],capture_output=True,timeout=15,check=True)
            if not r.stdout or len(r.stdout)>2*1024*1024:raise ValueError()
            output.append('data:image/jpeg;base64,'+base64.b64encode(r.stdout).decode())
        except (subprocess.SubprocessError,ValueError):raise HTTPException(422,'视频关键帧读取失败')
    return output

def wav(row):
    tool=shutil.which('ffmpeg')
    if not tool:raise HTTPException(503,'服务器尚未安装音频处理工具')
    try:
        r=subprocess.run([tool,'-v','error','-i',str(ROOT/row['filename']),'-vn','-ac','1','-ar','16000','-f','wav','pipe:1'],capture_output=True,timeout=20,check=True)
        if not r.stdout or len(r.stdout)>8*1024*1024:raise ValueError()
        return r.stdout
    except (subprocess.SubprocessError,ValueError):raise HTTPException(422,'语音转换失败')
