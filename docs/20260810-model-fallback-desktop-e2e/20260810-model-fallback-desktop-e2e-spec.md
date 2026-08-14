# 20260810 Model Fallback Desktop E2E Spec：问答后即时同步 fallback 状态

## 背景

模型 fallback 已经在服务端完成，但 `/api/chat/query` 原先只返回答案、来源和知识库范围。桌面问答页的模型健康状态来自缓存 60 秒的 `/api/model/options` 查询，因此一次问答触发自动切换后，页面可能继续显示旧模型和旧状态，用户无法立即确认是否已经切换。

## 目标

1. `/api/chat/query` 在正常回答和 fallback 重试后都返回当前 `model_health` 快照。
2. Web 问答成功后立即刷新模型选项，使当前模型名称和切换提示同步更新。
3. 保持现有 fallback 只对可恢复错误生效，单次请求最多重试一次，不改变来源和知识库隔离逻辑。

## 验收标准

- fallback 重试成功的 query 响应包含 `model_health.state=fallback_applied`、`fallback_from` 和 `fallback_to`。
- 无 fallback 的正常 query 响应也包含 `model_health`，避免客户端处理分支漂移。
- Agent 问答成功处理器触发 `modelOptionsQuery.refetch()`，不依赖 60 秒 staleTime 或窗口重新聚焦。
- 现有 Python 非 slow 测试、Web Node 测试和 Vite build 继续通过。
