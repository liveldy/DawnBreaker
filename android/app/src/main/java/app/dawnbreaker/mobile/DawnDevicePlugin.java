package app.dawnbreaker.mobile;
import android.app.Activity;import android.content.*;import android.net.*;import com.getcapacitor.*;import com.getcapacitor.annotation.*;import androidx.activity.result.ActivityResult;import org.json.*;import java.util.concurrent.*;
@CapacitorPlugin(name="DawnDevice")
public class DawnDevicePlugin extends Plugin{
 private final ExecutorService worker=Executors.newFixedThreadPool(4);
 @PluginMethod public void action(PluginCall call){String command=call.getString("command","");JSObject options=call.getObject("options",new JSObject());
  if(command.equals("warp.start")){Intent consent=android.net.VpnService.prepare(getContext());if(consent!=null){startActivityForResult(call,consent,"vpnConsent");return;}startVpn(call,options);return;}
  if(command.startsWith("wallpaper.")){call.reject("浮光掠影仅支持 Windows 桌面端");return;}
  if(command.equals("cloud.open")){if(android.os.Build.VERSION.SDK_INT<28){call.reject("隔离网盘窗口需要 Android 9 或更新版本");return;}try{DawnCloudActivity.validateStart(options.optString("provider"),options.optString("url"));getActivity().startActivity(new Intent(getContext(),DawnCloudActivity.class).putExtra("provider",options.optString("provider")).putExtra("url",options.optString("url")));call.resolve(new JSObject().put("message","已打开独立网盘窗口。登录后选择文件，使用 LinkSwift 解析下载。"));}catch(Exception e){call.reject("请输入支持的网盘 HTTPS 页面地址");}return;}
  if(command.equals("cloud.jobs")){call.resolve(new JSObject().put("jobs",new JSArray()));return;}
  worker.execute(()->{try{JSONObject result;if(command.startsWith("system."))result=DawnSystemTools.action(getContext(),command,options);else if(command.startsWith("warp."))result=DawnWarpService.action(getContext(),command,options);else throw new Exception("未知操作");call.resolve(JSObject.fromJSONObject(result));}catch(Exception e){call.reject(e.getMessage()==null?"设备操作失败":e.getMessage());}});
 }
 private final java.util.concurrent.atomic.AtomicBoolean starting=new java.util.concurrent.atomic.AtomicBoolean();
 private void startVpn(PluginCall call,JSObject options){if(!starting.compareAndSet(false,true)){call.reject("折跃门正在初始化，请等待本轮完成");return;}worker.execute(()->{try{DawnWarpService.prepare(getContext(),options);Intent i=new Intent(getContext(),DawnWarpService.class);androidx.core.content.ContextCompat.startForegroundService(getContext(),i);for(int n=0;n<1300;n++){Thread.sleep(100);if(DawnWarpService.running||!DawnWarpService.starting||!DawnWarpService.error.isEmpty())break;}if(!DawnWarpService.running)throw new Exception(DawnWarpService.error.isEmpty()?"VPN 启动超时":DawnWarpService.error);call.resolve(JSObject.fromJSONObject(DawnWarpService.action(getContext(),"warp.status",new JSONObject())));}catch(Exception e){DawnWarpService.stop(getContext());call.reject(e.getMessage()==null?"VPN 启动失败":e.getMessage());}finally{starting.set(false);}});}
 @ActivityCallback private void vpnConsent(PluginCall call,ActivityResult result){if(call==null)return;if(result.getResultCode()!=Activity.RESULT_OK){call.reject("未获得系统 VPN 授权");return;}startVpn(call,call.getObject("options",new JSObject()));}

}
