# xAI connectivity

星丛对 xAI 使用官方语言模型列表 `/v1/language-models`，避免把图像或视频模型作为对话模型；天眼读取完整 `/v1/models`。两者统一规范基础地址，兼容根地址、版本地址及误填的 `/responses`、`/chat/completions` 地址。天眼按 xAI 返回的 USD cents / 100 million tokens 转换为每百万 Token 的美元价格；没有公开的余额和账单仍显示缺失，不使用普通推理密钥冒充 Management API。

官方文档：[模型列表与价格单位](https://docs.x.ai/developers/rest-api-reference/inference/models)、[Responses](https://docs.x.ai/developers/rest-api-reference/inference/responses)、[地域端点](https://docs.x.ai/developers/advanced-api-usage/regions)。不自动改用另一个地域或更换用户选择的模型。

管理员入口为 **管理后台 → AI 出站**。在此更换 HTTPS 订阅地址、读取备选节点、独立测试、手动应用固定节点、启停及检查当前出口。订阅支持 Clash YAML/JSON，以及受支持的 SS、VLESS、VMess、Trojan、AnyTLS 节点链接。导入只采纳节点，不导入监听端口、TUN、规则或外部提供者；SS 的内置传输插件参数会保留。含不安全 TLS 跳过验证的节点不启用。

更新订阅和候选测试不会更换当前出口。测试在独立的临时核心中执行，不发送模型密钥；通过后 10 分钟内才可应用。应用只包含一个固定节点，不创建自动选择、故障转移或负载均衡。当前节点故障时保持选择并报错；检查发现上游出口 IP 与应用时不同会提示管理员。停用时暂停 xAI 请求，不自动直连。变更有权限校验、并发锁、订阅版本校验和审计记录。

订阅地址和节点凭据使用平台密钥加密保存在服务器；API 只返回节点名称、类型、受限的订阅域名提示、连通检查和应用状态。代理认证与控制密钥另存于 `DAWN_DATA_DIR/xai-egress/connection.json`（0600）。不放入源码、网页或审计详情。

首次部署：维护者核验官方 Mihomo Linux 二进制后，在服务器执行 `python scripts/install_xai_egress.py --core /path/to/verified/mihomo`。安装器创建回环监听与认证的独立服务，默认拒绝出站；之后由管理员在应用内导入、测试和应用节点。服务端代理只对精确的 `api.x.ai` / `us.api.x.ai` 的 HTTPS 443 生效，其他自定义平台继续使用 DNS 固定与公网地址验证。CONNECT 后仍验证 xAI 的 TLS 证书，不接受重定向，模型密钥处于 TLS 隧道内。

未部署管理组件的独立安装仍可由维护者显式设置 `DAWN_XAI_HTTPS_PROXY`（HTTP CONNECT 或 HTTPS 代理），普通 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量不被隐式采纳。已启用管理组件后，以管理员配置为准。

客户端本机的折跃门或其他代理不自动改变服务器的出口。网络错误与鉴权、模型不存在、额度限制分别显示；错误不包含请求密钥、代理凭据或上游完整响应。
