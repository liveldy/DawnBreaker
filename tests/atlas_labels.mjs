import assert from'node:assert/strict';
import{buildSync}from'esbuild';
const result=buildSync({entryPoints:['src/atlasGeometry.ts'],bundle:true,platform:'node',format:'cjs',write:false}),module={exports:{}};
new Function('module','exports',result.outputFiles[0].text)(module,module.exports);
const{placeLabels}=module.exports,measureText=name=>name.length*7;
const sparse=[{id:'one',name:'Model One',x:100,y:100},{id:'two',name:'Model Two',x:500,y:250}];
assert.equal(placeLabels(sparse,900,420,{measureText}).length,2);
const dense=Array.from({length:100},(_,i)=>({id:String(i),name:'Crowded Model '+i,x:400+(i%4),y:200+(i%5)}));
const labels=placeLabels(dense,900,420,{measureText,selectedId:'99'});
assert(labels.length>0&&labels.length<10,'dense clusters must hide names, not scatter them across the chart');
assert(labels.some(l=>l.id==='99'),'selected point has label priority');
for(const label of labels){
 const w=measureText(label.name)+2,box={x:label.labelX,y:label.labelY-12,w,h:16};
 const horizontal=Math.max(box.x-label.x,0,label.x-box.x-box.w),vertical=Math.max(box.y-label.y,0,label.y-box.y-box.h);
 assert(Math.hypot(horizontal,vertical)<24,'name must stay beside its own point');
 assert(!('lineX'in label)&&!('lineY'in label));
 assert(box.x>=48&&box.y>=28&&box.x+box.w<=874&&box.y+box.h<=366);
 for(const other of labels.filter(l=>l.id!==label.id)){
  const a={x:other.labelX,y:other.labelY-12,w:measureText(other.name)+2,h:16};
  assert(!(box.x<a.x+a.w&&box.x+box.w>a.x&&box.y<a.y+a.h&&box.y+box.h>a.y));
 }
 for(const p of dense)assert(!(p.x>box.x-8&&p.x<box.x+box.w+8&&p.y>box.y-8&&p.y<box.y+box.h+8),'label must not cover another dot');
}
assert.equal(placeLabels([{id:'huge',name:'W'.repeat(500),x:100,y:100}],900,420,{measureText}).length,0,'unfittable labels must stay hidden');
console.log('PASS: sparse names, dense hiding, selection priority, no connectors, no collisions, bounds and long names');
