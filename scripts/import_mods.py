"""Convert user-supplied legacy vocabulary and media into server content.

Original mods are never edited. Only web-sized card images are packaged.
Usage: python scripts/import_mods.py
"""
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path
import xlrd
from PIL import Image
from mutagen.mp3 import MP3

PROJECT=Path(__file__).resolve().parents[1]
MODS=PROJECT/'mods'; OUT=PROJECT/'server'/'content'
OUT.mkdir(parents=True,exist_ok=True)
def write(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

book=xlrd.open_workbook(str(next(MODS.glob('*.xls'))))
words=[]; seen={}; duplicates=[]; source_rows=[]
for sheet in book.sheets():
    for i in range(sheet.nrows):
        cells=[str(v).strip().replace('\xa0',' ') for v in sheet.row_values(i)]
        if len(cells)<3 or not cells[0]: continue
        word,phonetic,translation=cells[:3]
        source_rows.append([word,phonetic,translation,i+1])
        if word in seen:
            duplicates.append({'word':word,'row':i+1})
            if translation not in seen[word]['trans']: seen[word]['trans'].append(translation)
            seen[word]['source_rows'].append(i+1)
            continue
        entry={'name':word,'phonetic':phonetic,'trans':[translation],'source_row':i+1,'source_rows':[i+1]}
        seen[word]=entry; words.append(entry)
write('kaoyan.json',words)
with (OUT/'考研词汇.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f); writer.writerow(['词汇','音标','释义','原表行号'])
    writer.writerows(source_rows)
(OUT/'考研词汇.md').write_text('# 考研英语词汇\n\n来源：用户提供的《01.考研英语词汇正序版.xls》。同词条释义合并，完整原始行保存在 CSV 中。\n\n|词汇|音标|释义|\n|---|---|---|\n'+'\n'.join('|'+ '|'.join([w['name'],w['phonetic'],'；'.join(w['trans']).replace('|','／')])+'|' for w in words),encoding='utf-8')

music=MODS/'MusicPlayer_QSX'; (OUT/'audio').mkdir(exist_ok=True)
tracks=[]
for mp3 in sorted((music/'mp3').glob('*.mp3')):
    lrc=(music/'lrc'/(mp3.stem+'.lrc')).read_text(encoding='utf-8-sig')
    title=re.search(r'\[ti:(.*?)\]',lrc); artist=re.search(r'\[ar:(.*?)\]',lrc)
    lyrics=[]
    for line in lrc.splitlines():
        times=re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]',line)
        text=re.sub(r'\[[^\]]*\]','',line).strip()
        if text:
            for minute,second in times: lyrics.append({'time':int(minute)*60+float(second),'text':text})
    tracks.append({'id':mp3.stem,'name':title[1] if title else mp3.stem,'artist':artist[1] if artist else '未知艺术家','file':mp3.name,'duration':round(MP3(mp3).info.length,2),'lyrics':sorted(lyrics,key=lambda x:x['time'])})
    shutil.copy2(mp3,OUT/'audio'/mp3.name)
write('music.json',tracks)

skins=json.loads((MODS/'LOLpackage'/'skins.json').read_text(encoding='utf-8-sig'))
cards=[]; missing=[]; (OUT/'cards').mkdir(exist_ok=True)
for skin in skins.values():
    source=MODS/'LOLpackage'/skin['loadScreenPath']
    if not source.is_file(): missing.append(skin['id']); continue
    rarity='SSR' if skin['rarity'] in ['kMythic','kLegendary','kUltimate','kExalted','kTranscendent'] else 'SR' if skin['rarity'] in ['kEpic','kRare'] else 'R'
    filename=str(skin['id'])+'.webp'
    with Image.open(source) as im:
        im.thumbnail((320,600))
        im.convert('RGB').save(OUT/'cards'/filename,'WEBP',quality=80)
    cards.append({'id':str(skin['id']),'name':skin['name'],'title':'基础英雄' if skin.get('isBase') else '英雄皮肤','rarity':rarity,'original_rarity':skin['rarity'],'image':'/api/plugins/collection/image/'+str(skin['id'])})
previous=json.loads((OUT/'cards.json').read_text(encoding='utf-8')) if (OUT/'cards.json').exists() else {}
others=[c for c in previous.get('cards',[]) if c.get('album_id') not in (None,'lol')]
write('cards.json',previous|{'cost':previous.get('cost',10),'probabilities':previous.get('probabilities',{'SSR':5,'SR':20,'R':75}),'cards':cards+others})
shutil.copy2(MODS/'logo.png',PROJECT/'public'/'logo.png')
with Image.open(MODS/'logo.png') as im:
    im.save(PROJECT/'public'/'icon.ico',sizes=[(16,16),(32,32),(48,48),(256,256)])
    for size in [192,512]: im.resize((size,size)).save(PROJECT/'public'/f'icon-{size}.png')
report={'vocabulary':{'source_rows':sum(s.nrows for s in book.sheets()),'words':len(words),'duplicates':duplicates,'first':words[0]['name'],'last':words[-1]['name']},'music':{'tracks':len(tracks),'lyrics':sum(len(t['lyrics']) for t in tracks)},'cards':{'source':len(skins),'imported':len(cards),'missing':missing,'rarities':dict(Counter(c['rarity'] for c in cards))}}
write('import-report.json',report)
print(json.dumps(report,ensure_ascii=True))
import runpy
runpy.run_path(str(PROJECT/'scripts/prepare_collection.py'))
runpy.run_path(str(PROJECT/'scripts/prepare_v120_content.py'))
