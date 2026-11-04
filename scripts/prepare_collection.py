"""Compile supplied universe/series metadata into the reusable album schema."""
import json,re
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
source=root/'mods/LOLpackage';out=root/'server/content'
def read(name):return json.loads((source/name).read_text(encoding='utf-8-sig'))
skins=read('skins.json');lines=read('skinlines.json');universes=read('universes.json');covers=read('albums.json')
config=json.loads((out/'cards.json').read_text(encoding='utf-8'))
for card in config['cards']:
    if card.get('album_id') not in (None,'lol'):continue
    skin=skins.get(card['id'])
    if not skin:continue
    card['album_id']='lol'
    card['series_ids']=['base'] if skin.get('isBase') else [str(s['id']) for s in skin.get('skinLines',[])] or ['other']
    card['categories']=card['series_ids']
    if skin.get('isBase'):card['title']='符文大陆'
ids={c['id'] for c in config['cards'] if c.get('album_id')=='lol'}
used={g for c in config['cards'] if c.get('album_id')=='lol' for g in c['series_ids']}
def node(id,name,kind,description='',cover=None,children=None):
    value={'id':str(id),'name':name,'kind':kind,'description':re.sub('<[^>]+>','',description)}
    if str(cover) in ids:value['cover_card_id']=str(cover)
    if children is not None:value['children']=children
    return value
series={str(s['id']):node(s['id'],s['name'],'series',s.get('description',''),s.get('coverSkinId')) for s in lines if str(s['id']) in used}
worlds=[node('runeterra','符文大陆','universe','符文大陆的英雄们。',covers.get('runeterra',{}).get('coverSkinId'),[node('base','英雄原貌','series',cover=covers.get('runeterra',{}).get('coverSkinId'))])]
assigned=set()
for universe in universes:
    children=[series[str(sid)] for sid in universe.get('skinSets',[]) if str(sid) in series]
    if children:
        worlds.append(node('universe-'+str(universe['id']),universe['name'],'universe',universe.get('description',''),universe.get('coverSkinId'),children))
        assigned.update(c['id'] for c in children)
for sid,group in series.items():
    if sid not in assigned:worlds.append(node('standalone-'+sid,group['name'],'universe',group.get('description',''),group.get('cover_card_id'),[group]))
if 'other' in used:worlds.append(node('other-universe','其他珍藏','universe',children=[node('other','其他珍藏','series')]))
album=node('lol','英雄联盟','album',cover=covers.get('package',{}).get('coverSkinId',103027),children=worlds)
album.update(content_plugin='lol',poster='posters/lol.webp',pack={'title':'灵魂莲华','subtitle':'阿狸','art_caption':'灵魂莲华 阿狸','caption':'让每一次相遇，在卡册里留下名字。'})
old_file=out/'card-albums.json'
previous=json.loads(old_file.read_text(encoding='utf-8')) if old_file.exists() else {}
others=[a for a in previous.get('albums',[]) if a['id']!='lol']
old_file.write_text(json.dumps({'schema_version':2,'albums':[album]+others},ensure_ascii=False,indent=2),encoding='utf-8')
(out/'cards.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'posters').mkdir(exist_ok=True)
with Image.open(source/skins['103027']['uncenteredSplashPath']) as im:
    im.thumbnail((1920,1200));im.convert('RGB').save(out/'posters/lol.webp','WEBP',quality=90)
print('Prepared shared album schema:',len(worlds),'universes,',len(used),'series,',len(ids),'cards')
