# 天眼运营商监视（2026-11-06 核对）

公开排行榜、能力、公开价格由服务器在北京时间每天 04:00 更新一次；进程重启会检查持久化的日期标记，不重复抓取。失败保留最近完整快照，下一日再尝试。用户“刷新显示”只读取服务器。私有 API 监视是另一组接口，只在保存或手动刷新时查询平台，测速须主动点击，最多 32 输出 Token。

`openai` 是 OpenAI Chat Completions（`POST /chat/completions`）及其兼容实现，不是另一种协议。`responses` 对应 `POST /responses`，与前者分开；Anthropic Messages、Gemini 原生协议也分开保存。旧 `openai` 配置继续兼容。

## 凭据与统计范围

| 运营商 | 本程序接入 / 获取方式 | 凭据与限制 | 官方资料 |
| --- | --- | --- | --- |
| OpenAI（GPT） | 模型列表；组织近 30 天 Costs、Completions Usage | 独立 Admin Key；费用为组织费用，用量只覆盖对话 API，无普通 Key 通用余额 | [管理 API](https://developers.openai.com/api/reference/administration/overview)、[Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) |
| Anthropic（Claude） | 模型列表；官方仍保留的 Usage & Cost API，组织近 30 天费用 / Token | Admin Key 或符合官方组织读取权限的凭据；费用金额由美分换算为美元，工作空间推理 Key 不替代管理 Key；官方另有新版 Usage & Cost Analytics API，本适配使用已公开的旧版合同 | [Usage & Cost](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)、[新版 Analytics](https://platform.claude.com/docs/en/manage-claude/usage-cost-analytics-api) |
| xAI（Grok） | 模型列表；团队预付余额；团队近 30 天消费、请求、Token | **推理 Key + 独立 Management Key + Team ID**。管理域名 `management-api.x.ai` 固定；余额 `total.val` 为有符号美分账本，信用记为负，显示值 `-val/100`；`usd` 为美元，`transactions` 为请求，`units` 仅累计 Token 单位，不计图片数量和音频秒数；截断统计不显示部分合计 | [Management](https://docs.x.ai/developers/management-api-guide)、[Billing 合同](https://docs.x.ai/developers/rest-api-reference/management/billing) |
| DeepSeek | 模型列表；`GET /user/balance` | 同一推理 Key；按返回币种（CNY / USD）显示，不换算、不合并不同币种。无公开 Key 全生命周期 Token / 请求统计 | [余额](https://api-docs.deepseek.com/api/get-user-balance/) |
| 月之暗面（Kimi） | 普通 Key `GET /users/me/balance`；国际站可选 Admin Key 读取组织账户和用量 | 国际 / 中国站余额分别 USD / CNY。国际站 Admin API（Beta、企业认证、`billing:read`）金额单位 milli-cent，除以 100000；用量时间使用毫秒和上海自然日，读前 30 个完整自然日；缓存命中已包含输入，禁止重复相加。组织累计消费与近 30 天用量分别标注 | [余额](https://platform.kimi.ai/docs/api/balance)、[Admin 概览](https://platform.kimi.ai/docs/admin-api/overview)、[OpenAPI](https://platform.kimi.ai/docs/admin-api/openapi.yaml) |
| OpenRouter | 模型列表 / 定价；当前 Key 消费和额度 | 同一推理 Key，`GET /key`；`limit_remaining` 是密钥剩余额度而非账户余额，无上限时显示空值 | [当前 Key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key) |
| 302.AI | 模型列表；`GET /dashboard/balance` | 普通 API Key 须有读取权限；不访问 Cookie 登录接口 | [余额](https://doc.302.ai/262796252e0) |
| Google（Gemini） | 模型列表；平台账单未接入 | Gemini Key 不具有云 IAM 权限；Cloud Billing 费用需设置 BigQuery 导出、服务账号与项目权限，读取 / 存储 BigQuery 也可能产生云费用 | [账单导出](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery) |
| 阿里云（Qwen） | 兼容模型列表；云账单未接入 | DashScope Key 与 RAM AccessKey 不同。BSS `QueryAccountBalance`、`QueryAccountBill` 需 RAM 费用权限与签名；不是向模型 Key 添加管理路径即可读取 | [账户余额](https://help.aliyun.com/en/user-center/developer-reference/api-bssopenapi-2017-12-14-queryaccountbalance)、[费用 API](https://help.aliyun.com/en/user-center/developer-reference/api-bssopenapi-2017-12-14-overview) |
| 腾讯（Hunyuan） | 兼容模型列表；云账单未接入 | 独立云 SecretId / SecretKey、TC3 签名、CAM 权限；`billing.tencentcloudapi.com` 的 `DescribeAccountBalance` 金额为分 | [余额](https://cloud.tencent.com/document/api/555/20253)、[CAM 权限](https://cloud.tencent.com/document/product/598/92835) |
| 字节跳动（Seed） | 方舟兼容模型接口；云账单未接入 | 推理 Key 与费用中心云 AccessKey 不同。官方 `QueryBalanceAcct`、账单查询需云签名授权 | [费用中心 API](https://docs.volcengine.com/docs/billing-center/api-overview?lang=zh) |
| 百度（ERNIE） | 千帆兼容模型接口；财务统计未接入 | 未核实由千帆模型 Key 查询余额的公开合同；云财务与模型 API 凭据分离，不猜测内部管理路径 | [千帆 API](https://cloud.baidu.com/doc/qianfan-api/s/3m7of64lb) |
| 智谱（GLM） | Chat Completions / 模型信息 | 未核实普通推理 Key 公开全量财务接口；Coding Plan 配额与按量账户余额区分，使用官方控制台 | [官方兼容指南](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction) |
| 美团（LongCat） | Responses 兼容 / 模型信息 | 额度查看 Usage 页面；未核实公开账单 API，不模拟控制台登录 | [官方协议说明](https://longcat.chat/platform/docs/Codex.html) |
| 小米（MiMo） | Chat Completions / 模型信息 | 未核实公开余额 / 全量用量合同；不使用网页 Cookie 和非公开接口 | [官方 API 文档](https://platform.xiaomimimo.com/docs/en-US/usage-guide/passing-back-reasoning_content) |
| MiniMax | 兼容模型信息；现金 / 套餐统计未接入 | PAYG Key 与 M Plan Subscription Key 分离。官方套餐查询 `https://www.minimax.io/v1/token_plan/remains` 返回套餐额度，不能冒充现金余额。中外站账号 / Key 不混用 | [协议](https://platform.minimax.io/docs/api-reference/text-openai-api)、[M Plan 用量查询](https://platform.minimax.io/subscribe/coding-plan) |
| TokenDance | 兼容模型接口 | 未核实官方公开余额 / 全量用量合同，统计只显示本程序真实调用；不会尝试其他中转平台的私有账单路径 | [官方文档](https://tokendance.space/docs) |
| SiliconFlow | 模型列表，保留本程序用量 | 官方 `/user/info` 已于 2026-08-14 停止，移除旧式余额探测；未使用已废弃端点 | [发布记录](https://docs.siliconflow.cn/docs/release-notes/overview) |

Muse（muse.ai）与 SWE（swe.org）未找到符合本模型接入场景的公开文档，依用户要求不添加。旧预设 `Meta（Muse）` 属错误映射，已移除；已有监视配置和密钥保留，并以自定义配置继续管理。

## 自定义与认证

星丛、天眼都有自定义入口。仅协议、基础地址必填，可不填名称、Key、模型 ID。未提供 Key 不发送空 Bearer 头；未提供模型不在 Chat Completions / Responses / Messages 请求体中伪造模型，由上游默认配置决定。Gemini 原生调用的 URL 必须包含模型 ID，调用时会要求补填。保存和读取匿名模型列表不受此限制。

自定义接口支持公网 HTTP 和 HTTPS；仍使用 DNS 固定解析地址，禁止本机 / 内网 / 保留地址和跳转。管理凭据只发送到核实的官方管理端，绝不跟随任意自定义基础地址；xAI 推理及管理均沿用管理员控制的固定出站代理。右下角“复制 API”始终复制**推理密钥**。

最初测试地址不可连接；按用户更新后的 `http://xn-e.suanjiayun.com:54644/v1`，已验证本机与服务器匿名模型列表、显式模型 / 默认模型调用、星丛完整对话和天眼监视。另用本地 HTTP 服务与契约样例验证可选字段、四协议适配、DNS 检查、密钥隔离和账单合同。未持有各平台管理权限的真实账号，不声称完成全部运营商的实账单验证。

## 合入的请求优化

按用户指定审查并整合 [lmliheng/DawnBreaker a935010](https://github.com/lmliheng/DawnBreaker/commit/a935010264f8f930e0af8aaa89e9477084a75a59)：gzip、ETag / 304、保留显式缓存头、卡图私有缓存。

修正了该提交同步调用所谓后台刷新导致仍阻塞的问题；以独立每日调度取代十分钟刷新，用户请求始终读快照。卡图使用一天私有缓存，避免未版本化资源的永久 immutable 缓存使后续封面修正长达一年不可见。保留 API 与静态页面 CSP 的独立分支，防止显式缓存的 API 响应被误套页面 CSP。ETag 按实际响应内容生成，含新鲜度及更新失败状态，304 之前仍检查权限与每日任务记录。
