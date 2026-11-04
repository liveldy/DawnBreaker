package app.dawnbreaker.mobile;
import android.app.*;
import android.appwidget.*;
import android.content.*;
import android.widget.RemoteViews;
import org.json.*;

public final class DawnWidgets {
 public static class QuoteWidget extends AppWidgetProvider {
  @Override public void onUpdate(Context c,AppWidgetManager m,int[] ids){update(c);final PendingResult result=goAsync();MediaStore.refreshQuote(c);MediaStore.IO.execute(result::finish);}
 }
 public static class MusicWidget extends AppWidgetProvider {@Override public void onUpdate(Context c,AppWidgetManager m,int[] ids){update(c);}}
 public static class Controls extends android.content.BroadcastReceiver {@Override public void onReceive(Context c,Intent intent){String action=intent.getAction();if("voice".equals(action)){try{androidx.core.content.ContextCompat.startForegroundService(c,new Intent(c,DawnQuoteService.class));}catch(Exception ignored){}return;}if("toggle".equals(action)||"next".equals(action)||"previous".equals(action))DawnMusicService.dispatch(c,action,0);}}
 static void update(Context c){
  AppWidgetManager m=AppWidgetManager.getInstance(c);
  for(boolean music:new boolean[]{false,true}){
   RemoteViews v=new RemoteViews(c.getPackageName(),music?R.layout.widget_music:R.layout.widget_quote);
   Intent open=new Intent(c,MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP);
   v.setOnClickPendingIntent(R.id.widget_open,PendingIntent.getActivity(c,20,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
   if(music){JSONObject s=DawnMusicService.instance==null?new JSONObject():DawnMusicService.instance.state();v.setTextViewText(R.id.widget_title,s.optString("name","还没有播放音乐"));v.setTextViewText(R.id.widget_author,s.optString("artist","打开弦音余韵选择歌曲"));v.setImageViewResource(R.id.widget_toggle,s.optBoolean("playing")?R.drawable.ic_widget_pause:R.drawable.ic_widget_play);v.setContentDescription(R.id.widget_toggle,s.optBoolean("playing")?"暂停":"播放");
    String[] actions={"previous","toggle","next"};int[] views={R.id.widget_previous,R.id.widget_toggle,R.id.widget_next};for(int i=0;i<3;i++)v.setOnClickPendingIntent(views[i],PendingIntent.getBroadcast(c,30+i,new Intent(c,Controls.class).setAction(actions[i]),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
   }else{try{JSONObject q=new JSONObject(MediaStore.prefs(c).getString("quote","{}"));v.setTextViewText(R.id.widget_title,q.optString("text","登录并安装流光笺，收下每日语录。"));v.setTextViewText(R.id.widget_author,q.optString("author","流光笺"));v.setViewVisibility(R.id.widget_voice,q.optString("audio","").startsWith("/api/plugins/quotes/audio/")?android.view.View.VISIBLE:android.view.View.GONE);v.setOnClickPendingIntent(R.id.widget_voice,PendingIntent.getBroadcast(c,40,new Intent(c,Controls.class).setAction("voice"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));}catch(Exception ignored){}}
   m.updateAppWidget(new ComponentName(c,music?MusicWidget.class:QuoteWidget.class),v);
  }
 }
}
