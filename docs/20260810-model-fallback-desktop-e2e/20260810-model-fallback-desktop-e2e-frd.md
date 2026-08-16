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


### FR-07 macOS 单次公证与多凭证策略

正式 `release:mac` 使用自定义 `afterSign` hook 调用 `@electron/notarize`，并在 mac build 配置中显式设置 `notarize=false`，关闭 electron-builder 内建自动公证，保证同一 app 每次构建只提交一次。

公证凭证按以下优先级选择第一组完整策略：

1. `APPLE_KEYCHAIN_PROFILE`，可选 `APPLE_KEYCHAIN`。
2. `APPLE_API_KEY` + `APPLE_API_KEY_ID` + `APPLE_API_ISSUER`。
3. `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID`。

如果某种策略只配置了一部分，预检返回策略名和缺失字段，不输出任何密码、私钥内容或凭证值。三种策略都未配置时，非严格预检输出可操作诊断，严格预检失败。

Developer ID Application 签名身份、`notarytool`、Electron bundle、hardened runtime、entitlements、CSP、包内容、codesign、Gatekeeper 和 stapler 仍是独立发布门禁；完整公证凭证不能替代签名证书。

### FR-08 Agent 直连模型的 Ollama 与 fallback

Agent 高级模式的 `llm_chat` 工具使用当前模型配置直接调用 provider：

1. 云端/OpenAI 兼容 provider 继续调用 `{api_base}/chat/completions` 并携带 Bearer API Key。
2. Ollama 调用 `{api_base}/api/chat`，使用 `stream=false` 的原生消息协议，不要求 API Key。
3. 首次调用遇到可恢复错误时，复用 `attempt_model_fallback` 探测并切换候选，然后读取更新后的 `current_llm_info` 重试一次。
4. fallback 未应用时保留原异常；重试仍失败时将健康状态更新为 `unavailable`，不进行无限重试。
5. Agent 结果和工具回执记录最终 provider/model、`model_health` 与结构化 fallback 来源/目标，不记录 API Key。
6. 前端 Agent 成功回调继续刷新 model options，以显示“已自动切换”和最终模型。
7. 成功切换后必须保留切换前模型快照；`select_model` 的健康状态重置不能丢失 `fallback_from`。

### FR-09 packaged runtime 只读/可写目录隔离

Electron 在 ready 后解析两个独立根目录：

- `resourceRoot`：开发模式为仓库根目录，packaged 模式为 `process.resourcesPath`，只用于读取 `run_api.py`、Web 静态文件、图标和 `localmodels`。
- `runtimeRoot`：开发模式继续使用仓库根目录，packaged 模式为 `path.join(app.getPath("userData"), "runtime")`，用于 Python `cwd` 和 Electron/Python 运行数据。

启动 Python 时必须满足：

1. 命令解析从 `resourceRoot` 查找项目虚拟环境或显式 `NORTHAGENT_PYTHON`。
2. 脚本为 `path.join(resourceRoot, "run_api.py")`。
3. `cwd` 为 `runtimeRoot`，启动前递归创建该目录。
4. 环境变量包含 `NORTHAGENT_DATA_ROOT=runtimeRoot`、`NORTHAGENT_MODEL_ROOT=path.join(resourceRoot, "localmodels")`、`PYTHONDONTWRITEBYTECODE=1` 和 `PYTHONIOENCODING=utf-8`，避免 Python 在只读 Resources 下创建 `__pycache__`。
5. Electron runtime log 写入 `runtimeRoot/storage/logs/desktop_runtime.log`。
6. runtimeRoot 创建失败时终止启动并向用户显示日志位置或错误原因；不得静默使用 resourceRoot 作为可写 fallback。

Python 配置在上述环境变量存在时将 `STORAGE_DIR`、`DATA_DIR` 和 `MODEL_DIR` 解析为绝对目录；未设置时继续兼容仓库根目录开发方式。会话、fallback 配置、KV 配置、embedding 和 reranker 不得通过字符串拼接破坏绝对路径。

### FR-10 packaged embedding 资源门禁

`desktop/package.json` 通过 `extraResources` 将 `localmodels` 复制到 app resources。`verify:package` 将默认 embedding 的配置、权重、tokenizer、SentenceTransformer modules 和 pooling 配置列为必需 runtime 文件；任一文件缺失时构建验证失败，避免应用在远程下载关闭时生成不可用安装包。

本轮不把源码和模型随包等同于自包含 Python runtime。packaged E2E 记录实际 resolved Python、Python 版本和 `pip check`；若面向没有兼容 Python 环境的清洁机分发，需独立设计 Python 解释器、原生依赖、体积和嵌套签名方案。

### FR-11 外部 Python runtime 发布门禁

新增 `desktop/scripts/verify-python-runtime.js`：

1. 若设置 `NORTHAGENT_PYTHON`、`THINKRAG_PYTHON` 或 `FOXGLOVE_PYTHON`，只验证第一个显式值，不静默回退。
2. 未显式设置时，macOS/Linux 按 conda `agent-kb`、项目 `.venv`、项目 `venv`、`python3` 顺序探测；Windows 按项目 `.venv`、项目 `venv`、`python` 顺序探测。
3. 通过无副作用探针返回 Python implementation、major/minor/patch 和缺失核心模块；要求 CPython 3.12。
4. 核心模块至少包括 `fastapi`、`uvicorn`、`llama_index`、`sentence_transformers` 和 `httpx`。
5. 通过 `importlib.metadata` 验证 `llama-index=0.11.19` 和 `llama-index-core=0.11.19`，并在结果中记录这两个版本；任一漂移均失败。
6. 模块与版本探针通过后执行 `<python> -m pip check`，只有退出码为 0 才判定 runtime ready。
7. 子进程设置 `PYTHONDONTWRITEBYTECODE=1`、UTF-8，并以仓库资源根目录为 cwd；诊断只记录命令路径、版本、缺失模块、锁定包版本和经过清洗/截断的错误摘要。

`desktop/package.json` 的 `build:preflight` 和 `release:preflight` 必须调用该 verifier；`desktop/scripts/build-target.js` 的 macOS 路径在 release preflight 和 electron-builder 之前执行 verifier。`verify-release-config.js` 对脚本缺失 verifier 的配置判定失败。
