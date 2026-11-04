package app.dawnbreaker.mobile;
import static org.junit.Assert.*;import org.junit.Test;import org.junit.runner.RunWith;import org.robolectric.RobolectricTestRunner;import org.robolectric.RuntimeEnvironment;import org.robolectric.annotation.Config;import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;import org.yaml.snakeyaml.Yaml;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class DeviceToolsTest{
 @Test public void importsCannotExposeControlListenersOrEscapeProviderDirectory()throws Exception{
  android.content.Context c=RuntimeEnvironment.getApplication();DawnWarpService.prepare(c,new JSONObject().put("name","local").put("yaml","allow-lan: true\nexternal-controller: 0.0.0.0:9090\nexternal-ui: /outside\nproxy-providers:\n  example:\n    type: http\n    url: https://example.com/subscribe\n    path: ../../escape.yaml\nproxies: []\nrules: [MATCH,DIRECT]\n"));
  Map<?,?> m;try(InputStream in=new FileInputStream(new File(DawnWarpService.root(c),"config.yaml"))){m=new Yaml().load(in);}
  assertEquals(false,m.get("allow-lan"));assertEquals("127.0.0.1",m.get("bind-address"));assertFalse(m.containsKey("external-controller"));assertFalse(m.containsKey("external-ui"));assertEquals(false,((Map<?,?>)m.get("tun")).get("enable"));String p=(String)((Map<?,?>)((Map<?,?>)m.get("proxy-providers")).get("example")).get("path");assertTrue(p.startsWith(DawnWarpService.root(c).getAbsolutePath()+File.separator));
 }
 @Test public void wallpaperProjectIsReusableAcrossPlatformsAndRejectsUnsafePaths()throws Exception{
  android.content.Context c=RuntimeEnvironment.getApplication();WallpaperProjects store=new WallpaperProjects(c,"");JSONObject made=store.create(new JSONObject().put("title","own wallpaper").put("variants",new JSONObject().put("desktop",new JSONObject().put("kind","web").put("markdown","<p>desktop</p>")).put("mobile",new JSONObject().put("kind","web").put("markdown","<p>mobile</p>"))));assertEquals(2,made.getJSONObject("manifest").getJSONObject("variants").length());assertTrue(store.pack(made.getString("id")).isFile());for(String p:new String[]{"../a","a/./b","a//b","C:/a","a\\b","CON.txt","a."})assertFalse(p,WallpaperProjects.safe(p));WallpaperProjects.remove(store.folder(made.getString("id")));
 }
}
