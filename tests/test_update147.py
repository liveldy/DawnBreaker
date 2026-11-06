import io,json,threading
from datetime import datetime,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from PIL import Image
import pytest
from fastapi import HTTPException
from tests.test_api import client,register,install
from server import db,outbound,secret_store
from server.plugins import library,atlas,monitors,constellation

def png():
    b=io.BytesIO();Image.new('RGB',(80,50),'teal').save(b,format='PNG');return b.getvalue()

def test_imported_images_backfill_short_refs_and_cleanup(client,monkeypatch,tmp_path):
    from server import library_storage
    monkeypatch.setattr(library_storage,'DATA',tmp_path)
    monkeypatch.setattr(library,'IMPORTS',tmp_path/'library-imports');monkeypatch.setattr(library,'IMAGES',tmp_path/'images')
    uid=register(client);install(client,'library');job='a'*32;work=library.job_path(uid,job);output=work/'output/media';output.mkdir(parents=True);(output/'image1.png').write_bytes(png())
    legacy='/api/plugins/library/imports/'+job+'/assets/media/image1.png'
    with db.connect(True) as d:
        doc=library.create_document(d,uid,None,'旧文档','![]('+legacy+')',job)
        d.execute("INSERT INTO import_jobs(id,user_id,title,filename,mode,status,document_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(job,uid,'导入书籍','source.docx','auto','completed',doc['id'],db.now(),db.now()))
    images=client.get('/api/plugins/library/images').json()['images'];assert len(images)==1
    image=images[0];assert image['reference']=='img/1' and image['references']==1 and image['source']=='import'
    assert client.get('/api/plugins/library/images/ref/1').content==png()
    assert client.get(image['url']).headers['content-type']=='image/png'
    path='/api/plugins/library/nodes/'+doc['id'];body={'title':'短路径','markdown':'![图](img/1)','revision':1,'parent_id':None}
    assert client.put(path,json=body).status_code==200
    assert client.delete('/api/plugins/library/images/'+image['id']).status_code==409
    assert client.delete('/api/plugins/library/imports/'+job).status_code==200 and client.get(legacy).status_code==200
    with db.connect() as d:
        from server.library_storage import usage
        info=usage(d,uid);assert info['imports_bytes']==len(png()) and info['images_bytes']==0
    assert client.delete(path).status_code==200
    assert client.get('/api/plugins/library/images').json()['images']==[]
    upload=client.post('/api/plugins/library/images',files={'file':('second.png',png(),'image/png')});assert upload.status_code==201,upload.text
    assert upload.json()['reference']=='img/2'

def test_image_alias_boundaries_and_account_isolation(client,monkeypatch,tmp_path):
    monkeypatch.setattr(library,'IMAGES',tmp_path/'images')
    uid=register(client);install(client,'library');one=client.post('/api/plugins/library/images',files={'file':('x.png',png(),'image/png')}).json()
    with db.connect(True) as d:
        library.create_document(d,uid,None,'不同引用','![](img/10)')
    assert client.get('/api/plugins/library/images').json()['images'][0]['references']==0
    client.post('/api/auth/logout');register(client,'image147other');install(client,'library')
    assert client.get(one['url']).status_code==404 and client.get('/api/plugins/library/images/ref/1').status_code==404

def test_daily_atlas_once_after_restart_and_failure_preserves_snapshot(monkeypatch,tmp_path):
    monkeypatch.setattr(atlas,'CACHE',tmp_path/'daily/live.json');calls=[]
    def fetch(index):
        calls.append(index)
        return {'general':{'models':[{'model_id':'a'}]}} if index==0 else [{'model_id':'a'}] if index==1 else {'data':[]}
    monkeypatch.setattr(atlas,'fetch_source',fetch);moment=datetime(2026,11,6,4,0,tzinfo=atlas.ZONE)
    monkeypatch.setattr(atlas.time,'time',lambda:moment.timestamp())
    assert atlas.slot(moment-timedelta(seconds=1)).date().isoformat()=='2026-11-05'
    assert atlas.update_daily(moment) and sorted(calls)==[0,1,2]
    snapshot=atlas.CACHE.read_bytes();calls.clear();assert not atlas.update_daily(moment+timedelta(hours=5)) and not calls
    # Replacing the process-local lock cannot reset the durable day marker.
    monkeypatch.setattr(atlas,'LOCK',threading.Lock());assert not atlas.update_daily(moment)
    def fail(index):calls.append(index);raise OSError()
    monkeypatch.setattr(atlas,'fetch_source',fail)
    assert not atlas.update_daily(moment+timedelta(days=1)) and atlas.CACHE.read_bytes()==snapshot
    assert atlas.read_state()['error'] and len(calls)==3
    assert not atlas.update_daily(moment+timedelta(days=1,hours=1)) and len(calls)==3

def test_custom_assistant_and_monitor_optional_key_model(client,monkeypatch,tmp_path):
    monkeypatch.setattr(secret_store,'DATA',tmp_path)
    register(client);install(client,'constellation','atlas');calls=[]
    body={'family':'custom','api_base':'http://api.example.org:50924/v1','protocol':'openai'}
    a=client.post('/api/plugins/constellation/assistants',json=body);assert a.status_code==201,a.text
    assert a.json()['name']=='自定义助手' and not a.json()['has_key'] and not a.json()['model']
    def request(url,body=None,headers=None,**kwargs):
        calls.append((url,body,headers,kwargs));return {'data':[{'id':'test'}]} if url.endswith('/models') else {'choices':[{'message':{'content':'hello','tool_calls':None}}]}
    monkeypatch.setattr(constellation,'request_json',request)
    r=client.post('/api/plugins/constellation/models',json=body);assert r.json()['models'][0]['id']=='test'
    config=constellation.Config(**body).model_dump();assert constellation.invoke(config,'',[{'role':'user','content':'hi'}],'test')=='hello'
    assert all('Authorization' not in c[2] and c[3]['allow_http'] for c in calls)
    assert 'model' not in calls[-1][1]
    monkeypatch.setattr(monitors,'request_json',request)
    r=client.post('/api/plugins/atlas/monitors',json={'api_base':body['api_base'],'protocol':'openai'});assert r.status_code==201,r.text
    m=r.json();r=client.post('/api/plugins/atlas/monitors/'+m['id']+'/refresh');assert r.status_code==200,r.text
    assert r.json()['report']['models_available'] and not r.json()['has_key']
    for url in ['http://127.0.0.1','http://10.1.2.3','http://user:secret@api.example.org']:
        assert client.post('/api/plugins/atlas/monitors',json={'api_base':url}).status_code==422
    assert client.post('/api/plugins/constellation/assistants',json=body|{'family':'gpt'}).status_code==422

def test_custom_http_transport_and_dns_guard(monkeypatch):
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(dict(self.headers));self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"data":[]}')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with pytest.raises(HTTPException):outbound.endpoint('http://api.example.org/v1')
        with pytest.raises(HTTPException):outbound.public_addresses('localhost',80)
        monkeypatch.setattr(outbound,'public_addresses',lambda *args:['127.0.0.1'])
        assert outbound.request_json('http://api.example.org:'+str(server.server_port)+'/v1/models',allow_http=True)=={'data':[]}
        assert 'Authorization' not in seen[0]
    finally:server.shutdown();server.server_close();thread.join(2)

