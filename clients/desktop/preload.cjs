const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('dawnDevice',Object.freeze({action:(command,options={})=>ipcRenderer.invoke('dawn:device',command,options)}));
contextBridge.exposeInMainWorld('dawnOffline',Object.freeze({info:()=>ipcRenderer.invoke('dawn:offline-info'),clear:()=>ipcRenderer.invoke('dawn:offline-clear'),logout:()=>ipcRenderer.invoke('dawn:offline-logout')}));
contextBridge.exposeInMainWorld('dawnMedia',Object.freeze({
 configure:options=>ipcRenderer.invoke('dawn:media-configure',options),
 widget:options=>ipcRenderer.invoke('dawn:media-widget',options),
 hide:()=>ipcRenderer.invoke('dawn:media-hide'),
 publish:state=>ipcRenderer.invoke('dawn:media-publish',state),
 reset:()=>ipcRenderer.invoke('dawn:media-reset'),
 onCommand:callback=>{const fn=(_event,value)=>callback(value);ipcRenderer.on('dawn:media-command',fn);return()=>ipcRenderer.removeListener('dawn:media-command',fn);}
}));
contextBridge.exposeInMainWorld('dawnNative',Object.freeze({
  getInfo:()=>ipcRenderer.invoke('dawn:info'),
  checkUpdate:()=>ipcRenderer.invoke('dawn:check-update'),
  downloadUpdate:()=>ipcRenderer.invoke('dawn:download-update'),
  installUpdate:()=>ipcRenderer.invoke('dawn:install-update'),
  onProgress:(callback)=>{const listener=(_event,value)=>callback(value);ipcRenderer.on('dawn:update-progress',listener);return ()=>ipcRenderer.removeListener('dawn:update-progress',listener);}
}));
