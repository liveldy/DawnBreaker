# 服务端

Python 3.11+，FastAPI、SQLite WAL；端口 7779。安装根目录 `requirements.txt` 后运行：

```sh
python -m uvicorn server.main:app --host 127.0.0.1 --port 7779
```

`DAWN_DATA_DIR` 默认为项目下 `data/`；生产环境应设为独立持久目录。数据库与 `keys/` 必须一起备份。`DAWN_SECURE_COOKIES=1` 用于 HTTPS 部署。`DAWN_SERVE_WEB=0` 可关闭内置静态网页服务，交给 Nginx。参考 `deploy/`，网页入口为 7780。

源码不附带真实素材、密码、管理员账号和 API Key。首次注册普通账号，随后使用 `scripts/create_admin.py` 在自己的数据库中创建管理员。可选素材通过导入脚本生成到 `server/content/`；未导入时保持空目录与示例词库。

插件位于 `plugins/`，按用户鉴权与安装状态检查；媒体、OCR、AI 调用、资产和任务均由服务端核验。生产部署前配置自己的地址、密钥和反向代理。