def test_etag_gzip_and_permissions_precede_conditional_response(client,monkeypatch,tmp_path):
    register(client);install(client,'atlas');monkeypatch.setattr(atlas,'CACHE',tmp_path/'live.json')
    atlas.atomic(atlas.CACHE,{'fetched_at':db.now(),'epoch':datetime.now(atlas.ZONE).timestamp(),'metadata':[{'model_id':'long-model-'+str(i)} for i in range(100)]})
    r=client.get('/api/plugins/atlas/live',headers={'Accept-Encoding':'gzip'})
    assert r.status_code==200 and r.headers['content-encoding']=='gzip' and 'Cookie' in r.headers['vary']
    etag=r.headers['etag'];assert client.get('/api/plugins/atlas/live',headers={'If-None-Match':etag}).status_code==304
    client.post('/api/auth/logout');register(client,'conditional147other')
    assert client.get('/api/plugins/atlas/live',headers={'If-None-Match':etag}).status_code==403

def test_xai_management_contract_and_separate_copy_key(client,monkeypatch,tmp_path):
    monkeypatch.setattr(secret_store,'DATA',tmp_path);register(client);install(client,'atlas');calls=[]
    def request(url,body=None,headers=None,**kwargs):
        calls.append((url,body,headers))
        if 'management-api.x.ai' not in url:
            assert headers['Authorization']=='Bearer inference-test';return {'data':[{'id':'grok-test'}]}
        assert headers['Authorization']=='Bearer management-test'
        if url.endswith('/prepaid/balance'):return {'total':{'val':'-2317'}}
        analytics=body['analyticsRequest'];assert analytics['timeRange']['timezone']=='Etc/GMT'
        if analytics['groupBy']:return {'timeSeries':[{'group':['Prompt text tokens'],'dataPoints':[{'values':[12]}]},{'group':['Completion text tokens'],'dataPoints':[{'values':[3]}]},{'group':['Audio seconds'],'dataPoints':[{'values':[99]}]}]}
        assert [v['name'] for v in analytics['values']]==['usd','transactions']
        return {'timeSeries':[{'dataPoints':[{'values':[1.25,4]}]}]}
    monkeypatch.setattr(monitors,'request_json',request)
    r=client.post('/api/plugins/atlas/monitors',json={'provider_id':'xai','api_base':'https://api.x.ai/v1','api_key':'inference-test','billing_key':'management-test','management_id':'team-uuid'});assert r.status_code==201,r.text
    path='/api/plugins/atlas/monitors/'+r.json()['id'];r=client.post(path+'/refresh');report=r.json()['report'];assert not report['errors']
    assert report['balance']==23.17 and report['spent']==1.25 and report['requests']==4 and report['tokens']==15
    assert client.post(path+'/key').json()=={'key':'inference-test'}
    assert 'management-test' not in r.text
    from server.ai_endpoints import is_xai_service
    assert is_xai_service('https://management-api.x.ai/v1/billing')
    assert not is_xai_service('https://management-api.x.ai.evil.example')

