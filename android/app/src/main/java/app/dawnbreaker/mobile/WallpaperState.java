package app.dawnbreaker.mobile;
import android.content.Context;import android.util.AtomicFile;import org.json.JSONObject;import java.io.*;import java.nio.channels.*;import java.nio.charset.StandardCharsets;
// SharedPreferences caches are per process. Wallpaper engines run separately from the app.
final class WallpaperState{
 private static AtomicFile file(Context c){return new AtomicFile(new File(c.getFilesDir(),"wallpaper-state.json"));}
 static synchronized JSONObject read(Context c){try(InputStream in=file(c).openRead()){return new JSONObject(new String(DawnWarpService.read(in,65536),StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
 static synchronized void update(Context c,JSONObject changes)throws Exception{try(RandomAccessFile lock=new RandomAccessFile(new File(c.getFilesDir(),"wallpaper-state.lock"),"rw");FileLock guard=lock.getChannel().lock()){JSONObject value=read(c);for(java.util.Iterator<String> keys=changes.keys();keys.hasNext();){String key=keys.next();value.put(key,changes.get(key));}AtomicFile target=file(c);FileOutputStream out=target.startWrite();try{out.write(value.toString().getBytes(StandardCharsets.UTF_8));target.finishWrite(out);}catch(Exception e){target.failWrite(out);throw e;}}}
}
