"""Adapt Pandoc's DOCX reader and LibreOffice's legacy DOC reader to library imports.

No hand-written Word/OMML parser: semantic conversion and LaTeX are upstream tools' work.
"""
import json,os,re,shutil,signal,subprocess,sys,zipfile
from pathlib import Path
from urllib.parse import unquote
from PIL import Image

class ConversionError(RuntimeError):pass

def binary(name,env):
    requested=os.environ.get(env) or name;value=shutil.which(requested) or requested
    if os.name=='nt' and not Path(value).is_file() and Path(value+'.exe').is_file():value+='.exe'
    if not value or not Path(value).is_file():raise ConversionError('Word 转换引擎尚未就绪，请安装 Pandoc 和 LibreOffice 后重试。')
    return value

def run(args,work,timeout=60,input=None):
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    process=subprocess.Popen(args,cwd=work,stdin=subprocess.PIPE if input else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**flags)
    try:out,err=process.communicate(input,timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name=='nt':process.kill()
        else:os.killpg(process.pid,signal.SIGKILL)
        process.communicate();raise ConversionError('Word 转换超时，请拆分文档后重试。')
    if process.returncode:raise ConversionError('Word 转换未完成，请检查文档是否完整、未加密。')
    if len(out)>24*1024*1024:raise ConversionError('Word 文档内容过多，请拆分后导入。')
    return out

def validate_docx(source):
    try:
        with zipfile.ZipFile(source) as z:
            items=z.infolist();names={i.filename for i in items}
            if len(items)>10000 or sum(i.file_size for i in items)>80*1024*1024 or 'word/document.xml' not in names or '[Content_Types].xml' not in names:raise ValueError()
            if any(i.flag_bits&1 or Path(i.filename).is_absolute() or '..' in Path(i.filename.replace('\\','/')).parts for i in items):raise ValueError()
    except (zipfile.BadZipFile,ValueError,OSError):raise ConversionError('DOCX 文件无效、已加密或解压后过大，请检查文件或拆分后导入。')

def convert(source,result):
    source=Path(source).resolve();result=Path(result).resolve();work=result.parent
    if source.parent!=work or source.suffix.lower() not in ('.doc','.docx'):raise ConversionError('Word 导入路径无效。')
    pandoc=binary('pandoc','DAWN_PANDOC');temporary=work/'word-temporary';output=work/'output';warnings=[]
    temporary.mkdir(exist_ok=True);output.mkdir(exist_ok=True)
    try:
        if source.suffix.lower()=='.doc':
            header=source.read_bytes()[:8]
            if header!=bytes.fromhex('D0CF11E0A1B11AE1') and not header.startswith(b'{\\rtf'):raise ConversionError('DOC 文件格式无效，请使用真实 Word 文档。')
            office=binary('libreoffice','DAWN_LIBREOFFICE');profile=temporary/'profile';profile.mkdir(exist_ok=True)
            # Untrusted imports never enable macros or update linked document content.
            (profile/'user').mkdir(exist_ok=True)
            (profile/'user/registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item><item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item></oor:items>''','utf8')
            run([office,'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault','--nofirststartwizard','--convert-to','docx:Office Open XML Text','--outdir',str(temporary),str(source)],work,90)
            source=temporary/(source.stem+'.docx')
            if not source.is_file():raise ConversionError('DOC 无法转换，请确认文档完整且未设置打开密码。')
        validate_docx(source)
        # The sandbox disables external file/network access in Pandoc readers/writers.
        tree=json.loads(run([pandoc,'--sandbox','--from=docx','--to=json','--extract-media=output',str(source)],work))
        title=tree.get('meta',{}).get('title',{})
        if title.get('t')=='MetaInlines' and title.get('c'):
            for block in tree['blocks']:
                if block.get('t')=='Header':block['c'][0]=min(6,block['c'][0]+1)
            tree['blocks'].insert(0,{'t':'Header','c':[1,['',[],[]],title['c']]})
        display_math=[]
        def walk(value):
            if isinstance(value,list):return [walk(v) for v in value]
            if not isinstance(value,dict):return value
            if value.get('t')=='Math' and value['c'][0].get('t')=='DisplayMath':display_math.append(value['c'][1])
            if value.get('t')=='Image':
                target=value['c'][-1][0];asset=(work/unquote(target)).resolve()
                try:
                    if not asset.is_relative_to(output) or asset.is_symlink() or not asset.is_file():raise ValueError()
                    with Image.open(asset) as image:
                        if image.width*image.height>24000000:raise ValueError()
                        image.verify();fmt=image.format
                    if fmt not in ('PNG','JPEG','WEBP','GIF'):raise ValueError()
                    if fmt=='GIF':
                        converted=asset.with_suffix('.png')
                        with Image.open(asset) as image:image.convert('RGBA').save(converted,'PNG')
                        asset=converted
                    value['c'][-1][0]='/api/plugins/library/imports/'+work.name+'/assets/'+asset.relative_to(output).as_posix()
                    value['c'][0]=['',[],[]]  # Word layout dimensions must not turn an image into raw HTML.
                    return value
                except (OSError,ValueError,Image.DecompressionBombError):
                    warnings.append('部分图片格式无法直接显示，正文与可转换公式已保留。')
                    return {'t':'Str','c':'[图片未能转换]'}
            return {k:walk(v) for k,v in value.items()}
        tree=walk(tree)
        markdown=run([pandoc,'--sandbox','--from=json','--to=markdown_strict+pipe_tables+tex_math_dollars+strikeout+footnotes-raw_html','--markdown-headings=atx','--wrap=none'],work,input=json.dumps(tree,ensure_ascii=False).encode()).decode('utf8').replace('\r\n','\n')
        for expression in set(display_math):
            markdown=re.sub(r'(?m)^\$\$'+re.escape(expression)+r'\$\$$',lambda _: '$$\n'+expression+'\n$$',markdown)
        if not markdown.strip():raise ConversionError('Word 文档没有可读取的内容。')
        if len(markdown)>1000000:raise ConversionError('Word 文档内容过长，请拆分后导入。')
        result.write_text(json.dumps({'markdown':markdown,'warnings':list(dict.fromkeys(warnings))},ensure_ascii=False),'utf8')
    finally:
        if temporary.is_dir() and temporary.resolve().is_relative_to(work) and not temporary.is_symlink():shutil.rmtree(temporary)

if __name__=='__main__':
    try:convert(sys.argv[1],sys.argv[2])
    except ConversionError as error:print(str(error),file=sys.stderr);sys.exit(2)