def test_xai_truncated_analytics_does_not_show_partial_totals(monkeypatch):
    from server.xai_statistics import statistics
    def request(url,**kwargs):return {'total':{'val':'-1000'}} if url.endswith('balance') else {'limitReached':True,'timeSeries':[]}
    report={'errors':[]};statistics('team','admin',request,report)
    assert report['balance']==10 and 'spent' not in report and 'tokens' not in report and len(report['errors'])==2

def test_kimi_admin_units_scope_and_cached_tokens(monkeypatch):
    calls=[]
    def request(url,**kwargs):
        calls.append((url,kwargs))
        if url.endswith('/users/me/balance'):return {'data':{'available_balance':2}}
        if url.endswith('/account'):return {'available_balance':150000,'total_consume':250000}
        assert kwargs['params']['start']>10**12 and kwargs['headers']['Authorization']=='Bearer admin-test'
        return {'data':[{'request_count':3,'prompt_tokens':10,'cached_tokens':8,'completion_tokens':2,'cache_write_5m_tokens':4}],'has_more':False}
    monkeypatch.setattr(monitors,'request_json',request)
    report={'errors':[]};monitors.provider_statistics({'provider_id':'moonshot','api_base':'https://api.moonshot.ai/v1','protocol':'openai','billing_secret':secret_store.seal('admin-test')},'inference',report)
    assert not report['errors'] and report['balance']==1.5 and report['spent']==2.5 and report['tokens']==16 and report['requests']==3
