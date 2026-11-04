package app.dawnbreaker.mobile;
import android.app.*;import android.content.*;import android.media.*;import android.os.*;import android.webkit.WebResourceResponse;import org.json.*;import java.io.*;import java.util.*;
/** Short widget voice playback with transient audio focus, independent of WebView. */
public class DawnQuoteService extends Service {
 private MediaPlayer player;private AudioManager audio;private AudioFocusRequest focus;private int generation;private File temporary;
 @Override public void onCreate(){super.onCreate();audio=(AudioManager)getSystemService(AUDIO_SERVICE);if(Build.VERSION.SDK_INT>=26){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel("quote-voice","流光笺语音",NotificationManager.IMPORTANCE_LOW));focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT).setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()).setOnAudioFocusChangeListener(change->{if(change==AudioManager.AUDIOFOCUS_LOSS||change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT)stopSelf();}).build();}}
 @Override public int onStartCommand(Intent intent,int flags,int start){
  Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(this,"quote-voice"):new Notification.Builder(this);startForeground(121,b.setSmallIcon(R.drawable.ic_music).setContentTitle("流光笺").setContentText("正在播放语录").setOnlyAlertOnce(true).build());
  final int token=++generation;final String account=MediaStore.prefs(this).getString("account","");MediaStore.IO.execute(()->{try{
   if(!MediaStore.prefs(this).getBoolean("quotes",false))throw new IOException();JSONObject quote=new JSONObject(MediaStore.prefs(this).getString("quote","{}"));String path=quote.optString("audio","");if(!path.matches("/api/plugins/quotes/audio/[A-Za-z0-9_.-]+"))throw new IOException();
   OfflineProxy proxy=new OfflineProxy(this,MediaStore.prefs(this).getString("base",""));WebResourceResponse response=proxy.get(path,Collections.emptyMap());if(response.getStatusCode()!=200)throw new IOException();byte[] bytes=OfflineProxy.read(response.getData(),8*1024*1024);
   File file=File.createTempFile("quote-voice-",".mp3",getCacheDir());try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}new Handler(Looper.getMainLooper()).post(()->{if(token!=generation||!account.equals(MediaStore.prefs(this).getString("account",""))){file.delete();return;}try{if(player!=null)player.release();if(temporary!=null)temporary.delete();temporary=file;
    if(Build.VERSION.SDK_INT>=26&&audio.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED)throw new IOException();player=new MediaPlayer();player.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());player.setDataSource(file.getAbsolutePath());player.setOnPreparedListener(MediaPlayer::start);player.setOnCompletionListener(p->stopSelf());player.setOnErrorListener((p,w,e)->{stopSelf();return true;});player.prepareAsync();}catch(Exception e){stopSelf();}});
  }catch(Exception e){stopSelf(start);}});return START_NOT_STICKY;
 }
 @Override public void onDestroy(){generation++;if(player!=null)player.release();if(temporary!=null)temporary.delete();if(Build.VERSION.SDK_INT>=26)audio.abandonAudioFocusRequest(focus);stopForeground(true);super.onDestroy();}
 @Override public IBinder onBind(Intent intent){return null;}
}
