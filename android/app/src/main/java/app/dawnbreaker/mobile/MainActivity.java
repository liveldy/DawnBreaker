package app.dawnbreaker.mobile;

import com.getcapacitor.BridgeActivity;
import android.app.DownloadManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.widget.Toast;

public class MainActivity extends BridgeActivity {
    boolean atlasFullscreen=false;
    boolean companionFullscreen=false;
    private int atlasPreviousOrientation=android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED;
    void setAtlasMode(boolean active){
        if(active&&!atlasFullscreen){atlasPreviousOrientation=getRequestedOrientation();atlasFullscreen=true;setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);}
        else if(!active&&atlasFullscreen){atlasFullscreen=false;setRequestedOrientation(atlasPreviousOrientation);}
    }

    @Override
    protected void load() {
        // Build JS plugin headers only after adding the app's native plugin.
        registerPlugin(DawnClientPlugin.class);
        registerPlugin(DawnMediaPlugin.class);
        registerPlugin(DawnOfflinePlugin.class);
        registerPlugin(DawnDevicePlugin.class);
        super.load();
        if(bridge!=null)bridge.getWebView().setWebViewClient(new OfflineWebViewClient(bridge));
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (bridge == null) return;
        getOnBackPressedDispatcher().addCallback(this,new androidx.activity.OnBackPressedCallback(true){
            @Override public void handleOnBackPressed(){
                if(companionFullscreen){companionFullscreen=false;bridge.triggerJSEvent("dawn:exit-companion","window");}
                else if(atlasFullscreen){setAtlasMode(false);bridge.triggerJSEvent("dawn:exit-atlas","window");}
                else{setEnabled(false);getOnBackPressedDispatcher().onBackPressed();setEnabled(true);}
            }
        });
        bridge.getWebView().setDownloadListener((url, userAgent, disposition, mime, length) -> {
            Uri base = Uri.parse(RemoteOrigin.base(bridge));
            Uri incoming=Uri.parse(url);
            if("localhost".equals(incoming.getHost())&&incoming.getPath().startsWith("/api/"))url=RemoteOrigin.base(bridge)+incoming.getEncodedPath()+(incoming.getEncodedQuery()!=null?"?"+incoming.getEncodedQuery():"");
            Uri source = Uri.parse(url);
            if (!java.util.Objects.equals(source.getScheme(), base.getScheme())
                || !java.util.Objects.equals(source.getHost(), base.getHost())
                || source.getPort() != base.getPort()) return;
            try {
                DownloadManager.Request request = new DownloadManager.Request(source);
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) request.addRequestHeader("Cookie", cookies);
                if (userAgent != null) request.addRequestHeader("User-Agent", userAgent);
                if (mime != null) request.setMimeType(mime);
                String name = URLUtil.guessFileName(url, disposition, mime);
                request.setTitle(name);
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                } else {
                    request.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, name);
                }
                DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                if (manager == null) throw new IllegalStateException();
                manager.enqueue(request);
                Toast.makeText(this, "已开始保存文件，可在系统下载中查看", Toast.LENGTH_LONG).show();
            } catch (Exception error) {
                Toast.makeText(this, "文件暂时无法保存，请稍后重试", Toast.LENGTH_LONG).show();
            }
        });
    }
}
