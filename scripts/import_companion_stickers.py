"""Copy the supplied nine PNGs per model unchanged; keep optional art out of source control."""
from pathlib import Path
import hashlib,shutil
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
for provider in ('deepseek','grok'):
    source=ROOT/'mods/emotion'/provider;target=ROOT/'server/content/emotion'/provider
    files=sorted(source.glob('image-3x3-tile-*.png'))
    if len(files)!=9:raise ValueError(f'{provider}: expected exactly nine supplied stickers')
    target.mkdir(parents=True,exist_ok=True)
    for i,file in enumerate(files,1):
        with Image.open(file) as image:
            if image.format!='PNG' or image.width>2048 or image.height>2048:raise ValueError('Unexpected sticker format or dimensions')
            image.verify()
        destination=target/(f'{i:02}.png');shutil.copyfile(file,destination)
        assert hashlib.sha256(file.read_bytes()).digest()==hashlib.sha256(destination.read_bytes()).digest()
    print(provider+': imported nine original PNGs unchanged')
