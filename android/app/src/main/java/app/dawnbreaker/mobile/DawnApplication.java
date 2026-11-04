package app.dawnbreaker.mobile;
public class DawnApplication extends android.app.Application{
 @Override public void onCreate(){super.onCreate();if(android.os.Build.VERSION.SDK_INT>=28){String process=android.app.Application.getProcessName();if(process.endsWith(":cloud"))android.webkit.WebView.setDataDirectorySuffix("cloud");}}
}
