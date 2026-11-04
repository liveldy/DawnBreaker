package app.dawnbreaker.mobile;
import static org.junit.Assert.*;
import android.content.*;import android.net.*;import androidx.test.ext.junit.runners.AndroidJUnit4;import androidx.test.platform.app.InstrumentationRegistry;import org.junit.*;import org.junit.runner.RunWith;import org.json.*;import java.net.*;import java.io.*;
/** Opt-in device test. Grant VPN consent on a dedicated test emulator before running. */
@RunWith(AndroidJUnit4.class)
public class WarpIntegrationTest{
 @Test public void coldGeoRulesVpnTrafficRestartAndNativeGroups()throws Exception{
  Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();
  assertNull("Grant the test application's VPN consent first",VpnService.prepare(c));
  JSONObject profile=new JSONObject().put("name","Native integration DIRECT").put("yaml","geodata-mode: true\nproxies: []\nproxy-groups:\n  - name: QA\n    type: select\n    proxies: [DIRECT]\nrules:\n  - GEOSITE,cn,DIRECT\n  - GEOIP,CN,DIRECT\n  - MATCH,DIRECT\n");
  try{
   for(int attempt=0;attempt<2;attempt++){
    DawnWarpService.prepare(c,profile);androidx.core.content.ContextCompat.startForegroundService(c,new Intent(c,DawnWarpService.class));
    long deadline=System.currentTimeMillis()+140000;while(!DawnWarpService.running&&DawnWarpService.error.isEmpty()&&System.currentTimeMillis()<deadline)Thread.sleep(200);
    assertTrue("VPN failed: "+DawnWarpService.error,DawnWarpService.running);
    JSONObject state=DawnWarpService.status();assertTrue(state.getJSONObject("proxies").has("QA"));
    ConnectivityManager manager=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);boolean vpn=false;for(Network network:manager.getAllNetworks()){NetworkCapabilities caps=manager.getNetworkCapabilities(network);if(caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN))vpn=true;}assertTrue("System VPN transport is missing",vpn);
    HttpURLConnection request=(HttpURLConnection)new URL("http://example.com/").openConnection();request.setConnectTimeout(20000);request.setReadTimeout(20000);try{assertEquals(200,request.getResponseCode());try(InputStream in=request.getInputStream()){assertTrue(in.read()!=-1);}}finally{request.disconnect();}
    DawnWarpService.action(c,"warp.select",new JSONObject().put("group","QA").put("name","DIRECT"));DawnWarpService.action(c,"warp.mode",new JSONObject().put("mode","direct"));assertEquals("direct",DawnWarpService.status().getString("mode"));
    DawnWarpService.stop(c);Thread.sleep(1200);assertFalse(DawnWarpService.running);
   }
  }finally{DawnWarpService.stop(c);}
 }
}
