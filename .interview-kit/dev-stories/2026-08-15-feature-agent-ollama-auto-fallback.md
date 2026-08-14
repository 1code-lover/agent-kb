# Agent 高级模式支持 Ollama 与自动模型切换

## 基本信息
- 类型：feature
- 日期：2026-08-15
- 相关模块：Agent 直连模型工具、Agent runtime、模型 fallback、桌面打包
- 相关文件：`api/services/agent_tools.py`、`api/services/agent_runtime.py`、`api/services/model_service.py`、`api/schemas/__init__.py`、`tests/api/test_agent_tools.py`

## 需求背景
基础问答和知识库问答已经能在模型额度耗尽、鉴权失败、模型不可用或网络异常时自动切换，但 Agent 高级模式的直连聊天仍有两个缺口：选择 Ollama 会直接抛出“未实现”，云端模型失败也会立即结束任务。这样用户在同一个桌面产品中会得到不一致的模型韧性，尤其无法把本地 Ollama 当作 Agent 的 fallback 候选。

## 设计与实现方案
1. 将 Agent 直连调用拆成当前配置读取、共享 JSON 请求、OpenAI 兼容调用和 Ollama 原生调用。Ollama 使用 `{api_base}/api/chat`、`stream=false`、system/user messages 和 temperature，不要求 API Key。
2. `run_llm_chat` 首次失败后调用现有 `model_service.attempt_model_fallback`，候选探活成功后重新读取 `current_llm_info`，按新 provider 协议重试一次。
3. 如果实际重试再次失败，停止循环并把模型健康状态覆盖为 `unavailable`；如果 fallback 未应用，则保留首次异常。
4. 对外返回经过裁剪的 fallback 摘要，移除 `selected.api_key`，只保留错误类别、候选数、来源/目标和探测摘要。Agent result、receipt、日志和 step 使用同一份安全元数据。
5. 扩展 `AgentRunData` 契约，并让 step 摘要显示“已自动切换到 provider / model”。同时补充 Ollama 常见 `model 'name' not found` 错误分类。

## 为什么选这个方案
项目已经有经过真实问答验证的候选排序、探活和健康状态存储，复用 `attempt_model_fallback` 能保证基础问答与 Agent 模式行为一致，也避免维护两套错误分类。Ollama 采用原生接口是因为当前配置默认是 `http://localhost:11434`，不要求用户手动改成 `/v1`。切换后重新读取配置而不是把 `selected` 直接传给调用器，既复用持久化状态，也避免 API Key 在跨层结果中传播。

## 其他方案与为什么没选
1. **要求 Ollama 开启 OpenAI 兼容 `/v1`（推断）**：会改变已有配置约定，而且用户默认填写的 11434 根地址无法直接工作。
2. **在 Agent 工具里重新实现候选枚举（推断）**：会与模型服务的 Ollama 动态发现、优先级和错误分类漂移。
3. **失败后不断尝试全部候选（推断）**：可能显著放大单次 Agent 请求延迟，也容易产生循环；本轮保持“探活后切换一次、实际调用重试一次”。

## 风险与权衡
- Ollama 服务可达不代表实际生成一定成功，因此真实重试失败时必须覆盖健康状态并停止。
- fallback 原始结果中的 `selected` 含 API Key，不能直接写入 API、receipt 或日志；通过显式白名单裁剪控制泄漏风险。
- 本机没有 Ollama 服务和模型，无法提供真实本地推理证据；当前证据包括请求协议单测、真实云端 fallback 和 packaged contents。
- 最新 macOS 产物仍为 ad-hoc 包，正式签名、公证和安装后回归继续依赖外部 Apple 条件。

## 验证与结果
- TDD 初始 Agent 测试：`5 failed, 4 passed`；Ollama 404 分类新增断言初始为 `1 failed`。
- Agent/model/chat 定向测试：`74 passed`。
- Python 全量：`790 passed, 1 deselected, 35 warnings`。
- Web：`89 passed`，Vite build 通过。
- Electron：`64 passed`。
- 当前真实云端模型直连成功；隔离内存配置把当前模型设为不存在模型后，真实 `run_llm_chat` 自动切到 `qwen-math-turbo`，得到 `fallback_applied=true`、`error_kind=model_unavailable`、`candidate_count=1`、`health_state=fallback_applied`。
- `npm run build:mac` 和 `npm run verify:package` 通过；packaged app 已包含 `_call_ollama`、`attempt_model_fallback` 和明确切换摘要。
- 本机 `127.0.0.1:11434` connection refused，未执行真实 Ollama 推理；严格 Apple 发布门禁仍因证书和凭证缺失失败。

## 面试表达版本
我在收口模型 fallback 时发现，基础问答已经能自动切换，但 Agent 高级模式遇到 Ollama会直接报未实现，云端失败也不会重试。我把 Agent 模型调用拆成 OpenAI 兼容和 Ollama 原生两条协议，并复用统一的候选探活服务做一次自动切换。为了避免泄漏，我没有直接返回包含 API Key 的 selected 对象，而是生成白名单式切换摘要。最后我用先失败后通过的测试、真实云端坏模型到可用模型切换、全量回归和最新 Electron 打包验证了实现，同时明确保留真实 Ollama 和 Apple 正式发布的外部验证边界。
