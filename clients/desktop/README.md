# Windows 桌面端

界面来自根目录 `src/`，本目录仅包含 Electron 原生能力。需要 Windows、Node 22+、Python 3.11+。

```powershell
npm ci
python scripts/fetch_native_components.py windows
python scripts/fetch_geodata.py
npm run build
npm run desktop
npm run desktop:build
```

构建输出：`release/desktop/`。默认服务器入口可用 `DAWN_WEB_URL` 环境变量覆盖。单实例、托盘、后台播放、桌面控件、离线缓存、Mihomo 系统代理、WorkerW 壁纸和独立 LinkSwift 网盘窗口均在此实现。系统代理只由明确操作开启，退出/停止后恢复先前设置。所有本地数据存于 Electron userData。

更新验证只包含公钥。自行分发时需生成自己的更新签名密钥，私钥不得提交。参见根 README 与 `third_party/NOTICE.md`。

网页壁纸按显示器独立渲染，支持选择屏幕、不同缩放与热插拔。桌面空白区域的鼠标移动、左键、中键与滚轮传递给网页；其他应用、桌面图标和右键菜单保留系统行为。不捕获全局键盘；键盘和输入法可在隔离的“交互窗口”使用。关闭壁纸或退出程序会停止输入转发。网盘操作见 [使用指南](../../docs/cloud-downloads.md)。
