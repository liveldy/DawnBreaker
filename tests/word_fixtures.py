"""Small synthetic Word fixtures produced with the established python-docx library."""
import io
from docx import Document
from docx.oxml import parse_xml
from PIL import Image

def word_file():
    doc=Document();doc.add_heading('公式笔记',0);doc.add_heading('能量与分数',1);doc.add_paragraph('中文正文，粗体与列表。').add_run('重点').bold=True
    doc.add_paragraph('第一项',style='List Bullet')
    table=doc.add_table(rows=2,cols=2);table.cell(0,0).text='名称';table.cell(0,1).text='数值';table.cell(1,0).text='能量';table.cell(1,1).text='42'
    para=doc.add_paragraph('行内公式：');para._p.append(parse_xml('''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>E=mc</m:t></m:r><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath>'''))
    para=doc.add_paragraph();para._p.append(parse_xml('''<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:oMath><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath></m:oMathPara>'''))
    image=io.BytesIO();Image.new('RGB',(160,100),'#dbe9e4').save(image,'PNG');image.seek(0);doc.add_picture(image)
    data=io.BytesIO();doc.save(data);return data.getvalue()
