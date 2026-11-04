package app.dawnbreaker.mobile;
import android.webkit.*;import com.getcapacitor.*;
public final class OfflineWebViewClient extends BridgeWebViewClient {
 private final OfflineProxy proxy;
 public OfflineWebViewClient(Bridge bridge){super(bridge);proxy=new OfflineProxy(bridge.getContext(),RemoteOrigin.base(bridge));}
 @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){if("localhost".equals(request.getUrl().getHost())&&request.getUrl().getPath().startsWith("/api/")&&"GET".equals(request.getMethod())){String path=request.getUrl().getEncodedPath();if(request.getUrl().getEncodedQuery()!=null)path+="?"+request.getUrl().getEncodedQuery();return proxy.get(path,request.getRequestHeaders());}return super.shouldInterceptRequest(view,request);}
}
