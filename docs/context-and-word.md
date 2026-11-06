# 星丛精简记忆与 Word 导入

## 星丛

长期记忆只保存新增的事实、偏好、约束、决定与简短进度，不再把每轮问答原文追加到记忆文档。`remember` 工具每次最多 800 字符、每轮最多 1200 字符；重复条目在本机去重，内容没有变化时不会重写文档。实际保存的文件操作可留下简短进度，不把等待确认的修改视为已经完成。

每个对话使用 `ai_threads.context_cursor` 记录已经总结的历史位置；聊天原文保留供界面查看。超过最近四轮或字符预算时，按完整问答对批量滚动，保留最近两轮和当前问题，将旧对话压缩为任务摘要。摘要最多 1000 字符、长期记忆注入最多 1800 字符，重复内容不再次注入。仅在滚动或旧记忆过长时调用原模型整理，整理输出上限 600 token，并关闭可选思考输出；不为每条消息另开总结调用。

旧版记忆在下次聊天时按需整理。整理失败不覆盖原记忆、不推进游标；同时允许正常回答。人工并发修改的记忆文档优先，旧快照不能覆盖它。聊天、记忆、保存的文件操作仍在原有事务与账号权限范围内。上下文字符数是预算依据，实际 token 与计费由模型厂商决定。

## 流萤集

文档转换复用 [Pandoc](https://github.com/jgm/pandoc) 的 DOCX / OMML 读取器与 Markdown writer；旧版 DOC 先通过 [LibreOffice Writer](https://www.libreoffice.org/discover/writer/) 转为 DOCX。部署需要同时安装 LibreOffice Math，以读取旧式公式对象，不编写自有 Word 或公式解析器。Pandoc 官方说明见 [User's Guide](https://pandoc.org/MANUAL.html)，LibreOffice 参数见 [官方文档](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)。

服务端运行 `python scripts/setup_word_remote.py` 安装 Debian 发行版维护的 Pandoc、Writer、Math。其他环境可安装对应程序，并以 `DAWN_PANDOC` / `DAWN_LIBREOFFICE` 指定绝对路径。客户端无需安装这些工具，不调用付费 OCR API。Word 任务沿用导入队列、30 MB 输入上限、账号图片权限与流萤集空间配额。

DOCX 原生公式转为 `$…$` / `$$…$$`；标题、列表、常见表格和嵌入图片转换为可读 Markdown。清除 Word 的展示尺寸属性，避免 Markdown 退回无法显示的原始 HTML 图片。复杂版式、合并单元格、特殊 OLE / MathType 对象受上游转换能力限制；无法显示的图片会留下提示，源文件保留于导入记录。禁止宏执行和外链更新，Pandoc 使用 sandbox，不自动下载远程图片。

测试包含 python-docx 生成的合成文档、OMML 行内和独立公式、表格、图片、旧 DOC 往返、图片越权隔离及外部图片不发起网络请求。CI 安装系统引擎运行实际转换，Windows 本机可用 `pypandoc_binary` 作为测试工具；未安装 LibreOffice 时仅跳过本机旧 DOC 测试。
