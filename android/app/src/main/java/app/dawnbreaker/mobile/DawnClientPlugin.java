package app.dawnbreaker.mobile;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.Base64;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.ActivityCallback;
import androidx.activity.result.ActivityResult;
import android.app.Activity;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@CapacitorPlugin(name="DawnClient")
public class DawnClientPlugin extends Plugin {
    @PluginMethod public void setAtlasMode(PluginCall call){getActivity().runOnUiThread(()->{if(getActivity() instanceof MainActivity)((MainActivity)getActivity()).setAtlasMode(call.getBoolean("active",false));call.resolve();});}
    @PluginMethod public void setCompanionMode(PluginCall call){getActivity().runOnUiThread(()->{if(getActivity() instanceof MainActivity)((MainActivity)getActivity()).companionFullscreen=call.getBoolean("active",false);call.resolve();});}

    @PluginMethod public void saveText(PluginCall call){
        String filename=call.getString("filename","破晓导出.txt").replaceAll("[\\\\/:\\r\\n]","_");String mime=call.getString("mime","text/plain");String content=call.getString("content","");
        if(filename.length()>150||content.getBytes(StandardCharsets.UTF_8).length>48*1024*1024||!java.util.Arrays.asList("text/plain","text/markdown","text/csv","application/json").contains(mime)){call.reject("导出文件格式或大小无效");return;}
        Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType(mime);intent.putExtra(Intent.EXTRA_TITLE,filename);startActivityForResult(call,intent,"saveTextResult");
    }
    @ActivityCallback private void saveTextResult(PluginCall call,ActivityResult result){
        if(call==null)return;if(result.getResultCode()!=Activity.RESULT_OK||result.getData()==null||result.getData().getData()==null){call.resolve(new JSObject().put("cancelled",true));return;}
        try(OutputStream out=getContext().getContentResolver().openOutputStream(result.getData().getData())){if(out==null)throw new IOException();out.write(call.getString("content","").getBytes(StandardCharsets.UTF_8));call.resolve(new JSObject().put("saved",true));}catch(Exception e){call.reject("文件暂时无法保存，请重试");}
    }
    @PluginMethod public void savePhoto(PluginCall call){
        String filename=call.getString("filename","暗格照片.png").replaceAll("[\\\\/:\\r\\n]","_");String mime=call.getString("mime","");String data=call.getString("data","");
        try{if(filename.length()>150||data.length()>7*1024*1024||!Arrays.asList("image/png","image/jpeg","image/webp").contains(mime))throw new IOException();byte[] bytes=Base64.decode(data,Base64.NO_WRAP);if(bytes.length==0||bytes.length>5*1024*1024)throw new IOException();}catch(Exception e){call.reject("照片格式或大小无效");return;}
        Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType(mime);intent.putExtra(Intent.EXTRA_TITLE,filename);startActivityForResult(call,intent,"savePhotoResult");
    }
    @ActivityCallback private void savePhotoResult(PluginCall call,ActivityResult result){
        if(call==null)return;if(result.getResultCode()!=Activity.RESULT_OK||result.getData()==null||result.getData().getData()==null){call.resolve(new JSObject().put("cancelled",true));return;}
        executor.execute(()->{try(OutputStream out=getContext().getContentResolver().openOutputStream(result.getData().getData())){if(out==null)throw new IOException();out.write(Base64.decode(call.getString("data",""),Base64.NO_WRAP));call.resolve(new JSObject().put("saved",true));}catch(Exception e){call.reject("照片暂时无法保存，请重试");}});
    }
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile JSONObject release;
    private volatile File ready;
    private JSONObject readyManifest;
    private String currentVersion() throws Exception { return getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0).versionName; }
    private long currentCode() throws Exception {PackageInfo p=getContext().getPackageManager().getPackageInfo(getContext().getPackageName(),0);return Build.VERSION.SDK_INT>=28?p.getLongVersionCode():p.versionCode;}
    private String base() { return RemoteOrigin.base(bridge); }
    private boolean newer(String latest, String current) {
        String[] x=latest.split("\\."), y=current.split("\\.");
        for(int i=0;i<3;i++){int a=Integer.parseInt(x[i]),b=Integer.parseInt(y[i]);if(a!=b)return a>b;} return false;
    }
    private HttpURLConnection connect(String path) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(base()+path).openConnection();c.setConnectTimeout(20000);c.setReadTimeout(30000);c.setRequestProperty("Accept","application/json, application/octet-stream");
        if(c.getResponseCode()!=200){c.disconnect();throw new IOException("服务暂时不可用");}return c;
    }
    private byte[] read(InputStream input,int max) throws Exception {
        ByteArrayOutputStream output=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;
        while((n=input.read(buffer))!=-1){if(output.size()+n>max)throw new IOException("数据过大");output.write(buffer,0,n);}return output.toByteArray();
    }
    private JSONObject verify(JSONObject envelope) throws Exception {
        byte[] signed=Base64.decode(envelope.getString("signed"),Base64.DEFAULT);
        String pem;
        try(InputStream in=getContext().getResources().openRawResource(R.raw.update_public)){pem=new String(read(in,8192),StandardCharsets.UTF_8);}
        byte[] key=Base64.decode(pem.replace("-----BEGIN PUBLIC KEY-----","").replace("-----END PUBLIC KEY-----","").replaceAll("\\s",""),Base64.DEFAULT);
        Signature verifier=Signature.getInstance("SHA256withRSA");verifier.initVerify(KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(key)));verifier.update(signed);
        if(!verifier.verify(Base64.decode(envelope.getString("signature"),Base64.DEFAULT)))throw new SecurityException("更新签名验证失败");
        JSONObject value=new JSONObject(new String(signed,StandardCharsets.UTF_8));
        if(!value.getString("platform").equals("android")||!value.getString("version").matches("\\d+\\.\\d+\\.\\d+")||!value.getString("filename").matches("DawnBreaker-[A-Za-z0-9.-]+\\.apk")||!value.getString("sha256").matches("[a-f0-9]{64}")||value.getLong("size")<1||value.getLong("size")>250L*1024*1024||value.getLong("version_code")<1)throw new SecurityException("更新信息无效");
        return value;
    }
    private String digest(File file) throws Exception {
        MessageDigest hash=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)hash.update(buffer,0,n);}
        StringBuilder result=new StringBuilder();for(byte b:hash.digest())result.append(String.format("%02x",b&255));return result.toString();
    }
    @PluginMethod public void getInfo(PluginCall call){try{JSObject result=new JSObject();result.put("platform","android");result.put("version",currentVersion());result.put("release_sequence",currentCode());call.resolve(result);}catch(Exception e){call.reject("无法读取客户端版本");}}
    @PluginMethod public void checkUpdate(PluginCall call){executor.execute(()->{
        HttpURLConnection connection=null;
        try{connection=connect("/api/releases/android?current="+currentVersion()+"&current_code="+currentCode());JSONObject envelope;try(InputStream in=connection.getInputStream()){envelope=new JSONObject(new String(read(in,65536),StandardCharsets.UTF_8));}
            JSONObject selected=verify(envelope);release=selected;JSObject result=new JSObject();result.put("available",selected.getLong("version_code")>currentCode());result.put("latest",selected.getString("version"));result.put("notes",selected.optString("notes"));result.put("size",selected.getLong("size"));result.put("ready",ready!=null&&ready.exists()&&readyManifest.getString("version").equals(selected.getString("version")));call.resolve(result);
        }catch(Exception e){call.reject("检查更新失败："+e.getMessage());}finally{if(connection!=null)connection.disconnect();}
    });}
    @PluginMethod public void downloadUpdate(PluginCall call){executor.execute(()->{
        HttpURLConnection connection=null;
        try{JSONObject selected=release;if(selected==null||selected.getLong("version_code")<=currentCode())throw new IOException("请先检查更新");
            File folder=new File(getContext().getFilesDir(),"client-updates");if(!folder.exists()&&!folder.mkdirs())throw new IOException("无法准备更新目录");
            File file=new File(folder,selected.getString("filename"));
            if(!file.exists()||file.length()!=selected.getLong("size")||!digest(file).equals(selected.getString("sha256"))){
                File partial=new File(folder,file.getName()+".partial");connection=connect("/api/releases/android/download/"+selected.getString("version"));long total=0;
                try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(partial)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){total+=n;if(total>selected.getLong("size"))throw new IOException("安装包大小不匹配");out.write(buffer,0,n);JSObject event=new JSObject();event.put("percent",(int)(total*100/selected.getLong("size")));notifyListeners("updateProgress",event);}}
                if(total!=selected.getLong("size")||!digest(partial).equals(selected.getString("sha256")))throw new SecurityException("安装包校验失败");
                if(file.exists()&&!file.delete())throw new IOException("无法替换更新缓存");if(!partial.renameTo(file))throw new IOException("无法保存更新缓存");
            }
            readyManifest=selected;ready=file;JSObject result=new JSObject();result.put("ready",true);result.put("latest",selected.getString("version"));call.resolve(result);
        }catch(Exception e){call.reject("下载更新失败："+e.getMessage());}finally{if(connection!=null)connection.disconnect();}
    });}
    @PluginMethod public void installUpdate(PluginCall call){
        try{File file=ready;JSONObject selected=readyManifest;if(file==null||!file.exists()||!digest(file).equals(selected.getString("sha256")))throw new IOException("请重新下载并校验安装包");
            PackageManager pm=getContext().getPackageManager();PackageInfo archive=pm.getPackageArchiveInfo(file.getAbsolutePath(),PackageManager.GET_SIGNATURES);PackageInfo current=pm.getPackageInfo(getContext().getPackageName(),PackageManager.GET_SIGNATURES);
            if(archive==null||!archive.packageName.equals(current.packageName)||archive.signatures==null||current.signatures==null||!Arrays.equals(archive.signatures[0].toByteArray(),current.signatures[0].toByteArray()))throw new SecurityException("安装包与当前应用签名不匹配");
            long code=Build.VERSION.SDK_INT>=28?archive.getLongVersionCode():archive.versionCode;
            if(code!=selected.getLong("version_code"))throw new SecurityException("安装包版本不匹配");
            if(Build.VERSION.SDK_INT>=26&&!pm.canRequestPackageInstalls()){
                Intent settings=new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getContext().getPackageName()));getActivity().startActivity(settings);JSObject result=new JSObject();result.put("needsPermission",true);call.resolve(result);return;
            }
            Uri uri=FileProvider.getUriForFile(getContext(),getContext().getPackageName()+".fileprovider",file);
            Intent intent=new Intent(Intent.ACTION_VIEW);intent.setDataAndType(uri,"application/vnd.android.package-archive");intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);getActivity().startActivity(intent);JSObject result=new JSObject();result.put("installing",true);call.resolve(result);
        }catch(Exception e){call.reject("无法安装更新："+e.getMessage());}
    }
    @Override protected void handleOnDestroy(){executor.shutdown();}
}
