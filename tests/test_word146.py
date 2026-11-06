import json,os,shutil,subprocess,zipfile,io,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
from tests.test_api import client,register,install
from tests.word_fixtures import word_file
from server import db,word_worker
from server.plugins import library

@pytest.fixture
def converter(monkeypatch):
    executable=os.environ.get('DAWN_PANDOC') or shutil.which('pandoc')
    if not executable:
        try:
            import pypandoc
            executable=pypandoc.get_pandoc_path()
        except (ImportError,OSError):pytest.skip('Install Pandoc for actual Word conversion tests')
    monkeypatch.setenv('DAWN_PANDOC',executable)
    return executable

def test_docx_structure_tables_images_and_omml_become_markdown_latex(tmp_path,converter):
    work=tmp_path/('a'*32);work.mkdir();source=work/'source.docx';source.write_bytes(word_file());result=work/'result.json'
    word_worker.convert(source,result);data=json.loads(result.read_text('utf8'));text=data['markdown']
    assert '# 公式笔记' in text and '能量与分数' in text and '中文正文' in text and '**重点**' in text
    assert '名称' in text and '| 能量' in text and '42' in text
    assert 'x^{2}' in text and '$$\n'+r'\frac{a}{b}'+'\n$$' in text
    assert '/api/plugins/library/imports/'+'a'*32+'/assets/media/' in text
    assert list((work/'output/media').glob('*.png')) and not (work/'word-temporary').exists()
    assert data['warnings']==[]

def test_legacy_doc_uses_libreoffice_then_same_reader(tmp_path,converter):
    office=os.environ.get('DAWN_LIBREOFFICE') or shutil.which('libreoffice')
    if not office:pytest.skip('Install LibreOffice to test real legacy DOC conversion')
    work=tmp_path/('b'*32);work.mkdir();docx=work/'fixture.docx';docx.write_bytes(word_file())
    word_worker.run([office,'-env:UserInstallation='+(work/'fixture-profile').as_uri(),'--headless','--convert-to','doc:MS Word 97','--outdir',str(work),str(docx)],work,90)
    source=work/'fixture.doc';assert source.is_file();result=work/'result.json';word_worker.convert(source,result)
    text=json.loads(result.read_text('utf8'))['markdown'];assert '中文正文' in text and '名称' in text and '42' in text and r'\frac{a}{b}' in text

def test_invalid_or_oversized_archive_is_not_read_as_a_document(tmp_path):
    invalid=tmp_path/'source.docx';invalid.write_text('not Word')
    with pytest.raises(word_worker.ConversionError):word_worker.validate_docx(invalid)
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('[Content_Types].xml','');z.writestr('word/document.xml','');z.writestr('../escape','bad')
    invalid.write_bytes(data.getvalue())
    with pytest.raises(word_worker.ConversionError):word_worker.validate_docx(invalid)

def test_linked_images_cannot_fetch_network_resources(tmp_path,converter):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):requests.append(self.path);self.send_error(404)
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    work=tmp_path/('c'*32);work.mkdir();source=work/'source.docx'
    try:
        with zipfile.ZipFile(io.BytesIO(word_file())) as z,zipfile.ZipFile(source,'w') as out:
            for item in z.infolist():
                data=z.read(item)
                if item.filename=='word/_rels/document.xml.rels':data=data.replace(b'Target="media/image1.png"',('Target="http://127.0.0.1:'+str(server.server_port)+'/private.png" TargetMode="External"').encode())
                out.writestr(item,data)
        try:word_worker.convert(source,work/'result.json')
        except word_worker.ConversionError:pass
        assert requests==[]
    finally:server.shutdown();server.server_close();worker.join(2)

def test_library_queued_import_assets_and_user_isolation(client,monkeypatch,tmp_path,converter):
    monkeypatch.setattr(library,'IMPORTS',tmp_path/'imports');monkeypatch.setattr(library.POOL,'submit',lambda *a:None)
    uid=register(client);install(client,'library');upload=client.post('/api/plugins/library/imports',files={'file':('课程笔记.docx',word_file(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert upload.status_code==202;id=upload.json()['id'];library.run_import(uid,id)
    data=client.get('/api/plugins/library').json();job=next(j for j in data['imports'] if j['id']==id);assert job['status']=='completed',job
    doc=client.get('/api/plugins/library/nodes/'+job['document_id']).json();assert r'\frac{a}{b}' in doc['markdown']
    asset='/api/plugins/library/imports/'+id+'/assets/media/image1.png';assert client.get(asset).status_code==200
    assert client.delete('/api/plugins/library/imports/'+id).status_code==200 and client.get(asset).status_code==200
    client.post('/api/auth/logout');register(client,'other_word');install(client,'library');assert client.get(asset).status_code==404
