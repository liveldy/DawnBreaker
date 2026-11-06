export type EntryType='password'|'card'|'identity';
export type VaultPhoto={name:string;data:string};
export type CustomField={id:string;label:string;value:string;secret:boolean;kind?:'text'|'photo';photo?:VaultPhoto};
export type VaultEntry={id:string;type:EntryType;title:string;username:string;password:string;url:string;notes:string;fields:Record<string,string>;photos?:{front?:VaultPhoto;back?:VaultPhoto};custom:CustomField[];created_at:string;updated_at:string;[key:string]:unknown};
export const PHOTO_MAX_BYTES=5*1024*1024;
export const VAULT_MAX_BYTES=32*1024*1024;
export const CARD_TYPES=['身份证','银行卡','信用卡','会员卡','其他卡片'];
export type FieldSpec={key:string;label:string;secret?:boolean;multiline?:boolean;options?:string[];placeholder?:string};
export const ENTRY_TYPES:{id:EntryType;name:string;singular:string}[]=[{id:'password',name:'密码',singular:'密码'},{id:'card',name:'卡包',singular:'卡片'},{id:'identity',name:'个人信息册',singular:'个人资料'}];
export const FIELDS:Record<EntryType,FieldSpec[]>={
 password:[{key:'username',label:'账号'},{key:'password',label:'密码',secret:true},{key:'url',label:'网址',placeholder:'https://'}],
 card:[{key:'card_type',label:'卡片类型'},{key:'holder',label:'持卡人 / 姓名'},{key:'number',label:'卡号 / 证件号 / 会员号',secret:true},{key:'issuer',label:'发卡 / 签发机构'},{key:'expiry',label:'有效期',placeholder:'例如 12/29 或长期有效'},{key:'cvv',label:'安全码',secret:true},{key:'pin',label:'卡片密码',secret:true},{key:'phone',label:'预留电话'}],
 identity:[{key:'full_name',label:'姓名'},{key:'document_type',label:'证件类型',options:['身份证','护照','其他证件']},{key:'document_number',label:'证件号码',secret:true},{key:'birthday',label:'出生日期',placeholder:'YYYY-MM-DD'},{key:'phone',label:'联系电话'},{key:'email',label:'邮箱'},{key:'address',label:'联系地址',multiline:true},{key:'organization',label:'单位 / 机构'},{key:'emergency_contact',label:'紧急联系人'}]
};
const text=(v:unknown,fallback='')=>v==null?fallback:typeof v==='string'?v:(()=>{throw Error('密码箱中的资料格式不受支持，原数据未被修改。');})();
export function normalizePhoto(value:any):VaultPhoto|undefined{
 if(value==null)return undefined;
 if(typeof value!=='object'||Array.isArray(value))throw Error('照片格式无效，原数据未被修改。');
 const data=text(value.data),name=text(value.name);
 const match=/^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})$/.exec(data);
 if(!match||match[2].length%4||match[2].length/4*3-(match[2].endsWith('==')?2:match[2].endsWith('=')?1:0)>PHOTO_MAX_BYTES)throw Error('照片格式或大小无效，请使用不超过 5 MB 的 PNG、JPEG 或 WebP。');
 return{name:name.slice(0,200),data};
}
export function normalizeEntries(data:any):VaultEntry[]{
 if(data?.check!=='dawn-vault-v1'||!Array.isArray(data.entries))throw Error('密码箱格式不受支持，请使用兼容版本打开。');
 if(data.schema!=null&&(!Number.isInteger(data.schema)||data.schema>3))throw Error('密码箱使用了新版本格式，请先更新客户端。');
 const seen=new Set<string>();
 return data.entries.map((value:any)=>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('密码箱记录格式无效。');
  const type=value.type??'password';if(!ENTRY_TYPES.some(t=>t.id===type))throw Error('密码箱包含新版本资料类型，请先更新客户端。');
  const id=text(value.id);if(!id||seen.has(id))throw Error('密码箱记录标识无效，原数据未被修改。');seen.add(id);
  if(value.fields!=null&&(typeof value.fields!=='object'||Array.isArray(value.fields)))throw Error('资料字段格式无效。');
  const fields=Object.fromEntries(Object.entries(value.fields||{}).map(([k,v])=>[k,text(v)]));
  if(value.custom!=null&&!Array.isArray(value.custom))throw Error('自定义字段格式无效。');
  const custom=(value.custom||[]).map((f:any)=>{if(!f||typeof f!=='object'||Array.isArray(f))throw Error('自定义字段格式无效。');if(f.kind!=null&&!['text','photo'].includes(f.kind))throw Error('密码箱包含新版本字段类型，请先更新客户端。');return{...f,id:text(f.id),label:text(f.label),value:text(f.value),secret:f.secret!==false,...(f.photo?{photo:normalizePhoto(f.photo)}:{})};});
  if(value.photos!=null&&(typeof value.photos!=='object'||Array.isArray(value.photos)||Object.keys(value.photos).some(k=>!['front','back'].includes(k))))throw Error('照片字段格式不受支持，请先更新客户端。');
  const photos=value.photos?{front:normalizePhoto(value.photos.front),back:normalizePhoto(value.photos.back)}:undefined;
  return{...value,id,type,title:text(value.title),username:text(value.username),password:text(value.password),url:text(value.url),notes:text(value.notes),created_at:text(value.created_at),updated_at:text(value.updated_at),fields,custom,...(photos?{photos}:{})};
 });
}
export function fieldValue(entry:VaultEntry,key:string){return entry.type==='password'&&['username','password','url'].includes(key)?String(entry[key]||''):entry.fields[key]||'';}
export function setField(entry:VaultEntry,key:string,value:string):VaultEntry{return entry.type==='password'&&['username','password','url'].includes(key)?{...entry,[key]:value}:{...entry,fields:{...entry.fields,[key]:value}};}
export function primaryValue(e:VaultEntry){if(e.type==='password')return{label:'密码',value:e.password};if(e.type==='card')return{label:'卡号',value:e.fields.number||''};return{label:e.fields.document_number?'证件号码':'联系电话',value:e.fields.document_number||e.fields.phone||''};}
export function entrySummary(e:VaultEntry){
 if(e.type==='password')return e.username||e.url||'未填写账号';
 if(e.type==='card'){const number=(e.fields.number||'').replace(/\s/g,'');return[e.fields.issuer||e.fields.card_type||'卡片',number?'尾号 '+number.slice(-4):'未填写卡号'].join(' · ');}
 return[e.fields.full_name,e.fields.document_type,e.fields.document_number?'证件尾号 '+e.fields.document_number.slice(-4):''].filter(Boolean).join(' · ')||'个人资料';
}
export function matchesEntry(e:VaultEntry,query:string){const q=query.trim().toLocaleLowerCase();return[e.title,e.username,e.url,e.notes,...Object.values(e.fields),...e.custom.flatMap(f=>[f.label,f.kind==='photo'?f.photo?.name||'':f.value])].some(v=>v.toLocaleLowerCase().includes(q));}
export function vaultPayload(entries:VaultEntry[]){const value={check:'dawn-vault-v1',schema:3,entries};if(new TextEncoder().encode(JSON.stringify(value)).length>VAULT_MAX_BYTES)throw Error('密码箱容量超过 32 MB，请移除部分照片后再保存。');return value;}
export function csvExport(entries:VaultEntry[]){
 const cell=(v:string)=>'"'+(/^[=+\-@\t\r\n]/.test(v)?"'":'')+v.split('"').join('""')+'"';
 const rows=entries.map(e=>[ENTRY_TYPES.find(t=>t.id===e.type)!.name,e.title,e.username,e.password,e.url,e.notes,JSON.stringify({fields:e.fields,photos:e.photos,custom:e.custom})]);
 return'\ufeff'+[['类型','名称','账号','密码','网址','备注','其他资料（JSON）'],...rows].map(r=>r.map(cell).join(',')).join('\r\n');
}
