# 20260810 Model Fallback Desktop E2E Test Plan

## 单元测试

- 模型错误分类：
  - 额度耗尽文本 -> `quota_exhausted`
  - HTTP 403 -> `forbidden`
  - HTTP 401 -> `unauthorized`
  - 模型不存在/不可用 -> `model_unavailable`
- fallback：
  - 当前模型失败后，跳过失败模型并选择第一个探活成功候选。
  - 无候选成功时记录 `unavailable`。
  - 成功 fallback 后清理 LLM 指纹并更新 session provider。
- QA eval resume：
  - 已有成功 case 会跳过。
  - API error case 会重新执行。
  - `--stop-on-api-error` 会写出部分报告并退出。

## 集成测试

- `GET /api/model/options` 返回 `model_health`。
- `/api/chat/query` 遇到模拟模型异常时 fallback 并重试。
- webapp 模型页和 Agent 页能渲染健康状态。

## E2E 验证

- 启动 API。
- 启动 webapp dev server。
- 启动 Electron 桌面 shell。
- 执行桌面真实工作流诊断：
  - 当前模型健康状态可读。
  - 可用模型可选择。
  - `grain-knowledge-base` 问答返回 answer、sources、evidence。
  - preview API 可打开首条 evidence。
  - `default` 查询不泄露 grain 来源。

## 通过标准

- 相关单测全部通过。
- 全量非 slow 测试通过。
- 前端 Node 测试和 build 通过。
- E2E 报告 `run_passed=true`。
