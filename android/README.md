# Android 移动端

共享网页界面由 Capacitor 打包，原生代码在 `app/src/main/java/app/dawnbreaker/mobile/`。

需要 Node 22+、Python 3.11+、Java 21、Android SDK 35。

```powershell
npm ci
python scripts/fetch_native_components.py android
python scripts/fetch_geodata.py
npm run build
npm run mobile:sync
cd android
.\gradlew.bat assembleDebug
```

设置 `JAVA_HOME`、`ANDROID_HOME`，或使用 Android Studio 打开本目录。`local.properties` 属于机器配置，不提交。发布签名由分发者自行配置；仓库不包含签名私钥、keystore 或已授权账号。

Android 后台音乐使用原生服务，提供系统桌面小组件。折跃门通过 Android VPN 授权建立设备代理，首次配置所需的规则数据库随包提供。浮光掠影已移除 Android 支持。网盘 WebView 运行在独立进程及独立数据目录，避免共享主程序 Cookie；隔离网盘窗口要求 Android 9+。

嵌入 libmihomo-android v0.3.13 的构建与许可证见 `third_party/NOTICE.md`，不要改为未校验的浮动版本。
