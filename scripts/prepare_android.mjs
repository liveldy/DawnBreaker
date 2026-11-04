import{cp,mkdir,rm}from'node:fs/promises';import{resolve,sep}from'node:path';
const root=resolve('android/app/src/main/assets'),dest=resolve(root,'linkswift');if(!dest.startsWith(root+sep))throw Error('Invalid asset path');await rm(dest,{recursive:true,force:true});await mkdir(dest,{recursive:true});await cp('third_party/linkswift',dest,{recursive:true});

await mkdir(resolve(root,'geodata'),{recursive:true});await cp('.tooling/geodata',resolve(root,'geodata'),{recursive:true});
await cp('third_party/geodata/manifest.json',resolve(root,'geodata/manifest.json'));
