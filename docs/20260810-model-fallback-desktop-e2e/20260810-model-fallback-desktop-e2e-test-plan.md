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
- macOS notarization credentials：
  - 完整 Keychain profile、API Key、Apple ID 策略均能生成正确的 `@electron/notarize` 参数。
  - 部分策略返回缺失字段，三种策略均缺失时严格预检失败。
  - Keychain profile 优先于 API Key，API Key 优先于 Apple ID；可选 `APPLE_KEYCHAIN` 正确透传。
  - release config 必须同时满足自定义 `afterSign` 存在和 `mac.notarize=false`，避免重复提交。
- QA eval resume：
  - 已有成功 case 会跳过。
  - API error case 会重新执行。
  - `--stop-on-api-error` 会写出部分报告并退出。

## 集成测试

- `GET /api/model/options` 返回 `model_health`。
- `/api/chat/query` 遇到模拟模型异常时 fallback 并重试。
- webapp 模型页和 Agent 页能渲染健康状态。
- `build:preflight` 验证 release config、凭证策略诊断、Developer ID Application 和 notarytool。
- `verify:mac-release` 验证 codesign、Gatekeeper 和 stapled ticket。

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
- 正式发布环境下 `release:preflight`、`release:mac`、`verify:package`、`verify:mac-release` 全部通过；公证日志只出现一次 submission。

## fallback 状态即时同步补充

- `/api/chat/query` 正常回答返回 `model_health` 快照。
- `/api/chat/query` fallback 重试后返回 `fallback_applied` 及来源/目标模型。
- Agent 问答成功后主动刷新模型 options，确保切换提示不等待缓存过期。

## Agent 直连 Ollama 与 fallback 补充

- Ollama 当前模型调用 `{api_base}/api/chat`，请求包含 `stream=false`、system/user messages 和 temperature，不携带 Authorization。
- 云端当前模型第一次返回额度/401/403/模型不可用/网络错误时，Agent 自动切换到候选并重试一次。
- fallback 切到 Ollama 后，第二次调用按 Ollama 原生协议执行，并在结果、回执和健康状态中记录最终模型。
- 非可恢复错误不切换；没有可用候选时保留原错误。
- fallback 后实际调用再次失败时不继续循环，健康状态更新为 `unavailable`。
- `agent_runtime.run_agent` 返回 `model_health` 和 fallback 元数据，step 摘要能说明自动切换。
- 成功 fallback 后 `model_health.fallback_from` 保留原 provider/model/api_base，不能被 `select_model` 重置为空。
- 真实 Ollama E2E 覆盖当前 Ollama 直接 Agent 推理，以及不可达云端模型通过动态 `/api/tags` 候选切换到本地模型；报告不使用真实 API Key，也不写 session/receipt。

## packaged runtime 数据隔离测试补充

### Electron 单元测试

- packaged 路径解析返回 Resources 下的 `resourceRoot` 和 userData 下的 `runtimeRoot`；开发模式两者均兼容仓库根目录。
- Python spawn 的脚本来自 `resourceRoot`，`cwd` 为 `runtimeRoot`，并传入正确的数据根和模型根环境变量。
- Electron runtime log 只接收 runtimeRoot，不在 Resources 创建 `storage/logs`。
- runtimeRoot 创建或写权限探测失败时启动失败，不回落到 Resources 或当前目录。
- Python 启动环境禁止写 bytecode，真实 Resources 清单不得出现新增 `__pycache__`。
- package verifier 在默认 embedding 任一必需文件缺失时失败，在文件完整时通过。

### Python 单元/集成测试

- 隔离子进程设置 `NORTHAGENT_DATA_ROOT` 和 `NORTHAGENT_MODEL_ROOT` 后，`config.STORAGE_DIR`、`DATA_DIR`、`MODEL_DIR` 均为对应绝对路径。
- KV config、session store 和 fallback store 的默认文件位于 data root 的 `storage` 下。
- embedding 和 reranker 拼接绝对 model root 时不产生 `.//absolute` 或源码目录前缀。
- 未设置新环境变量时，现有仓库开发和测试路径保持通过。

### packaged E2E

1. 构建后记录 `.app/Contents/Resources` 文件清单、大小和 SHA-256。
2. 指定独立 `--user-data-dir` 启动 app，等待 API 和 embedding ready。
3. 验证日志、配置、session、知识库数据写入 `<userData>/runtime`。
4. 执行知识库导入/问答与 Ollama 直接调用、自动 fallback。
5. 退出 app，确认其启动的 Python 子进程停止。
6. 再次记录 Resources 清单并逐项比较，要求完全一致。
7. 记录 resolved Python 路径、Python 版本和 `pip check`，明确当前产物依赖外部兼容 Python 环境。

### 新增通过标准

- package 必须包含默认 embedding 必需文件且 `verify:package` 通过。
- Resources 启动前后哈希完全一致，不出现新增、删除或变更文件。
- data/model 诊断路径分别指向 userData/runtime 和 Resources/localmodels。
- Apple 凭证缺失时可以完成 ad-hoc runtime 验证，但不得据此宣称正式签名、公证或 release 完成。
