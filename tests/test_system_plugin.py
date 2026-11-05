from tests.test_api import client,register,install
def test_system_metadata_is_local_and_requires_installation(client):
    register(client)
    assert client.get('/api/plugins/system').status_code==403
    plugin=next(p for p in client.get('/api/catalog').json()['plugins'] if p['id']=='system')
    assert plugin['platforms']==['desktop','mobile'] and plugin['type']=='standard'
    install(client,'system')
    assert client.get('/api/plugins/system').json()=={'local_only':True,'platforms':['desktop','mobile']}
