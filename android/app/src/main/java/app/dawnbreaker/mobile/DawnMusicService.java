package app.dawnbreaker.mobile;
import android.app.*;
import android.content.*;
import android.media.*;
import android.media.session.*;
import android.os.*;
import android.net.Uri;
import androidx.core.content.ContextCompat;
import org.json.*;
import java.util.*;
import java.io.File;

/** Owns playback independently of the activity/WebView, with a system media session. */
public class DawnMusicService extends Service {
 static DawnMusicService instance;
 private MediaPlayer player;private MediaSession session;private AudioManager audio;private AudioFocusRequest focus;private boolean wantsPlaying=false;
 private final Handler handler=new Handler(Looper.getMainLooper());private JSONArray tracks=new JSONArray();private int index=0;private boolean prepared=false,resumeFocus=false;private String error="";
 private String listeningSession=UUID.randomUUID().toString();private double played=0;private long lastTick,lastReport;private boolean wasPlaying=false;private double unreported=0;private PlaybackLedger ledger;private double lastPosition=0;
 static void dispatch(Context c,String action,int index){Intent i=new Intent(c,DawnMusicService.class).setAction(action).putExtra("index",index);try{ContextCompat.startForegroundService(c,i);}catch(Exception e){if(instance!=null)instance.error="系统暂不允许后台播放，请打开破晓后重试。";}}
 private final BroadcastReceiver noisy=new BroadcastReceiver(){public void onReceive(Context c,Intent i){pause();}};
 private final AudioManager.OnAudioFocusChangeListener focusListener=change->{if(change==AudioManager.AUDIOFOCUS_LOSS){resumeFocus=false;pause();}else if(change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT){resumeFocus=isPlaying();pause();}else if(change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK)volume(.2f);else if(change==AudioManager.AUDIOFOCUS_GAIN){volume(.8f);if(resumeFocus){resumeFocus=false;play(index);}}};
 @Override public void onCreate(){super.onCreate();instance=this;ledger=new PlaybackLedger(this);audio=(AudioManager)getSystemService(AUDIO_SERVICE);
  if(Build.VERSION.SDK_INT>=26){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel("music","弦音余韵",NotificationManager.IMPORTANCE_LOW));focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setOnAudioFocusChangeListener(focusListener).build();}
  session=new MediaSession(this,"DawnMusic");session.setCallback(new MediaSession.Callback(){public void onPlay(){play(index);}public void onPause(){pause();}public void onSkipToNext(){step(1);}public void onSkipToPrevious(){step(-1);}public void onSeekTo(long p){seek(p/1000.0);}public void onStop(){stopSelf();}});session.setActive(true);
  if(Build.VERSION.SDK_INT>=33)registerReceiver(noisy,new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY),Context.RECEIVER_NOT_EXPORTED);else registerReceiver(noisy,new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY));
  lastTick=SystemClock.elapsedRealtime();lastReport=lastTick;report();handler.post(tick);
 }
 @Override public int onStartCommand(Intent intent,int flags,int id){
  startForeground(120,notification());
  if(!MediaStore.prefs(this).getBoolean("music",false)){stopSelf();return START_NOT_STICKY;}
  try{tracks=new JSONArray(MediaStore.prefs(this).getString("tracks","[]"));}catch(Exception ignored){}
  String action=intent==null?"pause":intent.getAction();
  if("next".equals(action))step(1);else if("previous".equals(action))step(-1);else if("toggle".equals(action)){if(isPlaying())pause();else play(index);}else if("play".equals(action))play(intent.getIntExtra("index",index));else pause();
  return START_NOT_STICKY;
 }
 private JSONObject track(){return tracks.optJSONObject(index)==null?new JSONObject():tracks.optJSONObject(index);}
 boolean isPlaying(){try{return prepared&&player!=null&&player.isPlaying();}catch(Exception e){return false;}}
 JSONObject state(){JSONObject s=new JSONObject();try{s.put("id",track().optString("id")).put("name",track().optString("name","弦音余韵")).put("artist",track().optString("artist")).put("playing",isPlaying()).put("position",prepared&&player!=null?player.getCurrentPosition()/1000.0:0).put("error",error);error="";}catch(Exception ignored){}return s;}
 void play(int requested){
  if(tracks.length()==0){error="请先打开弦音余韵并选择歌曲。";stopSelf();return;}wantsPlaying=true;handler.removeCallbacks(stopPaused);
  int next=Math.floorMod(requested,tracks.length());error="";
  startForeground(120,notification());
  int granted=Build.VERSION.SDK_INT>=26?audio.requestAudioFocus(focus):audio.requestAudioFocus(focusListener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN);
  if(granted!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED){error="其他应用正在使用音频，请稍后再试。";pause();return;}
  if(next==index&&player!=null&&prepared){player.start();publish();return;}
  releasePlayer();index=next;
  try{player=new MediaPlayer();player.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build());player.setWakeMode(this,PowerManager.PARTIAL_WAKE_LOCK);
   Map<String,String> headers=new HashMap<>();headers.put("Cookie",MediaStore.prefs(this).getString("cookie",""));
   File cached=MusicCache.file(this,track().optString("id"));if(cached!=null&&cached.isFile()){player.setDataSource(cached.getAbsolutePath());cached.setLastModified(System.currentTimeMillis());}else{if(!OfflineProxy.connected(this))throw new java.io.IOException("not cached");player.setDataSource(this,Uri.parse(MediaStore.prefs(this).getString("base","")+"/api/plugins/music/audio/"+track().optString("id")),headers);MusicCache.download(this,track().optString("id"));}
   player.setOnPreparedListener(p->{prepared=true;if(wantsPlaying)p.start();publish();});player.setOnCompletionListener(p->step(1,true));player.setOnErrorListener((p,w,e)->{error="歌曲暂时无法读取，请重新选择。";releasePlayer();publish();stopForeground(false);return true;});player.prepareAsync();publish();
  }catch(Exception e){error="音频暂时无法播放，请检查连接。";releasePlayer();publish();stopForeground(false);}
 }
 void pause(){report();wantsPlaying=false;if(isPlaying())player.pause();publish();stopForeground(false);handler.removeCallbacks(stopPaused);handler.postDelayed(stopPaused,600000);}
 private final Runnable stopPaused=()->{if(!isPlaying())stopSelf();};
 void step(int delta){step(delta,false);}
 void step(int delta,boolean automatic){
  int n=tracks.length();if(n==0)return;
  String mode=MediaStore.prefs(this).getString("playback_mode","sequence");
  if(automatic&&mode.equals("sequence")&&index==n-1){pause();return;}
  int next=automatic&&mode.equals("single")?index:Math.floorMod(index+delta,n);
  if(mode.equals("random")&&n>1){next=new java.security.SecureRandom().nextInt(n-1);if(next>=index)next++;}
  if(next==index)releasePlayer();play(next);
 }
 void seek(double seconds){if(prepared&&player!=null&&Double.isFinite(seconds)){report();lastPosition=seconds;player.seekTo((int)Math.max(0,Math.min(seconds*1000,player.getDuration())));publish();}}
 void volume(float value){if(player!=null){float v=Math.max(0,Math.min(1,value));player.setVolume(v,v);}}
 private void releasePlayer(){report();lastPosition=0;prepared=false;if(player!=null){player.release();player=null;}}
 private PendingIntent command(String action,int request){return PendingIntent.getService(this,request,new Intent(this,DawnMusicService.class).setAction(action),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
 private Notification notification(){
  PendingIntent open=PendingIntent.getActivity(this,10,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(this,"music"):new Notification.Builder(this);
  return b.setSmallIcon(R.drawable.ic_music).setContentTitle(track().optString("name","弦音余韵")).setContentText(track().optString("artist","破晓")).setContentIntent(open).setVisibility(Notification.VISIBILITY_PUBLIC).setOnlyAlertOnce(true).setOngoing(isPlaying()).setStyle(new Notification.MediaStyle().setMediaSession(session.getSessionToken()).setShowActionsInCompactView(0,1,2)).addAction(new Notification.Action.Builder(android.R.drawable.ic_media_previous,"上一首",command("previous",11)).build()).addAction(new Notification.Action.Builder(isPlaying()?android.R.drawable.ic_media_pause:android.R.drawable.ic_media_play,isPlaying()?"暂停":"播放",command("toggle",12)).build()).addAction(new Notification.Action.Builder(android.R.drawable.ic_media_next,"下一首",command("next",13)).build()).build();
 }
 private void publish(){if(session==null)return;long position=prepared&&player!=null?player.getCurrentPosition():0;
  session.setPlaybackState(new PlaybackState.Builder().setActions(PlaybackState.ACTION_PLAY|PlaybackState.ACTION_PAUSE|PlaybackState.ACTION_PLAY_PAUSE|PlaybackState.ACTION_SKIP_TO_NEXT|PlaybackState.ACTION_SKIP_TO_PREVIOUS|PlaybackState.ACTION_SEEK_TO|PlaybackState.ACTION_STOP).setState(isPlaying()?PlaybackState.STATE_PLAYING:PlaybackState.STATE_PAUSED,position,isPlaying()?1:0).build());
  session.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,track().optString("name","弦音余韵")).putString(MediaMetadata.METADATA_KEY_ARTIST,track().optString("artist")).putLong(MediaMetadata.METADATA_KEY_DURATION,(long)(track().optDouble("duration",0)*1000)).build());
  ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(120,notification());DawnWidgets.update(this);
 }
 private final Runnable tick=new Runnable(){public void run(){long now=SystemClock.elapsedRealtime();boolean playing=isPlaying();double position=0;try{position=prepared&&player!=null?player.getCurrentPosition()/1000.0:0;}catch(Exception ignored){}if(playing&&wasPlaying&&position>lastPosition&&position-lastPosition<=(now-lastTick)/1000.0+.5){double seconds=Math.min(Math.min((now-lastTick)/1000.0,2),position-lastPosition+.1);played+=seconds;unreported+=seconds;}wasPlaying=playing;lastPosition=position;lastTick=now;if(now-lastReport>=10000){lastReport=now;report();}handler.postDelayed(this,1000);}};
 private void report(){if(ledger==null)return;if(unreported>.1){double value=unreported;unreported=0;ledger.add(track().optString("id"),value,System.currentTimeMillis()/1000.0);}ledger.sync();}
 @Override public void onDestroy(){handler.removeCallbacksAndMessages(null);report();releasePlayer();if(Build.VERSION.SDK_INT>=26)audio.abandonAudioFocusRequest(focus);else audio.abandonAudioFocus(focusListener);session.release();unregisterReceiver(noisy);instance=null;stopForeground(true);DawnWidgets.update(this);super.onDestroy();}
 @Override public IBinder onBind(Intent i){return null;}
}
