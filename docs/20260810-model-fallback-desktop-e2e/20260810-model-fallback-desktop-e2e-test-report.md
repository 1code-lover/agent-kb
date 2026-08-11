# 20260810 Model Fallback Desktop E2E Test Report

## 结论

本轮模型配置韧性、评测断点续跑、模型健康 API/UI、桌面端真实工作流诊断、macOS 打包内容校验和跨知识库泛化诊断均已完成验证。macOS 启动桌面端时出现的“危险 App / Electron.app 被移除”问题已定位为旧 Electron 31.7.7 公证撤销，升级到 Electron 43.3.0 后桌面端可独立启动，并能使用 conda `agent-kb` 环境拉起 API。本次增量还把 fallback 探测结果写入 `fallback_attempts`，并在 Models 页和 Agent 页展示 `probeSummary`，让用户能直接看到最近一次候选探测摘要。

正式签名/公证尚未完成：本机缺少 Apple Developer 凭证、Developer ID 证书和 `APPLE_ID` / `APPLE_APP_SPECIFIC_PASSWORD` / `APPLE_TEAM_ID` 环境变量，因此当前结论只覆盖发布配置、预检、打包、packaged app 启动和内容校验。

## 验证项

| 验证项 | 结果 | 证据 |
|---|---:|---|
| 模型错误分类与 fallback 单测 | 通过 | `tests/api/test_model_service.py` |
| chat query 模型失败后 fallback 重试 | 通过 | `tests/api/test_chat_service.py` |
| `GET /api/model/health` | 通过 | `tests/api/test_settings_routes.py` |
| QA eval `--resume` / `--stop-on-api-error` | 通过 | `tests/scripts/test_run_grain_qa_eval.py` |
| 前端模型健康状态映射 | 通过 | `webapp/src/domain/modelHealth.test.js` |
| fallback 探测摘要 UI | 通过 | `webapp/src/pages/ModelsPage.jsx`、`webapp/src/pages/AgentPage.jsx` |
| 桌面 Python 运行时选择 | 通过 | `desktop/src/python-process.test.js` |
| 前端 build | 通过 | `cd webapp && npm run build` |
| 桌面端独立启动 API | 通过 | `storage/logs/desktop_runtime.log` |
| 桌面工作流 E2E | 通过 | `artifacts/desktop-model-workflow-report-after-electron-fix.json` |
| macOS dmg/zip 打包与 packaged resources | 通过 | `desktop/dist/` + `desktop/scripts/verify-package.js` |
| 跨知识库泛化诊断 | 通过 | `artifacts/cross-domain-kb-eval-report.json` |

## 已执行命令

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
- `node --test desktop/scripts/*.test.js`：`29 passed`，新增 `verify-package.test.js` 覆盖完整 package、x64 `mac/` 布局与无 arch 后缀产物、mac-universal 布局与 universal 产物、缺失 release artifact、缺失 runtime 文件和 `app.asar` 混入 `.test.js` 的阻断路径。
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
