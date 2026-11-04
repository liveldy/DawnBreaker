import runpy
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[1]
runpy.run_path(str(R/'scripts/import_music.py'))
out=R/'server/content/ai';out.mkdir(exist_ok=True)
for file in (R/'mods/ai').glob('*.webp'):
    with Image.open(file) as im:
        im.thumbnail((500,750));im.save(out/file.name,'WEBP',quality=88)
p=R/'src/ConstellationPage.tsx';s=p.read_text(encoding='utf-8').replace("const library=useData('/plugins/library')","const library=useData(r.data?.library_enabled?'/plugins/library':null)");p.write_text(s,encoding='utf-8')
p=R/'src/workspace.css';s=p.read_text(encoding='utf-8').replace('grid-template-columns:165px minmax(0,1fr))','grid-template-columns:165px minmax(0,1fr)');p.write_text(s,encoding='utf-8')
print('Prepared',len(list(out.glob('*.webp'))),'AI portraits')
