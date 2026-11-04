import{cp,rm,mkdir}from'node:fs/promises';import{resolve,sep,basename}from'node:path';
import{build}from'esbuild';
await build({stdin:{contents:"module.exports={yaml:require('yaml'),...require('fflate')}",resolveDir:resolve('.')},bundle:true,platform:'node',format:'cjs',outfile:'clients/desktop/vendor.cjs',legalComments:'eof'});
const root=resolve('clients/desktop'),destination=resolve(root,'web');
if(!destination.startsWith(root+sep)||basename(destination)!=='web')throw Error('Invalid generated web directory');
await rm(destination,{recursive:true,force:true});await mkdir(destination,{recursive:true});await cp(resolve('dist'),destination,{recursive:true});
console.log('Bundled local desktop app shell for offline startup');
