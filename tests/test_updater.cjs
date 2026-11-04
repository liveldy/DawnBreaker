const assert=require('node:assert/strict');const crypto=require('node:crypto');
const {verifyRelease,newer,updateAvailable,installScript}=require('../clients/desktop/updater.cjs');
const {publicKey,privateKey}=crypto.generateKeyPairSync('rsa',{modulusLength:2048});
const valid={platform:'windows',version:'1.1.0',filename:'DawnBreaker-1.1.0-Windows.exe',size:1000,sha256:'a'.repeat(64)};
const sign=value=>{const bytes=Buffer.from(JSON.stringify(value));return {signed:bytes.toString('base64'),signature:crypto.sign('RSA-SHA256',bytes,privateKey).toString('base64')};};
assert.equal(verifyRelease(sign(valid),publicKey).version,'1.1.0');
const tampered=sign(valid);tampered.signed=Buffer.from(JSON.stringify({...valid,version:'9.9.9'})).toString('base64');assert.throws(()=>verifyRelease(tampered,publicKey),/签名/);
assert.throws(()=>verifyRelease(sign({...valid,platform:'android'}),publicKey));
assert.throws(()=>verifyRelease(sign({...valid,filename:'../outside.exe'}),publicKey));
assert.throws(()=>verifyRelease(sign({...valid,size:9999999999}),publicKey));
assert(newer('1.10.0','1.9.9'));assert(!newer('1.0.0','1.1.0'));assert(!newer('1.1.0','1.1.0'));
const script=installScript({pid:12345,target:'D:\\with spaces\\DawnBreaker.exe',source:'D:\\cache\\update.exe',sha256:'a'.repeat(64)});
assert(script.includes('Get-FileHash -LiteralPath'));assert(!script.includes('Remove-Item'));assert(!script.includes('ExecutionPolicy'));assert(script.includes('Wait-Process'));
console.log('Updater checks passed: signatures, tamper rejection, platform/path/size guards, semantic version comparison and replacement script');

assert(updateAvailable({version:'1.0.0',version_code:7},'1.3.0',6));assert(!updateAvailable({version:'1.0.0',version_code:7},'1.0.0',7));assert(updateAvailable({version:'1.0.1',version_code:8},'1.0.0',7));
