package app.dawnbreaker.mobile;
import android.webkit.CookieManager;
import com.getcapacitor.*;import com.getcapacitor.annotation.CapacitorPlugin;
@CapacitorPlugin(name="DawnOffline")
public class DawnOfflinePlugin extends Plugin {
 @PluginMethod public void info(PluginCall call){new PlaybackLedger(getContext()).sync();JSObject result=new JSObject();result.put("music_count",MusicCache.count(getContext()));result.put("cached_ids",MusicCache.ids(getContext()));result.put("sync_error",OfflineProxy.prefs(getContext()).getString("sync_error",""));result.put("sync_revision",OfflineProxy.prefs(getContext()).getString("sync_revision",""));result.put("pending_seconds",new PlaybackLedger(getContext()).pendingSeconds());call.resolve(result);}
 @PluginMethod public void clear(PluginCall call){MediaStore.IO.execute(()->{OfflineProxy.clear(getContext());MusicCache.clear(getContext());call.resolve();});}
 @PluginMethod public void logout(PluginCall call){getActivity().runOnUiThread(()->{CookieManager cookies=CookieManager.getInstance();cookies.setCookie(RemoteOrigin.base(bridge),"dawn_session=; Max-Age=0; Path=/");cookies.flush();OfflineProxy.prefs(getContext()).edit().remove("account").apply();call.resolve();});}
}
