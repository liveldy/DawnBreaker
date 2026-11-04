package app.dawnbreaker.mobile;
import static org.junit.Assert.*;import org.junit.Test;import org.junit.runner.RunWith;import org.robolectric.RobolectricTestRunner;import org.robolectric.RuntimeEnvironment;import org.robolectric.annotation.Config;import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;import org.yaml.snakeyaml.Yaml;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class DeviceToolsTest{
 @Test public void cloudMessagesAreMainFrameAndOriginScoped(){
  assertTrue(DawnCloudActivity.messageAllowed(android.net.Uri.parse("https://pan.baidu.com"),true));assertFalse(DawnCloudActivity.messageAllowed(android.net.Uri.parse("https://pan.baidu.com"),false));assertFalse(DawnCloudActivity.messageAllowed(android.net.Uri.parse("https://pan.baidu.com.evil.example"),true));assertFalse(DawnCloudActivity.messageAllowed(android.net.Uri.parse("http://pan.baidu.com"),true));assertFalse(DawnCloudActivity.messageAllowed(android.net.Uri.parse("https://pan.baidu.com:8443"),true));
 }
 @Test public void importsCannotExposeControlListenersOrEscapeProviderDirectory()throws Exception{
  android.content.Context c=RuntimeEnvironment.getApplication();DawnWarpService.prepare(c,new JSONObject().put("name","local").put("yaml","allow-lan: true\nexternal-controller: 0.0.0.0:9090\nexternal-ui: /outside\nproxy-providers:\n  example:\n    type: http\n    url: https://example.com/subscribe\n    path: ../../escape.yaml\nproxies: []\nrules: [MATCH,DIRECT]\n"));
  Map<?,?> m;try(InputStream in=new FileInputStream(new File(DawnWarpService.root(c),"config.yaml"))){m=new Yaml().load(in);}
  assertEquals(false,m.get("allow-lan"));assertEquals("127.0.0.1",m.get("bind-address"));assertFalse(m.containsKey("external-controller"));assertFalse(m.containsKey("external-ui"));assertEquals(false,((Map<?,?>)m.get("tun")).get("enable"));String p=(String)((Map<?,?>)((Map<?,?>)m.get("proxy-providers")).get("example")).get("path");assertTrue(p.startsWith(DawnWarpService.root(c).getAbsolutePath()+File.separator));
 }

}
