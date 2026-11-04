package app.dawnbreaker.mobile;
import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.*;
import java.util.concurrent.*;

final class MediaStore {
 static final ExecutorService IO=Executors.newSingleThreadExecutor();
 static SharedPreferences prefs(Context c){return c.getSharedPreferences("dawn-media",Context.MODE_PRIVATE);}
 static JSONObject request(Context c,String path,JSONObject body)throws Exception{
  SharedPreferences p=prefs(c);String base=p.getString("base","");
  if(!path.startsWith("/api/plugins/")||base.isEmpty())throw new IOException();
  HttpURLConnection conn=(HttpURLConnection)new URL(base+path).openConnection();
  conn.setInstanceFollowRedirects(false);conn.setConnectTimeout(8000);conn.setReadTimeout(8000);conn.setRequestProperty("Cookie",p.getString("cookie",""));
  try{if(body!=null){conn.setRequestMethod("POST");conn.setDoOutput(true);conn.setRequestProperty("Content-Type","application/json");try(OutputStream out=conn.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}}
   if(conn.getResponseCode()!=200)throw new IOException("not authorized");
   try(InputStream in=conn.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){if(out.size()+n>1048576)throw new IOException();out.write(b,0,n);}return new JSONObject(out.toString("UTF-8"));}
  }finally{conn.disconnect();}
 }
 static void refreshQuote(Context c){final String account=prefs(c).getString("account","");IO.execute(()->{
  try{if(!prefs(c).getBoolean("quotes",false))throw new IOException();JSONObject q=request(c,"/api/plugins/quotes",null);if(!account.equals(prefs(c).getString("account","")))return;prefs(c).edit().putString("quote",q.toString()).apply();}
  catch(Exception e){if(account.equals(prefs(c).getString("account",""))&&!prefs(c).getBoolean("quotes",false))prefs(c).edit().remove("quote").apply();}
  DawnWidgets.update(c);
 });}
}
