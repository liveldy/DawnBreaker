import pytest
from fastapi import HTTPException
from server import outbound
from server.ai_endpoints import api_base,is_xai,models_url
from server.plugins import monitors,constellation
from tests.test_api import client,register,install

def test_xai_bases_and_language_models():
    for value in ['https://api.x.ai',' https://api.x.ai/v1/ ','https://api.x.ai/v1/responses','https://api.x.ai/v1/chat/completions','https://api.x.ai/v1/models']:
        assert api_base(value)=='https://api.x.ai/v1'
        assert models_url(value,True)=='https://api.x.ai/v1/language-models'
    assert api_base('https://us.api.x.ai')=='https://us.api.x.ai/v1'
    assert not is_xai('https://api.x.ai.attacker.example/v1')
    assert not is_xai('https://api.x.ai:8443/v1')
    assert models_url('https://custom.example/v1',True)=='https://custom.example/v1/models'

def test_xai_price_units_and_non_text_prices(monkeypatch):
    monkeypatch.setattr(monitors,'request_json',lambda *a,**k:{'data':[{'id':'grok-text','owned_by':'xai','prompt_text_token_price':12500,'completion_text_token_price':25000},{'id':'image','pricing':[{'quality':'hd','image_price':123}]}]})
    report=monitors.probe({'api_base':'https://api.x.ai','provider_id':'xai','protocol':'responses','billing_secret':''},'fake-test')
    assert report['models_available'] and not report['errors']
    assert report['models'][0]['input_price']==1.25 and report['models'][0]['output_price']==2.5
    assert report['models'][1]['input_price'] is None
    assert report['balance'] is None and report['spent'] is None

def test_assistant_reads_only_language_models(client,monkeypatch):
    register(client);install(client,'constellation');calls=[]
    def request(url,**kw):
        calls.append(url);return {'models':[{'id':'grok-chat','aliases':['grok-latest']}]}
    monkeypatch.setattr(constellation,'request_json',request)
    response=client.post('/api/plugins/constellation/models',json={'api_base':'https://api.x.ai/v1/responses','protocol':'responses','api_key':'fake-test'})
    assert response.status_code==200 and response.json()['models'][0]['id']=='grok-chat'
    assert calls==['https://api.x.ai/v1/language-models']

def test_official_xai_proxy_is_explicit_and_scoped(monkeypatch):
    monkeypatch.setenv('DAWN_XAI_HTTPS_PROXY','http://admin:secret@127.0.0.1:12345')
    seen=[]
    monkeypatch.setattr(outbound,'proxy_request',lambda *args:seen.append(args) or {'data':[]})
    assert outbound.request_json('https://api.x.ai/v1/models')=={'data':[]}
    assert len(seen)==1
    monkeypatch.setattr(outbound,'public_addresses',lambda *a:(_ for _ in ()).throw(HTTPException(422,'private destination')))
    for url in ['https://api.x.ai.attacker.example/models','https://api.x.ai:8443/v1/models','https://127.0.0.1/models']:
        with pytest.raises(HTTPException) as error:outbound.request_json(url)
        assert error.value.status_code==422
    assert len(seen)==1

def test_proxy_keeps_tls_redirect_and_error_boundaries(monkeypatch):
    monkeypatch.delenv('DAWN_XAI_HTTPS_PROXY',raising=False)
    monkeypatch.setattr(outbound,'public_addresses',lambda *a:(_ for _ in ()).throw(HTTPException(422,'invalid DNS')))
    seen={}
    class Response:
        status_code=302
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Client:
        def __init__(self,**kwargs):seen.update(kwargs)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,*args,**kwargs):return Response()
    monkeypatch.setattr(outbound.httpx,'Client',Client)
    with pytest.raises(HTTPException) as error:outbound.request_json('https://api.x.ai/v1/models')
    # Without explicit configuration, no environment proxy is implicitly trusted.
    monkeypatch.setenv('DAWN_XAI_HTTPS_PROXY','http://admin:private@127.0.0.1:12345')
    with pytest.raises(HTTPException) as error:outbound.request_json('https://api.x.ai/v1/models')
    assert error.value.status_code==502 and 'private' not in error.value.detail
    assert seen['trust_env'] is False and seen['follow_redirects'] is False and 'verify' not in seen
