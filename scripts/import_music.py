"""Incremental music import; IDs and existing account progress remain stable."""
import json,re,shutil
from pathlib import Path
from mutagen.mp3 import MP3
R=Path(__file__).resolve().parents[1];source=R/'mods/MusicPlayer_QSX';out=R/'server/content';(out/'audio').mkdir(exist_ok=True)
existing=json.loads((out/'music.json').read_text(encoding='utf-8'));by_id={t['id']:t for t in existing};added=[]
for mp3 in sorted((source/'mp3').glob('*.mp3')):
    lyric=(source/'lrc'/(mp3.stem+'.lrc')).read_text(encoding='utf-8-sig');title=re.search(r'\[ti:(.*?)\]',lyric);artist=re.search(r'\[ar:(.*?)\]',lyric);lines=[]
    for line in lyric.splitlines():
        stamps=re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]',line);text=re.sub(r'\[[^\]]*\]','',line).strip()
        if text:
            for minute,second in stamps:lines.append({'time':int(minute)*60+float(second),'text':text})
    track={'id':mp3.stem,'name':title[1] if title else mp3.stem,'artist':artist[1] if artist else '未知艺术家','file':mp3.name,'duration':round(MP3(mp3).info.length,2),'lyrics':sorted(lines,key=lambda x:x['time'])}
    if mp3.stem not in by_id:added.append(track['name'])
    by_id[mp3.stem]=track;target=out/'audio'/mp3.name
    if not target.exists() or target.stat().st_size!=mp3.stat().st_size:shutil.copy2(mp3,target)
(out/'music.json').write_text(json.dumps(list(by_id.values()),ensure_ascii=False,indent=2),encoding='utf-8')
print('Music tracks:',len(by_id),'; added:',', '.join(added))
