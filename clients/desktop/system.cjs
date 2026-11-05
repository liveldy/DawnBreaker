const{app,screen,shell}=require('electron');const os=require('node:os'),path=require('node:path');const{execFile,spawn}=require('node:child_process');const{promisify}=require('node:util');
const execute=promisify(execFile),wait=ms=>new Promise(r=>setTimeout(r,ms));
const SETTINGS=Object.freeze({system:'ms-settings:about',storage:'ms-settings:storagesense',apps:'ms-settings:appsfeatures'});
let trimming=false,storageCache=null;
function processMemory(){const metrics=app.getAppMetrics();return{bytes:metrics.reduce((n,m)=>n+Math.max(0,m.memory?.workingSetSize||0)*1024,0),ids:[...new Set(metrics.map(m=>m.pid).filter(p=>Number.isInteger(p)&&p>0))].slice(0,64)};}
async function helper(action,args=[]){const executable=path.join(process.env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe'),script=app.isPackaged?path.join(process.resourcesPath,'app.asar.unpacked','system-tools.ps1'):path.join(__dirname,'system-tools.ps1');const result=await execute(executable,['-NoProfile','-NonInteractive','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',script,'-Action',action,...args],{windowsHide:true,timeout:20000,maxBuffer:128*1024,encoding:'utf8'});return JSON.parse(result.stdout.trim());}
async function storage(){if(storageCache&&Date.now()-storageCache.stamp<10000)return storageCache.value;try{const value=await helper('storage',['-DataPath',app.getPath('userData')]);storageCache={value,stamp:Date.now()};return value;}catch{return null;}}
function cpuTotals(){return os.cpus().reduce((s,c)=>{s.idle+=c.times.idle;s.total+=Object.values(c.times).reduce((a,b)=>a+b,0);return s;},{idle:0,total:0});}
async function info(){
 const before=cpuTotals(),disk=storage();await wait(300);const after=cpuTotals(),delta=after.total-before.total;
 return{platform:'desktop',device_name:os.hostname(),os_name:os.version(),os_version:os.release(),architecture:os.arch(),cpu_model:os.cpus()[0]?.model||null,cpu_cores:os.cpus().length,cpu_percent:delta>0?Math.max(0,Math.min(100,(1-(after.idle-before.idle)/delta)*100)):null,uptime_seconds:os.uptime(),memory:{total:os.totalmem(),available:os.freemem(),app:processMemory().bytes,app_scope:'破晓客户端进程'},storage:await disk,displays:screen.getAllDisplays().map(d=>({name:d.label||'显示器',width:Math.round(d.size.width*d.scaleFactor),height:Math.round(d.size.height*d.scaleFactor),scale:d.scaleFactor})),battery:null,app_version:app.getVersion(),fetched_at:new Date().toISOString(),capabilities:{trim_memory:true,task_manager:true,settings:['system','storage','apps']}};
}
async function action(command,options={}){
 if(command==='system.info')return info();
 if(command==='system.trim-memory'){
  if(trimming)throw Error('内存整理正在进行，请稍候');trimming=true;
  try{const before=processMemory();if(!before.ids.length)throw Error('暂时无法读取破晓进程');const result=await helper('trim-memory',['-ProcessIds',before.ids.join(','),'-ExecutablePath',process.execPath]);if(!result.processed_count)throw Error('当前进程暂不支持内存整理');await wait(350);const after=processMemory().bytes;return{before_bytes:before.bytes,after_bytes:after,reclaimed_bytes:Math.max(0,before.bytes-after),processed_count:result.processed_count,message:'已整理破晓进程的可回收内存'};}finally{trimming=false;}
 }
 if(command==='system.open-settings'){const uri=SETTINGS[options.section];if(typeof uri!=='string')throw Error('系统设置项无效');await shell.openExternal(uri);return{message:'已打开 Windows 系统设置'};}
 if(command==='system.task-manager'){const child=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32','Taskmgr.exe'),[],{detached:true,stdio:'ignore',windowsHide:false});await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});child.unref();return{message:'已打开任务管理器'};}
 throw Error('不支持的系统操作');
}
module.exports={action,processMemory,SETTINGS};
