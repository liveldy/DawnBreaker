"""Synchronise static-site preview captions with successfully loaded screenshots."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'website/site.js';s=p.read_text(encoding='utf-8')
start=s.index("const image=document.querySelector('#stage-image')")
end=s.index("document.querySelectorAll('[data-show]')",start)
s=s[:start]+'''const image=document.querySelector('#stage-image');let current='draw',displayed='draw';const imageCache=new Map();
function readyImage(src){if(!imageCache.has(src))imageCache.set(src,new Promise((resolve,reject)=>{const asset=new Image();asset.onload=()=>resolve(asset);asset.onerror=reject;asset.src=src;}));return imageCache.get(src);}
Object.values(previews).forEach(p=>readyImage(p.src).catch(()=>{}));
async function showPreview(name){
 if(!previews[name]||name===current)return;current=name;const p=previews[name];image.setAttribute('aria-busy','true');
 try{await readyImage(p.src);if(current!==name)return;image.src=p.src;image.alt=p.alt;image.classList.remove('swapping');void image.offsetWidth;image.classList.add('swapping');displayed=name;document.querySelector('#stage-caption').textContent=p.caption;document.querySelectorAll('.preview-controls button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.show===name)));}
 catch{if(current===name)current=displayed;}
 finally{if(current===name)image.setAttribute('aria-busy','false');}
}
''' +s[end:]
p.write_text(s,encoding='utf-8')
print('Preview image and caption now switch together after loading')
