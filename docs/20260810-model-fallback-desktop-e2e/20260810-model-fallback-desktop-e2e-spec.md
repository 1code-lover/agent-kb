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

## 2026-08-15 Agent 直连模型补充

### 当前缺口

`api/services/agent_tools.py` 的 Agent 直连聊天在当前 provider 为 Ollama 时直接抛出“not implemented”，并且云端模型请求失败后不会调用现有 fallback。基础问答已经具备自动切换，但高级 Agent 模式仍可能因同一模型故障直接失败。

### 目标行为

- Ollama 使用原生 `/api/chat` 完成 Agent 直连聊天，支持 system prompt、temperature 和 `stream=false`。
- 云端或 Ollama 首次调用出现可恢复错误时，自动切换到首个探活成功候选并只重试一次。
- Agent 返回结果包含最终 `model_health` 和 fallback 元数据，receipt 记录最终模型及切换摘要。
- fallback 不可用或第二次调用失败时返回明确错误，并保持可诊断健康状态。
- 切换成功后的健康状态同时保留 `fallback_from` 和 `fallback_to`；真实 Ollama E2E 报告必须验证动态发现、原生推理和明确切换摘要。

## 2026-08-15 packaged runtime 路径规范

### 路径契约

| 名称 | 开发模式 | packaged 模式 | 权限 |
|---|---|---|---|
| `resourceRoot` | 仓库根目录 | `process.resourcesPath` | 只读 |
| `runtimeRoot` | 仓库根目录 | `<userData>/runtime` | 可写 |
| Python script | `<resourceRoot>/run_api.py` | `<resourceRoot>/run_api.py` | 只读 |
| Python cwd | `runtimeRoot` | `runtimeRoot` | 可写 |
| Data root env | `runtimeRoot` | `runtimeRoot` | 可写 |
| Model root env | `<resourceRoot>/localmodels` | `<resourceRoot>/localmodels` | 只读 |

Electron 主进程不在模块加载时调用依赖 ready 状态的 `app.getPath()`；由可测试的纯函数根据 `isPackaged`、resources path 和 userData path 生成路径，再在 `app.whenReady()` 后初始化目录和 Python API。

runtimeRoot 初始化采用 fail-closed：创建或写权限探测失败即终止 API 启动并显示可操作错误，不允许改写 resourceRoot，也不允许退回当前工作目录。Python 子进程设置 `PYTHONDONTWRITEBYTECODE=1`，防止导入模块时在 Resources 产生 `__pycache__`。

### 不变性验证

真实 packaged E2E 使用独立 userData 目录，启动前后分别计算 Resources 下所有常规文件的相对路径、大小和 SHA-256。两份清单必须完全一致；同时必须观察到 runtime 日志及至少一类 Python 持久化文件写入 `<userData>/runtime`。API health 中默认 embedding 必须 ready，模型诊断的本地路径必须指向 Resources/localmodels。报告同时记录实际 resolved Python 路径、Python 版本和 `pip check`，不得隐含宣称安装包已包含自包含 Python runtime。
