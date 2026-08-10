# 20260810 Model Fallback Desktop E2E FRD

## 功能设计

### FR-01 模型错误分类

后端提供统一错误分类函数，至少输出：

- `quota_exhausted`
- `forbidden`
- `unauthorized`
- `model_unavailable`
- `network_error`
- `unknown`

分类输入包括 HTTP 状态码、异常文本和 OpenAI 兼容接口返回 JSON。

### FR-02 自动 fallback

当 `/api/chat/query` 运行中遇到可恢复模型错误时：

1. 记录失败模型、错误类别、错误摘要。
2. 从当前 provider 的其他模型和自定义 provider 列表中枚举候选。
3. 调用轻量 chat completions 探活。
4. 选中首个可用模型，写回 `current_llm_info`。
5. 清理运行时 LLM 指纹，让后续请求加载新模型。
6. 对当前 query 重试一次。

### FR-03 模型健康状态 API

模型选项响应中增加 `model_health` 字段，包含：

- `state`：`unknown`、`healthy`、`degraded`、`fallback_applied`、`unavailable`
- `current_provider`
- `current_model`
- `last_error_kind`
- `last_error`
- `last_checked_at`
- `last_fallback_at`
- `fallback_from`
- `fallback_to`
- `candidate_count`

### FR-04 前端健康状态展示

模型页和 Agent 页读取 `model_health`，在当前模型信息旁展示健康状态。状态不阻塞已有操作；没有健康数据时显示 `状态未知`。

### FR-05 QA eval 断点续跑

`scripts.run_grain_qa_eval` 新增：

- `--resume`：读取已有输出报告，复用已成功用例。
- `--stop-on-api-error`：遇到 API 错误时立即写出部分报告并退出非 0。
- 报告新增 `resume` 元信息，说明复用数量和执行数量。

### FR-06 桌面 E2E 验证

新增或复用诊断脚本执行真实 API 链路：

- 查询模型 options 和健康状态。
- 测试/选择可用模型。
- 对 `grain-knowledge-base` 发起问答并校验 answer、sources、evidence。
- 调用 preview API 校验证据可预览。
- 对 `default` 范围发起隔离问题，确认不泄露 grain 来源。
- 可启动 webapp dev server 和 Electron shell，并产出启动日志。
