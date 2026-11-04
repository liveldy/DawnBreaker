from pathlib import Path
import pytest
from PIL import Image
from tests.test_api import client,register,install
from server import db
from server.core import credit,state,set_state
from server.plugins import collection

@pytest.mark.skipif(not any(a['id']=='sgs' for a in collection.ALBUMS['albums']),reason='Optional SGS media pack not imported')
def test_imported_sgs_complete_catalog_art_and_draw(client):
    uid=register(client);install(client,'collection')
    assert not client.get('/api/plugins/collection').json()['albums']
    install(client,'sgs','journal')
    data=client.get('/api/plugins/collection').json();album=data['albums'][0]
    assert album['id']=='sgs' and album['name']=='三国杀'
    assert album['total']==len(data['cards'])==2123
    assert {c['rarity'] for c in data['cards']}=={'R','SR'}
    assert set(data['packs'][0]['probabilities'])=={'R','SR'}
    assert sum(data['packs'][0]['probabilities'].values())==100
    worlds={n['name']:n for n in album['children']}
    assert set(worlds)=={'界限突破','一将成名','限定专属','威系列','谋定天下','星河璀璨','群英荟萃','皮肤珍藏'}
    assert {n['name'] for n in worlds['界限突破']['children']}=={'标准','一将成名','星火燎原'}
    cards={c['id']:c for c in data['cards']};members=set()
    for world in album['children']:
        assert world['kind']=='universe'
        for series in world['children']:
            assert series['kind']=='series' and series['total']>0
            members.update(series['card_ids'])
    assert members==set(cards)
    for card in cards.values():
        with Image.open(collection.ROOT/'cards'/(card['id']+'.webp')) as image:assert image.size==(360,540)
        assert (collection.ROOT/'splashes'/(card['id']+'.webp')).is_file()
        assert card['character_name'] and card['source_url'].startswith('https://wiki.biligame.com/sgs/')
    sample=next(c for c in cards.values() if c['rarity']=='SR')
    assert client.get(sample['image']).status_code==200
    assert client.get(sample['splash']).status_code==200
    with db.connect(True) as d:credit(d,uid,'essence',1000,'验证','sgs-draw-seed')
    request={'pack_id':'sgs','count':10,'request_id':'sgs-ten-real-pool'}
    first=client.post('/api/plugins/collection/draw',json=request)
    assert first.status_code==200,first.text
    assert len(first.json()['cards'])==10 and all(c['album_id']=='sgs' for c in first.json()['cards'])
    assert client.post('/api/plugins/collection/draw',json=request).json()==first.json()
    with db.connect() as d:assert all(n==1 for n in state(d,uid,'collection','owned',{}).values())
    series=worlds['界限突破']['children'][0]
    with db.connect(True) as d:set_state(d,uid,'collection','owned',{id:1 for id in series['card_ids']})
    tasks=client.get('/api/plugins/journal').json()['tasks']
    assert next(t for t in tasks if t['title']=='绝无仅有')['progress']==1
    assert client.delete('/api/catalog/sgs').status_code==200
    assert client.get(sample['image']).status_code==403
