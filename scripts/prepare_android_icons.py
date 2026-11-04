from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
logo=Image.open(root/'public/logo.png').convert('RGBA')
res=root/'android/app/src/main/res'
for density,size,foreground in [('mdpi',48,108),('hdpi',72,162),('xhdpi',96,216),('xxhdpi',144,324),('xxxhdpi',192,432)]:
    folder=res/('mipmap-'+density);folder.mkdir(exist_ok=True)
    for name in ['ic_launcher.png','ic_launcher_round.png']: logo.resize((size,size)).save(folder/name)
    icon=Image.new('RGBA',(foreground,foreground),(248,248,245,255))
    art=logo.resize((round(foreground*.62),round(foreground*.62)))
    icon.alpha_composite(art,((foreground-art.width)//2,(foreground-art.height)//2));icon.save(folder/'ic_launcher_foreground.png')
for file in res.glob('drawable*/splash.png'):
    with Image.open(file) as old: size=old.size
    bg=Image.new('RGBA',size,(248,248,245,255));side=min(min(size)//3,220);art=logo.resize((side,side));bg.alpha_composite(art,((size[0]-side)//2,(size[1]-side)//2));bg.convert('RGB').save(file)
print('Applied supplied logo to Android launcher and splash assets')
