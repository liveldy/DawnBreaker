package app.dawnbreaker.mobile;

import android.app.ActivityManager;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import org.json.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class DawnSystemTools {
 private static final AtomicBoolean trimming=new AtomicBoolean();
 private DawnSystemTools(){}
 static long appMemory(){Debug.MemoryInfo memory=new Debug.MemoryInfo();Debug.getMemoryInfo(memory);return memory.getTotalPss()*1024L;}
 public static JSONObject info(Context context)throws Exception{
  ActivityManager manager=(ActivityManager)context.getSystemService(Context.ACTIVITY_SERVICE);ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();
  if(manager!=null)manager.getMemoryInfo(memory);
  StatFs disk=new StatFs(context.getFilesDir().getAbsolutePath());
  JSONObject ram=new JSONObject().put("total",memory.totalMem).put("available",memory.availMem).put("app",appMemory()).put("app_scope","破晓当前进程").put("low",memory.lowMemory);
  Intent intent=context.registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));JSONObject battery=null;
  if(intent!=null){int level=intent.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),scale=intent.getIntExtra(BatteryManager.EXTRA_SCALE,-1),status=intent.getIntExtra(BatteryManager.EXTRA_STATUS,-1);if(level>=0&&scale>0)battery=new JSONObject().put("percent",level*100.0/scale).put("charging",status==BatteryManager.BATTERY_STATUS_CHARGING||status==BatteryManager.BATTERY_STATUS_FULL);}
  JSONArray displays=new JSONArray();WindowManager window=(WindowManager)context.getSystemService(Context.WINDOW_SERVICE);
  if(window!=null){DisplayMetrics metrics=new DisplayMetrics();window.getDefaultDisplay().getRealMetrics(metrics);displays.put(new JSONObject().put("name","本机屏幕").put("width",metrics.widthPixels).put("height",metrics.heightPixels).put("scale",metrics.density));}
  String version=context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionName;
  return new JSONObject().put("platform","mobile").put("device_name",Build.MANUFACTURER+" "+Build.MODEL).put("os_name","Android").put("os_version",Build.VERSION.RELEASE+" · API "+Build.VERSION.SDK_INT).put("architecture",Build.SUPPORTED_ABIS.length>0?Build.SUPPORTED_ABIS[0]:"未知").put("cpu_model",Build.VERSION.SDK_INT>=31?Build.SOC_MODEL:Build.HARDWARE).put("cpu_cores",Runtime.getRuntime().availableProcessors()).put("cpu_percent",JSONObject.NULL).put("uptime_seconds",SystemClock.elapsedRealtime()/1000L).put("memory",ram).put("storage",new JSONObject().put("name","应用所在内部存储").put("total",disk.getTotalBytes()).put("available",disk.getAvailableBytes())).put("battery",battery==null?JSONObject.NULL:battery).put("displays",displays).put("app_version",version).put("fetched_at",System.currentTimeMillis()).put("capabilities",new JSONObject().put("trim_memory",true).put("task_manager",false).put("settings",new JSONArray().put("system").put("storage").put("apps")));
 }
 static Intent settingsIntent(Context context,String section){
  Intent intent;
  switch(section){case "system":intent=new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS);break;case "storage":intent=new Intent(Settings.ACTION_INTERNAL_STORAGE_SETTINGS);break;case "apps":intent=new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+context.getPackageName()));break;default:throw new IllegalArgumentException("系统设置项无效");}
  return intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
 }
 public static JSONObject action(Context context,String command,JSONObject options)throws Exception{
  if(command.equals("system.info"))return info(context);
  if(command.equals("system.trim-memory")){
   if(!trimming.compareAndSet(false,true))throw new IllegalStateException("内存整理正在进行，请稍候");
   try{long before=appMemory();System.gc();Thread.sleep(350);long after=appMemory();return new JSONObject().put("before_bytes",before).put("after_bytes",after).put("reclaimed_bytes",Math.max(0,before-after)).put("processed_count",1).put("message","已请求回收破晓当前进程的空闲内存");}finally{trimming.set(false);}
  }
  if(command.equals("system.open-settings")){Intent intent=settingsIntent(context,options.optString("section"));try{context.startActivity(intent);}catch(ActivityNotFoundException e){throw new IllegalStateException("当前设备没有提供此系统设置入口");}return new JSONObject().put("message","已打开 Android 系统设置");}
  throw new IllegalArgumentException("不支持的系统操作");
 }
}
