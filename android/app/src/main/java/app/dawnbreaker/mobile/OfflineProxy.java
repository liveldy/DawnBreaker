package app.dawnbreaker.mobile;
import android.content.*;
import android.net.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

final class OfflineProxy {
 private final Context context;private final String base;private long failedUntil;
 OfflineProxy(Context c,String origin){context=c.getApplicationContext();base=origin;}
 static SharedPreferences prefs(Context c){return c.getSharedPreferences("dawn-offline",Context.MODE_PRIVATE);}
 static File folder(Context c){String account=prefs(c).getString("account","");if(!account.matches("[a-f0-9]{32}"))account="anonymous";return new File(c.getFilesDir(),"offline-http/"+account);}
 static boolean connected(Context c){try{ConnectivityManager manager=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);NetworkCapabilities cap=manager.getNetworkCapabilities(manager.getActiveNetwork());return cap!=null&&cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);}catch(Exception e){return true;}}
 private boolean cacheable(String url){return url.equals("/api/bootstrap")||url.equals("/api/catalog")||url.startsWith("/api/plugins/library")||url.startsWith("/api/plugins/collection")||url.startsWith("/api/plugins/music")||url.startsWith("/api/plugins/atlas")||url.startsWith("/api/plugins/quotes")||url.startsWith("/api/profile/avatar/");}
 private File file(String url)throws Exception{StringBuilder hash=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(url.getBytes(StandardCharsets.UTF_8)))hash.append(String.format("%02x",b&255));return new File(folder(context),hash.toString());}
 static byte[] read(InputStream in,int max)throws IOException{if(in==null)return new byte[0];try(InputStream input=in;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] bytes=new byte[16384];int n;while((n=input.read(bytes))!=-1){if(out.size()+n>max)throw new IOException("large resource");out.write(bytes,0,n);}return out.toByteArray();}}
 static WebResourceResponse response(int status,Map<String,String> headers,byte[] body){String type=headers.getOrDefault("Content-Type","application/json").split(";")[0];return new WebResourceResponse(type,type.startsWith("text/")||type.contains("json")||type.contains("javascript")?"UTF-8":null,status,status>=200&&status<300?"OK":"Error",headers,new ByteArrayInputStream(body));}
 private WebResourceResponse cached(String url,Map<String,String> requestHeaders){
  if(!cacheable(url)||prefs(context).getString("account","").isEmpty())return null;
  try{File file=file(url);JSONObject meta=new JSONObject(new String(read(new FileInputStream(file+".json"),65536),StandardCharsets.UTF_8));byte[] bytes=read(new FileInputStream(file+".body"),24*1024*1024);Map<String,String> headers=new HashMap<>();JSONObject original=meta.getJSONObject("headers");for(Iterator<String> keys=original.keys();keys.hasNext();){String key=keys.next();headers.put(key,original.getString(key));}headers.put("X-Dawn-Offline","1");
   if(url.startsWith("/api/plugins/atlas/live")){JSONObject value=new JSONObject(new String(bytes,StandardCharsets.UTF_8));value.put("offline",true).put("stale",true);bytes=value.toString().getBytes(StandardCharsets.UTF_8);}
   String range=requestHeaders.get("Range");if(range==null)range=requestHeaders.get("range");if(range!=null&&range.matches("bytes=\\d+-\\d*")){String[] parts=range.substring(6).split("-",-1);int start=Integer.parseInt(parts[0]),end=parts[1].isEmpty()?bytes.length-1:Math.min(Integer.parseInt(parts[1]),bytes.length-1);if(start>=bytes.length||end<start)return response(416,Collections.singletonMap("Content-Range","bytes */"+bytes.length),new byte[0]);headers.put("Content-Range","bytes "+start+"-"+end+"/"+bytes.length);headers.put("Content-Length",String.valueOf(end-start+1));return response(206,headers,Arrays.copyOfRange(bytes,start,end+1));}
   headers.put("Content-Length",String.valueOf(bytes.length));return response(200,headers,bytes);
  }catch(Exception ignored){return null;}
 }
 WebResourceResponse get(String url,Map<String,String> requestHeaders){
  if(!connected(context)||System.currentTimeMillis()<failedUntil){WebResourceResponse cached=cached(url,requestHeaders);if(cached!=null)return cached;if(url.equals("/api/bootstrap")&&prefs(context).getString("account","").isEmpty())return response(401,Collections.singletonMap("Content-Type","application/json"),"{\"detail\":\"首次使用需联网登录\"}".getBytes(StandardCharsets.UTF_8));}
  HttpURLConnection connection=null;
  try{connection=(HttpURLConnection)new URL(base+url).openConnection();connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(5000);connection.setReadTimeout(30000);connection.setRequestProperty("Accept-Encoding","identity");String cookie=android.webkit.CookieManager.getInstance().getCookie(base+url);if(cookie!=null)connection.setRequestProperty("Cookie",cookie);
   for(Map.Entry<String,String> h:requestHeaders.entrySet()){String name=h.getKey().toLowerCase(Locale.ROOT);if(Arrays.asList("range","accept","user-agent").contains(name)&&!(name.equals("range")&&url.startsWith("/api/plugins/quotes/audio/")))connection.setRequestProperty(h.getKey(),h.getValue());}
   int status=connection.getResponseCode();Map<String,String> headers=new HashMap<>();for(Map.Entry<String,List<String>> h:connection.getHeaderFields().entrySet()){if(h.getKey()==null||h.getValue()==null)continue;String key=h.getKey();if(!Arrays.asList("set-cookie","content-encoding","content-length","transfer-encoding","connection").contains(key.toLowerCase(Locale.ROOT)))headers.put(key,String.join(", ",h.getValue()));}
   headers.put("Content-Type",connection.getContentType()==null?"application/json":connection.getContentType());byte[] bytes=read(status>=400?connection.getErrorStream():connection.getInputStream(),24*1024*1024);
   if(status==401&&url.equals("/api/bootstrap")){prefs(context).edit().remove("account").apply();context.stopService(new Intent(context,DawnMusicService.class));}
   if(status>=500){WebResourceResponse cached=cached(url,requestHeaders);if(cached!=null)return cached;}
   if(status==200&&url.equals("/api/bootstrap")){String uid=new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getJSONObject("user").getString("id");if(uid.matches("[a-f0-9]{32}"))prefs(context).edit().putString("account",uid).apply();}
   if(status==200&&cacheable(url)&&!prefs(context).getString("account","").isEmpty()){try{File target=file(url);target.getParentFile().mkdirs();File temporary=new File(target+".partial");try(FileOutputStream out=new FileOutputStream(temporary)){out.write(bytes);}if(!temporary.renameTo(new File(target+".body")))throw new IOException();JSONObject meta=new JSONObject().put("url",url).put("headers",new JSONObject(headers));try(FileOutputStream out=new FileOutputStream(target+".json")){out.write(meta.toString().getBytes(StandardCharsets.UTF_8));}}catch(Exception ignored){}}
   failedUntil=0;headers.put("Content-Length",String.valueOf(bytes.length));return response(status,headers,bytes);
  }catch(Exception e){failedUntil=System.currentTimeMillis()+5000;WebResourceResponse cached=cached(url,requestHeaders);if(cached!=null)return cached;if(url.equals("/api/bootstrap")&&prefs(context).getString("account","").isEmpty())return response(401,Collections.singletonMap("Content-Type","application/json"),"{\"detail\":\"首次使用需联网登录\"}".getBytes(StandardCharsets.UTF_8));return response(503,Collections.singletonMap("Content-Type","application/json"),"{\"detail\":\"网络不可用，这份内容尚未缓存\"}".getBytes(StandardCharsets.UTF_8));}
  finally{if(connection!=null)connection.disconnect();}
 }
 static void clear(Context c){File directory=folder(c);File[] files=directory.listFiles(f->f.getName().endsWith(".json"));if(files==null)return;for(File file:files){try{JSONObject meta=new JSONObject(new String(read(new FileInputStream(file),65536),StandardCharsets.UTF_8));String url=meta.optString("url");if(url.equals("/api/bootstrap")||url.equals("/api/catalog"))continue;new File(file.getPath().replaceFirst("\\.json$",".body")).delete();file.delete();}catch(Exception ignored){}}}
}
