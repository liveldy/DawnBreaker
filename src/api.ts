export class ApiError extends Error { constructor(public status:number,message:string){super(message);} }
export async function api<T=any>(path:string, options:RequestInit={}):Promise<T> {
  const response=await apiFetch('/api'+path,{credentials:'include',...options,headers:{'Content-Type':'application/json',...options.headers}});
  let data:any;
  try { data=await response.json(); } catch { throw new ApiError(response.status,'服务暂时没有响应，请稍后重试'); }
  if(!response.ok) { const detail=data.detail; throw new ApiError(response.status,typeof detail==='string'?detail:response.status===422?'请检查输入内容和长度':'操作失败，请稍后重试'); }
  return data;
}
export const post=(path:string,body?:unknown)=>api(path,{method:'POST',body:body===undefined?undefined:JSON.stringify(body)});
export type Plugin={id:string;name:string;description:string;type:'standard'|'content';category:string;icon:string;ui?:string;parent?:string;installed:boolean;version:string;note?:string;requires:string[]};
export type User={id:string;username:string;nickname:string;bio:string;created_at:string;role:'user'|'admin';avatar_url?:string|null};
export type Bootstrap={user:User;wallet:{essence:number;stones:number};plugins:Plugin[];version:string};
export const go=(route:string)=>{location.hash=route;};
export const number=(n:number)=>n.toLocaleString('zh-CN');
export const date=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
import{apiFetch}from'./offline';
