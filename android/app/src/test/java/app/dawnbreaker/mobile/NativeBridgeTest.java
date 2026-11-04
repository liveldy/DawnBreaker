package app.dawnbreaker.mobile;

import static org.junit.Assert.*;
import com.getcapacitor.JSExport;
import com.getcapacitor.PluginHandle;
import com.getcapacitor.CapConfig;
import java.util.Collections;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.util.ReflectionHelpers;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.shadows.ShadowWebView;
import android.content.pm.PackageInfo;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
@LooperMode(LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.LEGACY)
public class NativeBridgeTest {
    @Test public void updatePluginIsExportedWhenActivityCreatesItsBridge() {
        PackageInfo webView=new PackageInfo();webView.packageName="com.google.android.webview";webView.versionName="130.0.0";
        ShadowWebView.setCurrentWebViewPackage(webView);
        try (ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class)) {
            // Robolectric has no installed Chromium service-worker provider. Disable only
            // that unrelated OS service; execute the real Activity/Bridge/plugin lifecycle.
            CapConfig config=new CapConfig.Builder(RuntimeEnvironment.getApplication()).setResolveServiceWorkerRequests(false).create();
            ReflectionHelpers.setField(controller.get(),"config",config);
            controller.create().start().resume();
            MainActivity activity=controller.get();
            assertNotNull("Activity must create a native bridge",activity.getBridge());
            PluginHandle plugin=activity.getBridge().getPlugin("DawnClient");
            assertNotNull("DawnClient must exist before the JS plugin list is exported",plugin);
            String javascript=JSExport.getPluginJS(Collections.singletonList(plugin));
            for(String method:new String[]{"getInfo","checkUpdate","downloadUpdate","installUpdate","setAtlasMode"}) {
                assertTrue("Missing exported method: "+method,javascript.contains(method));
            }
            int original=activity.getRequestedOrientation();activity.setAtlasMode(true);
            assertTrue(activity.atlasFullscreen);assertEquals(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE,activity.getRequestedOrientation());
            activity.getOnBackPressedDispatcher().onBackPressed();assertFalse(activity.atlasFullscreen);assertEquals(original,activity.getRequestedOrientation());
            PluginHandle media=activity.getBridge().getPlugin("DawnMedia");
            assertNotNull(media);
            String mediaJS=JSExport.getPluginJS(Collections.singletonList(media));
            for(String method:new String[]{"configure","playlist","play","pause","seek","volume","widget","getState","reset"})assertTrue(mediaJS.contains(method));
        }
    }
}
