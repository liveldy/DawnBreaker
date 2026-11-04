export type Point={id:string;name:string;cost:number|null;score:number};
export function killCounts(selected:Point,plotted:Point[],all:Point[]){
 const killed=(m:Point)=>m.id!==selected.id&&m.cost!==null&&selected.cost!==null&&m.cost>=selected.cost&&m.score<=selected.score;
 return{plot:plotted.filter(killed).length,all:all.filter(killed).length,priced:all.filter(m=>m.cost!==null).length};
}
export function placeLabels(points:{id:string;name:string;x:number;y:number}[],width:number,height:number,options:{selectedId?:string;measureText?:(name:string)=>number}={}){
 const occupied:{x:number;y:number;w:number;h:number}[]=[],labels:{id:string;name:string;x:number;y:number;labelX:number;labelY:number}[]=[];
 const overlaps=(a:typeof occupied[number],b:typeof occupied[number],gap=3)=>a.x<b.x+b.w+gap&&a.x+a.w+gap>b.x&&a.y<b.y+b.h+gap&&a.y+a.h+gap>b.y;
 const density=(p:typeof points[number])=>points.filter(q=>Math.hypot(q.x-p.x,q.y-p.y)<70).length;
 // Prefer isolated points and the selection; a busy cluster keeps its dots,
 // rather than sending their names to unrelated empty parts of the chart.
 const ordered=points.map((p,index)=>({p,index,density:density(p)})).sort((a,b)=>Number(b.p.id===options.selectedId)-Number(a.p.id===options.selectedId)||a.density-b.density||a.index-b.index);
 for(const{p}of ordered){
  const w=Math.ceil(options.measureText?.(p.name)??[...p.name].reduce((n,c)=>n+(c.charCodeAt(0)>255?12:7.5),0))+2,h=16;
  const candidates=[[p.x+10,p.y-h/2],[p.x-w-10,p.y-h/2],[p.x-w/2,p.y-h-10],[p.x-w/2,p.y+10],[p.x+10,p.y-h-6],[p.x+10,p.y+6],[p.x-w-10,p.y-h-6],[p.x-w-10,p.y+6]];
  const box=candidates.map(([x,y])=>({x,y,w,h})).find(b=>b.x>=48&&b.y>=28&&b.x+w<=width-26&&b.y+h<=height-54&&!occupied.some(a=>overlaps(a,b))&&!points.some(q=>overlaps({x:q.x-8,y:q.y-8,w:16,h:16},b,1)));
  if(!box)continue;
  occupied.push(box);labels.push({...p,labelX:box.x,labelY:box.y+12});
 }
 return labels;
}
