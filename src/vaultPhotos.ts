import {Capacitor,registerPlugin} from '@capacitor/core';
import {normalizePhoto,PHOTO_MAX_BYTES,type VaultPhoto} from './vaultEntries';
import {unb64} from './vaultCrypto';

const native=registerPlugin<{savePhoto:(options:{filename:string;data:string;mime:string})=>Promise<{cancelled?:boolean}>}>('DawnClient');
export async function readVaultPhoto(file:File):Promise<VaultPhoto>{
 if(!file.size||file.size>PHOTO_MAX_BYTES)throw Error('请选择不超过 5 MB 的照片。');
 const bytes=new Uint8Array(await file.slice(0,12).arrayBuffer());
 const mime=bytes[0]===137&&bytes[1]===80&&bytes[2]===78&&bytes[3]===71?'image/png':bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'image/jpeg':String.fromCharCode(...bytes.slice(0,4))==='RIFF'&&String.fromCharCode(...bytes.slice(8,12))==='WEBP'?'image/webp':'';
 if(!mime)throw Error('照片仅支持 PNG、JPEG 或 WebP。');
 const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve('data:'+mime+';base64,'+String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('照片读取失败，请重新选择。'));reader.readAsDataURL(file);});
 const img=new Image();
 await new Promise<void>((resolve,reject)=>{img.onload=()=>resolve();img.onerror=()=>reject(Error('照片无法打开，请选择有效的图片。'));img.src=data;});
 const value=normalizePhoto({name:file.name,data});if(!value)throw Error('照片读取失败');return value;
}
export async function downloadVaultPhoto(photo:VaultPhoto,fallback:string){
 const valid=normalizePhoto(photo)!;
 const mime=valid.data.slice(5,valid.data.indexOf(';')),data=valid.data.slice(valid.data.indexOf(',')+1),ext=mime==='image/jpeg'?'jpg':mime.slice(6);
 const name=(fallback||photo.name||'暗格照片').replace(/[\\/:*?"<>|\r\n]/g,'_').slice(0,120).replace(/\.(png|jpe?g|webp)$/i,'')+'.'+ext;
 if(Capacitor.getPlatform()==='android'){
  if(!Capacitor.isPluginAvailable('DawnClient'))throw Error('请更新客户端后保存照片。');
  return native.savePhoto({filename:name,data,mime});
 }
 const url=URL.createObjectURL(new Blob([unb64(data) as BlobPart],{type:mime})),link=document.createElement('a');
 link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
