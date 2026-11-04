package app.dawnbreaker.mobile;
import static org.junit.Assert.*;
import android.app.*;
import android.content.*;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Looper;
import android.view.View;
import android.widget.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ServiceController;
import org.robolectric.annotation.*;
import org.robolectric.shadows.*;
import org.robolectric.shadows.util.DataSource;
import java.time.Duration;
import java.util.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
@LooperMode(LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.LEGACY)
public class MediaServiceTest {
 @Test public void nativePlaybackSurvivesWithoutAnActivityAndHonorsPauseSeekAndNext() throws Exception {
  Context c=RuntimeEnvironment.getApplication();String base="http://127.0.0.1:9";
  MediaStore.prefs(c).edit().putBoolean("music",true).putString("base",base).putString("cookie","test-only")
   .putString("tracks","[{\"id\":\"001\",\"name\":\"第一首\",\"artist\":\"歌者\",\"duration\":180},{\"id\":\"002\",\"name\":\"第二首\",\"artist\":\"歌者\",\"duration\":180}]").commit();
  MediaStore.prefs(c).edit().putString("account","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa").commit();
  Map<String,String> headers=new HashMap<>();headers.put("Cookie","test-only");
  for(String id:new String[]{"001","002"}){java.io.File file=MusicCache.file(c,id);file.getParentFile().mkdirs();try(java.io.FileOutputStream out=new java.io.FileOutputStream(file)){out.write(new byte[100]);}ShadowMediaPlayer.addMediaInfo(DataSource.toDataSource(file.getAbsolutePath()),new ShadowMediaPlayer.MediaInfo(180000,100));}
  ServiceController<DawnMusicService> controller=Robolectric.buildService(DawnMusicService.class).create();DawnMusicService service=controller.get();
  try{
   service.onStartCommand(new Intent(c,DawnMusicService.class).setAction("play").putExtra("index",0),0,1);
   Shadows.shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(150));
   assertTrue(service.isPlaying());assertEquals("001",service.state().getString("id"));
   service.seek(30);Shadows.shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(150));assertTrue(service.state().getDouble("position")>=30);
   service.pause();assertFalse(service.isPlaying());service.play(0);assertTrue(service.isPlaying());
   service.step(1);Shadows.shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(150));assertTrue(service.isPlaying());assertEquals("002",service.state().getString("id"));
   NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
   Notification n=Shadows.shadowOf(manager).getNotification(120);assertNotNull(n);assertEquals(3,n.actions.length);assertNotNull(n.extras.getParcelable(Notification.EXTRA_MEDIA_SESSION));
  }finally{controller.destroy();}
  assertNull(DawnMusicService.instance);
 }
 @Test public void widgetLayoutsExposeQuoteAndThreePlaybackActions(){
  Context c=RuntimeEnvironment.getApplication();
  View quote=new RemoteViews(c.getPackageName(),R.layout.widget_quote).apply(c,new FrameLayout(c));
  assertNotNull(quote.findViewById(R.id.widget_title));assertNotNull(quote.findViewById(R.id.widget_author));assertTrue(quote.findViewById(R.id.widget_voice) instanceof ImageButton);
  View music=new RemoteViews(c.getPackageName(),R.layout.widget_music).apply(c,new FrameLayout(c));
  for(int id:new int[]{R.id.widget_previous,R.id.widget_toggle,R.id.widget_next})assertTrue(music.findViewById(id) instanceof ImageButton);
 }
}
