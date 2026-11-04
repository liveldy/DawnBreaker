const {app,BrowserWindow,Tray,Menu,ipcMain,powerSaveBlocker,screen}=require('electron');
const path=require('node:path');const fs=require('node:fs');const {createWindowLayer}=require('./window-layer.cjs');
function registerMedia(getWindow,target){
 let tray,quitting=false,state={name:'还没有播放音乐',artist:'弦音余韵',playing:false},quote={text:'打开破晓，登录后显示今日语录。',author:'流光笺'},blocker;
 const nativeLayer=createWindowLayer();
 const widgets=new Map();const preferences=path.join(app.getPath('userData'),'widget-settings.json');let layers={quotes:'bottom',music:'bottom'};
 try{const saved=JSON.parse(fs.readFileSync(preferences,'utf8'));for(const kind of ['quotes','music'])if(['top','bottom'].includes(saved[kind]))layers[kind]=saved[kind];}catch{}
 const persist=()=>{fs.writeFileSync(preferences+'.tmp',JSON.stringify(layers));fs.renameSync(preferences+'.tmp',preferences);};
 const applyLayer=async(win,kind)=>{const top=layers[kind]==='top';await nativeLayer.set(win,!top);if(!win.isDestroyed()){win.setAlwaysOnTop(top);win.setFocusable(top);}};
 const widgetCaller=e=>{for(const [kind,win] of widgets)if(!win.isDestroyed()&&win.webContents===e.sender)return{kind,win};throw Error('请求来源不匹配');};
 ipcMain.handle('widget:layer',async(e,mode)=>{const{kind,win}=widgetCaller(e);if(!['top','bottom'].includes(mode))throw Error('未知窗口层级');const previous=layers[kind];layers[kind]=mode;try{await applyLayer(win,kind);}catch(error){layers[kind]=previous;throw error;}persist();broadcast();return{mode,alwaysOnTop:win.isAlwaysOnTop()};});
 const mainCaller=e=>{const url=e.senderFrame?new URL(e.senderFrame.url):null;if(e.sender!==getWindow()?.webContents||url?.protocol!=='dawn:'||url.hostname!=='app')throw Error('请求来源不匹配');};
 const broadcast=()=>{for(const [kind,win] of widgets)if(!win.isDestroyed())win.webContents.send('widget:state',{state,quote,layer:layers[kind]});};
 const command=value=>{getWindow()?.webContents.send('dawn:media-command',value);};
 const show=()=>{const w=getWindow();w?.show();w?.focus();};
 const refreshQuote=async()=>{try{const r=await getWindow().webContents.session.fetch('dawn://app/api/plugins/quotes',{credentials:'include'});if(!r.ok)throw Error();quote=await r.json();}catch{quote={text:'请登录并安装流光笺，查看每日语录。',author:'流光笺'};}broadcast();};
 function widget(kind){
  if(!['music','quotes'].includes(kind))throw Error('未知控件');
  if(widgets.has(kind)){const existing=widgets.get(kind);existing.showInactive();applyLayer(existing,kind).catch(console.error);return;}
  const area=screen.getPrimaryDisplay().workArea;const win=new BrowserWindow({width:340,height:kind==='quotes'?240:180,x:area.x+area.width-365,y:area.y+(kind==='quotes'?40:300),frame:false,resizable:false,skipTaskbar:true,show:false,backgroundColor:'#f8f8f5',title:kind==='quotes'?'流光笺':'弦音余韵',webPreferences:{preload:path.join(__dirname,'widget-preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true}});
  widgets.set(kind,win);win.on('ready-to-show',()=>{win.showInactive();applyLayer(win,kind).catch(console.error);});win.loadFile(path.join(__dirname,'widget.html'),{query:{kind}});win.webContents.setWindowOpenHandler(()=>({action:'deny'}));win.webContents.on('will-navigate',e=>e.preventDefault());win.webContents.on('did-finish-load',()=>{broadcast();refreshQuote();});win.on('close',()=>nativeLayer.set(win,false).catch(()=>{}));win.on('closed',()=>{widgets.delete(kind);});
 }
 ipcMain.handle('dawn:media-configure',(e,options)=>{mainCaller(e);if(!options.music){command('pause');state={...state,playing:false};if(blocker!==undefined){powerSaveBlocker.stop(blocker);blocker=undefined;}}if(!options.quotes)quote={text:'请先安装流光笺。',author:'流光笺'};else refreshQuote();broadcast();return {};});
 ipcMain.handle('dawn:media-widget',(e,{kind})=>{mainCaller(e);widget(kind);return {};});
 ipcMain.handle('dawn:media-hide',e=>{mainCaller(e);setImmediate(()=>getWindow()?.close());return {};});
 ipcMain.handle('dawn:media-publish',(e,value)=>{mainCaller(e);state={id:String(value.id||''),name:String(value.name||'').slice(0,120),artist:String(value.artist||'').slice(0,120),playing:!!value.playing,position:Number(value.position)||0};
  if(state.playing&&blocker===undefined)blocker=powerSaveBlocker.start('prevent-app-suspension');
  if(!state.playing&&blocker!==undefined){powerSaveBlocker.stop(blocker);blocker=undefined;}
  tray?.setToolTip('破晓 · '+state.name+(state.playing?' · 播放中':' · 已暂停'));broadcast();return {};
 });
 ipcMain.handle('dawn:media-reset',e=>{mainCaller(e);command('pause');if(blocker!==undefined){powerSaveBlocker.stop(blocker);blocker=undefined;}state={name:'还没有播放音乐',playing:false};quote={text:'登录后显示今日语录。',author:'流光笺'};broadcast();return {};});
 ipcMain.on('widget:command',(e,value)=>{if(![...widgets.values()].some(w=>w.webContents===e.sender))return;if(value==='close')BrowserWindow.fromWebContents(e.sender)?.close();else if(value==='open')show();else if(value==='refresh')refreshQuote();else if(value==='voice'&&/^\/api\/plugins\/quotes\/audio\/[A-Za-z0-9_-]+$/.test(quote.audio||'')){const sender=e.sender;getWindow().webContents.session.fetch('dawn://app'+quote.audio,{credentials:'include'}).then(async r=>{if(!r.ok)throw Error();const bytes=new Uint8Array(await r.arrayBuffer());if(bytes.length>8*1024*1024)throw Error();if(!sender.isDestroyed())sender.send('widget:voice',{bytes});}).catch(()=>{if(!sender.isDestroyed())sender.send('widget:voice',{error:'语录暂时无法播放'});});}else if(['toggle','next','previous'].includes(value))command(value);});
 app.on('before-quit',()=>{quitting=true;nativeLayer.close();});
 return {attach(){const win=getWindow();win.on('close',e=>{if(!quitting){e.preventDefault();win.hide();}});tray=new Tray(path.join(__dirname,'icon.ico'));tray.setToolTip('破晓');tray.on('double-click',show);tray.setContextMenu(Menu.buildFromTemplate([{label:'打开破晓',click:show},{label:'流光笺控件',click:()=>widget('quotes')},{label:'弦音余韵控件',click:()=>widget('music')},{type:'separator'},{label:'播放 / 暂停',click:()=>command('toggle')},{label:'上一首',click:()=>command('previous')},{label:'下一首',click:()=>command('next')},{type:'separator'},{label:'退出破晓',click:()=>app.quit()}]));const timer=setInterval(refreshQuote,30*60*1000);timer.unref();}};
}
module.exports={registerMedia};
