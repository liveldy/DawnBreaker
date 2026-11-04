"""Exercise a second, synthetic content pack to prevent League-only rendering/data rules."""
from server.collection_catalog import tree_for
from tests.test_api import client,register,install
from server import db
from server.core import credit

def test_unique_counts_for_multi_series_membership():
    spec={'id':'sample','name':'样例卡册','kind':'album','children':[{'id':'world','name':'宇宙','kind':'universe','children':[{'id':'a','name':'甲','kind':'series'},{'id':'b','name':'乙','kind':'series'}]}]}
    cards=[{'id':'one','image':'/one.webp','series_ids':['a','b']},{'id':'two','image':'/two.webp','series_ids':['b']}]
    result=tree_for(spec,cards,{'one':3})
    assert result['total']==2 and result['owned']==1
    assert result['children'][0]['total']==2
    assert [s['total'] for s in result['children'][0]['children']]==[1,2]

def test_second_pack_isolation_entitlements_and_draw_replay(client,monkeypatch):
    from server.plugins import collection
    # Existing catalog installation is reused as a separately entitled synthetic content provider.
    uid=register(client);install(client,'collection','lol','vocabulary','kaoyan')
    spec={'id':'new-world','name':'另一卡册','kind':'album','content_plugin':'kaoyan','children':[{'id':'new-universe','name':'另一宇宙','kind':'universe','children':[{'id':'new-series','name':'另一系列','kind':'series'}]}],'pack':{'title':'另一卡包','cost':3,'probabilities':{'R':100}}}
    card={'id':'new-world-card','name':'新卡片','image':'/api/plugins/collection/image/new-world-card','rarity':'R','album_id':'new-world','series_ids':['new-series']}
    monkeypatch.setattr(collection,'ALBUMS',collection.ALBUMS|{'albums':collection.ALBUMS['albums']+[spec]})
    monkeypatch.setattr(collection,'CONFIG',collection.CONFIG|{'cards':collection.CONFIG['cards']+[card]})
    data=client.get('/api/plugins/collection').json()
    new=next(a for a in data['albums'] if a['id']=='new-world')
    assert new['children'][0]['children'][0]['card_ids']==['new-world-card']
    with db.connect(True) as conn:credit(conn,uid,'essence',30,'测试','new-pack-seed')
    body={'count':10,'pack_id':'new-world','request_id':'cross-pack-request'}
    response=client.post('/api/plugins/collection/draw',json=body)
    assert response.status_code==200,response.text
    assert {c['id'] for c in response.json()['cards']}=={'new-world-card'}
    assert sum(c['new'] for c in response.json()['cards'])==1
    assert client.post('/api/plugins/collection/draw',json=body).json()==response.json()
    assert client.post('/api/plugins/collection/draw',json=body|{'pack_id':'lol'}).status_code==409
    assert response.json()['refund']==45
    assert client.get('/api/bootstrap').json()['wallet']['essence']==45
    assert next(c for c in client.get('/api/plugins/collection').json()['cards'] if c['id']==card['id'])['owned']==1
    assert client.delete('/api/catalog/kaoyan').status_code==200
    data=client.get('/api/plugins/collection').json()
    assert all(a['id']!='new-world' for a in data['albums']) and all(c['id']!='new-world-card' for c in data['history'])
