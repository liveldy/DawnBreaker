export type Point={id:string;name:string;cost:number|null;score:number};
export function killCounts(selected:Point,plotted:Point[],all:Point[]){
 const killed=(m:Point)=>m.id!==selected.id&&m.cost!==null&&selected.cost!==null&&m.cost>=selected.cost&&m.score<=selected.score;
 return{plot:plotted.filter(killed).length,all:all.filter(killed).length,priced:all.filter(m=>m.cost!==null).length};
}
export function placeLabels(points:{id:string;name:string;x:number;y:number}[],width:number,height:number){
 const occupied:{x:number;y:number;w:number;h:number}[]=[];
 return points.map(p=>{const w=Math.min(210,Math.max(32,[...p.name].reduce((n,c)=>n+(c.charCodeAt(0)>255?12:6.3),0))),h=15;let box={x:Math.min(width-w-12,p.x+10),y:Math.max(25,p.y-17),w,h};let found=false;
  const fits=(b:typeof box)=>b.x>=48&&b.y>=20&&b.x+w<=width-15&&b.y+h<=height-58&&!occupied.some(a=>b.x<a.x+a.w+5&&b.x+w+5>a.x&&b.y<a.y+a.h+3&&b.y+h+3>a.y);
  for(let ring=0;ring<14&&!found;ring++)for(const dx of[10,-w-10])for(const dy of[-18-ring*17,4+ring*17]){const candidate={x:Math.max(48,Math.min(width-w-15,p.x+dx)),y:p.y+dy,w,h};if(!found&&fits(candidate)){box=candidate;found=true;}}
  if(!found)for(let y=22;y<height-58&&!found;y+=18)for(let x=50;x<width-w-15&&!found;x+=30){const candidate={x,y,w,h};if(fits(candidate)){box=candidate;found=true;}}
  occupied.push(box);return{...p,labelX:box.x,labelY:box.y+12,lineX:Math.max(box.x,Math.min(p.x,box.x+w)),lineY:box.y+7};
 });
}
