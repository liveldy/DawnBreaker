package app.dawnbreaker.mobile;
import static org.junit.Assert.*;
import org.junit.Test;import org.junit.runner.RunWith;import org.robolectric.RobolectricTestRunner;import org.robolectric.RuntimeEnvironment;import org.robolectric.annotation.Config;
import android.content.*;import android.provider.Settings;import org.json.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class SystemToolsTest{
 @Test public void localSnapshotAndSettingsArePlatformScoped()throws Exception{
  Context context=RuntimeEnvironment.getApplication();org.robolectric.shadows.ShadowStatFs.registerStats(context.getFilesDir(),10000,5000,4000);JSONObject info=DawnSystemTools.info(context);
  assertEquals("mobile",info.getString("platform"));assertTrue(info.getJSONObject("memory").getLong("app")>=0);
  assertTrue(info.getJSONObject("storage").getLong("total")>0);assertFalse(info.getJSONObject("capabilities").getBoolean("task_manager"));
  Intent settings=DawnSystemTools.settingsIntent(context,"apps");assertEquals(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,settings.getAction());assertEquals("package:"+context.getPackageName(),settings.getDataString());
  try{DawnSystemTools.settingsIntent(context,"https://example.com");fail();}catch(IllegalArgumentException expected){}
  try{DawnSystemTools.action(context,"system.kill-process",new JSONObject().put("pid",1));fail();}catch(IllegalArgumentException expected){}
 }
 @Test public void memoryRequestDoesNotKillProcesses()throws Exception{
  JSONObject result=DawnSystemTools.action(RuntimeEnvironment.getApplication(),"system.trim-memory",new JSONObject());
  assertEquals(1,result.getInt("processed_count"));assertTrue(result.getLong("reclaimed_bytes")>=0);
 }
}
