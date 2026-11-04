package app.dawnbreaker.mobile;
import android.Manifest;
import android.appwidget.AppWidgetManager;
import android.content.*;
import android.os.Build;
import android.webkit.CookieManager;
import com.getcapacitor.*;
import com.getcapacitor.annotation.*;
import org.json.*;

@CapacitorPlugin(name="DawnMedia",permissions={@Permission(alias="notifications",strings={Manifest.permission.POST_NOTIFICATIONS})})
public class DawnMediaPlugin extends Plugin {
 @PluginMethod public void configure(PluginCall call){
  String base=RemoteOrigin.base(bridge);String cookie=CookieManager.getInstance().getCookie(base);String account=call.getString("account","");
  SharedPreferences p=MediaStore.prefs(getContext());
  if(!account.equals(p.getString("account",""))){getContext().stopService(new Intent(getContext(),DawnMusicService.class));String mode=p.getString("playback_mode","sequence");p.edit().clear().putString("playback_mode",mode).apply();}
  p.edit().putString("base",base).putString("cookie",cookie==null?"":cookie).putString("account",account).putBoolean("music",call.getBoolean("music",false)).putBoolean("quotes",call.getBoolean("quotes",false)).apply();
  if(!call.getBoolean("music",false))getContext().stopService(new Intent(getContext(),DawnMusicService.class));
  MediaStore.refreshQuote(getContext());new PlaybackLedger(getContext()).sync();call.resolve();
 }
 @PluginMethod public void playlist(PluginCall call){
  try{JSArray input=call.getArray("tracks");if(input==null||input.length()>500)throw new Exception();JSONArray tracks=new JSONArray();
   for(int i=0;i<input.length();i++){JSONObject t=input.getJSONObject(i);String id=t.getString("id");if(!id.matches("[a-zA-Z0-9_-]{1,80}"))throw new Exception();tracks.put(new JSONObject().put("id",id).put("name",t.getString("name").substring(0,Math.min(120,t.getString("name").length()))).put("artist",t.optString("artist")).put("duration",t.optDouble("duration")));}
   MediaStore.prefs(getContext()).edit().putString("tracks",tracks.toString()).apply();call.resolve();
  }catch(Exception e){call.reject("播放列表无效");}
 }
 @PluginMethod public void play(PluginCall call){if(Build.VERSION.SDK_INT>=33&&getPermissionState("notifications")!=PermissionState.GRANTED){requestPermissionForAlias("notifications",call,"notificationResult");return;}startPlay(call);}
 @PermissionCallback private void notificationResult(PluginCall call){startPlay(call);}
 private void startPlay(PluginCall call){getActivity().runOnUiThread(()->{DawnMusicService.dispatch(getContext(),"play",call.getInt("index",0));call.resolve();});}
 @PluginMethod public void pause(PluginCall call){getActivity().runOnUiThread(()->{if(DawnMusicService.instance!=null)DawnMusicService.instance.pause();call.resolve();});}
 @PluginMethod public void seek(PluginCall call){getActivity().runOnUiThread(()->{if(DawnMusicService.instance!=null)DawnMusicService.instance.seek(call.getDouble("seconds",0.0));call.resolve();});}
 @PluginMethod public void volume(PluginCall call){getActivity().runOnUiThread(()->{if(DawnMusicService.instance!=null)DawnMusicService.instance.volume(call.getDouble("value",0.8).floatValue());call.resolve();});}
 @PluginMethod public void playbackMode(PluginCall call){String mode=call.getString("mode","sequence");if(!mode.equals("sequence")&&!mode.equals("random")&&!mode.equals("single")){call.reject("播放模式无效");return;}MediaStore.prefs(getContext()).edit().putString("playback_mode",mode).apply();call.resolve();}
 @PluginMethod public void step(PluginCall call){getActivity().runOnUiThread(()->{if(DawnMusicService.instance!=null)DawnMusicService.instance.step(call.getInt("delta",1),call.getBoolean("automatic",false));call.resolve();});}
 @PluginMethod public void getState(PluginCall call){getActivity().runOnUiThread(()->{JSObject value=new JSObject();DawnMusicService s=DawnMusicService.instance;if(s!=null){JSONObject state=s.state();for(java.util.Iterator<String> it=state.keys();it.hasNext();){String k=it.next();value.put(k,state.opt(k));}}call.resolve(value);});}
 @PluginMethod public void reset(PluginCall call){getContext().stopService(new Intent(getContext(),DawnQuoteService.class));getContext().stopService(new Intent(getContext(),DawnMusicService.class));MediaStore.prefs(getContext()).edit().clear().apply();DawnWidgets.update(getContext());call.resolve();}
 @PluginMethod public void widget(PluginCall call){String kind=call.getString("kind","");if(!kind.equals("quotes")&&!kind.equals("music")){call.reject("未知控件");return;}JSObject result=new JSObject();
  AppWidgetManager manager=AppWidgetManager.getInstance(getContext());
  if(Build.VERSION.SDK_INT>=26&&manager.isRequestPinAppWidgetSupported()){manager.requestPinAppWidget(new ComponentName(getContext(),kind.equals("quotes")?DawnWidgets.QuoteWidget.class:DawnWidgets.MusicWidget.class),null,null);result.put("message","请在桌面确认添加控件。");}
  else result.put("message","请长按系统桌面，在小组件列表中添加破晓控件。");call.resolve(result);
 }
}
