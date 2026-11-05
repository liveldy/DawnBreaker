package app.dawnbreaker.mobile;
import static org.junit.Assert.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import android.content.Context;import android.os.Process;import org.junit.Test;import org.junit.runner.RunWith;import org.json.JSONObject;
@RunWith(AndroidJUnit4.class)
public class SystemIntegrationTest {
 @Test public void readsRealDeviceResourcesAndKeepsProcessAlive()throws Exception{
  Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();int before=Process.myPid();
  JSONObject info=DawnSystemTools.action(context,"system.info",new JSONObject());
  assertEquals("mobile",info.getString("platform"));assertTrue(info.getJSONObject("memory").getLong("total")>0);assertTrue(info.getJSONObject("memory").getLong("available")>0);assertTrue(info.getJSONObject("storage").getLong("total")>0);assertTrue(info.getJSONArray("displays").length()>0);
  try(java.io.FileOutputStream out=new java.io.FileOutputStream(new java.io.File(context.getCacheDir(),"system-info-qa.json"))){out.write(info.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
  JSONObject trim=DawnSystemTools.action(context,"system.trim-memory",new JSONObject());assertEquals(before,Process.myPid());assertTrue(trim.getLong("reclaimed_bytes")>=0);assertTrue(DawnSystemTools.info(context).getJSONObject("memory").getLong("app")>0);
  assertEquals("android.settings.APPLICATION_DETAILS_SETTINGS",DawnSystemTools.settingsIntent(context,"apps").getAction());
  try{DawnSystemTools.action(context,"system.kill-process",new JSONObject().put("pid",1));fail();}catch(IllegalArgumentException expected){}
 }
}
