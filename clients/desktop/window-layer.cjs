// Electron 39 has no moveBottom(). Use HWND_BOTTOM without activating the widget.
const {spawn}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');const readline=require('node:readline');
function createWindowLayer(){
 let helper,next=0;const pending=new Map();
 function start(){
  if(helper&&!helper.killed)return helper;
  const source=fs.readFileSync(path.join(__dirname,'window-layer.ps1'),'utf8').replace('PARENT_PROCESS_ID',String(process.pid));
  const child=helper=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(source,'utf16le').toString('base64')],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const fail=()=>{if(helper===child)helper=undefined;for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('桌面控件层级服务不可用'));}pending.clear();};
  readline.createInterface({input:child.stdout}).on('line',line=>{const[id,status]=line.trim().split(' ');const p=pending.get(Number(id));if(!p)return;clearTimeout(p.timer);pending.delete(Number(id));status==='ok'?p.resolve():p.reject(Error('无法调整桌面控件层级'));});
  child.on('error',fail);child.on('exit',fail);child.stderr.resume();return child;
 }
 const set=(win,bottom)=>{
  if(process.platform!=='win32')return Promise.resolve();
  const h=win.getNativeWindowHandle();const handle=h.length===8?h.readBigUInt64LE():BigInt(h.readUInt32LE());
  const child=start(),id=++next;
  return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('桌面控件层级服务响应超时'));},15000);pending.set(id,{resolve,reject,timer});child.stdin.write(`${id} ${bottom?'bottom':'remove'} ${handle}\n`,error=>{if(error){clearTimeout(timer);pending.delete(id);reject(error);}});});
 };
 return{set,close(){helper?.stdin.end();helper?.kill();helper=undefined;}};
}
module.exports={createWindowLayer};
