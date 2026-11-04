const {app,ipcMain,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');const {spawn}=require('node:child_process');
const {pipeline}=require('node:stream/promises');const {Readable,Transform}=require('node:stream');
const newer=(a,b)=>{const x=a.split('.').map(Number),y=b.split('.').map(Number);for(let i=0;i<3;i++){if(x[i]!==y[i])return x[i]>y[i];}return false;};
const updateAvailable=(release,current,sequence)=>Number.isSafeInteger(sequence)&&sequence>0&&Number.isSafeInteger(release.version_code)?release.version_code>sequence:newer(release.version,current);
function verifyRelease(envelope,publicKey){
 const bytes=Buffer.from(envelope.signed,'base64');
 if(!crypto.verify('RSA-SHA256',bytes,publicKey,Buffer.from(envelope.signature,'base64')))throw Error('更新签名验证失败');
 const payload=JSON.parse(bytes);
 if(payload.platform!=='windows'||!/^\d+\.\d+\.\d+$/.test(payload.version)||!/^DawnBreaker-[A-Za-z0-9.-]+\.exe$/.test(payload.filename)||!/^[a-f0-9]{64}$/.test(payload.sha256)||!Number.isSafeInteger(payload.size)||payload.size<1||payload.size>400*1024*1024)throw Error('更新信息无效');
 if(payload.version_code!=null&&(!Number.isSafeInteger(payload.version_code)||payload.version_code<1))throw Error('更新构建序号无效');
 return payload;
}
function installScript(config){
 const encoded=Buffer.from(JSON.stringify(config)).toString('base64');
 return `$ErrorActionPreference='Stop'
$update = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('${encoded}')) | ConvertFrom-Json
$targetPath = [IO.Path]::GetFullPath($update.target)
$sourcePath = [IO.Path]::GetFullPath($update.source)
if ([IO.Path]::GetExtension($targetPath) -ne '.exe' -or [IO.Path]::GetExtension($sourcePath) -ne '.exe' -or $sourcePath -eq $targetPath) { throw 'Invalid update paths' }
Wait-Process -Id $update.pid -Timeout 60 -ErrorAction SilentlyContinue
if (Get-Process -Id $update.pid -ErrorAction SilentlyContinue) { throw 'Application is still running' }
if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $update.sha256) { throw 'Update checksum mismatch' }
$backupPath = $targetPath + '.previous'
try {
 if (Test-Path -LiteralPath $targetPath) { Copy-Item -LiteralPath $targetPath -Destination $backupPath -Force }
 $copied = $false
 for ($attempt = 0; $attempt -lt 30; $attempt++) {
  try { Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force; $copied = $true; break }
  catch { Start-Sleep -Milliseconds 300 }
 }
 if (-not $copied) { throw 'Portable launcher has not released the executable' }
 if ((Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $update.sha256) { throw 'Installed file checksum mismatch' }
 Start-Process -FilePath $targetPath -WindowStyle Normal
} catch {
 if (Test-Path -LiteralPath $backupPath) { Copy-Item -LiteralPath $backupPath -Destination $targetPath -Force }
 Start-Process -FilePath $targetPath -WindowStyle Normal
}
`;
}
function registerUpdater(getWindow,target){
 let release=null,ready=null,downloading=null;const sequence=require('./package.json').dawnReleaseSequence;
 const publicKey=fs.readFileSync(path.join(__dirname,'update-public.pem'));
 const assertCaller=event=>{if(!event.senderFrame)throw Error('请求来源不匹配');const url=new URL(event.senderFrame.url);if(event.sender!==getWindow()?.webContents||!(url.protocol==='dawn:'&&url.hostname==='app'))throw Error('请求来源不匹配');};
 ipcMain.handle('dawn:info',()=>({platform:'windows',version:app.getVersion(),release_sequence:sequence}));
 ipcMain.handle('dawn:check-update',async event=>{
  assertCaller(event);
  const response=await fetch(new URL('/api/releases/windows?current='+app.getVersion()+'&current_code='+sequence,target),{signal:AbortSignal.timeout(20000)});
  if(!response.ok)throw Error('暂时无法检查更新');
  const body=await response.text();if(body.length>65536)throw Error('更新信息过大');
  release=verifyRelease(JSON.parse(body),publicKey);
  return {available:updateAvailable(release,app.getVersion(),sequence),latest:release.version,notes:release.notes,size:release.size,ready:ready?.version===release.version};
 });
 ipcMain.handle('dawn:download-update',async event=>{
  assertCaller(event);if(!release||!updateAvailable(release,app.getVersion(),sequence))throw Error('请先检查更新');
  if(downloading)return downloading;
  const selected={...release};
  downloading=(async()=>{
   const folder=path.join(app.getPath('userData'),'updates');fs.mkdirSync(folder,{recursive:true});
   const filename=path.join(folder,selected.filename),partial=filename+'.partial';
   const response=await fetch(new URL('/api/releases/windows/download/'+selected.version,target),{signal:AbortSignal.timeout(600000)});
   if(!response.ok||!response.body)throw Error('安装包下载失败');
   const hash=crypto.createHash('sha256');let size=0;
   try{
    const meter=new Transform({transform(chunk,_encoding,callback){size+=chunk.length;if(size>selected.size){callback(Error('安装包大小不匹配'));return;}hash.update(chunk);getWindow()?.webContents.send('dawn:update-progress',{percent:Math.floor(size/selected.size*100)});callback(null,chunk);}});
    await pipeline(Readable.fromWeb(response.body),meter,fs.createWriteStream(partial));
    if(size!==selected.size||hash.digest('hex')!==selected.sha256)throw Error('安装包校验失败');
    fs.renameSync(partial,filename);ready={...selected,path:filename};return {ready:true,latest:selected.version};
   }catch(error){throw error;}
  })();try{return await downloading;}finally{downloading=null;}
 });
 ipcMain.handle('dawn:install-update',async event=>{
  assertCaller(event);if(!ready)throw Error('请先下载并校验更新');
  const current=process.env.PORTABLE_EXECUTABLE_FILE;
  if(!current)throw Error('请使用发布的便携 EXE 安装更新，开发模式不支持替换客户端');
  const result=await dialog.showMessageBox(getWindow(),{type:'question',buttons:['安装并重启','稍后'],defaultId:0,cancelId:1,title:'更新破晓',message:'已验证 '+ready.version+' 安装包。安装将关闭并重新打开破晓。'});
  if(result.response!==0)return {cancelled:true};
  const script=installScript({pid:process.pid,target:path.resolve(current),source:ready.path,sha256:ready.sha256});
  const child=spawn('powershell.exe',['-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')],{detached:true,stdio:'ignore',windowsHide:true});child.unref();setTimeout(()=>app.quit(),400);return {installing:true};
 });
}
module.exports={registerUpdater,verifyRelease,newer,updateAvailable,installScript};
