# 系统管理

系统管理是仅用于 Windows / Android 的本机插件。服务器只保存安装状态；系统快照通过本机桥接直接读取，不会上传设备名称、内存、磁盘或电池数据。离线时也可使用。

Windows：通过 Node 与 Electron 读取真实系统和进程数据，内存按 Electron 返回的 KB 换算。原生辅助程序只接收客户端自行枚举的进程 ID，并再次核对可执行程序路径；使用 [EmptyWorkingSet](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset) 整理当前客户端进程的工作集。不会终止其他应用，不修改系统代理、文件或注册表。系统设置与任务管理器入口均使用固定目标，不接受命令行或任意路径。

Android：通过 ActivityManager、Debug、StatFs、Build 和公开电池接口读取可用数据；内存整理使用运行时垃圾回收请求，返回实际观察到的前后占用。该请求不会保证释放特定容量。Android 14 起第三方应用不能通过 [killBackgroundProcesses](https://developer.android.com/reference/android/app/ActivityManager#killBackgroundProcesses(java.lang.String)) 清理其他应用，程序不请求此权限，也不以关闭音乐或 VPN 的方式伪装内存清理。

存储操作打开系统提供的管理页面，由用户选择所需操作；程序不执行全盘临时文件删除。内存占用可能随正常使用重新增加。
