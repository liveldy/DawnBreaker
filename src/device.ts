import{Capacitor,registerPlugin}from'@capacitor/core';
declare global{interface Window{dawnDevice?:{action:(command:string,options?:any)=>Promise<any>}}}
const android=registerPlugin<{action:(v:{command:string;options:any})=>Promise<any>}>('DawnDevice');
export const devicePlatform=window.dawnDevice?'desktop':Capacitor.getPlatform()==='android'?'mobile':'web';
export const nativeDevice=devicePlatform!=='web';
export function device(command:string,options:any={}){if(window.dawnDevice)return window.dawnDevice.action(command,options);if(devicePlatform==='mobile')return android.action({command,options});return Promise.reject(new Error('请使用 Windows 或 Android 客户端。'));}

export const pluginAvailable=(plugin:{platforms?:string[]})=>!plugin.platforms||plugin.platforms.includes(devicePlatform);
