"""Isolated, free CPU OCR. Preserve equations as LaTeX, never execute document content."""
import os,sys,json
from pathlib import Path
input_file=Path(sys.argv[1]).resolve();result_file=Path(sys.argv[2]).resolve();mode=sys.argv[3]
cache=Path(os.environ.get('DAWN_DATA_DIR','/var/lib/dawnbreaker'))/'model-cache'
for name,folder in {'PIX2TEXT_HOME':'pix2text','CNOCR_HOME':'cnocr','CNSTD_HOME':'cnstd','HF_HOME':'huggingface','TORCH_HOME':'torch','XDG_CACHE_HOME':'xdg','MPLCONFIGDIR':'matplotlib','YOLO_CONFIG_DIR':'yolo'}.items():
    path=cache/folder;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
os.environ['OMP_NUM_THREADS']='4';os.environ['OPENBLAS_NUM_THREADS']='4';os.environ['TOKENIZERS_PARALLELISM']='false';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from PIL import Image
import fitz
from pix2text import Pix2Text
output=result_file.parent/'output';output.mkdir(exist_ok=True)
os.chdir(result_file.parent)
p2t=Pix2Text.from_config(enable_table=False,device='cpu')
def recognize(image,page):
    image.thumbnail((2400,3200))
    if mode=='formula':return '$$\n'+p2t.recognize_formula(image)+'\n$$'
    if mode=='auto':return p2t.recognize_text_formula(image,return_text=True)
    root='/api/plugins/library/imports/'+input_file.parent.name+'/assets/page-'+str(page)
    return p2t.recognize_page(image,page_number=page,title_contain_formula=True,text_contain_formula=True).to_markdown(output/('page-'+str(page)),root_url=root)
if input_file.suffix.lower()=='.pdf':
    parts=[]
    with fitz.open(input_file) as pdf:
        if pdf.is_encrypted or len(pdf)>30:raise ValueError('PDF must be unencrypted and at most 30 pages')
        for page in pdf:
            pix=page.get_pixmap(dpi=150,alpha=False);image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
            parts.append('## 第 '+str(page.number+1)+' 页\n\n'+recognize(image,page.number))
    markdown='\n\n'.join(parts)
else:
    with Image.open(input_file) as image:
        if image.width*image.height>24000000:raise ValueError('Image too large')
        markdown=recognize(image.convert('RGB'),0)
result_file.write_text(json.dumps({'markdown':markdown},ensure_ascii=False),encoding='utf-8')
