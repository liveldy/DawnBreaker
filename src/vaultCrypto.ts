import{gcm}from'@noble/ciphers/aes.js';import{pbkdf2Async}from'@noble/hashes/pbkdf2.js';import{sha256}from'@noble/hashes/sha2.js';
export const ITERATIONS=600000;
export const randomBytes=(size:number)=>{if(!globalThis.crypto?.getRandomValues)throw Error('当前浏览器不支持安全随机数，请使用新版浏览器或客户端。');return globalThis.crypto.getRandomValues(new Uint8Array(size));};
export const b64=(bytes:Uint8Array)=>{let text='';for(let i=0;i<bytes.length;i+=32768)text+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(text);};
export const unb64=(text:string)=>Uint8Array.from(atob(text),c=>c.charCodeAt(0));
export async function derive(password:string,salt:Uint8Array){return pbkdf2Async(sha256,new TextEncoder().encode(password),salt,{c:ITERATIONS,dkLen:32,asyncTick:10});}
export function encrypt(key:Uint8Array,uid:string,value:unknown,salt:Uint8Array,version:number){const nonce=randomBytes(12);return{version,salt:b64(salt),nonce:b64(nonce),ciphertext:b64(gcm(key,nonce,new TextEncoder().encode(uid)).encrypt(new TextEncoder().encode(JSON.stringify(value)))),iterations:ITERATIONS,algorithm:'PBKDF2-SHA256/AES-256-GCM'};}
export function decrypt(key:Uint8Array,uid:string,record:any){if(record.iterations!==ITERATIONS||record.algorithm!=='PBKDF2-SHA256/AES-256-GCM')throw Error('不支持的加密格式');return JSON.parse(new TextDecoder().decode(gcm(key,unb64(record.nonce),new TextEncoder().encode(uid)).decrypt(unb64(record.ciphertext))));}
export function generatePassword(){const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*+-_';let result='';const ceiling=65536-65536%alphabet.length;while(result.length<20){const bytes=randomBytes(2),n=(bytes[0]<<8)|bytes[1];if(n<ceiling)result+=alphabet[n%alphabet.length];}return result;}
