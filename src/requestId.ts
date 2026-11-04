/** UUID is optional on HTTP origins; getRandomValues works without a secure context. */
export function requestId():string{
 if(typeof globalThis.crypto?.randomUUID==='function')return globalThis.crypto.randomUUID();
 if(globalThis.crypto?.getRandomValues){const bytes=globalThis.crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');}
 return Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2);
}
