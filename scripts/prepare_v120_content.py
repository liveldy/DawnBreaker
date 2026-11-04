"""Import supplied rarity artwork, full splash art and voiced quote pack."""
import json, shutil, re
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'server/content'; LOL=ROOT/'mods/LOLpackage'
skins=json.loads((LOL/'skins.json').read_text(encoding='utf-8-sig'))
config=json.loads((OUT/'cards.json').read_text(encoding='utf-8'))
(OUT/'splashes').mkdir(exist_ok=True); (OUT/'rarity').mkdir(exist_ok=True)
for name in ['limited','legendary','mythic']:
    shutil.copy2(LOL/'Rarity'/f'{name}.png',OUT/'rarity'/f'{name}.png')
for c in config['cards']:
    if c.get('album_id')!='lol':continue
    s=skins[c['id']]; rarity=s.get('rarity','kNoRarity')
    badge='mythic' if rarity in ['kMythic','kUltimate','kExalted','kTranscendent'] else 'legendary' if rarity=='kLegendary' else 'limited' if s.get('isLegacy') else None
    c.update(description=re.sub('<[^>]+>','',s.get('description','')),original_rarity=rarity,rarity_badge='/api/plugins/collection/rarity/'+badge if badge else None)
    source=LOL/s.get('uncenteredSplashPath','missing')
    if source.is_file():
        with Image.open(source) as im:
            im.thumbnail((1600,1000)); im.convert('RGB').save(OUT/'splashes'/f"{c['id']}.webp",'WEBP',quality=85)
        c['splash']='/api/plugins/collection/splash/'+c['id']
    c['legacy']=s.get('isLegacy',False)
(OUT/'cards.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'voice').mkdir(exist_ok=True)
quotes=[]
for i,q in enumerate(json.loads((ROOT/'mods/LOLSound/sound.json').read_text(encoding='utf-8-sig'))):
    filename=Path(q['file']).name
    shutil.copy2(ROOT/'mods/LOLSound/sound'/filename,OUT/'voice'/('lol-'+filename))
    quotes.append({'id':f'lol-{i+1:03d}','text':q['text'],'author':q['author'],'audio':'lol-'+filename,'content_plugin':'lol-quotes'})
(OUT/'lol-quotes.json').write_text(json.dumps(quotes,ensure_ascii=False,indent=2),encoding='utf-8')
print('Imported',len(quotes),'voiced quotes;',len(list((OUT/'splashes').glob('*.webp'))),'full splash images')
