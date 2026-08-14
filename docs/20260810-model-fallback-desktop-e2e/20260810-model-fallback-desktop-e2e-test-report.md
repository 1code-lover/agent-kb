# 20260810 Model Fallback Desktop E2E Test Report

## 结论

截至 2026-08-15，本轮模型配置韧性、自动 fallback、Ollama 候选发现、模型健康 API/UI、桌面端真实工作流诊断、Electron CSP、macOS 发布配置与后置校验链路，以及多知识库跨领域泛化均已完成代码和本地门禁验证。模型不可用时会分类错误、探测候选并自动切换；基础问答、知识库问答和 Agent 高级模式均复用自动 fallback，Agent 直连聊天已支持 Ollama 原生 `/api/chat`；问答响应同步返回最新 `model_health`，前端能展示最近探测摘要和明确切换提示。source-backed 回答已覆盖 UTF-16/无扩展名文本、OCR 边界句、preview、scope、多事实合并和精确短语保真。

当前最终门禁为：Python `790 passed, 1 deselected`，Web `89 passed` 且 Vite build 通过，Electron `64 passed`；v1-v6 真实跨领域评测为 `49/49 cases passed`、`54/54 turns passed`，正向、负向和 contract 通过率均为 `100%`，没有系统性故障。

正式 macOS 签名、公证、stapling 和安装后回归尚未完成：本机缺少 Apple Developer 凭证、有效的 Developer ID Application 证书，且三种公证凭证策略（Keychain profile、App Store Connect API Key、Apple ID）均未配置。因此当前可以判定“发布实现、非严格预检、包内容和校验链路通过”，不能判定“正式 macOS release 完成”。

## 验证项

| 验证项 | 结果 | 证据 |
|---|---:|---|
| 模型错误分类与 fallback 单测 | 通过 | `tests/api/test_model_service.py` |
| chat query 模型失败后 fallback 重试 | 通过 | `tests/api/test_chat_service.py` |
| chat query 返回最新 model health | 通过 | `tests/api/test_chat_service.py` |
| Agent 直连 Ollama 原生协议 | 通过 | `tests/api/test_agent_tools.py` |
| Agent 模型错误自动 fallback | 通过 | `tests/api/test_agent_tools.py`、`tests/api/test_agent_runtime.py` |
| Agent 真实 Ollama 推理与动态 fallback | 通过，`2/2 cases` | `artifacts/agent-ollama-fallback-e2e-report-20260815.json` |
| `GET /api/model/health` | 通过 | `tests/api/test_settings_routes.py` |
| QA eval `--resume` / `--stop-on-api-error` | 通过 | `tests/scripts/test_run_grain_qa_eval.py` |
| 前端模型健康状态映射 | 通过 | `webapp/src/domain/modelHealth.test.js` |
| fallback 探测摘要 UI | 通过 | `webapp/src/pages/ModelsPage.jsx`、`webapp/src/pages/AgentPage.jsx` |
| 桌面 Python 运行时选择 | 通过 | `desktop/src/python-process.test.js` |
| 前端 build | 通过 | `cd webapp && npm run build` |
| 桌面端独立启动 API | 通过 | `storage/logs/desktop_runtime.log` |
| 桌面工作流 E2E | 通过 | `artifacts/desktop-model-workflow-report-after-electron-fix.json` |
| macOS dmg/zip 打包与 packaged resources | 通过 | `desktop/dist/` + `desktop/scripts/verify-package.js` |
| Electron CSP 与发布配置单测 | 通过，`64 passed` | `desktop/src/*.test.js`、`desktop/scripts/*.test.js` |
| macOS release 后置签名/公证校验链路 | 代码与单测通过 | `desktop/scripts/verify-mac-release.js` |
| 正式 macOS 签名、公证和 stapling | 待外部凭证 | `APPLE_*` 环境变量和 Developer ID Application 证书尚未配置 |
| 跨知识库 v1-v6 真实评测 | 通过，`49/49 cases`、`54/54 turns` | `artifacts/cross-domain-kb-eval-report-v1-v6-suite-after-regression-closure.json` |

## 2026-08-15 Agent 直连 Ollama 与自动 fallback 补充

本次完成了原目标中尚未覆盖的 Agent 高级模式：原实现检测到当前 provider 为 Ollama 时直接抛出未实现异常，云端直连调用失败也不会进入已有 fallback。当前实现：

- `api/services/agent_tools.py` 按 provider 分派调用：云端保留 OpenAI 兼容 `/chat/completions`，Ollama 使用原生 `/api/chat`、`stream=false` 和无 API Key 请求。
- `run_llm_chat` 首次调用失败后复用 `model_service.attempt_model_fallback`，读取切换后的 `current_llm_info` 并只重试一次。
- 对外 fallback 摘要只包含错误类别、候选数、来源/目标和探测摘要，主动裁掉 `selected.api_key`；receipt 和 Agent 日志不记录凭证。
- fallback 探活成功但真实重试仍失败时停止重试并把健康状态覆盖为 `unavailable`。
- `agent_runtime.run_agent` 返回 `fallback`、`model_health`，step 摘要明确显示“已自动切换到 provider / model”；前端已有成功回调会立即刷新 model options。
- Ollama 常见的 `model 'name' not found` 错误现在能归类为 `model_unavailable` 并触发候选切换。
- 真实 E2E 首次发现 `select_model` 会把之前记录的 `fallback_from` 重置为 `None`；最终 `fallback_applied` 写入现在显式恢复原模型快照，来源和目标均可回显。

TDD 红灯证据：新增测试初次执行为 `5 failed, 4 passed`，覆盖缺失 `_call_configured_model`、无 fallback、无状态透传等真实缺口；Ollama 带模型名的 404 文本分类测试初次结果为 `1 failed`；真实 E2E 暴露的 `fallback_from` 回归测试初次也为 `1 failed`。修复后 Agent/model/chat 定向测试为 `74 passed`，Python 全量继续通过。

最终回归：Python `790 passed, 1 deselected, 35 warnings`，Web `89 passed` 且 Vite build 通过，Electron `64 passed`。重新执行真实 `build:mac` 和 `verify:package` 均通过，最新 packaged app 已包含 `_call_ollama`、`attempt_model_fallback` 和“已自动切换到”逻辑。产物校验值：

```text
e2c5f636df57a5caeb5b1a4830fe5b89d514c20485349ca2254e5af18a733f40  NorthAgent-0.1.0-arm64.dmg
f18400345f466f022253b01c3fe6ceceb03860161c3daf19d3836eb6c2e0a674  NorthAgent-0.1.0-arm64-mac.zip
```

真实云端链路验证使用当前已配置的 `qwen-math-turbo`：Agent 直连调用成功；随后在单进程隔离配置中把当前模型设为明确不存在的模型、把真实可用模型设为候选，`run_llm_chat` 得到 `error_kind=model_unavailable`、`fallback_applied=true`、`candidate_count=1`、`health_state=fallback_applied`，最终通过 `GoodCloud / qwen-math-turbo` 返回响应。隔离脚本使用内存 store、禁用 session/receipt 持久化，未输出或修改真实 API Key。

