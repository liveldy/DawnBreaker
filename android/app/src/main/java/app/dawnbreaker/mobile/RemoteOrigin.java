package app.dawnbreaker.mobile;
import com.getcapacitor.Bridge;
final class RemoteOrigin {
 static String base(Bridge bridge){String url=bridge.getServerUrl();return url!=null&&!url.contains("localhost")?url.replaceAll("/+$",""):"http://110.42.63.153:7780";}
}
