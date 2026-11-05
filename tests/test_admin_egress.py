import base64,json,time
import pytest
from fastapi import HTTPException
from tests.test_api import client,register
from server import db,secret_store,xai_egress as manager
from server.egress_nodes import subscription_nodes

def prepare(client,monkeypatch,tmp_path):
    uid=register(client)
    assert client.get('/api/admin/xai-egress').status_code==403
    assert client.post('/api/admin/xai-egress/enabled',json={'enabled':False}).status_code==403
    with db.connect(True) as d:d.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
    monkeypatch.setattr(secret_store,'DATA',tmp_path)
    monkeypatch.setattr(manager,'ROOT',tmp_path/'egress');manager.ROOT.mkdir()
    manager.atomic(manager.ROOT/'connection.json',{'username':'test-user','password':'controller-private','mixed_port':12345,'controller_port':12346,'controller_secret':'private-secret','core':'/unused/core'})
    uri='ss://'+base64.urlsafe_b64encode(b'aes-128-gcm:private-node-password').decode()+'@node.example:443#Fixed-US'
    monkeypatch.setattr(manager,'fetch_subscription',lambda url:uri.encode())
    return uid

def test_admin_stages_subscription_without_switching_and_hides_secrets(client,monkeypatch,tmp_path):
    prepare(client,monkeypatch,tmp_path)
    response=client.post('/api/admin/xai-egress/subscription',json={'url':'https://provider.example/token/private-subscription'})
    assert response.status_code==200
    value=response.json();assert not value['enabled'] and value['active'] is None and len(value['nodes'])==1
    assert 'private-subscription' not in response.text and 'private-node-password' not in response.text
    with db.connect() as d:
        assert 'private-node-password' not in d.execute('SELECT value FROM settings WHERE key=?',(manager.KEY,)).fetchone()[0]
        assert 'private-subscription' not in d.execute('SELECT after_json FROM audit').fetchone()[0]
    assert not (manager.ROOT/'runtime.json').exists()
    selected={'node_id':value['nodes'][0]['id'],'revision':value['revision']}
    assert client.post('/api/admin/xai-egress/apply',json=selected).status_code==409

def test_apply_requires_fresh_test_and_refresh_preserves_current_exit(client,monkeypatch,tmp_path):
    uid=prepare(client,monkeypatch,tmp_path);value=client.post('/api/admin/xai-egress/subscription',json={'url':'https://provider.example/sub'}).json();node=value['nodes'][0]
    current=manager.stored();current['test']={'ok':True,'node_id':node['id'],'revision':value['revision'],'epoch':time.time(),'exit_ip':'8.8.8.8','region':'US'};manager.save(current,uid,'seed test')
    reloads=[];monkeypatch.setattr(manager,'reload_core',lambda config,c:reloads.append(config))
    selected={'node_id':node['id'],'revision':value['revision']};r=client.post('/api/admin/xai-egress/apply',json=selected)
    assert r.status_code==200 and r.json()['enabled'];assert manager.configured_proxy().startswith('http://test-user:')
    assert len(reloads[0]['proxies'])==1 and reloads[0]['rules']==['MATCH,xai-fixed']
    assert 'proxy-groups' not in reloads[0] and reloads[0]['allow-lan'] is False
    active=r.json()['active'];r=client.post('/api/admin/xai-egress/subscription',json={});assert r.status_code==200 and r.json()['active']==active and r.json()['enabled']
    assert len(reloads)==1 and client.post('/api/admin/xai-egress/apply',json=selected).status_code==409
    monkeypatch.setattr(manager,'health',lambda proxy:{'ok':True,'exit_ip':'1.1.1.1','epoch':time.time()})
    r=client.post('/api/admin/xai-egress/test-current');assert r.json()['last_test']['ip_changed'] and r.json()['active']==active and len(reloads)==1
    assert client.post('/api/admin/xai-egress/enabled',json={'enabled':False}).status_code==200
    with pytest.raises(HTTPException) as error:manager.configured_proxy()
    assert error.value.status_code==503

def test_parser_does_not_import_subscription_listeners_or_yaml_aliases():
    data={'mixed-port':9999,'allow-lan':True,'tun':{'enable':True},'external-controller':'0.0.0.0:1','proxies':[{'name':'Node','type':'ss','server':'example.com','port':443,'cipher':'aes-128-gcm','password':'secret','dialer-proxy':'unsafe-group'}]}
    parsed=subscription_nodes(json.dumps(data).encode());assert len(parsed)==1
    assert 'dialer-proxy' not in parsed[0]['config'] and 'tun' not in parsed[0]['config']
    with pytest.raises(ValueError):subscription_nodes(b'proxies: &nodes\n  - *nodes')
    raw=base64.urlsafe_b64encode(b'ss://YWVzLTEyOC1nY206c2VjcmV0@example.com:443#US')
    assert subscription_nodes(raw)[0]['name']=='US'
    data['proxies'][0].update(plugin='gost-plugin',**{'plugin-opts':{'mode':'websocket','host':'edge.example','path':'/tunnel'}})
    parsed=subscription_nodes(json.dumps(data).encode())
    assert parsed[0]['config']['plugin']=='gost-plugin' and parsed[0]['config']['plugin-opts']['path']=='/tunnel'

def test_failed_reload_keeps_active_runtime_and_does_not_apply_stale_test(client,monkeypatch,tmp_path):
    uid=prepare(client,monkeypatch,tmp_path);value=client.post('/api/admin/xai-egress/subscription',json={'url':'https://provider.example/sub'}).json();node=value['nodes'][0]
    current=manager.stored();current['test']={'ok':True,'node_id':node['id'],'revision':value['revision'],'epoch':time.time()-601};manager.save(current,uid,'test')
    selected={'node_id':node['id'],'revision':value['revision']};assert client.post('/api/admin/xai-egress/apply',json=selected).status_code==409
    current['test']['epoch']=time.time();manager.save(current,uid,'test')
    monkeypatch.setattr(manager,'reload_core',lambda *a:(_ for _ in ()).throw(HTTPException(502,'unavailable')))
    assert client.post('/api/admin/xai-egress/apply',json=selected).status_code==502
    assert not manager.stored().get('enabled') and not (manager.ROOT/'runtime.json').exists()