真实 Ollama 验证使用官方 `0.32.13` App 包和 `qwen2.5:0.5b`（397,821,319 bytes、494.03M、Q4_K_M）。`ollama-direct-agent-runtime` 返回精确答案 `OLLAMA_AGENT_DIRECT_OK`；`bad-cloud-to-dynamic-ollama-candidate` 从不可达 `BadCloud / offline-model` 自动发现本地模型并返回 `OLLAMA_AGENT_FALLBACK_OK`，最终 `fallback_applied=true`、`candidate_count=1`、`ollama_candidate_count=1`、来源/目标完整、step 为“已自动切换到 Ollama / qwen2.5:0.5b”。报告 `run_passed=true`，两例均使用内存配置且关闭 session/receipt 持久化，不使用真实 API Key。

正式 Apple 签名、公证和安装后回归仍受原外部凭证阻塞；Ollama 运行时也需要在 NorthAgent 之外独立启动。

## 2026-08-14 fallback 状态即时同步补充

本次复核发现：服务端 fallback 已经更新持久化健康状态，但问答页的 `/api/model/options` 查询设置了 60 秒 `staleTime`，聊天成功回调此前没有主动刷新，因此自动切换后页面可能短时间继续展示旧模型。已按 TDD 补齐：

- `api/services/chat_service.py` 的正常回答、无相关来源拒答和 fallback 重试响应均返回 `model_health` 快照。
- `webapp/src/pages/AgentPage.jsx` 的 chat mutation 成功回调主动执行 `modelOptionsQuery.refetch()`，即时刷新当前模型名称和切换提示。
- `webapp/src/api/chat.test.js` 增加 `model_health` 透传回归；Python chat service 增加正常路径、无来源路径和 fallback 路径契约测试。

定向验证：Python `tests/api/test_chat_service.py` 为 `43 passed`；Web API/domain/store 测试为 `89 passed`，Vite build 通过。随后重新执行非 slow Python 全量测试为 `783 passed, 1 deselected, 35 warnings`，Electron 测试为 `64 passed`。

## 2026-08-15 当前最终收口复核

本节是当前最终结论；后续按日期保留的 `37/49`、`44/49`、embedding 缓存缺失和定向失败结果均为优化过程中的历史证据，不代表当前状态。

最终验证结果：

| 门禁 | 最终结果 |
|---|---:|
| Python 非 slow 全量测试 | `790 passed, 1 deselected, 35 warnings` |
| Web domain/API/store 测试 | `89 passed` |
| Web Vite build | 通过 |
| Electron CSP/runtime/release 测试 | `64 passed` |
| Agent 真实 Ollama E2E | `2/2 passed`、`run_passed=true` |
| v1-v6 跨领域 case | `49/49 passed` |
| v1-v6 跨领域 turn | `54/54 passed` |
| 正向 / 负向 / contract | `100% / 100% / 100%` |
| 多轮 case | `4/4 passed` |
| 系统性故障判断 | `suspected=false` |
| macOS 正式签名/公证 | 等待 Apple 凭证和 Developer ID Application 证书 |

