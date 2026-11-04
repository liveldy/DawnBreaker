"""Export only curated product UI images and public brand/font assets."""
from pathlib import Path
from PIL import Image
import shutil
root=Path(__file__).resolve().parents[1]
out=root/'website/assets';out.mkdir(parents=True,exist_ok=True)
qa=root/'.taste-skill/v110'
crops={'words.webp':('vocabulary-1440.png',(280,319,1100,783)),
       'albums.webp':('categories-1440.png',(280,300,1392,705)),
       'cards.webp':('album-cards-1440.png',(280,230,1392,680)),
       'draw-mobile.webp':('draw-390.png',(0,60,390,900)),
       'words-mobile.webp':('vocabulary-390.png',(0,60,390,900)),
       'albums-mobile.webp':('categories-390.png',(0,60,390,900)),
       'cards-mobile.webp':('album-cards-390.png',(0,60,390,900))}
crops['tools.webp']=('market-1440.png',(280,190,1392,700))
crops['tools-mobile.webp']=('market-390.png',(0,60,390,900))
for name,(source,box) in crops.items():
    with Image.open(qa/source) as image:
        image.crop(box).convert('RGB').save(out/name,'WEBP',quality=92,method=6)
revised={
    'draw-mobile.webp':('draw-390.png',(0,60,390,900)),
    'albums.webp':('universes-1440.png',(280,300,1392,750)),
    'albums-mobile.webp':('universes-390.png',(0,60,390,900)),
    'cards.webp':('cards-1440.png',(280,230,1392,680)),
    'cards-mobile.webp':('cards-390.png',(0,60,390,900)),
}
for name,(source,box) in revised.items():
    path=root/'.taste-skill/v111'/source
    if path.is_file():
        with Image.open(path) as image:image.crop(box).convert('RGB').save(out/name,'WEBP',quality=92,method=6)
shutil.copy2(root/'public/logo.png',out/'logo.png')
for weight,name in [('400','instrument-sans.woff2'),('500','instrument-sans-medium.woff2')]:
    font=next((root/'dist/assets').glob('instrument-sans-latin-'+weight+'-normal-*.woff2'))
    shutil.copy2(font,out/name)
shutil.copy2(root/'node_modules/@fontsource/instrument-sans/LICENSE',out/'OFL.txt')
print('Prepared public website UI, logo and licensed fonts')
