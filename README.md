# 破晓 DawnBreaker

以插件组成的个人工具集，支持网页、Windows 与 Android，共用账号、数据和界面代码。

[官网下载](https://liveldy.github.io/dawnbreaker-website/) · [网页版](http://110.42.63.153:7780) · [源码](https://github.com/liveldy/dawnbreaker-app) · [发布版](https://github.com/liveldy/dawnbreaker-app/releases)

## 仓库结构

采用单仓库。网页和客户端共享 React 界面，原生能力按端独立，服务端统一提供业务 API。

| 路径 | 用途 |
|---|---|
| `src/`、`public/` | 网页端及两个客户端的共享界面 |
| `clients/desktop/` | Windows / Electron 原生功能与构建说明 |
| `android/` | Android / Capacitor 原生功能与构建说明 |
| `server/` | Python / FastAPI 服务端与插件 |
| `website/` | 独立官网下载页；部署到原官网仓库 |
| `deploy/` | Linux Nginx、systemd 配置 |
| `scripts/`、`tests/` | 构建、资源导入、发布与验证工具 |
| `third_party/` | 第三方脚本、许可证及来源 |

详见 [架构说明](docs/architecture.md)。本仓库是程序源码仓库，`dawnbreaker-website` 继续只承载官网及既有发布文件。

## 本地运行

需要 Node 22+、Python 3.11+。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm ci
# 终端一：服务端 7779
.venv/Scripts/python -m uvicorn server.main:app --host 127.0.0.1 --port 7779
# 终端二：网页端 7780
npm run dev
```

`npm run build` 构建网页。生产配置参考 `deploy/`，数据目录由 `DAWN_DATA_DIR` 指定。默认没有任何预置账号或密码：注册普通账号；在自己的服务器上运行 `python scripts/create_admin.py` 创建管理员。

## 客户端构建

```powershell
python scripts/fetch_native_components.py all
npm run build
npm run desktop:build
npm run mobile:sync
```

Windows 构建见 [桌面端说明](clients/desktop/README.md)。Android 需 Java 21、SDK 35，见 [移动端说明](android/README.md)。原生核心以固定版本和 SHA256 校验下载，不提交二进制到 Git。自行发行需使用自己的 Android 签名与更新签名密钥。

服务端默认端口 **7779**；网页端默认 **7780**。本地开发使用 Vite 同源代理。桌面远程入口可通过 `DAWN_WEB_URL` 覆盖，Android 远程入口见 `RemoteOrigin.java`。

## 插件

- 朝暮签、拾光记：签到、每日任务和递进成就。
- 流光笺：每日语录、语音播放、管理员语录日历与桌面控件。
- 飞跃：学习、测试、复习、记忆词库、批次队列、进度表；Windows 提供全屏飞速记忆与历史记录。
- 珍藏阁：单抽、十连、抽卡动画、统一卡面、三级卡册、重复卡自动分解。
- 弦音余韵：歌词、顺序 / 随机 / 单曲循环、后台播放、通知栏 / 托盘及控件。
- 流萤集：Markdown + LaTeX 文档、书籍管理与 OCR 导入。
- 星丛：自定义 AI 助手、提示词、文档工作空间、长期记忆与可归档对话。
- 暗格：以用户主密码加密的密码箱与导出。
- 天眼：实时模型排行榜、能力成本图、斩杀判定和私有 API 监视。
- 留痕下载：yt-dlp 视频队列，以及基于 LinkSwift 的客户端网盘助手。
- 折跃门：Windows / Android 本机 Mihomo，兼容 Clash 配置与订阅。
- 浮光掠影：客户端图像 / 视频 / 网页壁纸、本地制作、分端适配与管理员云端发布。

客户端支持离线阅读文档、浏览卡册和缓存模型数据、播放已缓存音乐；离线听曲时长联网后幂等同步。插件按账号安装，服务端始终核验权限。未开放的第三方 API 指标显示缺失，不编造余额与用量。

## 素材与可选依赖

本仓库不包含 `mods/`、用户数据、真实 API Key、部署凭据、签名私钥、客户端缓存或已生成安装包。程序可在没有素材包的情况下运行：媒体为空，词汇提供少量内置示例。

持有使用权的素材可放到 `mods/`，参考 `scripts/import_mods.py` 及各资源准备脚本导入 `server/content/`。英雄联盟图像与语音、音乐和角色立绘等版权归各权利人，不因程序开源而改变授权。OCR 的 Pix2Text / RapidOCR 为可选依赖，服务端配置与限制见 `server/ocr.py`。

## 验证与许可证

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python scripts/source_smoke.py
npm run build
```

包含私有素材的完整工作区可运行 `python -m pytest tests -q`；部分资源集成测试需要对应素材包。Android 原生测试为 `gradlew testDebugUnitTest`。

项目采用 **AGPL-3.0-or-later**。Mihomo 和模型数据适配代码保留 GPL-3.0，LinkSwift 保留 AGPL-3.0-or-later。许可证、固定版本、修改说明与对应源码来源见 [第三方声明](third_party/NOTICE.md)。发布版提供对应源码，服务界面也提供源码入口。