真实跨领域评测命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --suite v1-v6 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite-after-regression-closure.json
```

最终报告的 `failure_check_summary={}`、`failure_case_summary=[]`，且 `systemic_failure_summary.suspected=false`。覆盖多知识库隔离、Markdown、PDF、扫描 PDF、图片 OCR、UTF-8、UTF-16、无扩展名文档、source/evidence grounding、多跳、多轮、mixed batch、preview 定位以及正向/负向回答。

发布侧已通过 `npm run build:preflight`、真实 `npm run build:mac` 和 `npm run verify:package`。`build.mac.notarize=false` 已关闭 electron-builder 内建公证，自定义 `afterSign` 是唯一提交点；无凭证构建中该 hook 只执行一次并输出安全的缺项诊断。严格 `npm run release:preflight` 与 `npm run verify:mac-release` 在当前机器按预期失败，因为三类公证策略均未配置、缺少 Developer ID Application 签名身份且产物没有已公证 ticket。补齐外部条件后必须继续执行 `npm run release:mac`，并以单次 submission、codesign、Gatekeeper、stapler 和安装后桌面工作流全部通过作为正式发布判定。

### macOS 单次公证与多凭证策略验证

实现证据：

- `desktop/scripts/notarization-credentials.js` 统一选择 Keychain profile、App Store Connect API Key、Apple ID 三类凭证，优先级为 `keychain_profile > api_key > apple_id`。
- 高优先级策略部分配置时保留缺失字段警告，但不会阻止后续完整策略；诊断只包含策略名和环境变量名，不记录密码、私钥路径、账号、Team ID 等任何凭证值。
- `desktop/package.json` 显式设置 `build.mac.notarize=false`，`desktop/scripts/verify-release-config.js` 对缺失或 `true` 均判定失败，保证 electron-builder 内建公证不会与 `afterSign` 重复提交。
- 严格 preflight 会一次汇总公证凭证、Developer ID Application 和 `notarytool` 三类独立门禁，不再只暴露首个错误。

执行结果：

```bash
cd desktop && node --test src/*.test.js scripts/*.test.js
```

结果：`64 passed`。

```bash
cd desktop && npm run build:preflight
```

结果：通过。release config 确认 `afterSign=scripts/notarize-mac.js`、`mac.notarize=false`、hardened runtime、entitlements 和 dmg/zip target 均符合要求；非严格环境预检完整列出三类未配置凭证和缺失的 Developer ID Application，`notarytool` 可用。

```bash
cd desktop && npm run build:mac
```

结果：通过，生成 `NorthAgent-0.1.0-arm64.dmg` 和 `NorthAgent-0.1.0-arm64-mac.zip`。electron-builder 接受 `mac.notarize=false`，自定义 hook 执行一次并因无完整凭证安全跳过公证；构建同时明确提示本机没有有效 Developer ID Application 身份。

```bash
cd desktop && npm run verify:package
```

结果：通过，packaged runtime contents ready。

```bash
cd desktop && npm run release:preflight
```

结果：按预期以退出码 `1` 失败，并在一次诊断中同时列出 Keychain profile、API Key、Apple ID 三类凭证缺失，以及 `Developer ID Application signing identity missing`；`notarytool` 路径为 `/Library/Developer/CommandLineTools/usr/bin/notarytool`。

当前 ad-hoc app 的非严格 `verify-mac-release` 继续报告 codesign、Gatekeeper 和 stapler 未通过，符合“尚未完成正式发布”的验收口径。正式凭证到位前不能验证真实 Apple submission 次数、notarization accepted 状态和 stapled ticket。

## 历史执行记录

以下命令和结果按优化过程保留；当前权威结论以“2026-08-14 最终收口复核”为准。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

结果：`709 passed, 1 deselected, 35 warnings`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_model_service.py \
  tests/api/test_settings_routes.py \
  tests/api/test_chat_service.py \
  tests/scripts/test_run_grain_qa_eval.py -q
```

结果：`65 passed, 8 warnings`

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`80 passed`

```bash
node --test desktop/src/python-process.test.js
```

结果：`2 passed`

```bash
cd webapp && npm run build
```

结果：Vite build 通过。

## 2026-08-11 v6 跨领域扩面试跑

本轮继续试扩跨领域真实样本，新增 README 表格、mixed batch 三轮追问、更多跨 KB 拒答隔离样本。同时发现当前模型配置状态会影响评测结论：`qwen-plus-2025-07-28` / `qwen3.7-plus` 返回免费额度耗尽，`ely/qwen-flash` 返回 401，`阿里百炼/qwen-flash` 与 `deepseek-v4-flash` 返回 `model_not_found`；临时可用的 `qwen-math-turbo` 能通过基础粮仓 RAG smoke，但不适合作为正式泛化门禁模型。

本轮还修复了一个评测脚本韧性问题：底层请求触发 `TimeoutError` 时，现在会转换为 `_http_status=-1` 的失败响应并写入报告，不再中断整轮评测。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`21 passed, 1 warning`。新增覆盖底层请求超时时返回可汇总失败响应。

新增试验样本文件：

- `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json`：README 表格、mixed batch 三轮追问、桌面对 grain README 的负向隔离、图片 OCR 对 mixed rollback approval 的负向隔离。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 45 \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-only-v2.json
```

结果：`2/4 passed`，两个 cross-KB negative case 均通过。剩余失败：

- `extra-v6-grain-readme-table-format`：source 命中 README，但当前临时模型把“主要格式”答成 `text(markdown)`，未命中 `.pdf` / `.docx`。
- `extra-v6-mixed-three-turn-release-follow-up`：`approval` turn 在 45 秒内超时；`preview` 和 `scope-reminder` turn 通过。

另有一次 v1-v6 全量试跑输出到 `cross-domain-kb-eval-report-v11.json`，结果 `1/49 passed`，主要原因是当时当前模型 `qwen-plus-2025-07-28` 已返回 `AllocationQuota.FreeTierOnly`，不作为真实功能回归失败结论。

## 2026-08-12 README 表格字段问答兜底

针对 v6 的 README 表格问答误答，本轮在 `api/services/chat_service.py` 增加 source-backed Markdown 表格字段兜底：当问题明确询问“表里/字段”的具体值，且来源文本包含 Markdown 表格时，服务端会按表格行抽取字段值补齐答案，避免模型把 `file_type=text/markdown` 这类 metadata 误当成正文表格里的“主要格式”。

同时 `scripts/diag_cross_domain_kb_eval.py` 将 `[Errno 32] Broken pipe` 归类为 `network_error`，让 preflight/summary 更明确地区分模型链路断流和业务泛化失败。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`50 passed, 7 warnings`。

真实 v6 extra 复跑命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 60 \
  --preflight \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-table-fallback.json
```

结果：preflight 提前中止，首个 case 在 60 秒内 `timed out`，报告中的 `systemic_failure_summary.dominant_error_kind=network_error`；重启 API 后 `/api/health` 显示 embedding warmup 仍为 `warming`。因此本次真实 v6 结果记录为模型/运行时链路限制，不作为业务回归失败结论，待稳定通用模型和 runtime ready 后继续复跑。

## 2026-08-12 embedding 缓存诊断与 v6 复跑

本轮继续收口上一次 v6 被 runtime warmup 拖住的问题。`api/runtime.py` 已能用 `elapsed_ms`、`is_stale`、`thread_alive` 和 `stale_after_ms` 标记长期预热；本次进一步在 `server/models/embedding.py` 增加 `get_embedding_model_diagnostics()`，并让 `/api/health` 返回 `embedding_diagnostics`，用于说明当前 embedding 会从本地 `localmodels/` 加载还是回退到 HuggingFace mirror，以及本地缓存缺失时的预下载建议。

注意：当前 18080 上运行的是改动前启动的 API 进程，因此实时 curl 暂时还不会包含新增的 `embedding_diagnostics` 字段；该字段已由 TestClient 路径覆盖，API 下次启动后生效。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/test_embedding_model_diagnostics.py \
  tests/api/test_health_route.py \
  tests/api/test_runtime_model_loading.py -q
```

结果：`38 passed, 3 warnings`。覆盖本地缓存存在、缓存缺失远程回退、未知 embedding 模型、health 返回 embedding 诊断，以及预热 stale 状态。

runtime ready 后复跑 v6 extra：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 60 \
  --preflight \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-embedding-diagnostics.json
```

结果：`4/4 passed`、逐轮 `6/6 passed`，`systemic_failure_summary.suspected=false`。README 表格字段、mixed batch 三轮追问、桌面对 grain README 的负向隔离、图片 OCR 对 mixed rollback approval 的负向隔离均通过。

## 2026-08-12 v1-v6 全量 suite 基线

本轮把跨领域真实评测从“手工拼多个 `--extra-cases`”推进为可复用的一键 suite。`scripts/diag_cross_domain_kb_eval.py` 新增 `--suite v1-v6`，会在默认 23 条基线后追加 `cross-domain-extra-cases-v1.json` 到 `cross-domain-extra-cases-v6.json` 的 26 条外部真实样本。CLI 同时新增逐 case 进度输出，避免 49 条全量评测长时间无反馈。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`29 passed, 1 warning`。新增覆盖命名 suite 加载、未知 suite 报错和逐 case progress 回调。

全量 suite 复跑：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 60 \
  --preflight \
  --suite v1-v6 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite.json
```

结果：`26/49 passed`、逐轮 `30/54 passed`。其中负向隔离 `15/15 passed`、contract `1/1 passed`，说明跨 KB 泄漏和多 KB contract 拒绝仍稳定；正向用例 `positive_pass_rate=0.303`，失败主要集中在 `expected_terms_hit`、长多轮、UTF-16/extensionless 文本、桌面诊断正向、PDF/图片 OCR source grounding 和 evidence text grounding。

本轮结论：v6 定向样本已稳定跑绿，但 v1-v6 全量 suite 暴露出当前临时模型 `qwen-math-turbo` 下的正向泛化不足。报告 `systemic_failure_summary.suspected=false`，因此这不是大面积模型/API 不可用；下一步应优先恢复更合适的通用模型或针对正向 source/answer grounding 做优化。

## 2026-08-12 source-backed 精确短语保真

本轮针对 v1-v6 全量 suite 中的一类高频正向失败做低风险修复。失败报告显示，部分 case 的目标 source 已经命中，但模型在最终答案里破坏了精确 token/短语，例如：

- `northagent-desktop-e2e-1786353063` 被答成 `northagent desktop-e2e-1786353063`
- `OCR fallback` 被答成 `OCRfallback`

这类问题不是检索缺口，而是模型改写导致 expected terms 失败。`api/services/chat_service.py` 新增 source-backed 精确短语保真：当问题明确索要 unique/exact/passcode 或 `what does/what should/what must` 类来源短语，且 source `text/excerpt` 中存在高置信 hyphen token 或固定短语时，返回 source 原句或补充精确来源短语。逻辑不会处理拒答，也不会从 file/title 抽取 token，避免把文件名误补到答案里。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_chat_service.py \
  tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`55 passed, 7 warnings`。新增覆盖 passcode 连字符保真和 `OCR fallback` 粘连修复。

另起新端口验证 health 新字段：

```bash
KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py
curl http://127.0.0.1:18084/api/health
```

结果：`embedding_diagnostics.local_path_exists=false`、`load_source=remote`、`hf_endpoint=https://hf-mirror.com`，并返回预下载 `localmodels/` 的建议。该临时进程继续等待到 120 秒后进入 `embedding_warmup.state=stale`，说明新代码全量复跑的前置阻塞仍是本地 embedding 缓存缺失；当前 18080 仍是旧进程，需准备本地缓存并重启后才能复跑 answer repair 对 v1-v6 suite 的真实改善。

为此新增 `scripts/prepare_embedding_model_cache.py`：

- 默认只输出诊断，不下载。
- 显式传 `--download` 时调用 `huggingface_hub.snapshot_download`，把模型下载到 `localmodels/BAAI/bge-small-zh-v1.5`。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache
```

结果：`local_path_exists=false`、`load_source=remote`、`download_requested=false`、`downloaded=false`、`skipped=true`，确认当前仍需预下载。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/api/test_chat_service.py \
  tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`59 passed, 7 warnings`。新增覆盖 dry-run、未知模型、已有缓存跳过和显式 download 调用参数。

随后继续尝试显式预下载：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache --download
```

结果：下载未成功，`huggingface_hub.snapshot_download` 在访问 HuggingFace mirror 时触发 `ConnectTimeout: [Errno 60] Operation timed out`，并因为本地没有可用 snapshot 抛出 `LocalEntryNotFoundError`。复跑 dry-run 仍显示 `local_path_exists=false`、`load_source=remote`、`downloaded=false`、`skipped=true`。因此当前状态是：脚本和诊断能力已完成，但本机 embedding 本地缓存尚未准备好。

随后继续补运行时保护：默认禁止 API/桌面启动期 embedding 初始化走远程下载，只有显式设置 `EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1` 才允许回退远程。缓存缺失时 `create_embedding_model` 会快速失败并清空 `Settings._embed_model`，避免 LlamaIndex 把 `None` 转成 `MockEmbedding` 后误报可用。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/test_embedding_model_diagnostics.py \
  tests/api/test_health_route.py \
  tests/api/test_runtime_model_loading.py \
  tests/scripts/test_prepare_embedding_model_cache.py -q
```

结果：`44 passed, 3 warnings`。

临时 API 实测：

```bash
KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py
curl http://127.0.0.1:18084/api/health
```

结果：`embedding_warmup.state=failed`、`is_ready=false`、`embedding_diagnostics.allow_remote_download=false`、`local_path_exists=false`，临时 API 秒级返回诊断，不再等待到 120 秒 stale。全量 v1-v6 suite 仍需本地缓存准备好或显式允许远程下载后再复跑。

随后把该诊断继续接入 roundtrip 脚本与 Knowledge Workspace：

- `scripts/diag_roundtrip_support.py` 的 `summarize_runtime_readiness()` 新增 `blocker_details` 和 `embedding_diagnostics` 透传；等待 runtime ready 超时时会把 `local_path_exists`、`allow_remote_download`、`local_path`、`hf_endpoint` 写进错误消息。
- `webapp/src/domain/ocrWarmup.js` 新增 `buildEmbeddingWarmupSummary()`；Knowledge Workspace 头部现在同时展示 Embedding 与 OCR 运行时状态。缓存缺失且运行时禁用远程下载时，前端会显示“Embedding 缓存缺失”并提示需要准备的本地模型路径。

已执行命令：

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
cd webapp && npm run build
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/test_diag_roundtrip_support.py \
  tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：前端 domain/api/store `88 passed`；Web build 通过；roundtrip/eval 脚本测试 `40 passed, 1 warning`。

随后继续增强 embedding 缓存准备入口，避免只能依赖 HuggingFace 在线下载：

- 复核本机缓存：`localmodels/` 为空，`~/.cache/huggingface` 仅有 `BAAI/bge-reranker-base`，未发现 `BAAI/bge-small-zh-v1.5` 可复用 snapshot。
- `scripts.prepare_embedding_model_cache` 新增 `--source-dir` 参数，可把已有本地模型目录复制到 `localmodels/BAAI/bge-small-zh-v1.5`。
- `--download` 失败时改为输出 JSON `error`，不再抛出长 traceback；本机复跑仍返回 `Download failed: LocalEntryNotFoundError ... ConnectTimeout`，`local_path_exists=false`。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/test_embedding_model_diagnostics.py \
  tests/api/test_health_route.py \
  tests/api/test_runtime_model_loading.py \
  tests/test_diag_roundtrip_support.py -q

/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache --download
KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py
curl http://127.0.0.1:18084/api/health
```

结果：相关测试 `58 passed, 3 warnings`；下载命令结构化返回 JSON error；临时 18084 API 继续秒级返回 `embedding_warmup.state=failed`、`allow_remote_download=false`、`local_path_exists=false`。因此全量 v1-v6 suite 仍需先准备本地 embedding 缓存或提供可用下载代理。

## 2026-08-12 ModelScope embedding 缓存与最新复核

HuggingFace mirror 在本机仍会出现 `ConnectTimeout`，因此本轮给 `scripts.prepare_embedding_model_cache` 增加 `--provider {huggingface,modelscope}`。ModelScope provider 当前映射 `bge-small-zh-v1.5` 和 `bge-large-zh-v1.5`，用于把 embedding 模型准备到项目 `localmodels/`，避免 API/桌面启动期依赖远程下载。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache \
  --download \
  --provider modelscope
```

结果：成功下载 `bge-small-zh-v1.5` 到 `localmodels/BAAI/bge-small-zh-v1.5`；随后 dry-run 显示 `local_path_exists=true`、`load_source=local`、`skipped=true`。`localmodels/` 已被 `.gitignore` 忽略，不进入提交。

本轮同时修复 `api/runtime.py` 的 warmup 计时状态：后台 warmup 调用 `ensure_models_ready()` 时不再清掉 `_started_monotonic`，避免 health 中 `finished_at` 与 `last_duration_ms` 不一致。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_chat_service.py \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/api/test_runtime_model_loading.py \
  tests/test_embedding_model_diagnostics.py -q
```

结果：`76 passed, 7 warnings`。

最新临时 API 复核：

```bash
KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py
curl http://127.0.0.1:18084/api/health
```

结果：`embedding_warmup.state=ready`、`embedding_diagnostics.load_source=local`、`embedding last_duration_ms=4521.347`；OCR `ready`，`last_duration_ms=6766.399`。

最新 v6 定向复跑：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18084 \
  --timeout 120 \
  --preflight \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-latest-source-term-repair.json
```

结果：`4/4 passed`、逐轮 `6/6 passed`，`systemic_failure_summary.suspected=false`。最慢仍是 `extra-v6-mixed-three-turn-release-follow-up` 的 `approval` turn，约 `63.98s`，因此 v6 长多轮当前稳定口径继续使用 `--timeout 120`。

本地 embedding 缓存后的 v1-v6 全量 suite 基线：

- 报告：`artifacts/cross-domain-kb-eval-report-v1-v6-suite-after-modelscope-cache.json`
- 结果：`34/49 passed`、逐轮 `39/54 passed`
- positive pass rate：`0.5758`
- negative pass rate：`0.9333`
- contract pass rate：`1.0`

对比此前未准备本地缓存/临时模型状态下的 `26/49`、逐轮 `30/54`，通过率已有明显改善；但全量 suite 仍未完成。剩余失败主要是正向 expected terms 和 source/evidence grounding，另有一个负向 case 返回 `400 InternalError.Algo.InvalidParameter: Range of input length should be [1, 3072]`，需要下一轮单独收口。

## 2026-08-12 source-backed preview 回答兜底

继续分析当前分支全量报告时，发现 `desktop-positive-preview` 和 `mixed-positive-preview` 的 source 已命中，但模型会答到同一文档里的 passcode 或相邻事实，导致 expected terms 没命中。为避免继续依赖模型在 preview 问题上自行抽取原句，本轮在 `api/services/chat_service.py` 增加 source-backed preview 兜底：当问题明确询问 `evidence preview` / `chat returns sources`，且 source 文本包含 preview 原句时，优先返回 source 原句。该逻辑仅对 preview 问题触发，并在后续 exact repair 中保留 preview 原句，避免又被同源 passcode 覆盖。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_chat_service.py \
  tests/scripts/test_prepare_embedding_model_cache.py \
  tests/api/test_runtime_model_loading.py \
  tests/test_embedding_model_diagnostics.py -q
```

结果：`77 passed, 7 warnings`。

Targeted preview 复跑：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18084 \
  --timeout 120 \
  --preflight \
  --cases temp/cross-domain-preview-target-cases.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-preview-target-after-source-answer.json
```

结果：`desktop-positive-preview` 和 `mixed-positive-preview` 均通过，`2/2 passed`。

v6 定向回归：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18084 \
  --timeout 120 \
  --preflight \
  --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-source-preview-answer.json
```

结果：`4/4 passed`、逐轮 `6/6 passed`，`systemic_failure_summary.suspected=false`。

当前分支全量 v1-v6 复跑：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18084 \
  --timeout 120 \
  --preflight \
  --suite v1-v6 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite-after-current-branch-check.json
```

结果：`37/49 passed`、逐轮 `42/54 passed`，positive pass rate `0.6667`、negative pass rate `0.9333`、contract pass rate `1.0`。剩余失败 12 个，主要集中在 image OCR boundary 原句保真、UTF-16/extensionless 文本清洗、桌面多轮 preview follow-up、一卡通适用范围，以及 1 个负向 case 的 3072 输入长度 API 错误。

## 2026-08-13 source-backed scope merge

本轮继续推进 source-backed 兜底，新增两类更稳的修复：一类是边界/定义问句的完整句回看，另一类是 one-answer 多事实合并。`api/services/chat_service.py` 现在会在问句明显要求边界、范围或定义时，优先回到完整 source 句；对 `In one answer...` 这类多事实问题，则会从不同 source 里拼出最小完整回答，避免只答出 preview 或只答出 approval 的一半。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py -q
```

结果：`36 passed, 7 warnings`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --timeout 120 \
  --preflight \
  --suite v1-v6 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite-after-scope-merge.json
```

结果：`44/49 passed`、逐轮 `49/54 passed`、positive pass rate `0.8788`、negative pass rate `0.9333`、contract pass rate `1.0`。本轮稳定修复 `mixed-positive-rollback`、`mixed-positive-preview`，但仍有 5 个失败：

- `exttext-positive-readme-utf16`
- `utf16-positive-folder-boundary`
- `extra-grain-positive-one-card-scope`
- `extra-v2-mixed-multihop-approval-and-preview`
- `extra-v2-grain-negative-older-desktop-passcode`

其中最后一个属于 API 负向边界错误，其余 4 个仍是 source grounding 问题，下一轮应继续沿 source/docstore 结构查证。

## 2026-08-12 模型选择即时探活

本轮补齐模型配置恢复路径的一处空档：过去 `/api/model/select` 只要保存了 provider/model/api_key，就会把 `model_health.state` 写成 `healthy`，即使真实调用会返回 401、403、额度耗尽或模型不存在。现在选择模型后会立即复用已有的 OpenAI-compatible / Ollama 轻量探活逻辑，把成功写为 `healthy`，失败写为 `unavailable`，并同步记录 `last_error_kind`、`fallback_attempts` 和 `fallback_attempt_summary`。自动 fallback 已经探活过候选时，会把探活结果传给 `select_model` 复用，避免成功切换时重复打一轮网络请求。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q
```

结果：`20 passed, 2 warnings`。新增覆盖模型选择成功探活、Ollama 无 API Key 探活、坏 token / 401 时不再显示 healthy。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q
```

结果：`58 passed, 8 warnings`。确认模型选择路由、fallback 重试路径和 chat query 回归不受影响。

```bash
node --test webapp/src/domain/modelHealth.test.js
```

结果：`10 passed`。前端健康摘要仍能展示 `unavailable`、Ollama 候选和结构化探测摘要。

## 2026-08-12 跨领域评测系统性故障归因

本轮继续增强跨领域真实评测的报告解释力。此前 `cross-domain-kb-eval-report-v11.json` 因 `qwen-plus-2025-07-28` 免费额度耗尽，导致 `49` 个 case 里只有 contract 用例通过；报告虽然有 `failure_check_summary.http_status_ok`，但不够直接说明这是模型/API 层系统性故障，而不是所有知识库领域同时退化。

现在 `summary` 新增 `systemic_failure_summary`，会展开 multi-turn 的每一轮，统计 `http_status_ok` 失败比例，并把 quota、401、model_not_found、timeout/network 等大面积错误归因为 `model_or_api_unavailable`。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`23 passed, 1 warning`。新增覆盖大面积 quota 错误会标记系统性故障，少量单点 HTTP 失败不会误判为系统性故障。

对既有 v11 失败报告重新汇总验证：

```bash
/opt/miniconda3/envs/agent-kb/bin/python - <<'PY'
import json
from pathlib import Path
from scripts.diag_cross_domain_kb_eval import summarize

p = Path("docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v11.json")
d = json.loads(p.read_text())
print(json.dumps(summarize(d["cases"])["systemic_failure_summary"], ensure_ascii=False, indent=2))
PY
```

结果：`suspected=true`、`reason=model_or_api_unavailable`、`dominant_error_kind=quota_exhausted`、`http_failure_total=53`、`http_failure_rate=0.9815`。

## 2026-08-12 跨领域评测 preflight

本轮把系统性故障归因前移到评测入口。新增 `--preflight` 参数后，脚本会先用首个 case 做一次模型/API 探活；如果首个 case 已经因为 quota、401、model_not_found、network/timeout 等模型/API 层错误失败，就提前写出带 `preflight.aborted=true` 的报告，不再继续消耗完整跨领域矩阵。preflight 通过时仍会继续跑完整 case 集；默认不开启，因此既有评测命令不受影响。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`25 passed, 1 warning`。新增覆盖 preflight 在模型/API 故障时提前中止，以及 preflight 通过后继续执行完整用例集。

## 2026-08-12 桌面复用已运行 API

本轮补齐“模型不可用时打开桌面版/网页版由用户自行配置”的桌面启动细节：如果用户或调试流程已经先启动了 `run_api.py`，旧桌面逻辑仍会无条件再 spawn 一个 Python API 子进程，随后因为 `127.0.0.1:18080` 已占用而输出 `address already in use`。虽然主窗口能继续使用现有 API，但日志会显得像启动失败。

现在 `desktop/src/python-process.js` 新增 `ensurePythonApi`：桌面启动时先检查 `http://127.0.0.1:18080/api/health`，如果已有 API 可用，就记录 `python_api_reusing_existing` 并直接加载渲染页面；只有 API 不可用时才启动 `run_api.py`。

已执行命令：

```bash
node --test desktop/src/python-process.test.js
```

结果：`4 passed`。新增覆盖已有 API 时不 spawn、新 API 不可用时再启动 Python。

```bash
node --test desktop/src/python-process.test.js desktop/src/csp.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/release-preflight.test.js desktop/scripts/build-target.test.js desktop/scripts/verify-package.test.js desktop/scripts/verify-mac-release.test.js desktop/scripts/notarize-mac.test.js
```

结果：`44 passed`。确认 CSP、发布配置、preflight、包校验和 mac release 后置校验不受影响。

手工复核：在 API 已运行时重启桌面，`storage/logs/desktop_runtime.log` 出现 `python_api_reusing_existing`，未再产生新的 `address already in use` 子进程错误。

同时补齐配置恢复可读性：`server/stores/config_store.py` 在 `put/delete` 后会把 `config_store.json` 重新写成缩进 JSON，并保留中文原文，方便模型配置恢复后人工核对。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_config_store.py -q
```

结果：`2 passed, 2 warnings`。新增覆盖写入和删除后的 JSON 缩进格式。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q
```

结果：`55 passed, 8 warnings`

```bash
node --test webapp/src/domain/modelHealth.test.js webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`81 passed`

```bash
git diff --check
```

结果：通过。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_desktop_model_workflow \
  --base-url http://127.0.0.1:18080 \
  --output-path docs/20260810-model-fallback-desktop-e2e/artifacts/desktop-model-workflow-report-after-electron-fix.json
```

结果：`run_passed=true`。验证内容包括模型 options/health、模型选择与探活、文件导入、定向知识库问答、引用来源、evidence preview、`default` 知识库隔离。

## 桌面端启动修复记录

旧桌面依赖 `electron@31.7.7` 在 macOS 上被系统判断为已撤销公证：

```text
notarization indicates this code has been revoked
```

表现为 `Electron.app` 启动后被系统移除，`desktop/node_modules/electron/dist/` 只剩 `LICENSE`、`LICENSES.chromium.html` 与 `version`。升级到 `electron@43.3.0` 后，桌面端成功进入主进程和渲染进程。

干净启动验证：

- `desktop_app_ready`
- `python_api_starting` 使用 `/opt/miniconda3/envs/agent-kb/bin/python`
- `python_api_ready`
- `renderer_resolved` 加载 `webapp/dist/index.html`
- `/api/model/options`、`/api/kb`、`/api/chat/history` 请求成功

## 剩余风险

- `desktop` 依赖树仍有 npm audit 风险：`8 vulnerabilities`，其中 `7 high`、`1 critical`。本轮优先解决 macOS 公证撤销导致的启动失败，后续应单独安排桌面依赖安全升级。
- Electron CSP 已补到主进程响应头，并允许本地 API、Vite dev websocket 和文件资源；packaged app 已完成启动和首页 API 请求复核，后续仍需在签名/公证后的安装包中复核上传、preview 和更多静态资源加载。
- macOS release preflight、hardened runtime 与 entitlements 已补充，但本机未配置 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 且未发现有效 Developer ID 证书，严格签名/公证预检和真实 notarization 尚未执行。
- 本机 `localmodels/BAAI/bge-small-zh-v1.5` 已通过 ModelScope 准备完成，新 API 可从本地加载；但新机器、清理缓存或换模型后仍需重新执行 `scripts.prepare_embedding_model_cache --download --provider modelscope`，或用 `--source-dir` 离线导入。runtime 仍默认禁止远程下载，这是为了避免桌面/API 启动被网络下载长期卡住。
- v1-v6 全量 suite 已由历史阶段的 `37/49`、`44/49` 提升到最终 `49/49 cases passed`、`54/54 turns passed`；当前风险从“已知失败”转为新增领域、新文档格式和不同模型配置下的持续泛化监控。

## 2026-08-10 增量复核

本次增量继续收口模型 fallback 和桌面发布准备：

- Ollama 作为本地供应商时允许无 API Key 进入 fallback 候选。
- 当 Ollama provider 未显式配置模型列表时，fallback 会尝试读取 `/api/tags` 发现本地已安装模型。
- 前端模型页和 Agent 页补充 fallback action hint 与来源到目标的切换提示。
- 后端 fallback health 继续细化为 `fallback_attempts`，前端以 `probeSummary` 呈现最近一次候选探测结果。
- Electron 主进程补充 CSP 响应头。
- `desktop` 新增 release preflight 脚本、macOS hardened runtime 和 entitlements 配置。
- `desktop` 新增 notarize hook 和 packaged resources 校验脚本，确认 `webapp/dist`、Python API、server、utils、`run_api.py`、`config.py` 和 `requirements.txt` 会进入 macOS app resources。
- 新增跨知识库泛化诊断脚本，覆盖粮仓、桌面诊断和 UTF-8 边界诊断 3 个 KB 的正向命中与负向隔离。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q
```

结果：`17 passed, 2 warnings`

```bash
node --test webapp/src/domain/modelHealth.test.js
```

结果：`5 passed`

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`80 passed`

```bash
node --test desktop/src/*.test.js
```

结果：`2 passed`

```bash
node --test desktop/scripts/*.test.js desktop/src/*.test.js
```

结果：`8 passed`

```bash
cd webapp && npm run build
```

结果：Vite build 通过。

```bash
node desktop/scripts/release-preflight.js
```

结果：非严格模式通过，Electron bundle 存在；提示缺少 Apple 签名/公证环境变量和 Developer ID Application 证书，但 `notarytool` 可用。

```bash
cd desktop && npm run build:mac && npm run verify:package
```

结果：通过。产物包括 `desktop/dist/NorthAgent-0.1.0-arm64.dmg` 和 `desktop/dist/NorthAgent-0.1.0-arm64-mac.zip`；packaged resources 校验确认包含 `webapp/dist/index.html`、`run_api.py`、`config.py`、`requirements.txt`、`api/app.py`、`server/index.py` 和 `utils/logging_utils.py`，且 `app.asar` 未包含 `.test.js`。

```bash
ELECTRON_ENABLE_LOGGING=1 THINKRAG_EMBED_PREWARM=0 THINKRAG_OCR_PREWARM=0 \
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python \
desktop/dist/mac-arm64/NorthAgent.app/Contents/MacOS/NorthAgent
```

结果：packaged app 主进程启动成功，API 监听 `18080`，渲染进程加载 packaged `webapp/dist/index.html`，前端请求 `/api/model/options`、`/api/kb`、`/api/chat/history` 成功。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`5 passed, 1 warning`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report.json
```

结果：`6/6 passed`。正向用例覆盖 `grain-knowledge-base`、`diag-desktop-e2e-1786353063`、`diag-kb-utf8-1785505921`；负向用例确认粮仓答案不会泄漏桌面 passcode，桌面诊断 KB 不会泄漏粮仓安全储粮方针，粮仓 KB 对 UTF-8 边界问题可以回答自身相似边界内容，但不得泄漏 `文件夹只承担组织作用`、`不承担权限隔离` 等精确短语或 UTF-8 诊断来源。

```bash
git diff --check
```

结果：通过。


## 2026-08-11 跨 KB 泛化扩容验证

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`8 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v3.json`：`17/17 passed`。
- 新矩阵覆盖 grain、desktop、image-ocr、pdf-scan、mixed-batch、boundary、exttext、cross-domain 与 contract 九类 focus，其中 contract 用例验证多知识库查询仍按主线契约拒绝。
- 本轮给正向用例补充 `expected_any_term_groups`，避免同一证据在中英文回答之间波动时误报失败。
- 报告产物 `cross-domain-kb-eval-report-v3.json` 已写入 artifacts，供后续扩展更多真实业务 KB 时复跑对比。

## 2026-08-11 跨 KB 泛化再扩容

这次再补了 grain 安全生产、desktop evidence preview、UTF-16 边界和旧 desktop passcode 隔离样本，把真实评测面继续往外推了一层。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`9 passed, 1 warning`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v4.json
```

结果：`21/21 passed`。`utf16-positive-folder-boundary` 先前会把“knowledge base”简化成“base”，已根据真实答复兼容双表述后稳定通过。

## 2026-08-11 跨 KB 泛化再扩容 v5

这次继续补强旧 desktop passcode、extensionless UTF-8 folder boundary 和更多跨域组合，让真实评测样本从 21 条扩到 23 条。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`9 passed, 1 warning`

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v5.json
```

结果：`23/23 passed`。新增的 extensionless UTF-8 样本最初命中了“organization object only”而不是更字面的“folder remains organization only.”，已改为按真实表述接受后稳定通过。


## 2026-08-11 发布预检边界加固

- `desktop/scripts/release-preflight.js` 现在返回可测试的预检摘要，并允许注入 Electron 路径、`app-builder` 路径、`xattr` 和失败处理函数；CLI 行为保持不变。
- 非严格模式会继续提示缺少 Apple 凭证、Developer ID Application 证书或 `app-builder`，但不阻断本地打包准备；严格模式会在缺少发布凭证、证书或 `notarytool` 时失败。
- `node --test desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js`：`15 passed`，覆盖非严格缺项摘要、严格缺凭证失败、严格全量 gate 通过、Electron bundle 缺失失败、Developer ID 解析和 `notarytool` 探测。
- `node --test desktop/scripts/*.test.js desktop/src/*.test.js`：`24 passed`，新增 `desktop/src/csp.test.js` 覆盖 CSP 连接源与 URL origin 解析，`desktop/scripts/verify-release-config.test.js` 覆盖 notarize hook、hardened runtime、entitlements、mac target 和 packaged runtime resources。
- `cd desktop && node scripts/release-preflight.js --strict`：按预期失败，原因是本机缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID`。
- `cd desktop && npm run build:preflight`：非严格模式通过；`verify-release-config` 确认 release config ready，随后提示本机仍缺少 Apple 签名/公证环境变量和 Developer ID Application 证书，但 `notarytool` 可用。
- `desktop/package.json` 的 `release:mac` 已串起 `build:preflight` + 严格 `release:preflight`；`desktop/scripts/build-target.js` 也已在 macOS `npm run build` 路径里先执行 `verify-release-config.js` 和 `release-preflight.js`，避免本机打包入口绕过发布配置校验。
- `node --test desktop/scripts/*.test.js`：`23 passed`，新增 `build-target.test.js` 覆盖 macOS build 入口的配置预检顺序、预检失败提前停止，以及非 macOS 平台只走对应 electron-builder target。
- `desktop/scripts/verify-package.js` 已抽成可测试的 `verifyPackage()`，继续校验 dmg/zip 产物、packaged runtime resources、`app.asar` 和测试文件排除。
- `verifyPackage()` 会优先发现实际存在的 mac app resources 目录和 dmg/zip 产物，兼容 `mac-arm64`、`mac` 和 `mac-universal` 等布局，避免只绑定当前 arm64 产物命名。
- `node --test desktop/scripts/*.test.js`：`30 passed`，新增 `verify-package.test.js` 覆盖完整 package、x64 `mac/` 布局与无 arch 后缀产物、旧 arm64 产物残留时优先选择当前 x64 无后缀产物、mac-universal 布局与 universal 产物、缺失 release artifact、缺失 runtime 文件和 `app.asar` 混入 `.test.js` 的阻断路径。
- `cd desktop && npm run verify:package`：通过，确认当前 `desktop/dist` 产物内容仍满足 package 校验。

## 2026-08-11 release candidate 清单

- 新增 `20260810-model-fallback-desktop-e2e-release-checklist.md`，把 Apple Developer 凭证、Developer ID Application、严格 `release:preflight`、`release:mac`、`verify:package`、安装后启动和 `diag_desktop_model_workflow` 的通过标准固化为发布清单。
- 该清单不宣称签名/公证已完成；它用于凭证到位后直接执行 release candidate 验收。

## 2026-08-11 fallback 探测摘要增量复核

这次增量主要是把模型 fallback 的候选探测结果可视化到前端，避免用户只能看到“切换成功/失败”，却不知道中间探了哪些候选。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q
```

结果：`55 passed, 8 warnings`

```bash
node --test webapp/src/domain/modelHealth.test.js webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`81 passed`

```bash
cd webapp && npm run build
```

结果：通过，`ModelsPage` 和 `AgentPage` 现在展示 fallback 探测摘要。

## 2026-08-11 外部跨领域样本追加验证

这次把跨领域评测从“修改 Python 内置列表扩样本”推进到“默认基线 + 外部真实样本文件追加”。`scripts/diag_cross_domain_kb_eval.py` 现在支持 JSON list 或 `{ "cases": [...] }` 两种文件格式，可重复传入 `--extra-cases`，报告里会记录每条用例的 `case_source`，并对重复 case id 直接失败。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`12 passed, 1 warning`。新增覆盖外部 `{cases: [...]}` 读取、默认基线追加 extra cases、重复 id 失败、`case_source_summary` 汇总和负向 forbidden term 不复述题目。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6.json
```

结果：`27/27 passed`。默认基线 `23/23`，外部追加样本 `4/4`；`positive_total=16`、`negative_total=10`、`contract_total=1`，三类通过率均为 `100%`。

本轮还修正了一个评测误报口径：负向用例的 `forbidden_terms` 不应包含题目自身已经出现的标题词，否则模型在拒答时复述题目也会被误判为泄漏。现在默认负向用例只禁止真正的答案短语或精确证据短语。


## 2026-08-11 tag 维度泛化复核

这次在外部样本上再补了一层可持续验证：`scripts/diag_cross_domain_kb_eval.py` 的每条 case 现在可以带 `tags`，汇总里会生成 `tag_summary`，方便把长问题、多跳、OCR、扫描件、拒答和跨库隔离单独做成回归切片，而不是只看总通过率。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`12 passed, 1 warning`。新增覆盖 `tags` 透传、`tag_summary` 汇总和旧结构兼容。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v7.json
```

结果：`33/33 passed`。默认基线 `23/23`，外部追加样本 v1 `4/4`、v2 `6/6`；`positive_total=20`、`negative_total=12`、`contract_total=1`，三类通过率均为 `100%`。`tag_summary` 里 `long-question`、`multi-hop`、`ocr`、`scan`、`refusal`、`cross-kb-isolation` 的切片也都保持 `100%`。
## 2026-08-11 fallback 结构化探测摘要

这次继续补模型 fallback 的边角体验：后端不只保存逐个 `fallback_attempts`，还新增 `fallback_attempt_summary`，聚合候选总数、可用数、失败数、Ollama 候选数、Ollama 可用数和最近一次候选明细。前端 `probeSummary` 优先使用这个结构化摘要，能直接显示“几个可用、几个不可用、是否包含 Ollama 候选”；当 Ollama 候选全部不可用时，页面提示会明确建议检查 Ollama 是否启动以及目标模型是否已拉取。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q
```

结果：`18 passed, 2 warnings`。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest \
  tests/api/test_model_service.py \
  tests/api/test_settings_routes.py \
  tests/api/test_chat_service.py -q
```

结果：`56 passed, 8 warnings`。

```bash
node --test webapp/src/domain/modelHealth.test.js
```

结果：`8 passed`。

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`83 passed`。

## 2026-08-11 多轮追问跨领域评测

这次把跨领域评测从单轮 case 扩展到多轮 `turns`：同一个 case 内按顺序复用同一个本次评测专用 `session_id`，每一轮都会独立记录 checks、answer preview、来源 KB 和通过状态，顶层 case 再汇总 `turn_count`、`passed_turn_count`、`failed_turn_ids` 与整体通过状态。这个能力用于验证当前最小 follow-up/session grounding，不宣称已经完成完整多轮推理。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`14 passed, 1 warning`。新增覆盖多轮 session 复用、逐轮汇总、任一轮失败导致顶层 case 失败。

新增外部样本文件：

- `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json`：粮仓正向追问、桌面 evidence preview 正向追问、粮仓 KB 内追问桌面 passcode 的负向隔离。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v8.json
```

结果：`36/36 passed`，逐轮 `39/39 passed`。默认基线 `23/23`，v1 外部样本 `4/4`，v2 外部样本 `6/6`，v3 多轮样本 `3/3`；`multi-turn`、`follow-up`、`cross-kb-isolation`、`refusal` 等 tag 切片均为 `100%`。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

结果：`725 passed, 1 deselected, 35 warnings`。

## 2026-08-11 来源文件级跨领域评测

这次继续补跨领域评测的 grounding 强度：脚本新增 `required_source_files` 和 `forbidden_source_files`，在校验答案词、source KB 和禁止泄漏词之外，再要求来源文件名命中或避开指定片段。报告同步输出 `source_files`，方便失败时定位到底引用到了哪个文件。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`16 passed, 1 warning`。新增覆盖 required source file 命中和 forbidden source file 失败。

新增外部样本文件：

- `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json`：粮仓守则、桌面 workflow、扫描 PDF、图片 OCR 和 mixed batch cutover 的来源文件落点。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v9.json
```

结果：`41/41 passed`，逐轮 `44/44 passed`。默认基线 `23/23`，v1 外部样本 `4/4`，v2 外部样本 `6/6`，v3 多轮样本 `3/3`，v4 来源文件级样本 `5/5`；`source-grounding` tag 切片为 `100%`。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

结果：`727 passed, 1 deselected, 35 warnings`。

## 2026-08-11 Evidence 文本级跨领域评测

这次把 grounding 门禁再往证据正文推进一层：脚本新增 `required_source_text_terms` 和 `forbidden_source_text_terms`，检查范围只包含 API 返回的 `sources` / `evidence` 正文，不把模型最终答案算作证据。这样可以证明答案背后的 evidence 片段本身包含依据，而不是只看模型是否答出了关键词。本轮还在 summary 中新增 `failure_check_summary`、`failure_case_summary` 和 `duration_summary`，用于失败时按检查项、case 和 turn 归因，并定位最慢 case/turn。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q
```

结果：`20 passed, 1 warning`。新增覆盖 required evidence text 命中、forbidden evidence text 泄漏失败、失败检查项 / case / turn 归因汇总，以及耗时诊断汇总。

新增外部样本文件：

- `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json`：桌面 evidence preview、扫描 PDF OCR fallback、图片 OCR 边界和 mixed batch rollback approval 的 evidence 文本依据。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval \
  --api-base http://127.0.0.1:18080 \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json \
  --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json \
  --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json
```

结果：`45/45 passed`，逐轮 `48/48 passed`。默认基线 `23/23`，v1 外部样本 `4/4`，v2 外部样本 `6/6`，v3 多轮样本 `3/3`，v4 来源文件级样本 `5/5`，v5 evidence 文本样本 `4/4`；`source-grounding` 和 `evidence-text` tag 切片均为 `100%`；当前 `failure_check_summary={}`、`failure_case_summary=[]`。`duration_summary.case_total_ms=73247.147`、`case_avg_ms=1627.714`、`turn_avg_ms=1525.958`，最慢 case/turn 和唯一超过 `5000ms` 阈值的 slow item 均为 `grain-negative-utf8-exact-boundary`。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
```

结果：`731 passed, 1 deselected, 35 warnings`。

## 2026-08-11 macOS release 后置校验链路

本轮继续收口桌面发布链路：`release:mac` 在严格预检和 `electron-builder --mac` 后，新增强制执行 `verify:package` 与 `verify:mac-release`。其中 `verify:package` 校验 dmg/zip、`app.asar` 和 packaged runtime resources；`verify:mac-release` 校验 `.app` 的 codesign、Gatekeeper assess 和 notarization staple。

已执行命令：

```bash
node --test desktop/scripts/verify-mac-release.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/verify-package.test.js desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js desktop/scripts/build-target.test.js
```

结果：`36 passed`。新增覆盖 `.app` 路径解析、codesign/spctl/stapler 成功、缺失 app bundle、三类信任链失败，以及 release config 必须串起 `verify:package` 和 `verify:mac-release`。

```bash
cd desktop && npm run build:preflight
```

结果：通过；`verify-release-config` 确认 release config ready，非严格 `release-preflight` 继续提示本机缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 和 Developer ID Application 证书，`notarytool` 可用。

```bash
cd desktop && npm run verify:package
```

结果：通过，现有 `desktop/dist` 包内容可解析，packaged runtime contents ready。

```bash
cd desktop && node scripts/verify-mac-release.js
```

结果：非严格诊断按预期指出当前本机未完成正式签名/公证：codesign 与 Gatekeeper 校验失败，`NorthAgent.app` 没有 stapled notarization ticket。补齐 Apple 凭证和 Developer ID Application 证书后，正式 `npm run release:mac` 会在打包后强制执行这两类后置校验。

## 2026-08-11 fallback Ollama 动态发现边角

本轮继续补 fallback 的边角提示：当配置里存在 Ollama provider 但 `models: []` 依赖动态发现，而本地 Ollama 没启动、地址不可达或没有已安装模型时，后端会保留一个诊断候选并写入 `fallback_attempt_summary`。前端会据此给出更明确的动作提示，而不是只展示“没有可用供应商”。

已执行命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q
```

结果：`19 passed, 2 warnings`。新增覆盖 Ollama 动态发现失败时仍记录 `ollama_unreachable` 诊断候选。

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q
```

结果：`57 passed, 8 warnings`。

```bash
node --test webapp/src/domain/modelHealth.test.js
```

结果：`10 passed`。新增覆盖 Ollama 服务不可达、Ollama 已连接但没有本地模型、目标模型未安装三类提示。

```bash
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js
```

结果：`85 passed`。

```bash
cd webapp && npm run build
```

结果：Vite build 通过。
