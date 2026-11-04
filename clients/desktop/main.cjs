const {app,BrowserWindow,Menu,shell,protocol,session}=require('electron');
const path=require('node:path');
const {registerUpdater}=require('./updater.cjs');
const {registerMedia}=require('./media.cjs');
const {registerOffline,localPage}=require('./offline.cjs');
const {registerDevice}=require('./device.cjs');
protocol.registerSchemesAsPrivileged([{scheme:'dawn',privileges:{standard:true,secure:true,supportFetchAPI:true,corsEnabled:true,stream:true,allowServiceWorkers:true}}]);
if(!app.isPackaged&&process.env.DAWN_QA_USER_DATA)app.setPath('userData',process.env.DAWN_QA_USER_DATA);
const address=process.env.DAWN_WEB_URL||'http://110.42.63.153:7780';
const target=new URL(address);
if(!['http:','https:'].includes(target.protocol)||target.username||target.password)throw new Error('Invalid service URL');
let window,splash,pendingActivation=false;
function activate(){if(!window||window.isDestroyed()){pendingActivation=true;return;}if(window.isMinimized())window.restore();window.show();window.moveTop();window.focus();pendingActivation=false;}
// The portable launcher extracts to a different directory on every launch.
// Keep the single-instance lock in the existing, stable account/profile directory.
app.setName('dawnbreaker-desktop');

function open(){
  window=new BrowserWindow({show:false,width:1360,height:920,minWidth:840,minHeight:640,title:'破晓 · DawnBreaker',backgroundColor:'#f8f8f5',icon:path.join(__dirname,'icon.ico'),webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false,partition:'persist:dawnbreaker'}});
  Menu.setApplicationMenu(null);
  window.webContents.setWindowOpenHandler(({url})=>{try{const link=new URL(url);if(['http:','https:'].includes(link.protocol))shell.openExternal(url);}catch{}return {action:'deny'};});
  window.webContents.on('will-navigate',(event,url)=>{if(!localPage(url))event.preventDefault();});
  window.webContents.on('did-fail-load',(_event,code,_description,url,isMainFrame)=>{if(isMainFrame&&code!==-3)window.loadFile(path.join(__dirname,'offline.html'));});
  window.webContents.on('will-navigate',(event,url)=>{if(url==='https://dawnbreaker.retry/'){event.preventDefault();window.loadURL('dawn://app/');}});
  window.once('ready-to-show',()=>{splash?.destroy();splash=null;activate();});
  window.loadURL('dawn://app/');
}
const primary=app.requestSingleInstanceLock();
if(!primary){app.quit();}else{
 app.on('second-instance',activate);
 app.whenReady().then(async()=>{app.setAppUserModelId('app.dawnbreaker.desktop');splash=new BrowserWindow({width:460,height:320,frame:false,resizable:false,backgroundColor:'#f8f8f5',icon:path.join(__dirname,'icon.ico'),webPreferences:{sandbox:true,nodeIntegration:false,contextIsolation:true}});splash.loadFile(path.join(__dirname,'splash.html'));await registerOffline(()=>window,target,session.fromPartition('persist:dawnbreaker'));registerUpdater(()=>window,target);registerDevice(()=>window,target);const media=registerMedia(()=>window,target);open();media.attach();});
 app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit();});
 app.on('activate',()=>{if(!BrowserWindow.getAllWindows().length)open();else activate();});
}
