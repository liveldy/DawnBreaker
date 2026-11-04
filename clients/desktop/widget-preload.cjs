const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('dawnWidget',{setLayer:value=>ipcRenderer.invoke('widget:layer',value),command:value=>ipcRenderer.send('widget:command',value),onState:cb=>ipcRenderer.on('widget:state',(_event,value)=>cb(value)),onVoice:cb=>ipcRenderer.on('widget:voice',(_event,value)=>cb(value))});
