# 天眼运营商接口（2026-11-04 核验）

API 密钥与组织管理密钥分别加密保存。组织近 30 天账单和本程序推理用量分开显示；缺少公开接口的指标显示“—”。自定义或地域基地址不匹配时，不转发组织管理密钥。

| 运营商 | 基础地址 | 官方资料 |
|---|---|---|
| Anthropic（Claude） | `https://api.anthropic.com/v1` | [API 文档](https://platform.claude.com/docs/en/manage-claude/usage-cost-api) |
| OpenAI（GPT） | `https://api.openai.com/v1` | [API 文档](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs) |
| Google（Gemini） | `https://generativelanguage.googleapis.com/v1beta` | [API 文档](https://ai.google.dev/gemini-api/docs/openai) |
| xAI（Grok） | `https://api.x.ai/v1` | [API 文档](https://docs.x.ai/developers/advanced-api-usage/regions) |
| 深度求索（DeepSeek） | `https://api.deepseek.com/v1` | [API 文档](https://api-docs.deepseek.com/api/get-user-balance/) |
| 月之暗面（Kimi） | `https://api.moonshot.ai/v1` | [API 文档](https://platform.kimi.ai/docs/api/balance) |
| Meta（Muse） | `https://api.meta.ai/v1` | [API 文档](https://dev.meta.ai/docs/overview) |
| 智谱（GLM） | `https://open.bigmodel.cn/api/paas/v4` | [API 文档](https://docs.bigmodel.cn/api-reference/模型-api/对话补全) |
| 阿里云（Qwen） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | [API 文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) |
| 美团（LongCat） | `https://api.longcat.chat/openai/v1` | [API 文档](https://longcat.chat/platform/docs/Codex.html) |
| 腾讯（Hunyuan） | `https://api.hunyuan.cloud.tencent.com/v1` | [API 文档](https://cloud.tencent.com/document/product/1729/111007) |
| 百度（ERNIE） | `https://qianfan.baidubce.com/v2` | [API 文档](https://cloud.baidu.com/doc/qianfan-api/s/3m7of64lb) |
| 小米（MiMo） | `https://api.xiaomimimo.com/v1` | [API 文档](https://platform.xiaomimimo.com/docs/en-US/usage-guide/passing-back-reasoning_content) |
| MiniMax（MiniMax） | `https://api.minimax.io/v1` | [API 文档](https://platform.minimax.io/docs/api-reference/text-openai-api) |
| 字节跳动（Seed） | `https://ark.cn-beijing.volces.com/api/v3` | [API 文档](https://www.volcengine.com/docs/82379/1330310) |
| TokenDance | `https://tokendance.space/gateway/v1` | [API 文档](https://tokendance.space/docs) |
| OpenRouter | `https://openrouter.ai/api/v1` | [API 文档](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key) |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1` | [API 文档](https://docs.siliconflow.cn/docs/release-notes/overview) |
| 302.AI | `https://api.302.ai/v1` | [API 文档](https://doc.302.ai/262796252e0) |

Muse 使用 Meta 公开 Model API；SWE 未查到公开模型 API 文档，按要求忽略。SiliconFlow 的 `/user/info` 已停用，不调用。

OpenAI / Anthropic 账单仅在额外填写 Admin Key 后查询组织近 30 天数据；Anthropic 费用从美分换算为美元。Kimi 国际站余额为 USD。302.AI 余额接口需要平台权限。TokenDance、LongCat 等未查到公开账单接口时，不推测余额。
